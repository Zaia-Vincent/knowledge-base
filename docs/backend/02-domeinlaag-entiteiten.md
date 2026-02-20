# Domeinlaag — Entiteiten & Business Rules

> **Doelgroep**: AI-studenten die het Domain-Driven Design patroon willen begrijpen in de context van een AI-applicatie met documentverwerking.

## Motivatie

De domeinlaag is het **hart** van elke Clean Architecture applicatie. Het bevat de bedrijfsconcepten als pure Python objecten — zonder enige afhankelijkheid van frameworks, databases of externe API's.

Waarom is dit belangrijk voor AI-projecten?

1. **Stabiliteit**: LLM-providers en modellen veranderen continu, maar het concept "een document classificeren tegen een ontologie" blijft stabiel
2. **Testbaarheid**: Domeinentiteiten kun je testen met simpele unit tests — geen database, geen API-key nodig
3. **Hergebruik**: Dezelfde entiteiten werken ongeacht of je SQLite, PostgreSQL, of MongoDB gebruikt
4. **Documentatie**: De entiteiten vormen een **levende specificatie** van het domein

## Theoretische Achtergrond

### Domain-Driven Design (DDD)

Domain-Driven Design (Eric Evans, 2003) stelt dat software **de taal van het domein** moet spreken. In dit project zien we dat terug:

- Een document wordt een `Resource` — niet een "file record" of "row"
- Een classificatieresultaat is een `ClassificationResult` met meerdere `ClassificationSignal`s
- Een zoekintentie is een `QueryIntent` met `MetadataFilter`s

### Value Objects vs. Entities

| Concept | Definitie | Voorbeelden |
|---------|-----------|-------------|
| **Entity** | Object met een unieke identiteit (`id`) | `Resource`, `OntologyConcept`, `ProcessingJob` |
| **Value Object** | Object gedefinieerd door zijn waarden | `ClassificationSignal`, `ConceptProperty`, `MetadataFilter` |

Value Objects zijn **immutabel** en **vergelijkbaar op basis van hun attributen**. Twee `ConceptProperty`-objecten met dezelfde `name` en `type` zijn identiek — ze hebben geen eigen ID nodig.

### State Machines

Sommige entiteiten doorlopen een reeks toestanden. Dit wordt gemodelleerd met Python `Enum`s en explicite state-transitie methoden:

```
Resource:     PENDING → EXTRACTING_TEXT → CLASSIFYING → EXTRACTING_METADATA → DONE
                  └──────────────────────────────────────────────────────────→ ERROR

ProcessingJob: QUEUED → PROCESSING → COMPLETED
                   │                      ↑
                   └──→ FAILED ───────────┘  (via mark_requeued)
```

## Entiteiten in Detail

### Resource — Het Centrale Document

De `Resource` is de belangrijkste entiteit: een document dat door de pipeline is verwerkt.

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ProcessingStatus(str, Enum):
    """Lifecycle states van een resource in de verwerkingspipeline."""
    PENDING = "pending"
    EXTRACTING_TEXT = "extracting_text"
    CLASSIFYING = "classifying"
    EXTRACTING_METADATA = "extracting_metadata"
    DONE = "done"
    ERROR = "error"


@dataclass
class Resource:
    """Een verwerkt document met classificatie en metadata-extractieresultaten.

    Metadata wordt opgeslagen als een platte JSONB dict:
        {"document_date": {"value": "2024-08-14", "confidence": 1.0}, ...}
    """
    filename: str
    original_path: str
    file_size: int
    mime_type: str
    stored_path: str = ""
    id: str | None = None
    status: ProcessingStatus = ProcessingStatus.PENDING

    # Koppeling aan databron
    data_source_id: str | None = None

    # Classificatieresultaten
    classification: ClassificationResult | None = None

    # Geëxtraheerde metadata (JSONB)
    metadata: dict[str, Any] = field(default_factory=dict)
    extra_fields: list[dict[str, Any]] = field(default_factory=list)
    summary: str | None = None
    extracted_text: str | None = None

    # Multi-document support
    origin_file_id: str | None = None   # Links sub-documenten aan het ouder-upload
    page_range: str | None = None       # bijv. "1-2", "3-3"

    # Timestamps
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: datetime | None = None
    error_message: str | None = None
