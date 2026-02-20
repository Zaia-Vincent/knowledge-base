# Data Sources & Achtergrondverwerking

> **Doelgroep**: AI-studenten die willen begrijpen hoe asynchrone verwerkingspipelines worden geïmplementeerd in Python.

## Motivatie

Documentverwerking is **tijdrovend**: een PDF classificeren en metadata extraheren kan 5-30 seconden duren per document. Het is onacceptabel om de HTTP-response te blokkeren terwijl het LLM nadenkt.

Daarom heeft het systeem een **achtergrondverwerkingsarchitectuur**:

1. De API ontvangt een upload/URL → maakt een `ProcessingJob` → reageert direct
2. Een **BackgroundProcessor** daemon pikt de job op en verwerkt hem asynchroon
3. **SSE (Server-Sent Events)** stuurt real-time statusupdates naar de frontend

## DataSource Entiteit

Een `DataSource` beschrijft een **bron** waaruit documenten worden ingevoerd:

```python
class DataSourceType(str, Enum):
    FILE_UPLOAD = "file_upload"   # Handmatige bestandsuploads
    WEBSITE = "website"           # Automatisch gecapturede websites

@dataclass
class DataSource:
    name: str
    source_type: DataSourceType
    config: dict[str, Any] = field(default_factory=dict)
    # Website: {"urls": ["https://example.com/page1", ...]}
```

Bij elke applicatiestart wordt de standaard "Files" bron automatisch aangemaakt:

```python
# In main.py lifespan:
async def _seed_default_data_sources():
    """Maak de ingebouwde 'Files' databron als die niet bestaat."""
```

## DataSourceService

De `DataSourceService` biedt de use cases voor bronbeheer:

```python
class DataSourceService:
    """Manages data sources and submits processing jobs."""

    async def create_source(self, name, source_type, config, description) -> DataSource:
        """Registreer een nieuwe databron."""

    async def submit_file(self, source_id, content, filename) -> ProcessingJob:
        """Upload een bestand en maak een verwerkingsjob aan."""

    async def submit_url(self, source_id, url) -> ProcessingJob:
        """Submit een URL voor website-capture en verwerking."""

    async def list_jobs(self, source_id, status=None) -> list[ProcessingJob]:
        """Toon alle jobs voor een bron, optioneel gefilterd op status."""

    async def restart_job(self, job_id) -> ProcessingJob:
        """Herstart een gefaalde job via mark_requeued()."""
```

## ProcessingJob Lifecycle

```
                submit_file()
                submit_url()
                     │
                     ▼
                ┌─────────┐
                │ QUEUED   │  ← Job wacht in de database
                └────┬────┘
                     │  BackgroundProcessor._poll_and_process()
                     ▼
                ┌──────────────┐
                │  PROCESSING  │  ← Daemon verwerkt de job
                └──────┬──────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
        ┌───────────┐    ┌──────────┐
        │ COMPLETED │    │  FAILED  │
        └───────────┘    └────┬─────┘
                              │  restart_job()
                              ▼
                         ┌─────────┐
                         │ QUEUED   │  ← Opnieuw in de wachtrij
                         └─────────┘
```

## De BackgroundProcessor

De `BackgroundProcessor` is een **asyncio daemon** — een oneindige loop die elke 5 seconden pollt voor nieuwe jobs.

### Architectuur

```python
class BackgroundProcessor:
    """Asyncio daemon die de processing_jobs tabel pollt."""

    def __init__(self, sse_manager, service_factory, capture_service):
        self._sse = sse_manager               # SSE voor real-time updates
        self._service_factory = service_factory # Bouwt per-job services
        self._capture_service = capture_service # Playwright voor website capture

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        while self._running:
            await self._poll_and_process()
            await asyncio.sleep(POLL_INTERVAL)  # 5 seconden
```

### Session-per-Job Isolatie

Een cruciaal ontwerpbesluit: **elke job krijgt zijn eigen database-sessie**:

