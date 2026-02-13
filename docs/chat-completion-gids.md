# Chat Completion Gids

Gedetailleerde ontwikkelaarsgids voor de Chat Completion service van het Knowledge Base project. Deze service biedt AI-gestuurde chatfunctionaliteit via **OpenRouter** als standaard provider, met ondersteuning voor meerdere AI-providers, multimodale input/output en kostenregistratie.

## Theoretische Achtergrond

### Chat Completions

Een **chat completion** is het genereren van een antwoord door een AI-model op basis van een conversatiegeschiedenis. Het model ontvangt een reeks berichten (systeem, gebruiker, assistent) en genereert het volgende bericht in de conversatie.

```
Gebruiker: "Wat is Clean Architecture?"
     ↓
  AI Model (via provider)
     ↓
Assistent: "Clean Architecture is een software-architectuur..."
```

### Multi-Provider Architectuur

De service is ontworpen met het **Strategy Pattern**: de `ChatProvider` abstracte interface definieert het contract, en concrete implementaties (adapters) verbinden met specifieke AI-providers.

```
┌─────────────────────────────┐
│   ChatCompletionService     │  ← Applicatielaag (use case)
│   (provider-agnostisch)     │
└────────────┬────────────────┘
             │ ChatProvider interface
     ┌───────┼───────┬───────────┐
     ▼       ▼       ▼           ▼
  OpenRouter  Groq  OpenAI   (toekomstig)
```

Nieuwe providers toevoegen vereist alleen:
1. Een nieuwe klasse die `ChatProvider` implementeert
2. Registratie in de dependency injection (`dependencies.py`)

### Multimodaliteit

Multimodale AI-modellen verwerken meerdere typen input (tekst + afbeeldingen) in één verzoek. De service ondersteunt dit via het OpenAI-compatibele content parts formaat:

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "Wat zie je op deze afbeelding?"},
    {"type": "image_url", "image_url": {"url": "https://example.com/foto.jpg"}}
  ]
}
```

### Server-Sent Events (SSE)

Voor streaming responses gebruikt de service **SSE** — een HTTP-gebaseerd protocol waarmee de server data kan "pushen" naar de client:

```
Client → POST /chat/completions/stream
Server → HTTP 200
         Content-Type: text/event-stream

data: {"choices":[{"delta":{"content":"Het"}}]}

data: {"choices":[{"delta":{"content":" antwoord"}}]}

data: {"choices":[{"delta":{"content":" is..."}}]}

data: [DONE]
```

Elk `data:` bericht is een JSON chunk die incrementeel de response opbouwt.

## Architectuur per Laag

### 1. Domain Layer

| Bestand | Beschrijving |
|---------|-------------|
| `domain/entities/chat_message.py` | `ChatMessage`, `ContentPart`, `TokenUsage`, `ChatCompletionResult` |
| `domain/entities/chat_request_log.py` | `ChatRequestLog` — logs met kosten en timing |
| `domain/exceptions.py` | `ChatProviderError` — provider-agnostieke fout |

### 2. Application Layer

| Bestand | Beschrijving |
|---------|-------------|
| `application/interfaces/chat_provider.py` | `ChatProvider(ABC)` — abstracte interface voor AI-providers |
| `application/interfaces/chat_request_log_repository.py` | `ChatRequestLogRepository(ABC)` — abstracte log opslag |
| `application/schemas/chat.py` | Pydantic v2 DTOs voor requests, responses en logs |
| `application/services/chat_completion_service.py` | `ChatCompletionService` — use case orchestratie |

### 3. Infrastructure Layer

| Bestand | Beschrijving |
|---------|-------------|
| `infrastructure/openrouter/openrouter_client.py` | `OpenRouterClient(ChatProvider)` — httpx-gebaseerde adapter |
| `infrastructure/database/models/chat_request_log.py` | `ChatRequestLogModel` — SQLAlchemy ORM tabel |
| `infrastructure/database/repositories/chat_request_log_repository.py` | Concrete repository implementatie |
| `infrastructure/dependencies.py` | FastAPI DI wiring |

### 4. Presentation Layer

| Bestand | Beschrijving |
|---------|-------------|
| `presentation/api/v1/endpoints/chat.py` | `POST /completions`, `POST /completions/stream`, `GET /logs` |

## Configuratie

### Environment Variabelen

Voeg de volgende variabelen toe aan je `.env` bestand:

```env
OPENROUTER_API_KEY=sk-or-v1-jouw-api-sleutel
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_APP_NAME=Knowledge Base
```

| Variabele | Standaard | Beschrijving |
|-----------|-----------|-------------|
| `OPENROUTER_API_KEY` | `""` | Je OpenRouter API sleutel |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter basis URL |
| `OPENROUTER_APP_NAME` | `Knowledge Base` | App naam voor OpenRouter rankings |

### API Sleutel Verkrijgen

1. Ga naar [openrouter.ai](https://openrouter.ai)
2. Maak een account aan of log in
3. Ga naar **Settings → Keys**
4. Genereer een nieuwe API sleutel

## Code Voorbeelden

### Niet-Streaming Request

```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/v1/chat/completions",
    json={
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Je bent een behulpzame assistent."},
            {"role": "user", "content": "Leg Clean Architecture uit."}
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
)
print(response.json())
```

### Streaming Request

```python
import httpx