```

**State-transitie methoden:**

```python
def mark_error(self, message: str) -> None:
    """Transitie naar foutstatus."""
    self.status = ProcessingStatus.ERROR
    self.error_message = message

def mark_done(self) -> None:
    """Transitie naar voltooide status."""
    self.status = ProcessingStatus.DONE
    self.processed_at = datetime.now(timezone.utc)
```

> **Ontwerpbeslissing**: State-transities zijn methoden op de entiteit zelf, niet externe functies. Dit garandeert dat de business rules voor state-management altijd worden gevolgd.

### ClassificationResult & ClassificationSignal

Het classificatiesysteem combineert meerdere signalen om het beste concept te bepalen:

```python
@dataclass
class ClassificationSignal:
    """Een enkel classificatiesignaal van één detectiemethode."""
    method: str          # "file_pattern" | "synonym_match" | "llm_analysis"
    concept_id: str
    score: float         # 0.0 – 1.0
    details: str = ""    # Uitleg in leesbare tekst


@dataclass
class ClassificationResult:
    """Geaggregeerd classificatieresultaat met signalen van meerdere methoden."""
    primary_concept_id: str
    confidence: float
    signals: list[ClassificationSignal] = field(default_factory=list)
```

**Voorbeeld in de praktijk:**

```python
result = ClassificationResult(
    primary_concept_id="invoice",
    confidence=0.92,
    signals=[
        ClassificationSignal(method="file_pattern", concept_id="invoice", score=0.8,
                             details="Filename contains 'factuur'"),
        ClassificationSignal(method="synonym_match", concept_id="invoice", score=0.9,
                             details="Text contains 'Factuurnummer'"),
        ClassificationSignal(method="llm_analysis", concept_id="invoice", score=0.95,
                             details="LLM classified as Invoice with high confidence"),
    ]
)
```

### OntologyConcept — Het Kennismodel

De ontologie definieert de **taxonomie** waartegen documenten worden geclassificeerd:

```python
@dataclass
class OntologyConcept:
    """Een knooppunt in de ontologie-hiërarchie.

    L1: Foundation concepts (Thing, Entity, Object)
    L2: Enterprise concepts (Invoice, Contract, Person)
    L3: User-defined (aangepast door de gebruiker)
    """
    id: str
    layer: str                    # "L1", "L2", "L3"
    label: str
    inherits: str | None = None   # Parent concept ID
    abstract: bool = False
    description: str = ""
    synonyms: list[str] = field(default_factory=list)
    mixins: list[str] = field(default_factory=list)
    properties: list[ConceptProperty] = field(default_factory=list)
    relationships: list[ConceptRelationship] = field(default_factory=list)
    extraction_template: ExtractionTemplate | None = None
    pillar: str | None = None     # "entities", "artifacts", "processes"

    @property
    def is_classifiable(self) -> bool:
        """True als dit concept als classificatiedoel kan dienen."""
        return not self.abstract and self.extraction_template is not None

    def get_all_hints(self) -> list[str]:
        """Retourneer alle classificatie-aanwijzingen inclusief synoniemen."""
        hints = list(self.synonyms)
        if self.extraction_template:
            hints.extend(self.extraction_template.classification_hints)
        return hints
```

**Ondersteunende value objects:**

```python
@dataclass
class ConceptProperty:
    """Getypeerde eigenschap op een concept (bijv. 'invoice_date: date')."""
    name: str
    type: str           # "string", "date", "number", "reference", "array"
    required: bool = False
    default_value: Any = None
    description: str = ""


@dataclass
class ExtractionTemplate:
    """Bepaalt hoe documenten worden geclassificeerd en geëxtraheerd."""
    classification_hints: list[str] = field(default_factory=list)  # ["factuur", "rekening"]
    file_patterns: list[str] = field(default_factory=list)         # ["*factuur*", "*invoice*"]


