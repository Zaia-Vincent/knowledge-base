# Query Engine — Natural Language Search

> **Doelgroep**: AI-studenten die willen begrijpen hoe natuurlijke taalvragen worden vertaald naar gestructureerde database-queries.

## Motivatie

Na het classificeren en extraheren van metadata uit documenten, willen gebruikers hun kennisbank **doorzoeken met gewone vragen**:

- *"Alle facturen van Molcon van dit jaar"*
- *"Contracten die in maart verlopen"*
- *"Welke werkorders heeft Jan gekregen?"*

De `QueryService` vertaalt deze vragen naar gestructureerde queries op de database — een tweestaps-proces dat LLM-intentieherkenning combineert met deterministische database-operaties.

## Theoretische Achtergrond

### Intent Recognition

Intent Recognition is een kerntechniek in NLP (Natural Language Processing):

> *Gegeven een gebruikersuitspraak, bepaal de **intentie** (wat wil de gebruiker?) en de **entiteiten** (welke objecten zijn relevant?).*

| Vraag | Intentie | Entiteiten |
|-------|----------|-----------|
| "Alle facturen van Molcon" | Zoek resources | concept: Invoice, vendor: Molcon |
| "Contracten die verlopen in maart" | Zoek resources | concept: Contract, filter: expiry_date ≤ 2024-03-31 |
| "Hoeveel werkorders zijn er?" | Tel resources | concept: WorkOrder |

### Semantic Search vs. Structured Query

| Aanpak | Hoe het werkt | Wanneer gebruiken |
|--------|---------------|-------------------|
| **Semantic Search** | Embeddings + vector similarity (pgvector) | Inhoudelijke vragen, "vind documenten over X" |
| **Structured Query** | NL → metadata-filters → JSONB query | Exacte filters op metadata-velden |

Dit project gebruikt een **hybride aanpak**: vector similarity search (pgvector) als primaire zoekmethode, met structured metadata-filters als aanvulling. Het LLM vertaalt de vraag naar een `QueryIntent` die zowel concept-filters, metadata-filters als een `text_query` kan bevatten. De `text_query` wordt omgezet naar een embedding-vector voor cosine-similarity zoekopdrachten.

## Two-Stage Flow

```
Gebruikersvraag
    │
    ▼
┌──────────────────────────────────────┐
│  Stage 1: Intent Resolution          │  ← LLM interpreteert de vraag
│                                      │
│  Input:  vraag + ontologie-context   │
│  Output: QueryIntent                 │
│    • concept_ids                     │
│    • metadata_filters                │
│    • text_query                      │
│    • keywords                        │
│    • reasoning                       │
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│  Stage 2: Vector + Database Search   │
│                                      │
│  1. Genereer query-embedding         │
│  2. pgvector cosine similarity       │
│  3. Filter op concept + status       │
│  4. Deduplificatie per resource       │
│  5. Fallback: retry zonder concept   │
│                                      │
│  Output: QueryResult                 │
│    • matches[]  (met similarity)     │
│    • total_matches                   │
└──────────────────────────────────────┘
```

## Stage 1: Intent Resolution

### Ontologie-context voor het LLM

Het LLM ontvangt de volledige ontologie als context:

```python
def _build_ontology_context(self, concepts: list[OntologyConcept]) -> str:
    """Bouw een gestructureerde beschrijving van de ontologie voor het LLM."""
    parts = []
    for concept in concepts:
        resolved_props = self._get_resolved_properties(concept)
        parts.append(
            f"- {concept.id} ({concept.label}): {concept.description}\n"
            f"  Synoniemen: {', '.join(concept.synonyms)}\n"
            f"  Velden: {', '.join(p.name for p in resolved_props)}"
        )
    return "\n".join(parts)
```

### LLM Prompt

```python
system_prompt = """Je bent een zoekexpert. Vertaal de gebruikersvraag naar
een gestructureerde zoekintentie op basis van de beschikbare ontologie.

Retourneer JSON met:
- concept_ids: lijst van relevante concept-IDs
- metadata_filters: [{field_name, value, operator}]
- keywords: zoektermen voor tekst-matching
- reasoning: motivatie voor je keuze
"""
```

### Canonicalisatie

Na de LLM-response worden termen **gecanoniseerd** — fuzzy matching tegen de ontologie:

```python
def _canonicalize_concept_ids(self, raw_ids: list[str]) -> list[str]:
    """Corrigeer typo's en variaties in concept-IDs.

    Voorbeelden:
      "invoice" → "Invoice"
      "factuur" → "Invoice"  (via synoniem-matching)
      "Invoicee" → "Invoice" (via fuzzy match)
    """
```

