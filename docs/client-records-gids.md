# Client Records — Generieke Data Opslag Service

## Overzicht

De **Client Records** service biedt een generiek CRUD-mechanisme waarmee de frontend willekeurige JSON-data kan opslaan in de backend database. Dit is bedoeld voor data die **niet** door de backend verwerkt hoeft te worden, zoals thema-instellingen, gebruikersvoorkeuren of module-configuratie.

### Kernconcepten

| Veld | Type | Beschrijving |
|------|------|-------------|
| `id` | UUID (string) | Unieke identifier, automatisch gegenereerd |
| `module_name` | string (max 100) | Naam van de module, bijv. `"setup"` |
| `entity_type` | string (max 100) | Type record, bijv. `"theme-colors"` |
| `data` | JSON object | Willekeurige JSON-payload |
| `parent_id` | UUID (optioneel) | Verwijzing naar een ouder-record voor hiërarchische relaties |
| `user_id` | string (optioneel) | Gebruikers-ID, voorbereid voor multi-user ondersteuning |
| `created_at` | datetime (UTC) | Aanmaaktijdstip |
| `updated_at` | datetime (UTC) | Laatst bijgewerkt |

---

## Architectuur

De service volgt de standaard **Clean Architecture** van het project, verdeeld over vier lagen:

```
┌─────────────────────────────────────────────────────┐
│  Presentation: FastAPI endpoints (client_records.py) │
├─────────────────────────────────────────────────────┤
│  Application: Service + Schemas + Repository Port   │
├─────────────────────────────────────────────────────┤
│  Domain: ClientRecord entity (pure Python)          │
├─────────────────────────────────────────────────────┤
│  Infrastructure: SQLAlchemy model + repository      │
│                  + dependency injection             │
└─────────────────────────────────────────────────────┘
```

### Bestanden

| Laag | Bestand | Beschrijving |
|------|---------|-------------|
| **Domain** | `domain/entities/client_record.py` | Dataclass met UUID, `update()` methode |
| **Application** | `application/interfaces/client_record_repository.py` | Abstract repository port (ABC) |
| **Application** | `application/schemas/client_record.py` | Pydantic v2 DTO's (Create, Update, Response) |
| **Application** | `application/services/client_record_service.py` | Use case orchestratie met DI |
| **Infrastructure** | `infrastructure/database/models/client_record.py` | SQLAlchemy ORM met composite index |
| **Infrastructure** | `infrastructure/database/repositories/client_record_repository.py` | Concrete SQLAlchemy implementatie |
| **Presentation** | `presentation/api/v1/endpoints/client_records.py` | REST endpoints |
| **DI** | `infrastructure/dependencies.py` | Factory: `get_client_record_service` |

---

## API Referentie

Alle endpoints zijn beschikbaar onder `/api/v1/client-records`.

### Records Ophalen (Lijst)

```
GET /api/v1/client-records
```

**Query Parameters:**

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `module_name` | string | Filter op module naam |
| `entity_type` | string | Filter op entity type |
| `parent_id` | string | Filter op ouder-record |
| `user_id` | string | Filter op gebruiker |
| `skip` | int | Offset voor paginatie (standaard: 0) |
| `limit` | int | Maximum resultaten (standaard: 100, max: 500) |

**Voorbeeld:**

```bash
# Alle theme-colors records voor de setup module
curl "http://localhost:8020/api/v1/client-records?module_name=setup&entity_type=theme-colors"
```

**Response (200):**

```json
[
  {
    "id": "27826b6a-f66c-43b3-babe-4170f99daf43",
    "module_name": "setup",
    "entity_type": "theme-colors",
    "data": { "background": "#C03232", "foreground": "#0A0A0A" },
    "parent_id": null,
    "user_id": null,
    "created_at": "2026-02-13T11:23:31.078424Z",
    "updated_at": "2026-02-13T11:23:31.078427Z"
  }
]
```

### Record Ophalen (Enkel)

```
GET /api/v1/client-records/{record_id}
```

**Response:** `200` met record, of `404` als niet gevonden.

### Record Aanmaken

```
POST /api/v1/client-records
```

**Request Body:**

