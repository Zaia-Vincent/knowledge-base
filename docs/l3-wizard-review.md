# L3 Wizard — Code Review & Verbeteringssuggesties

> **Scope**: Volledige stack review van de L3 Concept Wizard — frontend `CreateConceptDialog.tsx`, backend `ontology_type_assistant_service.py`, testen, controller en dependency injection.

---

## Samenvatting

De L3 wizard is functioneel sterk: AI-geassisteerde conceptgeneratie met fallback, smart merging, inheritance-conflictdetectie en referentieverrijking. Echter, zowel frontend als backend vertonen tekenen van **monolithische groei** en missen op meerdere vlakken best practices. Hieronder volgt een gestructureerde analyse per laag met concrete verbetervoorstellen.

---

## 1. Frontend — `CreateConceptDialog.tsx` (1356 regels)

### 1.1 ❌ Monolithisch component — Schending Single Responsibility

Het volledige wizard-component bevat **30+ `useState`-hooks**, 3 render-functies, 15+ event handlers, merge-logica, en zoekfunctionaliteit — allemaal in één bestand van 1356 regels.

**Best practice (2025)**: componenten splitsen bij >200 regels. Gebruik het **Compound Component** of **Step Component** patroon.

**Aanbeveling**: Decomponeer naar afzonderlijke bestanden:

```
components/wizards/create-concept/
├── CreateConceptDialog.tsx        # Orkestrator (~150 regels)
├── hooks/
│   ├── useWizardFormState.ts      # useReducer-gebaseerde state
│   ├── useParentSearch.ts         # Debounced parent search + details
│   ├── useSourceConcept.ts        # Blueprint source zoek- en importlogica
│   └── useAiSuggestion.ts        # AI draft generatie staat en handlers
├── steps/
│   ├── AiBriefStep.tsx            # Stap 1: AI brief
│   ├── DetailsStep.tsx            # Stap 2: velden, relaties, hints
│   └── ReviewStep.tsx             # Stap 3: review en submit
├── components/
│   ├── TagListInput.tsx           # Herbruikbaar: synoniemen/hints/patronen
│   ├── PropertyEditor.tsx         # Eigenschap-rij editor
│   ├── RelationshipEditor.tsx     # Relatie-rij editor
│   └── ConceptSearchDropdown.tsx  # Herbruikbaar zoek-dropdown
└── utils/
    ├── mergeHelpers.ts            # mergeProperties, mergeRelationships
    └── formatters.ts              # toKebabCase, dedupeStrings
```

### 1.2 ❌ `useState` explosie → `useReducer`

Met 30+ individuele `useState`-hooks is state management oncontroleerbaar. De reset-functie (regels 268–307) moet 35 individuele setters aanroepen — een duidelijk teken dat `useReducer` nodig is.

**Voorbeeld verbetering**:

```typescript
type WizardState = {
  step: number;
  label: string;
  id: string;
  idManuallyEdited: boolean;
  inherits: string;
  description: string;
  synonyms: string[];
  properties: CreateConceptPropertyPayload[];
  relationships: CreateConceptRelationshipPayload[];
  hints: string[];
  filePatterns: string[];
  // ... overige velden
};

type WizardAction =
  | { type: 'RESET' }
  | { type: 'SET_FIELD'; field: keyof WizardState; value: any }
  | { type: 'APPLY_AI_SUGGESTION'; suggestion: SuggestOntologyTypeResponse }
  | { type: 'IMPORT_FROM_SOURCE'; source: ConceptDetail }
  | { type: 'ADD_PROPERTY' }
  | { type: 'REMOVE_PROPERTY'; index: number }
  | { type: 'UPDATE_PROPERTY'; index: number; field: string; value: any }
  | { type: 'GO_NEXT' }
  | { type: 'GO_BACK' };
```

**Voordelen**: gecentraliseerde state transitions, één `dispatch({ type: 'RESET' })` in plaats van 35 setters, makkelijker te testen en debuggen.

### 1.3 ⚠️ Herhaald UI-patroon — Tag-input componenten

De patronen voor synoniemen (regels 1035–1065), classificatiehints (1067–1097), bestandspatronen (1099–1129), en AI-referentie-URLs (714–743) zijn vrijwel identiek. Dit is een duidelijke **DRY-schending**.

**Aanbeveling**: Maak een herbruikbaar `<TagListInput>` component:

```tsx
<TagListInput
  label="Synonyms"
  items={synonyms}
  onAdd={(s) => dispatch({ type: 'ADD_SYNONYM', value: s })}
  onRemove={(s) => dispatch({ type: 'REMOVE_SYNONYM', value: s })}
  placeholder="Add synonym…"
/>
```

### 1.4 ⚠️ Dropdown sluit niet bij klik erbuiten

De `showParentDropdown` en `showSourceDropdown` dropdowns worden alleen gesloten bij selectie. Er is geen `onClickOutside` handler — een veelvoorkomende UX-bug.

**Aanbeveling**: Gebruik een `useClickOutside` hook of een `<Popover>` component van shadcn.

### 1.5 ⚠️ Geen form-validatie library

