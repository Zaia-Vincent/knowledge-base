# LLM Integratie — Ports, Adapters & Tool-Calling

> **Doelgroep**: AI-studenten die willen begrijpen hoe LLM's geïntegreerd worden in een productieklare applicatie met Clean Architecture.

## Motivatie

LLM's zijn krachtig maar veranderlijk: modellen worden vervangen, API's wijzigen, providers komen en gaan. Een naïeve integratie koppelt je codebase aan één specifieke provider (bijv. OpenAI). Daarom gebruiken we het **Ports & Adapters** patroon:

- **Port** (`LLMClient` ABC): definieert *welke operaties* de applicatie nodig heeft
- **Adapter** (`OpenRouterLLMClient`): implementeert *hoe* die operaties worden uitgevoerd

Dit maakt het triviaal om van provider te wisselen — alleen de adapter verandert.

## Theoretische Achtergrond

### Ports & Adapters Pattern

Het Ports & Adapters patroon (ook bekend als Hexagonal Architecture) scheidt technologie van logica:

```
Application Layer                Infrastructure Layer
┌────────────────────────┐      ┌────────────────────────────┐
│                        │      │                            │
│  ClassificationService │─────▶│  LLMClient (Port / ABC)    │
│  MetadataExtractionSvc │      │                            │
│  QueryService          │      └────────────┬───────────────┘
│                        │                   │ implements
└────────────────────────┘      ┌────────────▼───────────────┐
                                │  OpenRouterLLMClient       │
                                │  (Adapter)                 │
                                │                            │
                                │  → OpenRouterClient        │
                                │  → HTTP API calls          │
                                └────────────────────────────┘
```

### Tool-Calling (Function Calling)

Tool-calling is een LLM-patroon waarbij het model **niet direct een antwoord geeft**, maar in plaats daarvan functies aanroept om informatie te verkrijgen of acties te ondernemen:

```
LLM                           Applicatie
 │  "Ik heb het schema nodig"     │
 │  ─────────────────────────────▶│
 │  tool_call: get_extraction_    │
 │  schema("Invoice")             │
 │                                │
 │  ◀───────────────────────────  │
 │  {properties: [...]}           │
 │                                │
 │  "Nu kan ik extracten"         │
 │  ─────────────────────────────▶│
 │  tool_call: submit_document(   │
 │    concept_id="Invoice", ...)  │
 │                                │
 │  ◀───────────────────────────  │
 │  {status: "accepted"}          │
```

Dit geeft het LLM **agency**: het beslist zelf welke informatie het nodig heeft en hoeveel documenten het vindt in een PDF.

## De LLMClient Interface (Port)

De abstracte interface definiëert vijf kernoperaties:

```python
from abc import ABC, abstractmethod

class LLMClient(ABC):
    """Abstracte interface voor LLM operaties."""

    @abstractmethod
    async def classify_document(
        self, request: LLMClassificationRequest
    ) -> LLMClassificationResponse:
        """Classificeer een document op basis van tekstexcerpt."""
        ...

    @abstractmethod
    async def extract_metadata(
        self, request: LLMExtractionRequest
    ) -> LLMExtractionResponse:
        """Extraheer gestructureerde metadata uit documenttekst."""
        ...

    @abstractmethod
    async def ocr_image(
        self, request: LLMVisionOCRRequest
    ) -> LLMVisionOCRResponse:
        """Extraheer tekst uit een afbeelding via LLM vision."""
        ...

    @abstractmethod
    async def process_pdf(
        self, request: LLMPdfProcessingRequest
    ) -> LLMPdfProcessingResponse:
        """Verwerk een PDF: classificeer en extraheer metadata in één call."""
        ...

    @abstractmethod
    async def process_pdf_with_tools(
        self, pdf_base64, filename, available_concepts, tool_handler
    ) -> list[LLMPdfProcessingResponse]:
        """Verwerk een PDF met tool-calling voor multi-document detectie."""
        ...
```

### Request/Response Dataclasses

De communicatie verloopt via type-safe dataclasses:

```python
@dataclass
class LLMClassificationRequest:
    text_excerpt: str                    # Document content (max 3000 chars)
    available_concepts: list[dict]       # [{id, label, description, hints}]

@dataclass
class LLMClassificationResponse:
    concept_id: str                      # Geselecteerd concept
    confidence: float                    # 0.0 – 1.0
    reasoning: str                       # Motivatie van het LLM
    usage: TokenUsage | None = None      # Token verbruik
    model: str | None = None             # Gebruikt model
```

## De OpenRouterLLMClient (Adapter)

### Architectuur