### Fallback bij LLM-falen

Als het LLM faalt, is er een **deterministische fallback**:

```python
def _deterministic_intent_resolution(self, question: str) -> QueryIntent:
    """Rule-based intent resolution als LLM niet beschikbaar is.

    Zoekt naar concept-namen, synoniemen en keywords in de vraag.
    """
    question_lower = question.lower()

    for concept in self._concepts:
        for synonym in concept.get_all_hints():
            if synonym.lower() in question_lower:
                return QueryIntent(
                    concept_ids=[concept.id],
                    keywords=question.split(),
                    ...
                )
```

## Stage 2: Vector Similarity Search (pgvector)

### De Embedding Pipeline

Vóór het zoeken worden documenten opgesplitst in **chunks** en voorzien van embedding-vectoren:

```
Resource (extracted_text + summary)
    │
    ▼
┌────────────────────────────────┐
│  EmbeddingService              │
│                                │
│  1. Bestaande chunks verwijderen│
│  2. Tekst splitsen in chunks   │
│     • 1200 chars per chunk     │
│     • 200 chars overlap        │
│     • Recursief: ¶ → \n → . →  │
│  3. Summary als aparte chunk   │
│  4. Batch embedding generatie  │
│     (max 50 per API call)      │
│  5. Opslag in resource_chunks  │
└────────────────────────────────┘
```

### EmbeddingProvider Interface

De `EmbeddingProvider` is een **abstracte port** — de concrete implementatie wordt geïnjecteerd:

```python
class EmbeddingProvider(ABC):
    """Port voor embedding-generatie — geïmplementeerd in de infrastructuurlaag."""

    @abstractmethod
    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Genereer embedding-vectoren voor een batch teksten."""
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Dimensionaliteit van de gegenereerde vectoren."""
        ...
```

### Concrete Implementatie: OpenRouterEmbeddingProvider

De concrete provider ondersteunt zowel **Google Gemini** als **Nomic** modellen via de OpenRouter API:

```python
class OpenRouterEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "google/gemini-embedding-001",
        model_dimensions: int = 768,
        ...
    ):
        ...

    @property
    def _is_nomic(self) -> bool:
        """Nomic-modellen vereisen task-specifieke prefixes."""
        return "nomic" in self._model.lower()

    async def generate_embeddings(self, texts: list[str], *, _query_mode=False):
        # Nomic: voeg "search_document: " of "search_query: " prefix toe
        if self._is_nomic:
            prefix = "search_query: " if _query_mode else "search_document: "
            input_texts = [f"{prefix}{t}" for t in texts]
        else:
            input_texts = texts  # Gemini: geen prefix nodig
        ...
```

### Ondersteunde Embedding-modellen

| Model | Provider | Dimensies | Task Prefix | Opmerkingen |
|-------|----------|-----------|-------------|-------------|
| `google/gemini-embedding-001` | Google via OpenRouter | 768 (Matryoshka) | Nee | **Standaard** — sneller en goedkoper |
| `nomic-ai/nomic-embed-text-v1.5` | Nomic via OpenRouter | 768 | Ja (`search_document:` / `search_query:`) | Vereist aparte prefixes |

> **Matryoshka Embeddings**: Gemini embedding-001 ondersteunt Matryoshka Representation Learning (MRL), waardoor je de dimensionaliteit kunt reduceren (3072 → 768) zonder significant kwaliteitsverlies. Dit bespaart opslagruimte en versnelt zoekopdrachten.

### Configuratie

Embedding-instellingen staan in de `.env` file en worden geladen via Pydantic Settings:

```ini
# .env
EMBEDDING_MODEL=google/gemini-embedding-001
EMBEDDING_DIMENSIONS=768
```

```python
# config.py
class Settings(BaseSettings):
    embedding_model: str = "google/gemini-embedding-001"
    embedding_dimensions: int = 768  # Gemini: Matryoshka (HNSW max: 2000)
```

### Opslag: pgvector + HNSW Index

Chunks met embeddings worden opgeslagen in de `resource_chunks` tabel:

```python
class ResourceChunkModel(Base):
    __tablename__ = "resource_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(String(36), ForeignKey("resources.id", ondelete="CASCADE"))
    chunk_index = Column(Integer, nullable=False)
    chunk_type = Column(String(30), nullable=False)   # "text" of "summary"
    content = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=True)     # pgvector kolom

    __table_args__ = (
        UniqueConstraint("resource_id", "chunk_type", "chunk_index"),
        Index("idx_chunks_embedding_hnsw", embedding,
              postgresql_using="hnsw",
              postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
```

