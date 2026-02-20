# Clean Architecture & Projectstructuur

> **Doelgroep**: AI-studenten die willen begrijpen hoe een productieklare AI-applicatie architecturaal is opgezet.

## Motivatie

Waarom besteden we zoveel aandacht aan architectuur in een AI-project? Het antwoord is eenvoudig: **AI-modellen veranderen snel, maar de bedrijfslogica niet**. Een goed gestructureerde codebase stelt je in staat om:

- Het LLM-model te wisselen (bijv. van GPT-4 naar Gemini) zonder de verwerkingslogica aan te passen
- De database te migreren (SQLite → PostgreSQL) zonder services te herschrijven
- Nieuwe verwerkingspipelines toe te voegen zonder bestaande code te breken
- Geïsoleerde unit tests te schrijven zonder een database of LLM-provider nodig te hebben

Dit project implementeert **Clean Architecture** — een benadering die deze flexibiliteit garandeert.

## Theoretische Achtergrond

### Clean Architecture (Robert C. Martin, 2012)

Clean Architecture is gebaseerd op het **Dependency Rule** principe:

> *Broncode-afhankelijkheden mogen alleen naar binnen wijzen. Niets in een binnenste cirkel mag iets weten over een buitenste cirkel.*

Dit betekent dat de kern van je applicatie (domeinlogica) volledig onafhankelijk is van frameworks, databases en externe API's.

```
┌──────────────────────────────────────────────────┐
│              Presentation Layer                  │  ← FastAPI routes, middleware
│  ┌────────────────────────────────────────────┐  │
│  │           Infrastructure Layer             │  │  ← SQLAlchemy, OpenRouter, Playwright
│  │  ┌──────────────────────────────────────┐  │  │
│  │  │        Application Layer             │  │  │  ← Services, interfaces (ports), DTOs
│  │  │  ┌────────────────────────────────┐  │  │  │
│  │  │  │        Domain Layer            │  │  │  │  ← Entiteiten, business rules
│  │  │  └────────────────────────────────┘  │  │  │
│  │  └──────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Dependency Inversion Principle (DIP)

Het vijfde SOLID-principe stelt:

> *Hoog-niveau modules mogen niet afhankelijk zijn van laag-niveau modules. Beide moeten afhankelijk zijn van abstracties.*

In de praktijk betekent dit dat een service niet direct een SQLAlchemy repository aanroept, maar een **abstracte interface** (port) definieert. De infrastructuurlaag levert dan de **concrete implementatie** (adapter).

```
┌─────────────────┐     depends on     ┌──────────────────────┐
│ ClassificationSvc├───────────────────►│ OntologyRepository   │  ← abstracte interface
└─────────────────┘                    │       (ABC)          │
                                       └──────────┬───────────┘
                                                   │ implements
                                       ┌───────────▼──────────┐
                                       │SQLAlchemyOntologyRepo│  ← concrete implementatie
                                       └──────────────────────┘