```json
{
  "module_name": "setup",
  "entity_type": "theme-colors",
  "data": {
    "light": { "background": "#FFFFFF", "primary": "#171717" },
    "dark": { "background": "#0A0A0A", "primary": "#E5E5E5" }
  },
  "parent_id": null,
  "user_id": null
}
```

**Response:** `201 Created` met het volledige record inclusief gegenereerde `id` en timestamps.

### Record Bijwerken

```
PUT /api/v1/client-records/{record_id}
```

**Request Body:**

```json
{
  "data": {
    "light": { "background": "#F0F0F0", "primary": "#333333" }
  }
}
```

**Response:** `200` met het bijgewerkte record (nieuwe `updated_at`), of `404`.

### Record Verwijderen

```
DELETE /api/v1/client-records/{record_id}
```

**Response:** `204 No Content` bij succes, of `404`.

---

## Theoretische Achtergrond

### Waarom een Generieke Service?

In plaats van voor elk type frontend-data (thema's, voorkeuren, layout-configuratie) een apart endpoint en databasetabel aan te maken, biedt een generieke opslag de volgende voordelen:

1. **Snelle feature-ontwikkeling** — Nieuwe datatypes vereisen geen backend-wijzigingen
2. **Scheiding van verantwoordelijkheden** — De backend hoeft de data niet te interpreteren
3. **Flexibiliteit** — Het JSON `data`-veld accepteert elke structuur die de frontend nodig heeft

### Scoping: module_name + entity_type

Het combinatiepatroon `module_name` + `entity_type` fungeert als een **logische namespace**. Dit voorkomt conflicten tussen modules en maakt het mogelijk om alle data voor een specifieke module of datatype op te halen.

```
module_name = "setup"     + entity_type = "theme-colors"   → thema-instellingen
module_name = "setup"     + entity_type = "preferences"    → gebruikersvoorkeuren
module_name = "dashboard" + entity_type = "layout"         → dashboard layout
```

### Parent/Child Relaties

Het optionele `parent_id`-veld maakt het mogelijk om hiërarchische datastructuren op te slaan. Bijvoorbeeld:

```
📁 Project (parent_id: null)
├── 📄 Configuratie (parent_id: project.id)
└── 📄 Instellingen (parent_id: project.id)
```

### UUID als Primary Key

In tegenstelling tot de `Article` entity (die auto-increment integers gebruikt), gebruikt `ClientRecord` UUID's als primary key. Dit is bewust gekozen omdat:

- De frontend records kan refereren voordat ze zijn opgeslagen (optimistic updates)
- Records uniek identificeerbaar zijn zonder sequentiële nummering
- Het voorbereid is op toekomstige gedistribueerde systemen

---

## Frontend Integratie Voorbeeld

Hieronder een voorbeeld van hoe de frontend de service kan gebruiken voor thema-opslag:

```typescript
const API_BASE = '/api/v1/client-records';

// Thema-kleuren opslaan
async function saveThemeColors(colors: ThemeColors): Promise<ClientRecord> {
  const response = await fetch(API_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      module_name: 'setup',
      entity_type: 'theme-colors',
      data: colors,
    }),
  });
  return response.json();
}

// Thema-kleuren ophalen
async function loadThemeColors(): Promise<ThemeColors | null> {
  const response = await fetch(
    `${API_BASE}?module_name=setup&entity_type=theme-colors&limit=1`
  );
  const records = await response.json();
  return records.length > 0 ? records[0].data : null;
}

// Record bijwerken
async function updateThemeColors(
  recordId: string,
  colors: ThemeColors
): Promise<ClientRecord> {
  const response = await fetch(`${API_BASE}/${recordId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data: colors }),
  });
  return response.json();
}
```

---

## Database Indexen

De `client_records` tabel bevat de volgende indexen voor optimale query-prestaties:

| Index | Kolommen | Doel |
|-------|----------|------|
| `ix_client_records_scope` | `module_name`, `entity_type` | Snelle filtering op scope |
| `ix_client_records_parent` | `parent_id` | Snel ophalen van child-records |
| `ix_client_records_user` | `user_id` | Snelle filtering op gebruiker |

---

## Swagger UI

De volledige API-documentatie met interactieve test-mogelijkheid is beschikbaar op:

```
http://localhost:8020/docs
```

Navigeer naar de sectie **Client Records** om alle endpoints te testen.