> **HNSW Index**: Hierarchical Navigable Small World — een approximate nearest neighbor index die zoekoperaties versnelt van O(n) naar O(log n). De `vector_cosine_ops` operator klasse optimaliseert voor cosine-similarity queries.

### Vector Search Query

De `PgChunkRepository` gebruikt de pgvector `<=>` operator voor cosine distance:

```python
async def search_similar(self, query_embedding, *, concept_ids=None, limit=20):
    vector_str = f"[{','.join(str(v) for v in query_embedding)}]"

    # literal_column() + .label() maakt de similarity score beschikbaar als kolom
    similarity_expr = literal_column(
        f"1 - (resource_chunks.embedding <=> '{vector_str}'::vector)"
    ).label("similarity")

    query = (
        select(
            ResourceChunkModel.id,
            ResourceChunkModel.content,
            ResourceModel.filename,
            ResourceModel.concept_id,
            similarity_expr,
            ...
        )
        .select_from(ResourceChunkModel)
        .join(ResourceModel, ResourceModel.id == ResourceChunkModel.resource_id)
        .where(ResourceModel.status == "done")
        .where(ResourceChunkModel.embedding.is_not(None))
    )

    if concept_ids:
        query = query.where(ResourceModel.concept_id.in_(concept_ids))

    query = query.order_by(text("similarity DESC")).limit(limit)
```

> **Cosine Distance vs. Similarity**: pgvector's `<=>` operator geeft de *afstand* (0 = identiek), terwijl we *similarity* willen (1 = identiek). Vandaar `1 - (embedding <=> query)`.

### Concept-Filtered Retry

Wanneer de LLM verkeerde concepten voorspelt, zou de vector search 0 resultaten opleveren. Het systeem voert automatisch een **retry zonder concept-filter** uit:

```python
# In _execute_vector_query():
results = await self._chunk_repo.search_similar(
    query_embedding, concept_ids=intent.concept_ids
)

# Als concept-gefilterde search niets oplevert → retry zonder filter
if not results and intent.concept_ids:
    logger.info("Retry zonder concept filter...")
    results = await self._chunk_repo.search_similar(
        query_embedding, concept_ids=None
    )
```

Dit is essentieel voor **graceful degradation** — zelfs als intent resolution faalt, worden semantisch relevante documenten nog steeds gevonden.

### JSONB Metadata Queries

Metadata is opgeslagen als JSONB, wat krachtige queries mogelijk maakt:

```python
# Zoek naar vendor "Molcon" in geneste metadata structuur:
# metadata = {"vendor": {"label": "Molcon Interwheels N.V.", "confidence": 0.95}}

ResourceModel.metadata["vendor"]["label"].astext.ilike("%Molcon%")
```

## Het QueryResult

```python
@dataclass
class QueryResult:
    intent: QueryIntent          # De geïnterpreteerde intentie
    matches: list[QueryMatch]    # Gevonden resources
    total_matches: int           # Totaal aantal matches

@dataclass
class QueryMatch:
    file_id: str
    filename: str
    concept_id: str | None
    concept_label: str | None
    confidence: float
    summary: str | None
    metadata: dict[str, Any]
    relevance_score: float       # Cosine similarity score (0.0 – 1.0)
```

## Leerpunten

1. **Hybride search**: Combineer vector similarity (semantic) met structured metadata queries (exacte filters). Dit geeft het beste van beide werelden.
2. **Embedding pipeline**: Chunking + batch embedding → opslag met pgvector is het standaardpatroon voor RAG-applicaties.
3. **Matryoshka embeddings**: Modellen zoals Gemini embedding-001 ondersteunen dimensie-reductie zonder significant kwaliteitsverlies — optimaal voor opslag en performance.
4. **HNSW indexing**: Approximate nearest neighbor indexing voorkomt dat vector search lineair schaalt met het aantal chunks.
5. **Graceful degradation**: Concept-filtered retry zorgt ervoor dat het systeem werkt zelfs als intent resolution verkeerde concepten voorspelt.
6. **Task prefixes**: Sommige embedding-modellen (Nomic) vereisen aparte prefixes voor documenten vs. queries — de provider abstraheert dit weg.
7. **Canonicalisatie**: LLM output is onvoorspelbaar — canonical mapping corrigeert typo's en variaties in concept-namen.
8. **JSONB queries**: PostgreSQL's JSONB-type maakt krachtige queries op geneste metadata mogelijk zonder schema-migraties.
