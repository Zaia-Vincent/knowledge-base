# Document Processing Pipeline — Classificatie & Extractie

> **Doelgroep**: AI-studenten die willen begrijpen hoe documenten automatisch worden verwerkt met een combinatie van rule-based en LLM-technieken.

## Motivatie

Het hart van het Knowledge Base systeem is de **verwerkingspipeline**: een reeks stappen die een rauw document (PDF, afbeelding, tekstbestand) omzet in een gestructureerd, geclassificeerd record met geëxtraheerde metadata.

Waarom een pipeline-architectuur?

- **Modulariteit**: elke stap (extractie, classificatie, metadata) is een onafhankelijke service
- **Vervangbaarheid**: het LLM kan worden uitgeschakeld voor rule-based verwerking
- **Transparantie**: elk classificatiesignaal wordt gelogd, zodat je kunt zien *waarom* een document een bepaald type kreeg
- **Herverwerking**: resources kunnen opnieuw door de pipeline worden gestuurd met eventueel een ander concept

## Pipeline Architectuur

### Twee Verwerkingspaden

Het systeem heeft twee verwerkingspaden, afhankelijk van het bestandstype:

```
                    ┌──────────────┐
                    │   Upload /   │
                    │   Ingest     │
                    └───────┬──────┘
                            │
                    ┌───────▼──────┐
                    │  _process_   │
                    │   resource   │
                    └───────┬──────┘
                            │
              ┌─────────────┼─────────────┐
              │ PDF?        │ non-PDF     │
              ▼             ▼             │
    ┌─────────────────┐  ┌───────────────┐│
    │ LLM Tool-Calling│  │ Text-Based    ││
    │ Pipeline        │  │ Pipeline      ││
    │                 │  │               ││
    │ PDF + Concepts  │  │ 1. Extract    ││
    │    → LLM →      │  │    Text       ││
    │ Tool calls:     │  │ 2. Classify   ││
    │ get_schema()    │  │ 3. Extract    ││
    │ submit_doc()    │  │    Metadata   ││
    └─────────────────┘  └───────────────┘│
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                    ┌───────────────┐
                    │   Resource    │
                    │   DONE ✓     │
                    └───────────────┘
```

### Text-Based Pipeline (non-PDF)

```python
async def _process_via_text_extraction(self, resource: Resource, *, concept_id=None):
    """Bestaande pipeline: extract text → classify → extract metadata."""

    # Stap 1: Tekst extractie
    await self._extract_text(resource)

    # Stap 2: Classificatie (tenzij concept handmatig opgegeven)
    if concept_id:
        resource.classification = ClassificationResult(
            primary_concept_id=concept_id, confidence=1.0, signals=[]
        )
    else:
        await self._classify(resource)

    # Stap 3: Metadata extractie
    await self._extract_metadata(resource)

    resource.mark_done()
```

### PDF via LLM Tool-Calling

PDF's worden met een geavanceerder proces verwerkt: het LLM ontvangt de PDF + conceptcatalogus en stuurt zelf de workflow aan via tool-calls:

```python
async def _process_pdf_via_llm(self, resource: Resource):
    """Process een PDF via tool-calling: het LLM stuurt classificatie + extractie.

    Het LLM ontvangt de PDF + conceptcatalogus en gebruikt tools:
    - get_extraction_schema(concept_id) → retourneert resolved properties
    - submit_document(concept_id, ...) → levert een geëxtraheerd document in
    """
```

## De ClassificationService — Multi-Signal Classificatie

De classificatieservice combineert drie signalen met gewogen aggregatie:

### Signaalweging

| Signaal | Methode | Gewicht | Beschrijving |
|---------|---------|---------|-------------|
| **File Pattern** | Regex op pad/bestandsnaam | 0.25 | Match tegen `extraction_template.file_patterns` |
| **Hint Match** | Keyword in documenttekst | 0.35 | Match tegen `synonyms` + `classification_hints` |
| **LLM Analysis** | Gemini/Claude excerpt analyse | 0.40 | LLM classificeert op basis van content |

### Waarom Multi-Signal?

Geen enkel signaal is perfect:

- **File patterns** zijn snel maar beperkt tot naamconventies (`**/facturen/**`)
- **Hint matching** vindt keywords maar kan false positives geven
- **LLM** is het meest nauwkeurig maar traag en kostbaar

