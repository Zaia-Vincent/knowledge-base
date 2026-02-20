# Opslag Bronnen — Fysieke Opslagstructuur

Dit document beschrijft de fysieke opslagstructuur van data-bronnen (bestanden en website-captures) in de Knowledge Base applicatie.

## Overzicht

Alle opgeslagen bestanden bevinden zich onder de configureerbare `upload_dir` (standaard: `backend/uploads/`). De opslag is opgedeeld in twee categorieën:

```
uploads/
├── files/                                    ← Geüploade bestanden
│   ├── factuur_molcon_20260219_091505.pdf
│   ├── contract_abc_20260218_143022.docx
│   └── ...
└── websites/                                 ← Website screenshots
    ├── example.com/
    │   ├── about_20260219_100812.png
    │   └── products_overview_20260219_100845.png
    ├── docs.python.org/
    │   └── 3_library_asyncio_20260219_102030.png
    └── ...
```

## Naamgeving Conventies

### Bestanden (`files/`)

Geüploade bestanden worden opgeslagen met een datetime-stempel in de bestandsnaam:

```
<gesanitiseerde_naam>_<JJJJMMDD_UUmmss>.<extensie>
```

**Voorbeeld:**  
`Factuur Molcon 2024.pdf` → `Factuur_Molcon_2024_20260219_091505.pdf`

**Sanitisatie-regels:**
- Speciale tekens (spaties, punten, etc.) worden vervangen door underscores (`_`)
- De naam wordt afgekapt op 80 tekens
- De datetime-stempel is altijd in UTC

### Website Captures (`websites/`)

Screenshots van webpagina's worden opgeslagen in een submap per domein:

```
websites/<domein>/<pad_slug>_<JJJJMMDD_UUmmss>.png
```

**Voorbeelden:**

| URL | Opslagpad |
|-----|-----------|
| `https://example.com/about` | `websites/example.com/about_20260219_100812.png` |
| `https://example.com/products/overview` | `websites/example.com/products_overview_20260219_100812.png` |
| `https://docs.python.org/3/library/asyncio` | `websites/docs.python.org/3_library_asyncio_20260219_102030.png` |
| `https://example.com/` (geen pad) | `websites/example.com/index_20260219_100812.png` |

**Domein-extractie:**
- Het domein wordt rechtstreeks uit de URL gehaald (inclusief subdomeinen)
- Ongeldige tekens worden vervangen door underscores

**Pad-slugificatie:**
- Alle segmenten van het URL-pad worden samengevoegd met underscores
- Als er geen pad is, wordt de paginatitel of `index` gebruikt als fallback

## Technische Achtergrond

### Architectuur

De opslaglogica bevindt zich in de `LocalFileStorage` klasse (`backend/app/infrastructure/storage/local_file_storage.py`). Deze klasse biedt drie hoofd-methoden:

| Methode | Doel | Opslaglocatie |
|---------|------|---------------|
| `store_file()` | Opslaan van geüploade bestanden | `files/<naam>_<stempel>.<ext>` |
| `store_website_capture()` | Opslaan van website screenshots | `websites/<domein>/<slug>_<stempel>.png` |
| `store_zip()` | Uitpakken en opslaan van ZIP-archieven | Delegeert naar `store_file()` |

### StoredFile Dataclass

Elke opslagoperatie retourneert een `StoredFile` object:

```python
@dataclass
class StoredFile:
    stored_path: str      # Volledig pad naar het opgeslagen bestand
    filename: str         # Bestandsnaam met datetime-stempel
    original_path: str    # Oorspronkelijke bestandsnaam of URL
    file_size: int        # Bestandsgrootte in bytes
    mime_type: str        # MIME-type (bijv. "application/pdf")
```

### Database Referentie

Het `stored_path` wordt opgeslagen in de `resources` tabel (kolom `stored_path`) en is beschikbaar via de API in zowel de summary- als detail-endpoints:

```json
{
    "id": "abc-123",
    "filename": "factuur_molcon_20260219_091505.pdf",
    "stored_path": "uploads/files/factuur_molcon_20260219_091505.pdf",
    "original_path": "Factuur Molcon 2024.pdf",
    "..."
}
```

## API Endpoints

### Bronbestand bekijken (inline)

```
GET /api/v1/resources/{resource_id}/view
```

Serveert het opgeslagen bestand inline in de browser. Geschikt voor het bekijken van PDF's, afbeeldingen en andere browser-compatibele formaten.

**Response:** Het bestand zelf met `Content-Disposition: inline`

### Bronbestand downloaden

```
GET /api/v1/resources/{resource_id}/download
```

Download het opgeslagen bestand als attachment.

**Response:** Het bestand met `Content-Disposition: attachment`

## Frontend Integratie

De Resources-pagina toont een **"View"** knop in het detailpaneel wanneer een resource een `stored_path` heeft. Deze knop opent het bestand in een nieuw browsertabblad via het `/view` endpoint.

Daarnaast wordt het `stored_path` getoond in de "General" sectie van het detailpaneel, zodat ontwikkelaars en beheerders het fysieke pad van het bestand kunnen inzien.
