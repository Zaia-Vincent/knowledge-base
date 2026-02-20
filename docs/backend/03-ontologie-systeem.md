# Ontologie Systeem — Compiler, Service & YAML

> **Doelgroep**: AI-studenten die willen begrijpen hoe een ontologie werkt als ruggengraat voor geautomatiseerde documentclassificatie.

## Motivatie

Waarom heeft een AI-documentverwerkingssysteem een **ontologie** nodig?

Zonder ontologie zou elke documentclassificatie ad-hoc zijn — hardcoded regels die snel verouderen. Een ontologie biedt:

1. **Gestructureerde kennisrepresentatie**: een hiërarchische taxonomie die definieert *welke soorten documenten bestaan* en *welke eigenschappen ze hebben*
2. **Automatische overerving**: een `Invoice` erft automatisch alle eigenschappen van `FinancialDocument`, die weer erft van `Document`
3. **LLM-sturing**: de ontologie genereert de prompts die het LLM vertellen waar het naar moet zoeken
4. **Uitbreidbaarheid**: gebruikers kunnen eigen concepten (L3) toevoegen zonder code aan te passen

## Theoretische Achtergrond

### Ontologieën in AI & Knowledge Representation

Een **ontologie** is een formele beschrijving van concepten en hun relaties binnen een domein. Het idee stamt uit de filosofie, maar in de informatica (met name het Semantic Web) is het een kernbegrip:

| Term | Definitie | Voorbeeld |
|------|-----------|-----------|
| **Concept** (klasse) | Een categorie van dingen | `Invoice`, `Contract`, `Person` |
| **Property** | Een kenmerk van een concept | `invoice_date: date`, `vendor: ref:Organisation` |
| **Hiërarchie** | Is-a relatie (overerving) | `Invoice` **is-a** `FinancialDocument` **is-a** `Document` |
| **Mixin** | Herbruikbare eigenschap-set | `Trackable` (created_date, modified_date) |

### Inspiratie: BFO (Basic Formal Ontology)

Dit project is geïnspireerd door de **Basic Formal Ontology** (ISO 21838-2), vereenvoudigd voor enterprise gebruik. De L1-laag hangt annotaties als `bfo_equivalent: "Continuant"` aan concepten voor formele interoperabiliteit.

## Het 3-Laags Systeem

```
┌─────────────────────────────────────────────────┐
│              L3: User-Defined                   │  ← Door gebruikers aangemaakt
│  (Aangepaste concepten voor hun domein)         │
├─────────────────────────────────────────────────┤
│              L2: Enterprise                     │  ← Standard bedrijfsconcepten
│  Invoice, Contract, Person, Product, ...        │
│  Georganiseerd in 4 pillars:                    │
│  • Entities  • Artifacts  • Processes  • Domain │
├─────────────────────────────────────────────────┤
│              L1: Foundation                     │  ← Abstracte bouwstenen
│  Thing → Entity → Actor, Object, Place, ...     │
│  Thing → Activity → Process, Task, Event        │
│  + Mixins: Trackable, Auditable, ...            │
└─────────────────────────────────────────────────┘
```

### Pillar-structuur (L2)

| Pillar | YAML-bestand | Beantwoordt | Voorbeelden |
|--------|-------------|-------------|-------------|
| **Entities** | `entities.yaml` | *Wie is betrokken?* | Person, Organisation, Vendor |
| **Artifacts** | `artifacts.yaml` | *Wat is geproduceerd?* | Invoice, Contract, Report |
| **Processes** | `processes.yaml` | *Wat gebeurt er?* | BusinessProcess, Approval |
| **Domain Knowledge** | `domain-knowledge.yaml` | *Wat weten we?* | BusinessDomain, KnowledgeArea |

## YAML Definitieformaat

### Concept Definitie