```
OpenRouterLLMClient
    │
    ├── _client: OpenRouterClient          # HTTP client voor OpenRouter API
    ├── _model: str                         # Model voor classificatie & extractie
    └── _pdf_model: str                     # Separaat model voor PDF verwerking
```

### Waarom twee modellen?

PDF-verwerking vereist vaak een **groter en duurder model** dat multimodal input (PDF als base64) aankan, terwijl tekstclassificatie met een kleiner model werkt. De configuratie maakt dit flexibel:

```python
# In config.py / .env
CLASSIFICATION_MODEL=google/gemini-2.0-flash-001
PDF_PROCESSING_MODEL=google/gemini-2.0-flash-001
```

### Prompt Engineering

Elke operatie heeft een **systeem-prompt** die het LLM instrueert:

| Operatie | Systeem-prompt | Output |
|----------|---------------|--------|
| Classificatie | `_CLASSIFICATION_SYSTEM_PROMPT` | JSON: `{concept_id, confidence, reasoning}` |
| Metadata extractie | `_EXTRACTION_SYSTEM_PROMPT` | JSON: `{field1: value1, ...}` |
| OCR | `_OCR_SYSTEM_PROMPT` | Ruwe tekst |
| PDF (single-pass) | `_PDF_PROCESSING_SYSTEM_PROMPT` | JSON classificatie + extractie |
| PDF (tool-calling) | `_PDF_TOOL_SYSTEM_PROMPT` | Tool calls → meerdere documenten |
| Image (website) | `_IMAGE_TOOL_SYSTEM_PROMPT` | Tool calls → content items |

### Tool-Calling Workflow (PDF)

Het tool-calling systeem definieert twee tools:

```python
# Tool 1: Schema opvragen
_TOOL_GET_EXTRACTION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_extraction_schema",
        "description": "Get the property schema for a concept",
        "parameters": {
            "type": "object",
            "properties": {
                "concept_id": {"type": "string"}
            },
            "required": ["concept_id"],
        },
    },
}

# Tool 2: Document inleveren
_TOOL_SUBMIT_DOCUMENT = {
    "type": "function",
    "function": {
        "name": "submit_document",
        "description": "Submit extracted data for one document",
        "parameters": {
            "type": "object",
            "properties": {
                "concept_id": {"type": "string"},
                "confidence": {"type": "number"},
                "extracted_properties": {"type": "object"},
                "summary": {"type": "string"},
                "page_range": {"type": "string"},
            },
        },
    },
}
```

**De workflow:**

1. LLM ontvangt PDF + conceptcatalogus
2. LLM roept `get_extraction_schema("Invoice")` aan → ontvangt de properties
3. LLM extraheert de waarden uit de PDF
4. LLM roept `submit_document(concept_id="Invoice", ...)` aan
5. Als de PDF meerdere documenten bevat: herhaal stap 2-4

### Multimodale Content

Het systeem ondersteunt verschillende content types:

```python
# Tekst
ContentPart(type="text", text="Classificeer dit document...")

# Afbeelding (base64)
ContentPart(type="image_url", image_url={
    "url": f"data:{mime_type};base64,{image_base64}"
})

# PDF bestand (base64)
ContentPart(type="file", file_data={
    "file_data": f"data:application/pdf;base64,{pdf_base64}",
    "filename": filename,
})
```

## Token Usage Tracking

Elke LLM-aanroep wordt gelogd voor kostenbeheer:

```python
class LLMUsageLogger:
    """Logt token/cost per LLM-aanroep voor auditability."""

    async def log_request(
        self,
        model: str,
        provider: str,
        feature: str,            # "classification", "extraction", "website_capture"
        usage: TokenUsage,
        duration_ms: int,
        tools_called: list[str] = [],
    ):
        log = ServiceRequestLog(
            model=model,
            provider=provider,
            feature=feature,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            cost=usage.cost,
            duration_ms=duration_ms,
        )
        await self._repo.create(log)
```

## Leerpunten

1. **Ports & Adapters voor AI**: Definieer een abstracte `LLMClient` interface zodat je provider kunt wisselen zonder businesslogica te wijzigen.
2. **Tool-calling geeft LLM's agency**: In plaats van alles in één prompt te stoppen, laat je het LLM tools aanroepen om schema's op te vragen en documenten in te leveren.
3. **Gescheiden modellen**: Gebruik een sneller/goedkoper model voor tekstclassificatie en een krachtiger model voor PDF/image verwerking.
4. **Type-safe communicatie**: Dataclasses voor requests/responses voorkomen runtimefouten en documenteren de verwachte structuur.
5. **Usage logging**: Track elke LLM-aanroep met tokens, kosten en duur — essentieel voor kostenbeheer in productie.