@dataclass
class Mixin:
    """Herbruikbare eigenschappenset die in elk concept kan worden gemixed."""
    id: str
    layer: str
    label: str
    description: str = ""
    properties: list[ConceptProperty] = field(default_factory=list)
```

### EmbeddedType — Ingebedde Waarde-Objecten

Embedded types zijn gestructureerde objecten die **alleen bestaan als onderdeel van een parent concept**:

```python
@dataclass
class EmbeddedType:
    """Gestructureerd waarde-object dat alleen binnen een parent-concept bestaat.

    Voorbeeld: InvoiceLineItem bestaat alleen binnen Invoice.
    """
    id: str
    layer: str
    description: str = ""
    applies_to: list[str] = field(default_factory=list)  # ["invoice", "credit-note"]
    synonyms: list[str] = field(default_factory=list)
    properties: list[EmbeddedTypeProperty] = field(default_factory=list)


@dataclass
class EmbeddedTypeProperty:
    """Getypeerde eigenschap met optionele enum-waarden."""
    name: str
    type: str
    required: bool = False
    description: str = ""
    values: list[str] = field(default_factory=list)  # enum: ["Phone", "Email", "Fax"]
```

### DataSource — Databronnen

```python
class DataSourceType(str, Enum):
    """Ondersteunde databrontypes."""
    FILE_UPLOAD = "file_upload"
    WEBSITE = "website"


@dataclass
class DataSource:
    """Een geregistreerde bron van documenten.

    Config voorbeelden:
        FILE_UPLOAD: {}
        WEBSITE:     {"urls": ["https://example.com/page1", ...]}
    """
    name: str
    source_type: DataSourceType
    config: dict[str, Any] = field(default_factory=dict)
    id: str | None = None
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### ProcessingJob — Verwerkingswachtrij

```python
class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProcessingJob:
    """Een eenheid werk in de achtergrondverwerkingswachtrij."""
    data_source_id: str
    resource_identifier: str   # bestandsnaam of URL
    resource_type: str         # "file" | "url"
    id: str | None = None
    status: JobStatus = JobStatus.QUEUED
    progress_message: str | None = None
    result_file_id: str | None = None

    def mark_processing(self, message: str = "Processing started") -> None:
        self.status = JobStatus.PROCESSING
        self.started_at = datetime.now(timezone.utc)
        self.progress_message = message

    def mark_completed(self, result_file_id: str) -> None:
        self.status = JobStatus.COMPLETED
        self.result_file_id = result_file_id
        self.completed_at = datetime.now(timezone.utc)

    def mark_failed(self, error: str) -> None:
        self.status = JobStatus.FAILED
        self.error_message = error
        self.completed_at = datetime.now(timezone.utc)

    def mark_requeued(self) -> None:
        """Reset job naar wachtrij voor opnieuw verwerken."""
        self.status = JobStatus.QUEUED
        self.error_message = None
        self.result_file_id = None
```

### Query Entiteiten — Zoeken in de Kennisbank

```python
@dataclass
class MetadataFilter:
    """Eén metadata-filter afgeleid uit de gebruikersvraag."""
    field_name: str
    value: str
    operator: str = "contains"  # "contains" | "equals" | "gte" | "lte"


@dataclass
class QueryIntent:
    """Gestructureerde zoekintentie uit een natural-language vraag.

    Geproduceerd door de LLM op basis van de vraag + ontologie-context.
    """
    original_question: str
    resolved_language: str = "en"
    concept_ids: list[str] = field(default_factory=list)
    metadata_filters: list[MetadataFilter] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class QueryResult:
    """Compleet zoekresultaat: intentie + matchende resources."""
    intent: QueryIntent
    matches: list[QueryMatch] = field(default_factory=list)
    total_matches: int = 0
```

## Domain Exceptions

De domeinlaag definieert ook eigen uitzonderingen — onafhankelijk van HTTP-statuscodes:

