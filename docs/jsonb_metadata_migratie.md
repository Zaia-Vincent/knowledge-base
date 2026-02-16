# JSONB Metadata Migratie — Van EAV naar PostgreSQL JSONB

## Achtergrond

### Probleemstelling

De oorspronkelijke metadata-opslag gebruikte een **Entity-Attribute-Value (EAV)** patroon met vier aparte tabellen:

| Tabel | Verantwoordelijkheid |
|-------|---------------------|
| `processed_files` | Basis-bestandsinformatie |
| `file_classifications` | Classificatieresultaat (concept, confidence) |
| `file_metadata` | Geëxtraheerde sleutel-waarde paren (per property een rij) |
| `file_summaries` | Document-samenvatting |

Dit patroon leidt tot:

- **N+1 queries**: elk bestand vereist meerdere JOINs om volledig op te halen
- **Schemarigiditeit**: nieuwe velden toevoegen vereist databasemigraties
- **Complexe repository-code**: handmatige JSON serialisatie/deserialisatie per child-tabel

### Oplossing: PostgreSQL JSONB

PostgreSQL biedt native [JSONB](https://www.postgresql.org/docs/17/datatype-json.html) kolommen met:

- **GIN-indexen** voor efficiënte `@>`, `?`, `->` operatoren
- **Directe Python dict-mapping** via `asyncpg` — geen handmatige `json.dumps()`/`json.loads()` nodig
- **Flexibel schema**: nieuwe velden in metadata vereisen geen databasemigratie

```mermaid
graph LR
    subgraph "Oud: EAV (4 tabellen)"
        PF1[processed_files] --> FC[file_classifications]
        PF1 --> FM[file_metadata<br/>N rijen per bestand]
        PF1 --> FS[file_summaries]
    end

    subgraph "Nieuw: JSONB (1 tabel)"
        PF2[processed_files<br/>metadata_ JSONB<br/>extra_fields JSONB]
    end

    PF1 -.->|migratie| PF2
```

---

## Architectuur

### Database-laag

De migratie consolideert alles naar **één flat tabel** met twee JSONB-kolommen:

```python
from sqlalchemy.dialects.postgresql import JSONB

class ProcessedFileModel(Base):
    __tablename__ = "processed_files"

    # Basis-velden
    id            = Column(String, primary_key=True)
    filename      = Column(String, nullable=False)
    # ...

    # Classificatie (geflattened)
    concept_id    = Column(String, nullable=True)
    concept_label = Column(String, nullable=True)
    confidence    = Column(Float, nullable=True)

    # JSONB-kolommen
    metadata_     = Column("metadata_", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    extra_fields  = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    # GIN-index voor snelle JSONB-queries
    __table_args__ = (
        Index("ix_processed_files_metadata_gin", metadata_, postgresql_using="gin"),
    )
```

> [!IMPORTANT]
> De kolom heet `metadata_` (met underscore) om conflict met SQLAlchemy's interne `.metadata` attribuut te voorkomen.

### JSONB-datastructuur

#### `metadata_` kolom

Bevat geëxtraheerde metadata als een dictionary van velden:

```json
{
  "invoice_number": {
    "value": "F-2025-001",
    "confidence": 0.95,
    "type": "string"
  },
  "total_amount": {
    "value": 1250.50,
    "confidence": 0.88,
    "type": "currency"
  },
  "invoice_date": {
    "value": "2025-03-15",
    "confidence": 0.92,
    "type": "date"
  }
}
```

#### `extra_fields` kolom

Bevat aanvullende ontdekte velden die niet in het ontologie-template passen:

```json
[
  {
    "field_name": "payment_reference",
    "value": "REF-2025-XYZ",
    "confidence": 0.7,
    "source_quote": "Betaling referentie: REF-2025-XYZ"
  }
]
```

---

## Domain-laag

### ProcessedFile Entity

De domain entity is vereenvoudigd — geen `ExtractedProperty` meer:

```python
@dataclass
class ProcessedFile:
    id: str
    filename: str
    # ...classificatie-velden direct op entity
    concept_id: str | None = None
    concept_label: str | None = None
    confidence: float | None = None
    # JSONB-velden
    metadata: dict = field(default_factory=dict)
    extra_fields: list[dict] = field(default_factory=list)
    summary: str | None = None
    language: str | None = None
    processing_time_ms: int | None = None
```

### Verwijderde types

| Verwijderd | Vervanging |
|-----------|-----------|
| `ExtractedProperty` dataclass | `dict` entries in `metadata` |
| `FileClassificationModel` | Velden direct op `ProcessedFileModel` |
| `FileMetadataModel` | `metadata_` JSONB kolom |
| `FileSummaryModel` | `summary` String kolom |

---

## Services-laag

### MetadataExtractionService

De service retourneert nu een tuple van drie waarden:

```python
async def extract(
    self,
    text: str,
    classification: ClassificationResult,
) -> tuple[dict, list[dict], str]:
    """
    Returns:
        metadata:     dict[str, {"value": ..., "confidence": ..., "type": ...}]
        extra_fields: list[{"field_name": ..., "value": ..., "confidence": ...}]
        summary:      str
    """
```

### Waarde-normalisatie

De `_normalize_value()` functie retourneert nu JSONB-compatibele dictionaries:

```python
# Oud (ExtractedProperty)
prop = ExtractedProperty(key="amount", value_numeric=1250.50, confidence=0.9)

# Nieuw (JSONB dict)
entry = {"value": 1250.50, "confidence": 0.9, "type": "currency"}
```

Normalisatie per type:

| Type | Opslagformaat |
|------|--------------|
| `string` | `{"value": "tekst", "confidence": 0.9}` |
| `date` | `{"value": "2025-03-15", "confidence": 0.9}` (ISO-formaat) |
| `currency`, `number` | `{"value": 1250.50, "confidence": 0.9}` |

---

## Repository-laag

De repository is sterk vereenvoudigd doordat `asyncpg` Python dicts automatisch naar JSONB converteert:

```python
# Oud: handmatige child-tabel management + json.dumps
model.metadata_records = [
    FileMetadataModel(key=p.key, value_text=p.value_text, ...)
    for p in entity.extracted_properties
]

# Nieuw: directe toewijzing
model.metadata_ = entity.metadata     # dict → JSONB automatisch
model.extra_fields = entity.extra_fields  # list[dict] → JSONB automatisch
```

---

## API-laag (Pydantic Schemas)

### Nieuwe schemas

```python
class MetadataFieldSchema(BaseModel):
    value: str | float | int | None
    confidence: float
    raw_text: str | None = None
    source_quote: str | None = None

class ExtraFieldSchema(BaseModel):
    field_name: str
    value: str | float | int | None
    confidence: float
    source_quote: str | None = None

class ProcessedFileDetailSchema(BaseModel):
    metadata: dict[str, MetadataFieldSchema]
    extra_fields: list[ExtraFieldSchema]
    # ... overige velden
```

### Voorbeeld API-response

```json
{
  "id": "abc-123",
  "filename": "factuur.pdf",
  "status": "done",
  "classification": {
    "primary_concept_id": "Invoice",
    "confidence": 0.92
  },
  "metadata": {
    "invoice_number": { "value": "F-2025-001", "confidence": 0.95 },
    "total_amount": { "value": 1250.50, "confidence": 0.88 }
  },
  "extra_fields": [],
  "summary": "Factuur van Acme BV voor IT-diensten"
}
```

---

## Frontend

### TypeScript types

```typescript
interface MetadataField {
    value: string | number | null;
    confidence: number;
    raw_text?: string | null;
    source_quote?: string | null;
}

interface ProcessedFileDetail {
    metadata: Record<string, MetadataField>;
    extra_fields: ExtraField[];
    // ...
}
```

### Rendering

De `FileDetailPage` itereert over `Object.entries(file.metadata)` en detecteert automatisch het waardetype voor correcte weergave (nummer, datum, of tekst).

---

## JSONB Querying (Geavanceerd)

Dankzij de GIN-index kunnen efficiënte queries uitgevoerd worden:

```sql
-- Alle bestanden met een specifiek factuurnummer
SELECT * FROM processed_files
WHERE metadata_ @> '{"invoice_number": {"value": "F-2025-001"}}';

-- Alle bestanden met een metadata-sleutel
SELECT * FROM processed_files
WHERE metadata_ ? 'total_amount';

-- Zoeken op genest veld
SELECT * FROM processed_files
WHERE (metadata_ -> 'total_amount' ->> 'value')::numeric > 1000;
```

---

## Installatie & Setup

### 1. PostgreSQL starten via Docker

```bash
docker compose up -d postgres
```

De `docker-compose.yml` configureert:

| Variabele | Waarde |
|-----------|--------|
| `POSTGRES_DB` | `knowledge_base` |
| `POSTGRES_USER` | `kb_user` |
| `POSTGRES_PASSWORD` | `kb_secret_2026` |
| Port | `5432` |

### 2. Omgevingsvariabelen

In `backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://kb_user:kb_secret_2026@localhost:5432/knowledge_base
```

### 3. Backend starten

```bash
cd backend
uv run uvicorn app.main:app --reload
```

> [!WARNING]
> Dit is een **backward-incompatibele** migratie. De bestaande SQLite-database (`knowledge_base.db`) is niet compatibel met het nieuwe schema. Verwijder deze handmatig voordat je de applicatie start met PostgreSQL.

---

## Testen

Alle bestaande tests zijn bijgewerkt:

```bash
cd backend
uv run pytest tests/ -v
```

Belangrijke test-aanpassingen:
- `test_metadata_extraction.py`: assertions controleren nu JSONB dict-structuur
- `test_file_processing.py`: `ExtractedProperty` import verwijderd