```yaml
- id: "Invoice"
  layer: L2
  inherits: "FinancialDocument"    # Overerving
  abstract: false                   # Kan als classificatiedoel dienen
  label: "Invoice"
  description: >
    A demand for payment for goods or services delivered.
  synonyms:                         # Voor hint-matching
    - "bill"
    - "factuur"
    - "Rechnung"
  mixins: []                        # Herbruikbare eigenschap-sets
  properties:                       # Concept-specifieke velden
    - name: "due_date"
      type: "date"
      required: false
      description: "Payment due date"
    - name: "vendor"
      type: "ref:Vendor"            # Referentie naar ander concept
      required: true
    - name: "line_items"
      type: "InvoiceLineItem[]"     # Embedded type array
      required: false
  relationships:
    - name: "paidVia"
      target: "TransactionRecord"
      cardinality: "0..*"
  extraction_template:              # Stuurt classificatie
    classification_hints:
      - "invoice"
      - "factuur"
    file_patterns:
      - "**/invoices/**"
      - "**/facturen/**"
```

### Mixin Definitie

Mixins zijn herbruikbare eigenschap-bundels — vergelijkbaar met interfaces in OO-design:

```yaml
mixins:
  - id: "Trackable"
    label: "Trackable"
    description: >
      Tracks creation and modification metadata.
    properties:
      - name: "created_date"
        type: "datetime"
        required: true
      - name: "modified_date"
        type: "datetime"
        required: false
      - name: "version"
        type: "integer"
        default: 1
```

Als een concept `mixins: ["Trackable"]` declareert, krijgt het automatisch alle Trackable-properties.

### Embedded Types

Embedded types zijn waarde-objecten zonder eigen identiteit:

```yaml
- id: "InvoiceLineItem"
  description: "A single line item on an invoice"
  applies_to: ["Invoice", "CreditNote"]
  properties:
    - name: "description"
      type: "string"
      required: true
    - name: "quantity"
      type: "decimal"
    - name: "unit_price"
      type: "decimal"
    - name: "line_total"
      type: "decimal"
```

## De OntologyCompiler

De `OntologyCompiler` wordt **eenmaal bij applicatiestart** uitgevoerd via de FastAPI lifespan. Hij leest alle YAML-bestanden en slaat de geparseerde concepten op in de database.

### Compilatieproces

```
Applicatiestart (lifespan)
    │
    ▼
OntologyCompiler.compile()
    │
    ├── 1. Snapshot L3+ concepten (user-created) → bewaren
    ├── 2. Clear bestaande compilatie
    ├── 3. Parse L1 foundation.yaml → save_concept() per concept
    ├── 4. Parse L1 mixins.yaml → save_mixin() per mixin
    ├── 5. Parse L2 yaml bestanden (entities, artifacts, processes, domain-knowledge)
    │       └── Pillar mapping: bestandsnaam → pillar naam
    ├── 6. Parse embedded-types.yaml → save_embedded_type()
    └── 7. Restore L3+ concepten (behoud gebruikerscreaties)
```

### Code: YAML → Domeinentiteit

```python
def _build_concept(self, entry: dict, layer: str, pillar: str | None) -> OntologyConcept:
    """Map een YAML dict naar een OntologyConcept domeinentiteit."""
    properties = [
        ConceptProperty(
            name=p["name"],
            type=p.get("type", "string"),
            required=p.get("required", False),
            description=p.get("description", ""),
        )
        for p in entry.get("properties", [])
    ]

    extraction_template = None
    et_data = entry.get("extraction_template")
    if et_data:
        extraction_template = ExtractionTemplate(
            classification_hints=et_data.get("classification_hints", []),
            file_patterns=et_data.get("file_patterns", []),
        )

    return OntologyConcept(
        id=entry["id"],
        layer=layer,
        label=entry.get("label", entry["id"]),
        inherits=entry.get("inherits"),
        abstract=entry.get("abstract", False),
        synonyms=entry.get("synonyms", []),
        mixins=entry.get("mixins", []),
        properties=properties,
        extraction_template=extraction_template,
        pillar=pillar,
    )
```

### L3-behoud bij hercompilatie

Een cruciaal ontwerpbesluit: **L3-concepten overleven hercompilatie**.

