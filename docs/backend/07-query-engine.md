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
| **Semantic Search** | Embeddings + vector similarity | Wanneer exacte velden onbekend zijn |
| **Structured Query** | NL → SQL/filter → database | Wanneer de ontologie de structuur definieert |

Dit project gebruikt **structured query** — de ontologie biedt al de structuur die nodig is voor nauwkeurige zoekresultaten.

## Two-Stage Flow

```
Gebruikersvraag
    │
    ▼
┌──────────────────────────────┐
│  Stage 1: Intent Resolution  │  ← LLM interpreteert de vraag
│                              │
│  Input:  vraag + ontologie   │
│  Output: QueryIntent         │
│    • concept_ids             │
│    • metadata_filters        │
│    • keywords                │
│    • reasoning               │
└─────────────┬────────────────┘
              │
              ▼
┌──────────────────────────────┐
│  Stage 2: Database Search    │  ← Deterministische query
│                              │
│  Input: QueryIntent          │
│  Output: QueryResult         │
│    • matches[]               │
│    • total_matches           │
└──────────────────────────────┘
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

## Stage 2: Database Search

De `QueryIntent` wordt omgezet in database-queries:

```python
async def _execute_search(self, intent: QueryIntent) -> list[QueryMatch]:
    """Voer de database-query uit op basis van de intent."""

    # 1. Filter op concept_ids
    query = select(ResourceModel).where(
        ResourceModel.concept_id.in_(intent.concept_ids)
    )

    # 2. Pas metadata-filters toe (JSONB queries)
    for filter in intent.metadata_filters:
        if filter.operator == "contains":
            query = query.where(
                ResourceModel.metadata[filter.field_name]
                    .astext.ilike(f"%{filter.value}%")
            )
        elif filter.operator == "gte":
            query = query.where(
                ResourceModel.metadata[filter.field_name]["value"]
                    .astext >= filter.value
            )

    # 3. Optionele text search
    if intent.text_query:
        query = query.where(
            ResourceModel.extracted_text.ilike(f"%{intent.text_query}%")
        )
```

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
    relevance_score: float
```

## Leerpunten

1. **Two-stage architectuur**: Scheid intent resolution (LLM, onbetrouwbaar) van database search (deterministic, betrouwbaar). Dit maakt het systeem robuuster.
2. **Ontologie als zoekindex**: De ontologie definieert niet alleen wat je kunt *opslaan*, maar ook wat je kunt *zoeken*. Metadata-velden worden automatisch zoekbaar.
3. **Canonicalisatie**: LLM output is onvoorspelbaar — canonical mapping corrigeert typo's en variaties.
4. **Graceful degradation**: Als het LLM niet beschikbaar is, werkt de zoekfunctie nog steeds met deterministische matching.
5. **JSONB queries**: PostgreSQL's JSONB-type maakt krachtige queries op geneste metadata mogelijk zonder schema-migraties.