Validatie gebeurt handmatig met `validateStepZero()`. Dit schaalt slecht en mist per-field error messaging.

**Aanbeveling**: Overweeg `react-hook-form` + `zod` voor getypeerde form-validatie met per-field errors. Dit is de React 2025 standaard voor complexe formulieren.

### 1.6 ⚠️ Geen loading states op zoek-results

De debounced zoekfuncties (regels 192–206, 230–244) tonen geen loading-indicator. Bij trage netwerken ziet de gebruiker een leeg dropdown zonder feedback.

### 1.7 ⚠️ Accessibility (a11y) ontbreekt

- Dropdown-opties missen `role="listbox"` en `role="option"`.
- Geen keyboard navigatie (pijltjestoetsen) voor dropdown resultaten.
- `<button>` tags voor badge-verwijdering missen `aria-label`.
- Geen `aria-live` regio voor import/error berichten.

### 1.8 💡 Kleine verbeterpunten

| Item | Probleem | Oplossing |
|------|----------|-----------|
| Lijst-keys | `key={s}` voor synoniemen — problematisch bij duplicate waarden | Gebruik index of `crypto.randomUUID()` |
| Error afhandeling | Catch blocks swallown errors stilletjes (`catch {}`) | Log naar console of toon toast |
| Hardcoded afmetingen | `w-[min(96vw,980px)] h-[min(92vh,860px)]` | Gebruik responsive design tokens |

---

## 2. Backend — `ontology_type_assistant_service.py` (710 regels)

### 2.1 ❌ Untyped return values — dict i.p.v. Pydantic modellen

`suggest_type()` retourneert `dict[str, Any]`. Dit is antipatroon in Clean Architecture en mist:
- Type safety in de controller laag
- Automatische validatie
- IDE autocompletion op response velden
- OpenAPI schema kwaliteit

**Aanbeveling**: Definieer expliciete domein- of response-modellen:

```python
@dataclass
class OntologyTypeSuggestion:
    payload: CreateConceptPayload
    rationale: str
    parent_reasoning: str
    adaptation_tips: list[str]
    warnings: list[str]
    references: list[ReferenceItem]
```

### 2.2 ❌ Hardcoded parent-inferentie heuristiek

De `_resolve_parent()` methode (regels 399–411) bevat hardcoded keyword matching:

```python
if any(k in text for k in ("blog", "article", "post", "news", "whitepaper")):
    if "Document" in by_id:
        return by_id["Document"]
```

Dit is **niet schaalbaar** en vereist code-wijzigingen bij elke ontologie-uitbreiding.

**Aanbeveling**: Verplaats de heuristieken naar een configureerbaar mapping-bestand (YAML/JSON) of gebruik de LLM zelf om de parent te suggereren:

```yaml
parent_inference_rules:
  - keywords: ["blog", "article", "post", "news", "whitepaper"]
    candidates: ["Document", "Report"]
  - keywords: ["email", "message", "chat", "notification"]
    candidates: ["Message", "Email"]
```

### 2.3 ⚠️ HTTP client niet gedeeld — per-request overhead

`_collect_reference_material()` maakt elke aanroep een nieuwe `httpx.AsyncClient`:

```python
async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
```

**Aanbeveling**: Injecteer een gedeelde `httpx.AsyncClient` via de constructor (lifecycle management via FastAPI lifespan). Dit volgt de resource management standaard uit de Foundry-architectuur.

### 2.4 ⚠️ Fragiele JSON-extractie

`_extract_json()` gebruikt eenvoudige string-matching met `find("{")` / `rfind("}")`. Dit faalt bij:
- Geneste JSON met `{` in string-waarden buiten het root object
- LLM responses met markdown uitleg vóór of na de JSON

**Aanbeveling**: Gebruik een robuustere parser met balanced bracket matching of een JSON-repair library zoals `json-repair`.

### 2.5 ⚠️ HTML scraping naïef

De `_fetch_reference()` methode (regels 480–507) doet rudimentaire HTML-parsing met regex:

```python
cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", body)
cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
```

Dit mist diverse edge cases (CDATA, comments, malformed HTML).

**Aanbeveling**: Gebruik `beautifulsoup4` + `lxml` of een bestaande extractie-library zoals `trafilatura` voor betrouwbaardere content-extractie.

### 2.6 ⚠️ Broad exception catch op LLM failure

```python
except Exception as exc:
    logger.exception("LLM suggestion failed, falling back to deterministic draft")
```

Dit vangt ook `KeyboardInterrupt`, `SystemExit`, en andere niet-LLM-gerelateerde fouten.

**Aanbeveling**: Vang specifieke exceptions:

```python
except (json.JSONDecodeError, httpx.HTTPError, ValueError) as exc:
```

Of definieer een `LLMSuggestionError` als custom exception.

### 2.7 💡 Overige backend verbeterpunten

