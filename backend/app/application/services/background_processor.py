"""Background Processor — asyncio daemon for processing queued jobs."""

import asyncio
import base64
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.application.services.sse_manager import SSEManager
from app.config import get_settings
from app.domain.entities.processing_job import JobStatus, ProcessingJob
from app.domain.exceptions import ChatProviderError
from app.infrastructure.database.session import async_session_factory

logger = logging.getLogger(__name__)

# Polling interval in seconds
POLL_INTERVAL = 5


class BackgroundProcessor:
    """Asyncio daemon that polls the processing_jobs table and executes queued work.

    Runs as an asyncio.Task inside FastAPI's lifespan. Each job gets its own
    database session with proper commit/rollback boundaries. Broadcasts status
    updates via the SSEManager so connected clients see real-time progress.
    """

    def __init__(
        self,
        sse_manager: SSEManager,
        service_factory: "callable",
        capture_service=None,
    ) -> None:
        self._sse = sse_manager
        self._service_factory = service_factory
        self._capture_service = capture_service
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the background processing loop."""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("BackgroundProcessor started")

    async def stop(self) -> None:
        """Gracefully stop the background processing loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("BackgroundProcessor stopped")

    async def _loop(self) -> None:
        """Main polling loop — picks up queued jobs and processes them."""
        while self._running:
            try:
                await self._poll_and_process()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("BackgroundProcessor polling error")

            await asyncio.sleep(POLL_INTERVAL)

    async def _poll_and_process(self) -> None:
        """Poll for queued jobs using a short-lived session, then process each."""
        from app.infrastructure.database.repositories import SQLAlchemyProcessingJobRepository

        # Use a dedicated session just for polling
        async with async_session_factory() as session:
            repo = SQLAlchemyProcessingJobRepository(session)
            jobs = await repo.get_queued(limit=5)
            await session.commit()

        # Process each job with its own session
        for job in jobs:
            if not self._running:
                break
            await self._process_job(job)

    async def _process_job(self, job: ProcessingJob) -> None:
        """Process a single job with its own database session."""
        from app.infrastructure.database.repositories import SQLAlchemyProcessingJobRepository

        logger.info("Processing job %s: %s", job.id, job.resource_identifier)

        async with async_session_factory() as session:
            repo = SQLAlchemyProcessingJobRepository(session)

            try:
                # Mark as processing
                job.mark_processing(f"Processing: {job.resource_identifier}")
                await repo.update(job)
                await session.commit()
                await self._broadcast_status(job)

                # Build the file processing service for this job
                file_service = await self._service_factory(session)

                if job.resource_type == "file":
                    await self._process_file_job(job, file_service)
                elif job.resource_type == "url":
                    await self._process_url_job(job, file_service, repo, session)
                elif job.resource_type == "text":
                    await self._process_text_job(job, file_service, repo, session)
                else:
                    raise ValueError(f"Unknown resource type: {job.resource_type}")

                # Mark completed
                await repo.update(job)
                await session.commit()
                await self._broadcast_status(job)

            except Exception as e:
                await session.rollback()
                logger.exception("Job %s failed: %s", job.id, e)

                # Mark failed in a fresh transaction
                job.mark_failed(str(e))
                await repo.update(job)
                await session.commit()
                await self._broadcast_status(job)

    async def _process_file_job(self, job: ProcessingJob, file_service) -> None:
        """Process a file job — delegates to ResourceProcessingService."""
        stored_path = job.resource_identifier

        path = Path(stored_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {stored_path}")

        content = path.read_bytes()
        filename = path.name

        result = await file_service.upload_file(
            content=content,
            filename=filename,
        )

        job.mark_completed(result.id)

    async def _process_url_job(self, job: ProcessingJob, file_service, repo, session) -> None:
        """Process a URL job — capture screenshot and extract data via LLM vision.

        Pipeline:
            1. Capture full-page screenshot with Playwright
            2. Fetch ontology concepts for classification
            3. Send screenshot + concepts to LLM vision with tool calling
            4. Create Resource records from LLM results
        """
        url = job.resource_identifier

        # ── Step 1: Capture screenshot ──────────────────────────────
        if not self._capture_service:
            raise RuntimeError("WebsiteCaptureService not configured — cannot process URLs")

        job.progress_message = f"Capturing screenshot: {url}"
        await repo.update(job)
        await session.commit()
        await self._broadcast_status(job)

        captured = await self._capture_service.capture_screenshot(url)
        logger.info(
            "Captured %s — %d bytes, title=%r",
            url,
            len(captured.screenshot_bytes),
            captured.title,
        )

        # Store the screenshot via LocalFileStorage (domain-based subfolder)
        from app.infrastructure.storage.local_file_storage import LocalFileStorage

        settings = get_settings()
        storage = LocalFileStorage(upload_dir=settings.upload_dir)
        stored = await storage.store_website_capture(
            content=captured.screenshot_bytes,
            url=url,
            title=captured.title,
        )
        screenshot_path = stored.stored_path

        # ── Step 2: Fetch ontology concepts ─────────────────────────
        job.progress_message = f"Classifying content from: {captured.title}"
        await repo.update(job)
        await session.commit()
        await self._broadcast_status(job)

        from app.infrastructure.database.repositories import SQLAlchemyOntologyRepository

        ontology_repo = SQLAlchemyOntologyRepository(session)
        classifiable = await ontology_repo.get_classifiable_concepts()

        if not classifiable:
            logger.warning("No classifiable concepts — skipping LLM processing for %s", url)
            job.mark_completed(None)
            job.progress_message = "No ontology concepts available for classification"
            return

        available_concepts = []
        for concept in classifiable:
            available_concepts.append({
                "id": concept.id,
                "label": concept.label,
                "description": concept.description,
                "synonyms": concept.synonyms,
                "hints": concept.extraction_template.classification_hints if concept.extraction_template else [],
            })

        # ── Step 3: LLM vision processing ──────────────────────────
        job.progress_message = f"Extracting data from screenshot ({len(available_concepts)} concepts)"
        await repo.update(job)
        await session.commit()
        await self._broadcast_status(job)

        image_base64 = base64.b64encode(captured.screenshot_bytes).decode("ascii")

        # Build tool handler for get_extraction_schema
        from app.application.services.ontology_service import OntologyService

        ontology_service = OntologyService(ontology_repo)

        async def tool_handler(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
            if tool_name == "get_extraction_schema":
                concept_id = args.get("concept_id", "")
                resolved = await ontology_service.get_resolved_properties(concept_id)
                embedded_types = await ontology_service.get_embedded_types_for_concept(concept_id)

                schema_fields = [
                    {
                        "name": prop.name,
                        "type": prop.type,
                        "required": prop.required,
                        "description": prop.description,
                    }
                    for prop in resolved
                ]

                embedded_schemas = [
                    {
                        "id": et.id,
                        "description": et.description,
                        "properties": [
                            {
                                "name": p.name,
                                "type": p.type,
                                "required": p.required,
                                "description": p.description,
                            }
                            for p in et.properties
                        ],
                    }
                    for et in embedded_types
                ]

                return {
                    "concept_id": concept_id,
                    "properties": schema_fields,
                    "embedded_types": embedded_schemas,
                }

            return {"error": f"Unknown tool: {tool_name}"}

        # Get LLM client from the file processing service
        llm_client = file_service._llm_client
        if not llm_client:
            raise RuntimeError(
                "LLM client not configured — set OPENROUTER_API_KEY to process website screenshots"
            )

        start = time.monotonic()
        try:
            results = await llm_client.process_image_with_tools(
                image_base64=image_base64,
                mime_type="image/png",
                source_url=url,
                available_concepts=available_concepts,
                tool_handler=tool_handler,
            )
        except ChatProviderError as exc:
            if exc.provider == "openrouter" and exc.status_code == 401:
                raise RuntimeError(
                    "OpenRouter authentication failed (401). "
                    "Verify OPENROUTER_API_KEY and ensure backend/.env is loaded."
                ) from exc
            raise
        duration_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "LLM vision processed %s — %d items extracted in %dms",
            url,
            len(results),
            duration_ms,
        )

        # ── Step 4: Create Resource records ────────────────────
        from app.domain.entities.resource import (
            Resource,
            ProcessingStatus,
            ClassificationResult,
            ClassificationSignal,
        )
        from app.infrastructure.database.repositories import SQLAlchemyResourceRepository

        resource_repo = SQLAlchemyResourceRepository(session)

        if not results:
            # Fallback: create a generic L1 Document resource
            logger.info(
                "No items extracted for %s — applying L1 Document fallback", url
            )
            classification = ClassificationResult(
                primary_concept_id="Document",
                confidence=0.2,
                signals=[
                    ClassificationSignal(
                        method="llm_vision_fallback",
                        concept_id="Document",
                        score=0.2,
                        details="No concept matched; L1 Document fallback applied",
                    )
                ],
            )
            resource = Resource(
                id=str(uuid.uuid4()),
                filename=f"{captured.title or 'webpage'}.png",
                original_path=url,
                stored_path=str(screenshot_path),
                file_size=len(captured.screenshot_bytes),
                mime_type="image/png",
                status=ProcessingStatus.DONE,
                classification=classification,
                extracted_text=captured.title or "",
                metadata={},
                summary=f"Web page captured from {url}",
                uploaded_at=datetime.now(timezone.utc),
                processed_at=datetime.now(timezone.utc),
            )
            await resource_repo.create(resource)
            await session.commit()
            job.mark_completed(resource.id)
            return

        first_result_id = None

        for i, result in enumerate(results):
            classification = ClassificationResult(
                primary_concept_id=result.concept_id,
                confidence=result.confidence,
                signals=[
                    ClassificationSignal(
                        method="llm_vision",
                        concept_id=result.concept_id,
                        score=result.confidence,
                        details=result.reasoning or "",
                    )
                ],
            )

            resource = Resource(
                id=str(uuid.uuid4()),
                filename=f"{captured.title or 'webpage'}_{i + 1}.png",
                original_path=url,
                stored_path=str(screenshot_path),
                file_size=len(captured.screenshot_bytes),
                mime_type="image/png",
                status=ProcessingStatus.DONE,
                classification=classification,
                extracted_text=result.summary or "",
                metadata=result.extracted_properties,
                summary=result.summary,
                uploaded_at=datetime.now(timezone.utc),
                processed_at=datetime.now(timezone.utc),
            )
            await resource_repo.create(resource)

            if first_result_id is None:
                first_result_id = resource.id

        await session.commit()
        job.mark_completed(first_result_id)

        # Log LLM usage
        if hasattr(file_service, '_usage_logger') and file_service._usage_logger and results:
            first = results[0]
            await file_service._usage_logger.log_request(
                model=first.model or "unknown",
                provider="openrouter",
                feature="website_capture",
                usage=first.usage,
                duration_ms=duration_ms,
                tools_called=first.tools_called or [],
                tool_call_count=len(first.tools_called or []),
                request_context=f"url={url} items={len(results)}",
            )

    async def _process_text_job(self, job: ProcessingJob, file_service, repo, session) -> None:
        """Process a text job — store as file and run through the standard pipeline.

        Pipeline:
            1. Look up text entry from DataSource.config["texts"]
            2. Store raw text content as a .txt file
            3. Delegate to ResourceProcessingService.upload_file()
        """
        text_id = job.resource_identifier

        # ── Step 1: Look up text entry ──────────────────────────────
        from app.infrastructure.database.repositories import SQLAlchemyDataSourceRepository

        ds_repo = SQLAlchemyDataSourceRepository(session)
        source = await ds_repo.get_by_id(job.data_source_id)
        if not source:
            raise ValueError(f"Data source {job.data_source_id} not found")

        entries: list[dict] = source.config.get("texts", [])
        entry = next((t for t in entries if t["id"] == text_id), None)
        if not entry:
            raise ValueError(f"Text entry {text_id} not found in source config")

        title = entry.get("title", "untitled")
        content = entry.get("content", "")

        job.progress_message = f"Processing text: {title}"
        await repo.update(job)
        await session.commit()
        await self._broadcast_status(job)

        # ── Step 2: Store as .txt file ──────────────────────────────
        content_bytes = content.encode("utf-8")

        # Sanitise title for filename
        safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")[:80]
        filename = f"{safe_title}.txt"

        # ── Step 3: Delegate to existing pipeline ───────────────────
        job.progress_message = f"Classifying: {title}"
        await repo.update(job)
        await session.commit()
        await self._broadcast_status(job)

        result = await file_service.upload_file(
            content=content_bytes,
            filename=filename,
            data_source_id=job.data_source_id,
        )

        job.mark_completed(result.id)

    async def _broadcast_status(self, job: ProcessingJob) -> None:
        """Broadcast job status update to SSE clients."""
        await self._sse.broadcast(
            "job_update",
            {
                "id": job.id,
                "data_source_id": job.data_source_id,
                "resource_identifier": job.resource_identifier,
                "resource_type": job.resource_type,
                "status": job.status.value,
                "progress_message": job.progress_message,
                "result_file_id": job.result_file_id,
                "error_message": job.error_message,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            },
        )
