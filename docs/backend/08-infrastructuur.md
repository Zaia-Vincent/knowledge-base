# Infrastructuur — Database, DI & Configuratie

> **Doelgroep**: AI-studenten die willen begrijpen hoe de technische infrastructuur de Clean Architecture ondersteunt.

## Motivatie

De infrastructuurlaag is de "adapter-laag" — ze verbindt de pure businesslogica van de applicatie met concrete technologieën: PostgreSQL, SQLAlchemy, FastAPI's DI-systeem, en Python's asyncio. Een goed ontworpen infrastructuurlaag is **onzichtbaar** voor de rest van de applicatie.

## Database Setup

### PostgreSQL + SQLAlchemy 2.0 Async

Het project gebruikt PostgreSQL als database met SQLAlchemy 2.0 in asynchrone modus:

```python
# infrastructure/database/base.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Basisklasse voor alle ORM-modellen."""
    pass

engine = create_async_engine(settings.database_url, echo=False)
```

### Async Session Factory

```python
# infrastructure/database/session.py
from sqlalchemy.ext.asyncio import async_sessionmaker

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

async def get_db_session():
    """FastAPI dependency — levert een sessie per request."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**Belangrijk**: `expire_on_commit=False` zorgt ervoor dat attributen na een commit nog steeds leesbaar zijn zonder een extra database-query. Dit is essentieel in async code.

## ORM Modellen vs. Domain Entities

### Het Mapping Patroon

Domain entities zijn pure Python dataclasses. ORM modellen zijn SQLAlchemy klassen. De repositories vertalen tussen beide:

```python
# Domain Entity (pure Python)
@dataclass
class Resource:
    id: str | None = None
    filename: str
    status: ProcessingStatus = ProcessingStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)

# ORM Model (SQLAlchemy)
class ResourceModel(Base):
    __tablename__ = "resources"

    id = mapped_column(String, primary_key=True)
    filename = mapped_column(String, nullable=False)
    status = mapped_column(String, default="pending")
    metadata_ = mapped_column("metadata", JSONB, default=dict)  # JSONB!
```

### SQLAlchemy 2.0 Patterns

Het project gebruikt modern SQLAlchemy 2.0 met `Mapped` en `mapped_column`:

```python
class OntologyConceptModel(Base):
    __tablename__ = "ontology_concepts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    layer: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    inherits: Mapped[str | None] = mapped_column(String, nullable=True)
    abstract: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(Text, default="")
    synonyms: Mapped[list] = mapped_column(JSONB, default=list)          # JSONB array
    properties: Mapped[list] = mapped_column(JSONB, default=list)        # JSONB array
    extraction_template: Mapped[dict | None] = mapped_column(JSONB)      # JSONB object
```

### JSONB voor Flexibele Metadata

JSONB is het sleuteltype voor dit project: metadata-velden variëren per concept, dus een vaste set kolommen werkt niet.

```sql
-- PostgreSQL JSONB bevragingen:
-- Zoek facturen met vendor "Molcon"
SELECT * FROM resources
WHERE metadata->'vendor'->>'label' ILIKE '%Molcon%';

-- Zoek documenten met bedrag > 1000
SELECT * FROM resources
WHERE (metadata->'amount'->>'value')::numeric > 1000;
```

## Repository Pattern

Repositories vertalen tussen domain entities en ORM modellen:

```python
class SQLAlchemyResourceRepository(ResourceRepository):
    """Concrete implementatie van de ResourceRepository interface."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, resource_id: str) -> Resource | None:
        """Haal een resource op en converteer naar domain entity."""
        result = await self._session.execute(
            select(ResourceModel).where(ResourceModel.id == resource_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)  # ORM → Domain

    async def save(self, resource: Resource) -> Resource:
        """Sla een resource op — insert of update."""
        model = self._to_model(resource)  # Domain → ORM
        self._session.add(model)
        return resource

    def _to_entity(self, model: ResourceModel) -> Resource:
        """Converteer ORM model naar domain entity."""
        return Resource(
            id=model.id,
            filename=model.filename,
            status=ProcessingStatus(model.status),
            metadata=model.metadata_ or {},
            ...
        )

    def _to_model(self, entity: Resource) -> ResourceModel:
        """Converteer domain entity naar ORM model."""
        return ResourceModel(
            id=entity.id,
            filename=entity.filename,
            status=entity.status.value,
            metadata_=entity.metadata,
            ...
        )
```

## Dependency Injection

### FastAPI `Depends()` als DI Container

FastAPI's `Depends()` wordt gebruikt als lightweight DI-container. Elke dependency is een async generator:

```python
# infrastructure/dependencies.py

async def get_db_session():
    """Sessie per request."""
    async with async_session_factory() as session:
        yield session

async def get_resource_processing_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[ResourceProcessingService, None]:
    """Bouw de volledige service-stack voor document processing."""

    # Repositories
    resource_repo = SQLAlchemyResourceRepository(session)
    ontology_repo = SQLAlchemyOntologyRepository(session)

    # Infrastructure
    storage = LocalFileStorage(upload_dir=settings.upload_dir)
    extractor = MultiFormatTextExtractor()

    # LLM client (optioneel)
    llm_client = None
    if settings.openrouter_api_key:
        openrouter = OpenRouterClient(api_key=settings.openrouter_api_key, ...)
        llm_client = OpenRouterLLMClient(openrouter_client=openrouter, ...)

    # Services
    classifier = ClassificationService(ontology_repo, llm_client, usage_logger)
    metadata_extractor = MetadataExtractionService(ontology_repo, llm_client, usage_logger)

    yield ResourceProcessingService(
        file_repository=resource_repo,
        classification_service=classifier,
        metadata_extractor=metadata_extractor,
        llm_client=llm_client,
        ...
    )
```

### De Volledige Wiring Chain

```
HTTP Request
    │
    ▼
get_db_session()
    │  → AsyncSession
    ▼
get_resource_processing_service(session)
    │
    ├── SQLAlchemyResourceRepository(session)
    ├── SQLAlchemyOntologyRepository(session)
    ├── LocalFileStorage(settings.upload_dir)
    ├── MultiFormatTextExtractor()
    ├── OpenRouterClient(api_key)
    │   └── OpenRouterLLMClient(client, model)
    ├── LLMUsageLogger(log_repo)
    ├── ClassificationService(ontology_repo, llm_client, logger)
    ├── MetadataExtractionService(ontology_repo, llm_client, logger)
    ├── OntologyService(ontology_repo)
    └── ResourceProcessingService(alles hierboven)
```

## Configuratie Management

### Pydantic Settings

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Applicatie-instellingen uit environment en .env bestand."""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/knowledge_base"

    # LLM
    openrouter_api_key: str = ""
    classification_model: str = "google/gemini-2.0-flash-001"
    pdf_processing_model: str = "google/gemini-2.0-flash-001"

    # Storage
    upload_dir: str = "data/uploads"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