```

### Ports & Adapters (Hexagonal Architecture)

Clean Architecture is nauw verwant aan het Ports & Adapters patroon:

| Concept | Betekenis | Voorbeeld in dit project |
|---------|-----------|--------------------------|
| **Port** | Abstracte interface — *wat* de applicatie nodig heeft | `LLMClient`, `OntologyRepository` |
| **Adapter** | Concrete implementatie — *hoe* het geleverd wordt | `OpenRouterLLMClient`, `SQLAlchemyOntologyRepository` |

Dit patroon is bijzonder waardevol voor AI-applicaties: de `LLMClient` port definieert operaties als `classify_document()` en `extract_metadata()`, terwijl de adapter bepaalt welke provider (OpenRouter, Groq, lokaal model) de calls uitvoert.

## De Vier Lagen

### Laag 1: Domain Layer (`app/domain/`)

De **kern** van de applicatie. Bevat pure Python objecten zonder enige framework-afhankelijkheid.

**Regel**: De Domain Layer importeert *niets* uit andere lagen — geen SQLAlchemy, geen FastAPI, geen Pydantic.

**Componenten:**

| Component | Bestand | Beschrijving |
|-----------|---------|-------------|
| `Resource` | `entities/resource.py` | Verwerkt document met classificatie en metadata |
| `OntologyConcept` | `entities/ontology_concept.py` | Hiërarchisch ontologie-knooppunt |
| `ConceptProperty` | `entities/ontology_concept.py` | Getypeerde eigenschap op een concept |
| `ExtractionTemplate` | `entities/ontology_concept.py` | Classificatie-hints en bestandspatronen |
| `Mixin` | `entities/ontology_concept.py` | Herbruikbare eigenschap-set |
| `EmbeddedType` | `entities/ontology_concept.py` | Ingebedde waarde-objecten |
| `ClassificationResult` | `entities/resource.py` | Geaggregeerd classificatieresultaat |
| `ClassificationSignal` | `entities/resource.py` | Individueel detectiesignaal |
| `DataSource` | `entities/data_source.py` | Geregistreerde databron |
| `ProcessingJob` | `entities/processing_job.py` | Eenheid werk in de verwerkingswachtrij |
| `QueryIntent` | `entities/query.py` | Gestructureerde zoekintentie uit NL-vraag |
| `QueryResult` | `entities/query.py` | Zoekresultaat met matches |
| `ChatMessage` | `entities/chat_message.py` | LLM berichten en token usage |
| `ServiceRequestLog` | `entities/service_request_log.py` | Audit trail voor LLM-aanroepen |

**Voorbeeld — Resource entiteit:**

```python
@dataclass
class Resource:
    """Verwerkt document met classificatie en metadata-extractieresultaten."""

    filename: str
    original_path: str
    file_size: int
    mime_type: str
    id: str | None = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    classification: ClassificationResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark_error(self, message: str) -> None:
        self.status = ProcessingStatus.ERROR
        self.error_message = message

    def mark_done(self) -> None:
        self.status = ProcessingStatus.DONE
        self.processed_at = datetime.now(timezone.utc)
```

### Laag 2: Application Layer (`app/application/`)

Bevat de **applicatielogica** (use cases), definieert abstracte interfaces, en valideert input/output via Pydantic DTOs.

**Componenten:**

**Interfaces (Ports):**

| Interface | Bestand | Operaties |
|-----------|---------|-----------|
| `ArticleRepository` | `interfaces/article_repository.py` | CRUD voor artikelen |
| `OntologyRepository` | `interfaces/ontology_repository.py` | Ontologie opslag en query |
| `ResourceRepository` | `interfaces/resource_repository.py` | Resource records beheer |
| `LLMClient` | `interfaces/llm_client.py` | Classificatie, extractie, OCR, PDF, tool-calling |
| `ChatProvider` | `interfaces/chat_provider.py` | Chat completion API |
| `TextExtractor` | `interfaces/text_extractor.py` | Tekst uit bestanden halen |
| `DataSourceRepository` | `interfaces/data_source_repository.py` | Databron opslag |
| `ProcessingJobRepository` | `interfaces/processing_job_repository.py` | Job wachtrij |

**Services (Use Cases):**

| Service | Verantwoordelijkheid |
|---------|---------------------|
| `ResourceProcessingService` | Orkestrator van de volledige verwerkingspipeline |
| `ClassificationService` | Multi-signal documentclassificatie |
| `MetadataExtractionService` | Template-gedreven metadata-extractie met LLM |
| `OntologyService` | CRUD en query-operaties op ontologie |
| `OntologyCompiler` | Compileert YAML-definities naar de database |
| `QueryService` | Natural language → structured query |
| `DataSourceService` | Databron- en job-management |
| `BackgroundProcessor` | Asyncio daemon voor achtergrondverwerking |
| `ChatCompletionService` | Generieke chat completion wrapper |
| `LLMUsageLogger` | Token/cost tracking per LLM-aanroep |
| `SettingsService` | Runtime model-instellingen |
| `SSEManager` | Server-Sent Events voor real-time updates |

### Laag 3: Infrastructure Layer (`app/infrastructure/`)

Implementeert de abstracte interfaces met concrete technologieën.

```
infrastructure/
├── database/
│   ├── base.py                     # SQLAlchemy DeclarativeBase
│   ├── session.py                  # Async sessie factory
│   ├── models/                     # ORM modellen
│   │   ├── resource_models.py      # Resource + ProcessingJob
│   │   ├── ontology_models.py      # Concept + Mixin + EmbeddedType
│   │   ├── data_source_models.py   # DataSource ORM
│   │   └── service_request_log.py  # LLM audit trail
│   └── repositories/              # Concrete repository implementations
│       ├── resource_repository.py
│       ├── ontology_repository.py
│       └── ...
├── capture/                       # Playwright website capture
├── extractors/                    # Multi-format tekst extractie
├── llm/                           # LLMClient adapter (OpenRouter)
├── openrouter/                    # HTTP client voor OpenRouter API
├── storage/                       # Lokale bestandsopslag
├── logging/                       # Logging configuratie
└── dependencies.py                # FastAPI DI wiring
```

### Laag 4: Presentation Layer (`app/presentation/`)

De buitenste laag — definieert HTTP endpoints en API-routing.

```
presentation/
└── api/
    ├── router.py                   # Top-level /api router
    └── v1/
        ├── router.py               # V1 route aggregatie
        ├── resources_controller.py  # Upload, list, delete, reprocess
        ├── ontology_controller.py   # Ontologie CRUD + tree + AI wizard
        ├── data_sources_controller.py # Bronbeheer + jobverwerking + SSE
        ├── query_controller.py      # Natural language queries
        ├── settings_controller.py   # Model instellingen
        └── endpoints/
            ├── articles.py          # CRUD artikelen
            ├── chat.py              # Chat completion
            ├── client_records.py    # Klantrecords
            └── health.py            # Health check