Door ze te combineren en te wegen, krijg je een **robuust** resultaat dat beter is dan elk signaal apart.

### Signaal 1: File Pattern Matching

```python
_W_FILE_PATTERN = 0.25

def _apply_file_pattern_signals(self, scores, concepts, filename, original_path):
    """Match bestand/map-patronen tegen extraction_template.file_patterns."""
    path_lower = (original_path or filename).lower()

    for concept in concepts:
        for pattern in concept.extraction_template.file_patterns:
            pattern_lower = pattern.lower().replace("*", "")
            if pattern_lower in path_lower:
                signal = ClassificationSignal(
                    method="file_pattern",
                    concept_id=concept.id,
                    score=0.8,
                    details=f"Pattern '{pattern}' matches voor '{filename}'",
                )
                scores[concept.id].weighted_score += 0.8 * _W_FILE_PATTERN
                break  # Eén match per concept is genoeg
```

### Signaal 2: Synonym/Hint Matching

```python
_W_HINT_MATCH = 0.35

def _apply_hint_signals(self, scores, concepts, text):
    """Match synoniemen en classificatie-hints tegen documenttekst."""
    text_lower = text[:5000].lower()

    for concept in concepts:
        hints = concept.get_all_hints()   # synoniemen + classification_hints
        matches = []
        for hint in hints:
            # Word boundary matching voorkomt deelmatches
            pattern = r"\b" + re.escape(hint.lower()) + r"\b"
            if re.search(pattern, text_lower):
                matches.append(hint)

        if matches:
            raw_score = min(len(matches) * 0.3, 1.0)  # Meer matches = hoger
            scores[concept.id].weighted_score += raw_score * _W_HINT_MATCH
```

### Signaal 3: LLM Content Analysis

```python
_W_LLM = 0.40
_LLM_EXCERPT_LENGTH = 3000

async def _apply_llm_signal(self, scores, concepts, text):
    """Gebruik LLM voor documentclassificatie."""
    excerpt = text[:_LLM_EXCERPT_LENGTH]

    available_concepts = [
        {
            "id": c.id,
            "label": c.label,
            "description": c.description[:200],
            "synonyms": c.synonyms[:5],
            "hints": c.extraction_template.classification_hints[:5],
        }
        for c in concepts
    ]

    request = LLMClassificationRequest(
        text_excerpt=excerpt,
        available_concepts=available_concepts,
    )
    response = await self._llm_client.classify_document(request)

    if response.concept_id in scores:
        scores[response.concept_id].weighted_score += response.confidence * _W_LLM
```

### Eindscore en Selectie

```python
# Vind het concept met de hoogste gewogen score
best = max(scores.values(), key=lambda s: s.weighted_score)

return ClassificationResult(
    primary_concept_id=best.concept_id,
    confidence=min(best.weighted_score, 1.0),
    signals=all_signals,  # Alle signalen voor transparantie
)
```

## MetadataExtractionService — Template-Driven Extractie

Na classificatie worden **gestructureerde metadata** geëxtraheerd op basis van het ontologieconcept.

### Extractieproces

```
Classificatie: concept_id = "Invoice"
        │
        ▼
get_resolved_properties("Invoice")
        │  → [document_date, vendor, amount, currency, due_date, line_items, ...]
        ▼
_extract_with_llm(text, concept, template_fields)
        │  → LLM prompt met velden + documenttekst
        ▼
_normalize_value() per geëxtraheerd veld
        │  → Taalaware normalisatie (NL/EN datums, bedragen)
        ▼
metadata = {"vendor": {"label": "Acme", "confidence": 0.95}, ...}
```

### Value Normalization — Taalaware Verwerking

Een bijzonder aspect is de **taalaware normalisatie** van geëxtraheerde waarden:

```python
def _normalize_value(field_name: str, field_type: str, raw_value) -> dict:
    """Normaliseer een ruwe waarde op basis van het veldtype.

    Handles:
    - Datums: ISO 8601, DD-MM-YYYY, DD/MM/YYYY
    - Getallen: Nederlands (1.250,00) EN Engels (1,250.00)
    - Strings: gestript
    """
```

**Voorbeelden:**