with httpx.stream(
    "POST",
    "http://localhost:8000/api/v1/chat/completions/stream",
    json={
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "Vertel een kort verhaal"}]
    }
) as response:
    for line in response.iter_lines():
        if line.startswith("data: "):
            print(line[6:])
```

### Multimodaal Request

```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/v1/chat/completions",
    json={
        "model": "openai/gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Beschrijf deze afbeelding."},
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/foto.jpg"}
                    }
                ]
            }
        ]
    }
)
```

### Logs Ophalen

```bash
curl http://localhost:8000/api/v1/chat/logs?limit=10
```

## Kosten Logging

Elke chat completion request wordt automatisch gelogd in de `chat_request_logs` tabel:

| Kolom | Type | Beschrijving |
|-------|------|-------------|
| `model` | `VARCHAR(255)` | Gebruikt model (bijv. `openai/gpt-4o-mini`) |
| `provider` | `VARCHAR(100)` | Provider naam (bijv. `openrouter`) |
| `prompt_tokens` | `INTEGER` | Aantal input tokens |
| `completion_tokens` | `INTEGER` | Aantal output tokens |
| `total_tokens` | `INTEGER` | Totaal tokens |
| `cost` | `FLOAT` | Kosten in USD (indien beschikbaar) |
| `duration_ms` | `INTEGER` | Verwerkingstijd in milliseconden |
| `status` | `VARCHAR(20)` | `success` of `error` |
| `error_message` | `TEXT` | Foutmelding bij fouten |
| `created_at` | `DATETIME` | Tijdstip van het verzoek |

## Nieuwe Provider Toevoegen

Om een nieuwe AI-provider toe te voegen (bijv. Groq):

### Stap 1: Implementeer de Interface

```python
# infrastructure/groq/groq_client.py
from app.application.interfaces import ChatProvider

class GroqClient(ChatProvider):
    @property
    def provider_name(self) -> str:
        return "groq"

    async def complete(self, messages, model, **kwargs):
        # Implementeer Groq API aanroep
        ...

    async def stream(self, messages, model, **kwargs):
        # Implementeer Groq SSE stream
        ...
```

### Stap 2: Voeg DI Factory Toe

```python
# infrastructure/dependencies.py
async def get_groq_chat_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[ChatCompletionService, None]:
    provider = GroqClient(api_key=settings.groq_api_key)
    log_repository = SQLAlchemyChatRequestLogRepository(session)
    yield ChatCompletionService(provider=provider, log_repository=log_repository)
```

### Stap 3: Registreer de Route

Je kunt de provider selecteren via de endpoint configuratie, of een provider-selectie parameter toevoegen aan het request.

## Testen

```bash
# Alle tests uitvoeren
pytest tests/ -v

# Alleen chat tests
pytest tests/unit/test_chat_completion_service.py -v
pytest tests/unit/test_openrouter_client.py -v
```