```

## Applicatie Lifespan

De FastAPI `lifespan` context manager voert de volgende stappen uit bij opstarten:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 0. Maak PostgreSQL database aan als die niet bestaat
    await _ensure_database_exists()

    # 1. Maak alle database-tabellen aan (idempotent)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Seed standaard databronnen (bijv. ingebouwde "Files" bron)
    await _seed_default_data_sources()

    # 3. Compileer ontologie YAML → database
    compiler = OntologyCompiler(l1_dir=..., l2_dir=..., repository=...)
    await compiler.compile()

    # 4. Maak upload-directory aan
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    # 5. Start Playwright browser voor website capture
    capture_service = WebsiteCaptureService(...)
    await capture_service.start()

    # 6. Start achtergrondverwerker (polling daemon)
    processor = BackgroundProcessor(
        sse_manager=get_sse_manager(),
        service_factory=_build_resource_processing_service,
        capture_service=capture_service,
    )
    await processor.start()

    yield  # Applicatie draait

    # Shutdown — stop processor, browser en SSE
    await processor.stop()
    await capture_service.stop()
```

## Dependency Injection Flow

FastAPI's `Depends()` wordt gebruikt als lightweight DI-container. Elke request krijgt een eigen database-sessie en daarop gebouwde services:

```
HTTP Request
    │
    ▼
get_db_session()           → AsyncSession
    │
    ▼
get_resource_processing_service()
    ├── SQLAlchemyResourceRepository(session)
    ├── SQLAlchemyOntologyRepository(session)
    ├── LocalFileStorage(upload_dir)
    ├── MultiFormatTextExtractor()
    ├── OpenRouterClient(api_key, ...)
    │   └── OpenRouterLLMClient(openrouter, model)
    ├── ClassificationService(ontology_repo, llm_client)
    ├── MetadataExtractionService(ontology_repo, llm_client)
    └── ResourceProcessingService(alles hierboven)
```

## Vergelijking: Monoliet vs. Clean Architecture

| Aspect | Monolithische aanpak | Clean Architecture |
|--------|---------------------|--------------------|
| **LLM wisselen** | Wijzigingen door hele codebase | Alleen adapter vervangen |
| **Database migratie** | Services herschrijven | Alleen repository-implementatie |
| **Unit testing** | Database/API mock nodig | Fake repositories, geen I/O |
| **Nieuwe feature** | Risico op regressie | Geïsoleerde toevoeging |
| **Onboarding** | Alles tegelijk begrijpen | Laag voor laag leren |

## Leerpunten

1. **Dependency Rule**: Binnenste lagen weten niets over buitenste lagen. Een `Resource` entiteit weet niet dat hij in PostgreSQL wordt opgeslagen.
2. **Ports & Adapters**: De `LLMClient` ABC definieert *wat* de applicatie nodig heeft; `OpenRouterLLMClient` bepaalt *hoe*.
3. **Lifespan Pattern**: Gebruik FastAPI's `lifespan` voor initialisatie (database, ontologie compilatie) en cleanup (browser, achtergrondprocessen).
4. **Request-scoped DI**: Elke HTTP request krijgt zijn eigen database-sessie en servicestack — dit voorkomt state-lekkage tussen requests.
5. **Service Composition**: Complexe services (`ResourceProcessingService`) worden opgebouwd uit eenvoudiger services (`ClassificationService`, `MetadataExtractionService`) — het **Composition over Inheritance** principe.