```python
class EntityNotFoundError(Exception):
    """Wanneer een gevraagde entiteit niet bestaat."""
    def __init__(self, entity_type: str, entity_id: int | str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} with id '{entity_id}' not found")


class DuplicateEntityError(Exception):
    """Wanneer er een duplicaat entiteit wordt aangemaakt."""
    ...


class ChatProviderError(Exception):
    """Wanneer een chat-provider een fout teruggeeft.
    Provider-agnostisch — werkt voor OpenRouter, Groq, OpenAI, etc.
    """
    def __init__(self, provider: str, status_code: int, message: str):
        self.provider = provider
        self.status_code = status_code
        ...
```

**Mapping naar HTTP**: De presentatielaag vertaalt deze naar HTTP-statuscodes:

| Domain Exception | HTTP Status |
|-----------------|-------------|
| `EntityNotFoundError` | 404 Not Found |
| `DuplicateEntityError` | 409 Conflict |
| `ChatProviderError` | 502 Bad Gateway |

## Patronen & Best Practices

### 1. Dataclasses vs. Pydantic

| Wanneer | Gebruik | Reden |
|---------|---------|-------|
| **Domain entities** | `@dataclass` | Geen framework-afhankelijkheid, pure Python |
| **API input/output** | `BaseModel` (Pydantic) | Automatische validatie, serialisatie |
| **Configuratie** | `BaseSettings` (Pydantic) | Environment variabelen laden |

```python
# Domain (dataclass) — geen validatie, pure data
@dataclass
class Resource:
    filename: str
    file_size: int

# Application schema (Pydantic) — validatie + serialisatie
class ResourceResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    model_config = ConfigDict(from_attributes=True)
```

### 2. Barrel Exports via `__init__.py`

Alle publieke entiteiten worden hergeëxporteerd via `__init__.py`:

```python
# domain/entities/__init__.py
from .resource import Resource, ProcessingStatus, ClassificationSignal, ClassificationResult
from .ontology_concept import OntologyConcept, ConceptProperty, Mixin, EmbeddedType
from .data_source import DataSource, DataSourceType
from .processing_job import ProcessingJob, JobStatus
from .query import MetadataFilter, QueryIntent, QueryMatch, QueryResult

__all__ = ["Resource", "ProcessingStatus", "OntologyConcept", ...]
```

Dit maakt imports schoon:

```python
# In plaats van:
from app.domain.entities.resource import Resource
from app.domain.entities.ontology_concept import OntologyConcept

# Schrijf je:
from app.domain.entities import Resource, OntologyConcept
```

### 3. Metadata als JSONB

Metadata wordt opgeslagen als een platte dictionary met confidence scores:

```python
metadata = {
    "invoice_number": {"value": "INV-2024-001", "confidence": 0.98},
    "vendor": {"label": "Acme Corp", "confidence": 0.95},
    "total_amount": {"value": 1250.50, "confidence": 0.92},
    "document_date": {"value": "2024-08-14", "confidence": 1.0},
}
```

Dit biedt flexibiliteit: elk concept kan zijn eigen set van metadata-velden definiëren zonder schema-migraties.

## Leerpunten

1. **Framework-onafhankelijkheid**: Domeinentiteiten zijn pure Python `@dataclass`-objecten. Ze werken met elke ORM, elk framework, elke provider.
2. **State machines met Enums**: `ProcessingStatus` en `JobStatus` modelleren expliciete levenscycli — voorkomt dat entiteiten in ongeldige toestanden terechtkomen.
3. **Rich Domain Model**: Entiteiten bevatten gedrag (`mark_done()`, `is_classifiable`) — ze zijn geen anemische data-containers.
4. **Composabiliteit**: `ClassificationResult` bevat een lijst van `ClassificationSignal`s — dit maakt het systeem transparant en debugbaar.
5. **JSONB metadata**: Flexibele metadataopslag zonder schema-migraties — essentieel voor een systeem waar ontologie-concepten dynamisch worden toegevoegd.
