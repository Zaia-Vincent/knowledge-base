# Bestanden Overzicht — Geoptimaliseerde Weergave

## Inleiding

Dit document beschrijft de geoptimaliseerde bestandenweergave van het Knowledge Base platform. De oorspronkelijke platte-lijst weergave is vervangen door een geavanceerde interface met drie kernfunctionaliteiten:

1. **Accordion-groepering** — ouder-kind document relaties
2. **Type-filtering** — filteren op beschikbare documenttypen
3. **Inline detailpaneel** — geformateerde en ruwe metadataweergave

---

## Architectuur

### Backend API Wijzigingen

Het `ProcessedFileSummarySchema` is uitgebreid met twee extra velden om document-hiërarchie te ondersteunen:

| Veld | Type | Beschrijving |
|------|------|-------------|
| `origin_file_id` | `str \| None` | Verwijzing naar het ouder-document (bijv. het originele PDF-bestand) |
| `page_range` | `str \| None` | Paginabereik binnen het ouder-document (bijv. `"3-5"`) |

### Theoretische achtergrond

Bij het verwerken van samengestelde documenten (bijv. een PDF met meerdere facturen) maakt de backend voor elk sub-document een apart `ProcessedFile` record aan, gekoppeld via `origin_file_id` aan het originele bestand. Dit volgt het **compositie-patroon** (Composite Pattern) uit de Gang of Four design patterns, waarbij een boomstructuur van objecten wordt behandeld als een uniforme hiërarchie.

```
Diverse_Facturen.pdf        ← ouder (origin_file_id = null)
├── Factuur_1.pdf           ← kind (origin_file_id = ouder.id, page_range = "1-2")  
├── Factuur_2.pdf           ← kind (origin_file_id = ouder.id, page_range = "3-4")
└── Factuur_3.pdf           ← kind (origin_file_id = ouder.id, page_range = "5-6")
```

---

## Frontend Implementatie

### 1. Accordion-groepering

De functie `groupFiles()` voert client-side groepering uit op basis van `origin_file_id`:

```typescript
function groupFiles(files: ProcessedFileSummary[]): FileGroup[] {
    // 1. Maak een lookup-map van alle bestanden op ID
    // 2. Identificeer kinderen (origin_file_id !== null)
    // 3. Groepeer kinderen onder hun ouder
    // 4. Niet-kind bestanden worden de hoofdrij in de accordion
}
```

**Gedrag:**
- Bestanden mét kinderen → klikbare accordion met chevron
- Bestanden zonder kinderen → gewone tabelrij
- Kindrijen worden ingesprongen weergegeven met `pl-12` padding
- Accordion expandeert automatisch als een kind-document is geselecteerd

### 2. Type Filter

De type-filter is geïmplementeerd als horizontale "pills" boven de tabel:

```typescript
// Afleiden van beschikbare types uit de geladen bestanden
const distinctTypes = useMemo(() => {
    const types = new Set<string>();
    for (const f of files) {
        if (f.classification_concept_id) {
            types.add(f.classification_concept_id);
        }
    }
    return Array.from(types).sort();
}, [files]);
```

De filter combineert met de bestaande tekst-zoekfunctie:

1. **Tekstfilter**: zoekt in bestandsnaam en classificatie
2. **Typefilter**: filtert op exacte `classification_concept_id`
3. Resultaten worden gegroepeerd ná filtering

### 3. Detailpaneel met Ruwe/Geformateerde Weergave

Het detailpaneel maakt gebruik van `ResizablePanelGroup` (shadcn/ui) met een standaard 55/45 verdeling:

```
┌────────────────────────────┬──────────────────────────┐
│                            │                          │
│   Bestanden tabel (55%)    │   Detail paneel (45%)    │
│                            │                          │
│   - Accordion groepen      │   - Bestandsinformatie   │
│   - Type filter pills      │   - Classificatie        │
│   - Zoekbalk               │   - Metadata (formatted  │
│                            │     of raw modus)        │
│                            │   - Samenvatting         │
│                            │   - Tekstafdruk          │
│                            │                          │
└────────────────────────────┴──────────────────────────┘
```

#### Geformateerde Modus

De geformateerde modus haalt de ontologie-conceptdefinitie op via `ontologyApi.getConcept()` om property-type informatie te verkrijgen:

| Property Type | Weergave |
|--------------|----------|
| `date` | Nederlandse datumnotatie (`nl-NL`) |
| `number` / `decimal` | Geformatteerd getal met locale |
| `enum` / `boolean` | Badge component |
| Arrays (embedded types) | Geneste tabel met key-value paren |
| `string` (standaard) | Platte tekst |

Elke metadata-veld toont ook het **vertrouwenspercentage** (confidence score) met kleurcodering:
- ≥ 80%: groen
- ≥ 50%: oranje  
- < 50%: rood

#### Ruwe Modus

Toont de volledige metadata als een JSON code block:

```typescript
<pre className="font-mono">
    {JSON.stringify(file.metadata, null, 2)}
</pre>
```

---

## Voorbeeldgebruik

### Scenario: Verwerking van samengestelde PDF

1. **Upload**: Gebruiker sleept `Diverse_Facturen.pdf` naar de uploadzone
2. **Verwerking**: Backend detecteert 3 facturen → maakt 3 kind-documenten + 1 ouder
3. **Weergave**: Ouder-document toont "4 documents" badge met accordion-chevron
4. **Filteren**: Gebruiker klikt op "Invoice" pill → alleen facturen zichtbaar
5. **Detail**: Klik op kind-document → detailpaneel opent met geformateerde factuurgegevens

### Scenario: Type filtering

```
Files weergave:
┌─────────────────────────────────────────────────────────────┐
│ Type: [All] [Document] [Invoice]                            │
│                                                             │
│ ▶ Diverse_Facturen.pdf    Done  Invoice   95%  1.2 MB       │
│   Bijdrage per band.pdf   Done  Document  87%  450 KB       │
│ ▶ Factuur_Molcon.pdf      Done  Invoice   92%  890 KB       │
└─────────────────────────────────────────────────────────────┘

Na klikken op [Invoice]:
┌─────────────────────────────────────────────────────────────┐
│ Type: [All] [Document] [Invoice ✓]                          │
│                                                             │
│ ▶ Diverse_Facturen.pdf    Done  Invoice   95%  1.2 MB       │
│ ▶ Factuur_Molcon.pdf      Done  Invoice   92%  890 KB       │
└─────────────────────────────────────────────────────────────┘
```

---

## Betrokken Bestanden

| Bestand | Wijziging |
|---------|-----------|
| `backend/app/application/schemas/files.py` | Schema uitgebreid met `origin_file_id`, `page_range` |
| `backend/app/presentation/api/v1/files_controller.py` | `_to_summary` mapper aangepast |
| `frontend/src/types/files.ts` | TypeScript interface uitgebreid |
| `frontend/src/pages/FilesPage.tsx` | Volledige herschrijving met accordion, filter, detailpaneel |