| Input (ruw LLM output) | Veldtype | Genormaliseerd |
|--------------------------|----------|----------------|
| `"14-08-2024"` | `date` | `{"value": "2024-08-14", "confidence": 1.0}` |
| `"€ 1.250,50"` | `decimal` | `{"value": 1250.50, "confidence": 1.0}` |
| `"$1,250.50"` | `decimal` | `{"value": 1250.50, "confidence": 1.0}` |
| `"Deli Tyres bv"` | `ref:Vendor` | `{"label": "Deli Tyres bv", "confidence": 0.0}` |
| `[{...}, {...}]` | `array` | `{"value": [{...}, {...}], "confidence": 0.0}` |

### NL vs. EN Getallen

```python
def _parse_numeric(s: str) -> float | None:
    """Parse een getal in Nederlands OF Engels formaat.

    Nederlands: 1.250,50 (punten als duizendtallen, komma als decimaal)
    Engels:     1,250.50 (komma's als duizendtallen, punt als decimaal)
    """
    # Heuristiek: als de laatste scheidingsteken een komma is → Nederlands
    # Als de laatste scheidingsteken een punt is → Engels
```

## Reprocessing Mechanisme

Resources kunnen opnieuw worden verwerkt, optioneel met een handmatig opgegeven concept:

```python
async def reprocess_resource(self, resource_id: str, *, concept_id: str | None = None):
    """Her-verwerk een bestaande resource.

    Stappen:
    1. Vind de resource (of zijn root als het een sub-document is)
    2. Verwijder child records (van multi-doc PDF splits)
    3. Reset de root resource naar PENDING
    4. Voer de pipeline opnieuw uit (optioneel met concept override)
    """
```

Dit is waardevol wanneer:
- Het ontologie-model is verbeterd
- Een document verkeerd was geclassificeerd
- Je wilt testen met een ander concept

## Multi-Document PDF Detectie

PDF's kunnen meerdere documenten bevatten (bijv. een scan met 3 facturen). Het LLM detecteert dit en maakt aparte `Resource`-records:

```python
# Het LLM roept submit_document() meerdere keren aan:
# 1. submit_document(concept_id="Invoice", page_range="1-2", ...)
# 2. submit_document(concept_id="Receipt", page_range="3-3", ...)

# Voor elk gedetecteerd sub-document:
child = Resource(
    filename=f"{resource.filename} [pp. {page_range}]",
    origin_file_id=resource.id,     # Link naar parent
    page_range=page_range,
)
```

## Sequence Diagram — Volledige Verwerking

```
Client          ResourceProcessingService    ClassificationSvc    MetadataExtractionSvc
  │                      │                        │                       │
  │  upload_file()       │                        │                       │
  │─────────────────────▶│                        │                       │
  │                      │                        │                       │
  │                      │  _extract_text()       │                       │
  │                      │─────────┐              │                       │
  │                      │◀────────┘              │                       │
  │                      │                        │                       │
  │                      │  classify()            │                       │
  │                      │───────────────────────▶│                       │
  │                      │                        │ file_patterns         │
  │                      │                        │ hint_matching         │
  │                      │                        │ llm_analysis          │
  │                      │  ClassificationResult  │                       │
  │                      │◀───────────────────────│                       │
  │                      │                        │                       │
  │                      │  extract()             │                       │
  │                      │────────────────────────┼──────────────────────▶│
  │                      │                        │  resolve_properties   │
  │                      │                        │  llm_extract          │
  │                      │                        │  normalize_values     │
  │                      │  metadata dict         │                       │
  │                      │◀───────────────────────┼───────────────────────│
  │                      │                        │                       │
  │  Resource (DONE)     │                        │                       │
  │◀─────────────────────│                        │                       │
```

## Leerpunten

1. **Multi-signal aggregatie**: Combineer goedkope (file patterns) en dure (LLM) signalen met weging. Dit biedt de beste balans tussen kosten, snelheid en nauwkeurigheid.
2. **Graceful degradation**: Als het LLM niet beschikbaar is, werkt het systeem nog steeds met rule-based signalen — de pipeline stopt niet.
3. **Template-driven extractie**: De ontologie definieert *welke velden* worden geëxtraheerd. Het LLM is slechts het *gereedschap* — de kennis zit in de templates.
4. **Taalaware normalisatie**: In een meertalige omgeving (NL/EN) is het essentieel dat datums en bedragen ongeacht het formaat correct worden geparseerd.
5. **Tool-calling voor complexe workflows**: PDF-verwerking laat het LLM de regie voeren via tool-calls — het bepaalt zelf welke schemas het nodig heeft en hoeveel documenten het vindt.