```

### Runtime Overrides via `data/settings.json`

Naast environment variabelen ondersteunt het systeem **runtime overrides**:

```json
// data/settings.json
{
    "classification_model": "anthropic/claude-3.5-sonnet",
    "pdf_processing_model": "google/gemini-2.0-pro"
}
```

Dit maakt het mogelijk om modellen te wisselen **zonder herstart** via de settings API.

## Application Lifespan

De FastAPI lifespan orcheseert 6 opstapstappen:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 0. Database aanmaken (als die niet bestaat)
    await _ensure_database_exists()

    # 1. Tabellen aanmaken (idempotent)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Standaard "Files" databron seeden
    await _seed_default_data_sources()

    # 3. Ontologie YAML → database compileren
    compiler = OntologyCompiler(...)
    await compiler.compile()

    # 4. Upload-directory aanmaken
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    # 5. Playwright browser starten
    capture_service = WebsiteCaptureService(...)
    await capture_service.start()

    # 6. BackgroundProcessor starten
    processor = BackgroundProcessor(...)
    await processor.start()

    yield  # ← Applicatie draait

    # Shutdown
    await processor.stop()
    await capture_service.stop()
```

## File Storage

```python
class LocalFileStorage:
    """Lokale bestandsopslag met gestructureerde directories."""

    def __init__(self, upload_dir: str):
        self._upload_dir = Path(upload_dir)

    def store(self, content: bytes, filename: str, resource_id: str) -> StoredFile:
        """Sla een bestand op in een resource-specifieke subdirectory."""
        target_dir = self._upload_dir / resource_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        target_path.write_bytes(content)
        return StoredFile(stored_path=str(target_path), ...)
```

## API Versioning & Router Structuur

```python
# presentation/api/router.py
router = APIRouter(prefix="/api")
router.include_router(v1_router, prefix="/v1")

# presentation/api/v1/router.py
v1_router = APIRouter()
v1_router.include_router(resources_router, prefix="/resources", tags=["Resources"])
v1_router.include_router(ontology_router, prefix="/ontology", tags=["Ontology"])
v1_router.include_router(data_sources_router, prefix="/data-sources", tags=["Data Sources"])
v1_router.include_router(query_router, prefix="/query", tags=["Query"])
v1_router.include_router(settings_router, prefix="/settings", tags=["Settings"])
```

**Resultaat:**
- `GET /api/v1/resources` — Lijst alle resources
- `POST /api/v1/resources/upload` — Upload bestand
- `GET /api/v1/ontology/tree` — Ontologie-boom
- `POST /api/v1/query` — Natural language zoekquery

## Logging Architectuur

```python
# infrastructure/logging/log_config.py
def setup_logging():
    """Configureer per-category log levels."""
    logging.getLogger("app.application").setLevel(logging.INFO)
    logging.getLogger("app.infrastructure").setLevel(logging.DEBUG)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# infrastructure/logging/colored_logger.py
class PipelineLogger:
    """Gestructureerde, gekleurde pipeline logging."""

    def step_start(self, stage: PipelineStage, message: str, **kwargs):
        """Log het begin van een pipeline-stap."""

    def step_complete(self, stage: PipelineStage, message: str, **kwargs):
        """Log de voltooiing van een pipeline-stap."""
```

## Leerpunten

1. **ORM ≠ Domain**: Houd SQLAlchemy modellen (infra) gescheiden van domain entities. Repositories vertalen tussen beide.
2. **JSONB voor flexibiliteit**: Gebruik PostgreSQL JSONB voor dynamische metadata — geen schema-migraties nodig wanneer concepten veranderen.
3. **Request-scoped DI**: Elke request krijgt een eigen sessie en servicestack via `Depends()` — voorkomt state-lekkage.
4. **Lifespan voor initialisatie**: Gebruik FastAPI's `lifespan` context manager voor database setup, ontologie compilatie, en achtergrondservices.
5. **Runtime configuratie**: Combineer `.env` (deploy-time) met `settings.json` (runtime) voor maximale flexibiliteit bij modelkeuze.