| Item | Probleem | Oplossing |
|------|----------|-----------|
| Magic numbers | `cleaned[:700]`, `title[:180]`, `max_tokens=2200`, `[:8]`, `[:12]` | Definieer als module-level constanten met beschrijvende namen |
| Prompt template | _SUGGESTION_SYSTEM_PROMPT is een grote inline string | Verplaats naar apart bestand (bijv. `prompts/ontology_suggestion.txt`) |
| `_property_to_dict` / `_relationship_to_dict` | Handmatige dict-constructie van domain objecten | Gebruik `.model_dump()` of `asdict()` als de entities dit ondersteunen |
| `_gather_safe` | Module-level functie die alleen door deze service wordt gebruikt | Maak het een `@staticmethod` of verplaats naar shared utility |

---

## 3. Testing — `test_ontology_type_assistant_service.py` (2 tests)

### 3.1 ❌ Onvoldoende testdekking

Er zijn slechts **2 tests** voor een service van 710 regels met complexe logica:

1. `test_suggest_type_fallback_without_llm` — Fallback pad
2. `test_suggest_type_llm_normalizes_unknown_parent` — Parent normalisatie

**Ontbrekende test-scenario's**:

| Scenario | Belang |
|----------|--------|
| `_resolve_parent` met diverse keyword matches | Hoog — kernlogica |
| `_resolve_parent` zonder matching concepts | Hoog — edge case |
| `_normalize_payload` met corrupte/incomplete LLM output | Kritisch — robuustheid |
| `_normalize_payload` inheritance property filtering | Hoog |
| `_extract_json` met fenced code blocks | Medium |
| `_extract_json` met geneste JSON / malformed input | Medium |
| `_find_similar_concepts` met diverse zoektermen | Medium |
| `suggest_type` met `include_internet_research=True` | Medium |
| `_fetch_reference` met HTTP errors en timeouts | Medium |
| Input validatie (`name` leeg, speciale tekens) | Hoog |
| `_dedupe_*` functies met edge cases | Laag |

**Aanbeveling**: Streef naar ≥80% testdekking. Voeg parameterized tests toe voor `_normalize_payload` en `_resolve_parent`.

### 3.2 ⚠️ Geen frontend tests

Er zijn **geen tests** voor `CreateConceptDialog.tsx`. Voor een 1356-regels component met complexe logica (merge-functies, validatie, AI-integratie) is dit een risico.

**Aanbeveling**: Schrijf unit tests voor de pure utility functies (`mergeProperties`, `mergeRelationships`, `dedupeStrings`, `toKebabCase`) en component tests met React Testing Library voor de wizard-stappen.

---

## 4. Architectuur & Clean Architecture

### 4.1 ⚠️ Frontend logica in page-component

Merge-functies (`mergeProperties`, `mergeRelationships`) en utilities (`toKebabCase`, `dedupeStrings`) staan inline in het page-component. Deze behoren in een aparte utility of domain-laag.

### 4.2 ⚠️ Backend service grenzen

De `OntologyTypeAssistantService` combineert:
- Ontology context ophalen (repository)
- Web scraping (HTTP)
- LLM interactie (chat provider)
- Output normalisatie en validatie
- Parent inferentie heuristiek

Dit zijn meerdere verantwoordelijkheden. Overweeg:
- **Extractie van `ReferenceCollector`**: apart component voor web scraping
- **Extractie van `ParentInferenceStrategy`**: configureerbare parent-selectie

### 4.3 ✅ Positieve observaties

- **Clean DI wiring**: Service dependencies correct geïnjecteerd via FastAPI Depends.
- **Fallback strategie**: Deterministic fallback als LLM niet beschikbaar is — robuust patroon.
- **Inheritance conflict detectie**: Frontend toont waarschuwing bij duplicate property namen.
- **LLM usage logging**: Correct geïntegreerd met `LLMUsageLogger`.
- **Defensive normalisatie**: `_normalize_payload` hardent LLM output grondig.

---

## 5. Prioritering van verbeteringen

| Prioriteit | Verbetering | Impact | Effort |
|------------|-------------|--------|--------|
| 🔴 Hoog | Frontend decomponeren naar sub-componenten | Onderhoud, testbaarheid | Medium |
| 🔴 Hoog | `useState` → `useReducer` met gestructureerde actions | State bugs, reset-logica | Medium |
| 🔴 Hoog | Backend return types naar typed modellen | Type safety, API docs | Laag |
| 🔴 Hoog | Testdekking backend uitbreiden (≥80%) | Betrouwbaarheid | Medium |
| 🟡 Medium | Herbruikbaar `TagListInput` component | DRY, consistentie | Laag |
| 🟡 Medium | Click-outside handler voor dropdowns | UX | Laag |
| 🟡 Medium | Hardcoded parent heuristiek externaliseren | Schaalbaarheid | Laag |
| 🟡 Medium | Gedeelde HTTPX client injecteren | Performance | Laag |
| 🟡 Medium | Frontend unit tests voor utility functies | Kwaliteit | Laag |
| 🟢 Laag | Accessibility verbeteringen | Inclusiviteit | Medium |
| 🟢 Laag | Magic numbers naar named constants | Leesbaarheid | Laag |
| 🟢 Laag | JSON extractie robuuster maken | Edge cases | Laag |
