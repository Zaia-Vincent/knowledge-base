# API Referentie

Documentatie van alle beschikbare API endpoints in het Knowledge Base project.

## Base URL

- **Ontwikkeling**: `http://localhost:8000/api/v1`
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Endpoints

### Health Check

#### `GET /api/v1/health`

Controleert de status van de backend applicatie.

**Response** `200 OK`:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "development"
}
```

---

### Articles

#### `GET /api/v1/articles`

Haalt een gepagineerde lijst van artikelen op.

**Query Parameters:**

| Parameter | Type | Default | Beschrijving |
|-----------|------|---------|-------------|
| `skip` | `int` | `0` | Aantal over te slaan resultaten |
| `limit` | `int` | `100` | Maximum aantal resultaten |

**Response** `200 OK`:
```json
[
  {
    "id": 1,
    "title": "Mijn Eerste Artikel",
    "content": "De inhoud van het artikel...",
    "created_at": "2026-02-13T09:00:00Z",
    "updated_at": "2026-02-13T09:00:00Z"
  }
]
```

---

#### `GET /api/v1/articles/{article_id}`

Haalt een enkel artikel op via ID.

**Path Parameters:**

| Parameter | Type | Beschrijving |
|-----------|------|-------------|
| `article_id` | `int` | Het unieke ID van het artikel |

**Response** `200 OK`:
```json
{
  "id": 1,
  "title": "Mijn Eerste Artikel",
  "content": "De inhoud van het artikel...",
  "created_at": "2026-02-13T09:00:00Z",
  "updated_at": "2026-02-13T09:00:00Z"
}
```

**Response** `404 Not Found`:
```json
{
  "detail": "Article with id '999' not found"
}
```

---

#### `POST /api/v1/articles`

Maakt een nieuw artikel aan.

**Request Body:**
```json
{
  "title": "Nieuw Artikel",
  "content": "De inhoud van het nieuwe artikel..."
}
```

| Veld | Type | Verplicht | Validatie |
|------|------|-----------|-----------|
| `title` | `string` | ✅ | 1–255 karakters |
| `content` | `string` | ✅ | Minimaal 1 karakter |

**Response** `201 Created`:
```json
{
  "id": 2,
  "title": "Nieuw Artikel",
  "content": "De inhoud van het nieuwe artikel...",
  "created_at": "2026-02-13T10:00:00Z",
  "updated_at": "2026-02-13T10:00:00Z"
}
```

**Response** `422 Unprocessable Entity` (validatie fout):
```json
{
  "detail": [
    {
      "loc": ["body", "title"],
      "msg": "String should have at least 1 character",
      "type": "string_too_short"
    }
  ]
}
```

---

#### `PUT /api/v1/articles/{article_id}`

Werkt een bestaand artikel bij. Alle velden zijn optioneel.

**Request Body:**
```json
{
  "title": "Bijgewerkte Titel",
  "content": "Nieuwe inhoud"
}
```

| Veld | Type | Verplicht | Validatie |
|------|------|-----------|-----------|
| `title` | `string` | ❌ | 1–255 karakters |
| `content` | `string` | ❌ | Minimaal 1 karakter |

**Response** `200 OK`: Bijgewerkt artikel object.

**Response** `404 Not Found`: Artikel niet gevonden.

---

#### `DELETE /api/v1/articles/{article_id}`

Verwijdert een artikel via ID.

**Response** `204 No Content`: Artikel succesvol verwijderd.

**Response** `404 Not Found`: Artikel niet gevonden.

---

## Foutafhandeling

Alle foutresponses volgen een consistent formaat:

| HTTP Status | Betekenis |
|-------------|-----------|
| `200` | Succesvol |
| `201` | Succesvol aangemaakt |
| `204` | Succesvol verwijderd (geen body) |
| `404` | Resource niet gevonden |
| `422` | Validatie fout |
| `500` | Interne server fout |

## Voorbeeld met `curl`

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Alle artikelen ophalen
curl http://localhost:8000/api/v1/articles

# Artikel aanmaken
curl -X POST http://localhost:8000/api/v1/articles \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "content": "Inhoud"}'

# Artikel bijwerken
curl -X PUT http://localhost:8000/api/v1/articles/1 \
  -H "Content-Type: application/json" \
  -d '{"title": "Nieuwe Titel"}'

# Artikel verwijderen
curl -X DELETE http://localhost:8000/api/v1/articles/1

# Chat completion (niet-streaming)
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Hallo!"}]}'

# Chat completion (streaming)
curl -N -X POST http://localhost:8000/api/v1/chat/completions/stream \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Vertel een verhaal"}]}'

# Chat logs ophalen
curl http://localhost:8000/api/v1/chat/logs?limit=10
```

---

### Chat Completions

#### `POST /api/v1/chat/completions`

Voert een niet-streaming chat completion uit via de geconfigureerde AI-provider.

**Request Body:**
```json
{
  "model": "openai/gpt-4o-mini",
  "messages": [
    {"role": "system", "content": "Je bent een behulpzame assistent."},
    {"role": "user", "content": "Wat is Clean Architecture?"}
  ],
  "temperature": 0.7,
  "max_tokens": 500
}
```

| Veld | Type | Verplicht | Beschrijving |
|------|------|-----------|-----------
| `model` | `string` | ✅ | Model ID (bijv. `openai/gpt-4o-mini`) |
| `messages` | `array` | ✅ | Conversatie berichten (min. 1) |
| `temperature` | `float` | ❌ | Sampling temperatuur (0.0–2.0) |
| `max_tokens` | `int` | ❌ | Maximum tokens in de response |

**Multimodaal bericht (tekst + afbeelding):**
```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "Beschrijf deze afbeelding."},
    {"type": "image_url", "image_url": {"url": "https://example.com/foto.jpg"}}
  ]
}
```

**Response** `200 OK`:
```json
{
  "model": "openai/gpt-4o-mini",
  "content": "Clean Architecture is een software-ontwerp...",
  "finish_reason": "stop",
  "provider": "openrouter",
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 120,
    "total_tokens": 135,
    "cost": 0.0002
  },
  "images": []
}
```

---

#### `POST /api/v1/chat/completions/stream`

Voert een streaming chat completion uit via Server-Sent Events (SSE).

**Request Body:** Identiek aan `/chat/completions`.

**Response** `200 OK` (`text/event-stream`):
```
data: {"choices":[{"delta":{"content":"Clean"}}]}

data: {"choices":[{"delta":{"content":" Architecture"}}]}

data: [DONE]
```

---

#### `GET /api/v1/chat/logs`

Haalt gelogde chat completion verzoeken op (meest recente eerst).

**Query Parameters:**

| Parameter | Type | Default | Beschrijving |
|-----------|------|---------|-------------|
| `skip` | `int` | `0` | Aantal over te slaan resultaten |
| `limit` | `int` | `100` | Maximum aantal resultaten |

**Response** `200 OK`:
```json
[
  {
    "id": 1,
    "model": "openai/gpt-4o-mini",
    "provider": "openrouter",
    "prompt_tokens": 15,
    "completion_tokens": 120,
    "total_tokens": 135,
    "cost": 0.0002,
    "duration_ms": 1234,
    "status": "success",
    "error_message": null,
    "created_at": "2026-02-13T11:00:00+00:00"
  }
]
```