```python
async def compile(self) -> int:
    # Snapshot user-created L3+ concepten voordat we alles wissen
    all_existing = await self._repo.get_all_concepts()
    existing_l3 = [c for c in all_existing if c.layer not in ("L1", "L2")]

    # Wis en herbouw L1 + L2
    await self._repo.clear_all()
    # ... parse L1 + L2 ...

    # Herstel L3+ concepten
    for concept in existing_l3:
        await self._repo.save_concept(concept)
```

## De OntologyService

De `OntologyService` biedt de business-operaties op het gecompileerde ontologie-systeem.

### Property Resolution met Overerving

Eén van de krachtigste features: **resolved properties** combineren eigen velden met die van ouders en mixins:

```python
async def get_resolved_properties(self, concept_id: str) -> list[ConceptProperty]:
    """Verzamel alle properties: voorouders + mixins + eigen.

    Resolutievolgorde per concept in de keten (root → kind):
      1. Mixin properties (in declaratievolgorde)
      2. Concept's eigen properties
    Kind-properties overschrijven ouder-properties met dezelfde naam.
    """
```

**Voorbeeld**: voor een `Invoice` produceert dit:

| Bron | Properties |
|------|-----------|
| `Thing` (L1) | `label`, `description`, `synonyms` |
| `Document` (L1) + Trackable mixin | `document_date`, `document_type`, `created_date`, `modified_date` |
| `FinancialDocument` (L2) + Auditable, HasMonetaryValue | `document_number`, `amount`, `currency`, `audit_trail` |
| `Invoice` (L2) | `due_date`, `vendor`, `tax_amount`, `line_items` |

### Tree-building voor UI

```python
async def get_tree(self) -> list[dict]:
    """Bouw de hiërarchie voor weergave in de UI.

    Returns: [{id, label, layer, abstract, children: [...]}]
    """
    concepts = await self._repo.get_all_concepts()
    by_parent = {}
    roots = []

    for concept in concepts:
        if concept.inherits:
            by_parent.setdefault(concept.inherits, []).append(concept)
        else:
            roots.append(concept)

    def _build_node(concept):
        return {
            "id": concept.id,
            "label": concept.label,
            "layer": concept.layer,
            "abstract": concept.abstract,
            "children": [_build_node(c) for c in by_parent.get(concept.id, [])],
        }

    return [_build_node(r) for r in roots]
```

## Hoe de Ontologie de LLM Stuurt

De ontologie is niet alleen opslag — het **genereert de prompts** die het LLM vertellen wat het moet doen:

```
Ontologie                      LLM Prompt
─────────                      ──────────
extraction_template             "Classificeer dit document.
  .classification_hints    →     Beschikbare types: Invoice (factuur, bill),
  .synonyms                      Contract (overeenkomst), ..."

properties                      "Extraheer de volgende velden:
  [{name, type, required,   →    - invoice_date (date, verplicht)
    description}]                 - vendor (referentie, verplicht)
                                  - due_date (date, optioneel)"
```

## Leerpunten

1. **Ontologieën als configuratie**: In plaats van classificatieregels te hardcoden, definieer je ze als data (YAML). Dit maakt het systeem configureerbaar zonder code-wijzigingen.
2. **Overerving in ontologieën**: Net als in OO-programmeren erft een kind alle eigenschappen van zijn ouders. `Invoice` erft automatisch `document_date` van `Document`.
3. **Mixins als horizontale hergebruik**: Properties die meerdere concepten delen (created_date, amount) worden als mixins gedefinieerd — vergelijkbaar met interfaces of traits.
4. **Compilatie-patroon**: De ontologie wordt **eenmalig** gecompileerd bij start, niet bij elke request. Dit is efficiënt en voorkomt parsing-overhead.
5. **L3-preservatie**: Gebruikerscreaties overleven hercompilatie van L1/L2 — cruciaal voor een systeem waar de base ontology updates krijgt terwijl gebruikers hun eigen concepten beheren.