```python
async def _process_job(self, job: ProcessingJob):
    """Verwerk één job met een eigen database-sessie."""
    async with async_session_factory() as session:
        repo = SQLAlchemyProcessingJobRepository(session)

        try:
            job.mark_processing("Processing started")
            await repo.update(job)
            await session.commit()

            # Bouw services voor deze specifieke sessie
            file_service = await self._service_factory(session)

            if job.resource_type == "file":
                await self._process_file_job(job, file_service)
            elif job.resource_type == "url":
                await self._process_url_job(job, file_service, repo, session)

            await repo.update(job)
            await session.commit()

        except Exception as e:
            await session.rollback()
            job.mark_failed(str(e))
            await repo.update(job)
            await session.commit()
```

Waarom? Omdat een fout in job A niet de transactie van job B mag corrumperen.

### Service Factory Pattern

De `service_factory` is een functie die per sessie een complete `ResourceProcessingService` opbouwt:

```python
# In main.py:
async def _build_resource_processing_service(session):
    """Bouw een ResourceProcessingService voor deze specifieke sessie."""
    resource_repo = SQLAlchemyResourceRepository(session)
    ontology_repo = SQLAlchemyOntologyRepository(session)
    storage = LocalFileStorage(upload_dir=settings.upload_dir)
    # ... alle afhankelijkheden worden gebouwd en gekoppeld ...
    return ResourceProcessingService(file_repository=resource_repo, ...)
```

### URL-Verwerking: Website Capture Pipeline

URL-jobs volgen een speciaal pad:

```
1. Playwright screenshot    → captured.screenshot_bytes
2. Opslaan als PNG           → LocalFileStorage
3. Ontologie laden           → classifiable concepts
4. LLM Vision + tool-calling → gestructureerde data
5. Resource records aanmaken → database
```

```python
async def _process_url_job(self, job, file_service, repo, session):
    # 1. Screenshot met Playwright
    captured = await self._capture_service.capture_screenshot(url)

    # 2. Opslaan
    stored = await storage.store_website_capture(
        content=captured.screenshot_bytes, url=url, title=captured.title
    )

    # 3. Ontologie laden
    classifiable = await ontology_repo.get_classifiable_concepts()

    # 4. LLM Vision verwerking
    results = await llm_client.process_image_with_tools(
        image_base64=image_base64,
        mime_type="image/png",
        source_url=url,
        available_concepts=available_concepts,
        tool_handler=tool_handler,
    )

    # 5. Resource records maken
    for result in results:
        resource = Resource(
            classification=ClassificationResult(...),
            metadata=result.extracted_properties,
            ...
        )
        await resource_repo.create(resource)
```

## SSE (Server-Sent Events)

De `SSEManager` broadcast real-time statusupdates naar verbonden clients:

```python
class SSEManager:
    """Beheert SSE-verbindingen voor real-time statusupdates."""

    async def broadcast(self, event_type: str, data: dict):
        """Stuur een event naar alle verbonden clients."""

# Gebruik in BackgroundProcessor:
await self._sse.broadcast("job_update", {
    "id": job.id,
    "status": job.status.value,
    "progress_message": job.progress_message,
    "result_file_id": job.result_file_id,
})
```

De frontend luistert via een `EventSource`:

```javascript
const sse = new EventSource("/api/v1/data-sources/stream");
sse.addEventListener("job_update", (event) => {
    const job = JSON.parse(event.data);
    updateJobStatus(job);  // Real-time UI update
});
```

## Leerpunten

1. **Asynchrone verwerking**: Gebruik een job-queue patroon voor langlopende operaties — blokkeer nooit de HTTP-response.
2. **Session-per-job isolatie**: Elke job krijgt een eigen database-sessie zodat fouten geïsoleerd zijn.
3. **Service Factory Pattern**: De `service_factory` callback maakt het mogelijk om per-job services te bouwen met de juiste sessie-scope.
4. **SSE voor real-time**: Server-Sent Events zijn eenvoudiger dan WebSockets voor unidirectionele real-time updates.
5. **Graceful shutdown**: De processor stopt netjes via `_running = False` en wacht op de laatste job.
