"""Resource processing service — orchestrates the full document processing pipeline."""

import base64
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.application.interfaces import ResourceRepository, OntologyRepository
from app.application.interfaces.llm_client import (
    LLMClient,
    LLMPdfProcessingRequest,
)
from app.application.services.ontology_service import OntologyService
from app.domain.entities import (
    ClassificationResult,
    ClassificationSignal,
    Resource,
    ProcessingStatus,
)
from app.infrastructure.extractors.multi_format_text_extractor import MultiFormatTextExtractor
from app.infrastructure.logging.colored_logger import PipelineLogger, PipelineStage
from app.infrastructure.storage.local_file_storage import LocalFileStorage, StoredFile

logger = logging.getLogger(__name__)
plog = PipelineLogger("ResourceProcessingService")


class ResourceProcessingService:
    """Application service that orchestrates the resource upload + processing pipeline.

    Pipeline (non-PDF): Store → Extract Text → Classify → Extract Metadata → Done
    Pipeline (PDF):     Store → Send PDF to LLM (tool-calling) → Classify + Extract → Done
    """

    def __init__(
        self,
        file_repository: ResourceRepository,
        file_storage: LocalFileStorage,
        text_extractor: MultiFormatTextExtractor,
        classification_service=None,
        metadata_extractor=None,
        llm_client: LLMClient | None = None,
        ontology_repo: OntologyRepository | None = None,
        ontology_service: OntologyService | None = None,
        usage_logger=None,
        embedding_service=None,
    ):
        self._resource_repo = file_repository
        self._storage = file_storage
        self._extractor = text_extractor
        self._classifier = classification_service
        self._metadata_extractor = metadata_extractor
        self._llm_client = llm_client
        self._ontology_repo = ontology_repo
        self._ontology_service = ontology_service
        self._usage_logger = usage_logger
        self._embedding_service = embedding_service

    # ── Upload Operations ────────────────────────────────────────────

    async def upload_file(
        self,
        content: bytes,
        filename: str,
        data_source_id: str | None = None,
    ) -> Resource:
        """Upload a single file: store, extract text, classify, and extract metadata."""
        plog.separator(f"Processing: {filename}")
        plog.step_start(PipelineStage.UPLOAD, f"Received file '{filename}'", size_bytes=len(content))

        stored = await self._storage.store_file(content, filename)
        plog.step_complete(
            PipelineStage.STORAGE, f"Stored '{filename}'",
            path=stored.stored_path, mime_type=stored.mime_type,
        )

        resource = await self._create_resource_record(stored, data_source_id=data_source_id)
        plog.detail(f"Database record created", id=resource.id)

        await self._process_resource(resource)
        return resource

    async def upload_zip(
        self,
        content: bytes,
        zip_filename: str,
        data_source_id: str | None = None,
    ) -> list[Resource]:
        """Upload a ZIP archive: extract, store each file, and process them."""
        plog.separator(f"Processing ZIP: {zip_filename}")
        plog.step_start(PipelineStage.UPLOAD, f"Received ZIP '{zip_filename}'", size_bytes=len(content))

        stored_files = await self._storage.store_zip(content, zip_filename)
        plog.step_complete(PipelineStage.STORAGE, f"Extracted {len(stored_files)} files from ZIP")

        results: list[Resource] = []
        for i, stored in enumerate(stored_files, 1):
            plog.separator(f"ZIP file {i}/{len(stored_files)}: {stored.filename}")
            resource = await self._create_resource_record(stored, data_source_id=data_source_id)
            await self._process_resource(resource)
            results.append(resource)

        plog.step_complete(
            PipelineStage.PIPELINE,
            f"ZIP processing complete",
            total_files=len(results),
        )
        return results

    # ── Query Operations ─────────────────────────────────────────────

    async def get_resource(self, resource_id: str) -> Resource | None:
        """Get a single processed resource by ID."""
        return await self._resource_repo.get_by_id(resource_id)

    async def list_resources(self, skip: int = 0, limit: int = 100) -> list[Resource]:
        """List all processed resources in reverse chronological order."""
        return await self._resource_repo.get_all(skip=skip, limit=limit)

    async def get_resources_by_source(self, source_id: str) -> list[Resource]:
        """List all resources belonging to a specific data source."""
        return await self._resource_repo.get_by_source(source_id)

    async def get_resource_count(self) -> int:
        """Get total number of processed resources."""
        return await self._resource_repo.count()

    async def delete_resource(self, resource_id: str) -> bool:
        """Delete a resource group: remove related rows and file from disk.

        Returns True if the resource was found and deleted, False if not found.
        """
        plog.step_start(PipelineStage.PIPELINE, f"Deleting resource", resource_id=resource_id)

        resource = await self._resource_repo.get_by_id(resource_id)
        if resource is None:
            plog.step_error(PipelineStage.ERROR, f"Resource not found for deletion: {resource_id}")
            return False

        # Determine the logical group root.
        # If a child is deleted, remove all siblings + parent as one group.
        root_id = resource.origin_file_id or resource.id

        total_count = await self._resource_repo.count()
        all_resources = await self._resource_repo.get_all(skip=0, limit=max(total_count, 1))
        group_resources = [
            r for r in all_resources
            if (r.id == root_id) or (r.origin_file_id == root_id)
        ]

        # Fallback: if root no longer exists, still delete all resources sharing origin_file_id.
        if not group_resources and resource.origin_file_id:
            group_resources = [
                r for r in all_resources
                if r.origin_file_id == resource.origin_file_id
            ]

        # Always include the requested resource itself.
        if resource.id and all(r.id != resource.id for r in group_resources):
            group_resources.append(resource)

        group_ids = [r.id for r in group_resources if r.id]

        # Step 1: Remove from database
        deleted_ids: list[str] = []
        for gid in group_ids:
            if await self._resource_repo.delete(gid):
                deleted_ids.append(gid)

        # Step 2: Remove underlying file(s) from disk only if not referenced elsewhere
        group_paths = {r.stored_path for r in group_resources if r.stored_path}
        remaining_resources = [r for r in all_resources if r.id not in set(group_ids)]
        for path in group_paths:
            still_referenced = any(r.stored_path == path for r in remaining_resources)
            if not still_referenced:
                await self._storage.delete_file(path)
                plog.detail(f"Removed from disk: {path}")

        plog.step_complete(
            PipelineStage.COMPLETE,
            f"Deleted '{resource.filename}' group",
            resource_id=resource_id,
            deleted_records=len(deleted_ids),
        )
        return True

    async def reprocess_resource(self, resource_id: str, *, concept_id: str | None = None) -> Resource:
        """Re-run the processing pipeline for an existing resource.

        Steps:
        1. Find the resource (or its root if it's a sub-document).
        2. Delete any child records (from multi-doc PDF splits).
        3. Reset the root resource to PENDING state.
        4. Re-run the full processing pipeline.

        Args:
            resource_id: ID of the resource to reprocess.
            concept_id: Optional concept override — skips classification
                        and uses this concept directly for metadata extraction.

        Returns the updated root resource after reprocessing.
        Raises ValueError if the resource is not found.
        """
        plog.separator(f"Reprocessing: resource_id={resource_id}" + (f" concept_override={concept_id}" if concept_id else ""))

        resource = await self._resource_repo.get_by_id(resource_id)
        if resource is None:
            raise ValueError(f"Resource not found: {resource_id}")

        # If this is a sub-document, find its root
        root_id = resource.origin_file_id or resource.id
        root = resource if resource.id == root_id else await self._resource_repo.get_by_id(root_id)
        if root is None:
            raise ValueError(f"Root resource not found: {root_id}")

        # Delete child records from previous multi-doc processing
        total = await self._resource_repo.count()
        all_resources = await self._resource_repo.get_all(skip=0, limit=max(total, 1))
        children = [r for r in all_resources if r.origin_file_id == root_id and r.id != root_id]
        for child in children:
            await self._resource_repo.delete(child.id)
            plog.detail(f"Deleted child record: {child.id} ({child.filename})")

        # Reset root resource state
        root.status = ProcessingStatus.PENDING
        root.classification = None
        root.metadata = {}
        root.extra_fields = []
        root.summary = None
        root.extracted_text = None
        root.language = None
        root.processing_time_ms = None
        root.processed_at = None
        root.error_message = None
        root.page_range = None
        await self._resource_repo.update(root)

        plog.step_start(
            PipelineStage.PIPELINE,
            f"Reprocessing '{root.filename}'",
            resource_id=root.id,
            deleted_children=len(children),
            concept_override=concept_id,
        )

        # Re-run the full processing pipeline
        await self._process_resource(root, concept_id=concept_id)
        return root

    # ── Internal Pipeline ────────────────────────────────────────────

    async def _create_resource_record(
        self,
        stored: StoredFile,
        data_source_id: str | None = None,
    ) -> Resource:
        """Create a new Resource record in the database."""
        resource = Resource(
            id=str(uuid.uuid4()),
            filename=stored.filename,
            original_path=stored.original_path,
            file_size=stored.file_size,
            mime_type=stored.mime_type,
            stored_path=stored.stored_path,
            status=ProcessingStatus.PENDING,
            data_source_id=data_source_id,
        )
        return await self._resource_repo.create(resource)

    async def _process_resource(self, resource: Resource, *, concept_id: str | None = None) -> None:
        """Run the processing pipeline, routing PDFs to the LLM path."""
        try:
            if resource.mime_type == "application/pdf" and self._llm_client and self._ontology_repo:
                plog.step_start(
                    PipelineStage.PIPELINE,
                    f"Using PDF→LLM pipeline for '{resource.filename}'",
                )
                await self._process_pdf_via_llm(resource)
            else:
                if resource.mime_type == "application/pdf":
                    plog.detail("LLM client not available — falling back to text extraction pipeline")
                plog.step_start(
                    PipelineStage.PIPELINE,
                    f"Using text extraction pipeline for '{resource.filename}'",
                    mime_type=resource.mime_type,
                )
                await self._process_via_text_extraction(resource, concept_id=concept_id)

        except Exception as e:
            plog.step_error(PipelineStage.ERROR, f"Pipeline failed for '{resource.filename}'", error=e)
            resource.mark_error(str(e))
            await self._resource_repo.update(resource)

    # ── PDF → LLM Pipeline (Tool-Calling) ──────────────────────────────

    async def _process_pdf_via_llm(self, resource: Resource) -> None:
        """Process a PDF using tool-calling: the LLM drives classification and extraction.

        The LLM receives the PDF + concept catalogue and uses tools:
        - get_extraction_schema(concept_id) → returns resolved properties
        - submit_document(concept_id, ...) → submits one extracted document

        For multi-document PDFs, additional Resource records are created
        linked to the original via origin_file_id.
        """
        assert self._llm_client is not None
        assert self._ontology_repo is not None

        resource.status = ProcessingStatus.CLASSIFYING
        await self._resource_repo.update(resource)

        # Step 1: Read and encode the PDF
        plog.step_start(PipelineStage.PDF_LLM, f"Reading PDF from disk: {resource.stored_path}")
        pdf_path = Path(resource.stored_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {resource.stored_path}")

        pdf_bytes = pdf_path.read_bytes()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("ascii")
        plog.detail(f"PDF encoded", size_kb=f"{len(pdf_bytes) // 1024}", base64_length=len(pdf_base64))

        # Step 2: Fetch classifiable concepts (catalogue only — no template fields)
        plog.step_start(PipelineStage.PDF_LLM, "Fetching ontology concepts for classification")
        classifiable = await self._ontology_repo.get_classifiable_concepts()

        if not classifiable:
            plog.step_error(PipelineStage.PDF_LLM, "No classifiable concepts in ontology — cannot process PDF")
            resource.mark_done()
            await self._resource_repo.update(resource)
            return

        plog.detail(f"Found {len(classifiable)} classifiable concepts")

        available_concepts = []
        for concept in classifiable:
            available_concepts.append({
                "id": concept.id,
                "label": concept.label,
                "description": concept.description,
                "synonyms": concept.synonyms,
                "hints": concept.extraction_template.classification_hints if concept.extraction_template else [],
            })

        # Step 3: Define tool handler for get_extraction_schema
        async def tool_handler(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
            """Handle tool calls from the LLM."""
            if tool_name == "get_extraction_schema":
                concept_id = args.get("concept_id", "")
                plog.detail(f"LLM requested schema for concept '{concept_id}'")

                if self._ontology_service:
                    resolved = await self._ontology_service.get_resolved_properties(concept_id)
                    embedded_types = await self._ontology_service.get_embedded_types_for_concept(concept_id)
                else:
                    # Fallback: get concept directly if no OntologyService
                    concept = await self._ontology_repo.get_concept(concept_id)
                    resolved = concept.properties if concept else []
                    embedded_types = []

                schema_fields = [
                    {
                        "name": prop.name,
                        "type": prop.type,
                        "required": prop.required,
                        "description": prop.description,
                    }
                    for prop in resolved
                ]

                # Include embedded type schemas so the LLM can extract sub-structures
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

                plog.detail(
                    f"Returning {len(schema_fields)} properties + "
                    f"{len(embedded_schemas)} embedded types for '{concept_id}'"
                )
                return {
                    "concept_id": concept_id,
                    "properties": schema_fields,
                    "embedded_types": embedded_schemas,
                }

            return {"error": f"Unknown tool: {tool_name}"}

        # Step 4: Call the LLM with tool-calling
        plog.step_start(PipelineStage.PDF_LLM, f"Starting tool-based processing for '{resource.filename}'")

        start = time.monotonic()
        results = await self._llm_client.process_pdf_with_tools(
            pdf_base64=pdf_base64,
            filename=resource.filename,
            available_concepts=available_concepts,
            tool_handler=tool_handler,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        # Log LLM usage for the PDF processing call
        if self._usage_logger and results:
            first = results[0]
            await self._usage_logger.log_request(
                model=first.model or "unknown",
                provider="openrouter",
                feature="pdf_processing",
                usage=first.usage,
                duration_ms=duration_ms,
                tools_called=first.tools_called or None,
                tool_call_count=first.tool_call_count,
                request_context=resource.filename,
            )

        if not results:
            plog.step_error(PipelineStage.PDF_LLM, "LLM returned no documents")
            resource.mark_error("LLM did not submit any documents")
            await self._resource_repo.update(resource)
            return

        # Step 5: Map results to domain entities
        plog.step_start(PipelineStage.PDF_LLM, f"Mapping {len(results)} document(s) to domain entities")

        if len(results) == 1:
            # Single document — update the existing Resource
            await self._apply_llm_result_to_resource(resource, results[0])
        else:
            # Multi-document — first result updates the original, rest create new records
            plog.detail(f"Multi-document PDF: {len(results)} documents detected")

            for i, doc_result in enumerate(results):
                if i == 0:
                    resource.page_range = doc_result.page_range
                    await self._apply_llm_result_to_resource(resource, doc_result)
                else:
                    sub_resource = Resource(
                        filename=f"{resource.filename} (document {i + 1})",
                        original_path=resource.original_path,
                        file_size=resource.file_size,
                        mime_type=resource.mime_type,
                        stored_path=resource.stored_path,
                        origin_file_id=resource.id,
                        page_range=doc_result.page_range,
                        data_source_id=resource.data_source_id,
                    )
                    sub_resource = await self._resource_repo.create(sub_resource)
                    await self._apply_llm_result_to_resource(sub_resource, doc_result)
                    plog.detail(
                        f"Created sub-document {i + 1}: '{sub_resource.filename}'",
                        id=sub_resource.id,
                        concept=doc_result.concept_id,
                        page_range=doc_result.page_range,
                    )

        plog.step_complete(
            PipelineStage.COMPLETE,
            f"PDF processing complete for '{resource.filename}'",
            total_documents=len(results),
        )

    async def _apply_llm_result_to_resource(self, resource: Resource, result) -> None:
        """Apply a single LLM document result to a Resource entity."""
        from app.application.services.metadata_extraction_service import _normalize_value

        # Classification
        resource.classification = ClassificationResult(
            primary_concept_id=result.concept_id,
            confidence=result.confidence,
            signals=[
                ClassificationSignal(
                    method="llm_tool_processing",
                    concept_id=result.concept_id,
                    score=result.confidence,
                    details=result.reasoning,
                ),
            ],
        )

        # Extracted metadata (JSONB dict)
        if result.extracted_properties:
            field_type_map: dict[str, str] = {}
            if self._ontology_service:
                resolved = await self._ontology_service.get_resolved_properties(result.concept_id)
                field_type_map = {prop.name: prop.type for prop in resolved}

            metadata: dict[str, Any] = {}
            for key, value in result.extracted_properties.items():
                if value is None:
                    continue
                field_type = field_type_map.get(key, "string")
                entry = _normalize_value(key, field_type, value)
                if entry:
                    entry["confidence"] = result.confidence
                    metadata[key] = entry

            resource.metadata = metadata

        # Embedded items (e.g. line items, clauses) extracted by LLM
        embedded_items = getattr(result, "embedded_items", None)
        if embedded_items and isinstance(embedded_items, dict):
            # Store under a special key in metadata
            if not resource.metadata:
                resource.metadata = {}
            resource.metadata["_embedded_items"] = embedded_items

        # Summary
        if result.summary:
            resource.summary = result.summary

        resource.mark_done()
        await self._resource_repo.update(resource)

        # Generate embeddings (non-blocking)
        await self._generate_embeddings(resource)

    # ── Text Extraction Pipeline (non-PDF) ───────────────────────────

    async def _process_via_text_extraction(self, resource: Resource, *, concept_id: str | None = None) -> None:
        """Run the existing pipeline: extract text → classify → extract metadata."""
        # Step 1: Text extraction
        await self._extract_text(resource)

        # Step 2: Classification (skip if concept override is provided)
        if concept_id:
            plog.detail(f"Concept override: skipping classification, using '{concept_id}'")
            resource.classification = ClassificationResult(
                primary_concept_id=concept_id,
                confidence=1.0,
                signals=[ClassificationSignal(
                    method="manual_override",
                    concept_id=concept_id,
                    score=1.0,
                    details=f"Manually set by user to '{concept_id}'",
                )],
            )
            await self._resource_repo.update(resource)
        elif self._classifier and resource.extracted_text:
            await self._classify(resource)

        # Step 3: Metadata extraction
        # When a concept override is provided, always attempt extraction
        # even if extracted_text is empty (e.g. for images).
        has_text = bool(resource.extracted_text)
        if (
            self._metadata_extractor
            and resource.classification
            and (has_text or concept_id)
        ):
            await self._extract_metadata(resource)
        else:
            # No metadata extractor or no classification — mark done
            resource.mark_done()
            await self._resource_repo.update(resource)

    async def _extract_text(self, resource: Resource) -> None:
        """Step 1: Extract text content from the file."""
        if not self._extractor.can_extract(resource.mime_type):
            plog.step_error(
                PipelineStage.TEXT_EXTRACTION,
                f"No extractor for MIME type '{resource.mime_type}' ({resource.filename})",
            )
            resource.extracted_text = ""
            return

        resource.status = ProcessingStatus.EXTRACTING_TEXT
        await self._resource_repo.update(resource)

        with plog.timed_step(PipelineStage.TEXT_EXTRACTION, f"Extracting text from '{resource.filename}'"):
            text = await self._extractor.extract_text(resource.stored_path, resource.mime_type)
            resource.extracted_text = text

        plog.stats(chars_extracted=len(text), mime_type=resource.mime_type)

    async def _classify(self, resource: Resource) -> None:
        """Step 2: Classify the file against the ontology."""
        resource.status = ProcessingStatus.CLASSIFYING
        await self._resource_repo.update(resource)

        with plog.timed_step(PipelineStage.CLASSIFICATION, f"Classifying '{resource.filename}'"):
            result = await self._classifier.classify(
                text=resource.extracted_text or "",
                filename=resource.filename,
                original_path=resource.original_path,
            )

        resource.classification = result
        await self._resource_repo.update(resource)

        plog.stats(
            concept=result.primary_concept_id,
            confidence=f"{result.confidence:.2f}",
            signals=len(result.signals),
        )

    async def _extract_metadata(self, resource: Resource) -> None:
        """Step 3: Extract structured metadata using the concept's template."""
        resource.status = ProcessingStatus.EXTRACTING_METADATA
        await self._resource_repo.update(resource)

        # For image files, load the image for vision-based extraction
        image_base64: str | None = None
        image_mime: str | None = None
        if resource.mime_type and resource.mime_type.startswith("image/") and resource.stored_path:
            try:
                image_path = Path(resource.stored_path)
                if image_path.exists():
                    image_bytes = image_path.read_bytes()
                    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                    image_mime = resource.mime_type
                    plog.detail(
                        f"Loaded image for vision extraction",
                        size_kb=f"{len(image_bytes) // 1024}",
                        mime=image_mime,
                    )
            except Exception as e:
                plog.detail(f"Could not load image for vision: {e}")

        with plog.timed_step(
            PipelineStage.METADATA,
            f"Extracting metadata for '{resource.filename}' (concept: {resource.classification.primary_concept_id})",
        ):
            metadata, extra_fields, summary = await self._metadata_extractor.extract(
                text=resource.extracted_text or "",
                classification=resource.classification,
                image_base64=image_base64,
                mime_type=image_mime,
            )

        resource.metadata = metadata
        resource.extra_fields = extra_fields
        resource.summary = summary if summary else None
        resource.mark_done()
        await self._resource_repo.update(resource)

        plog.stats(
            properties_extracted=len(metadata),
            has_summary=bool(summary),
            vision_used=bool(image_base64),
        )

        # Generate embeddings (non-blocking)
        await self._generate_embeddings(resource)

    async def _generate_embeddings(self, resource: Resource) -> None:
        """Generate and store embeddings for a processed resource (best-effort)."""
        if not self._embedding_service:
            return
        try:
            count = await self._embedding_service.embed_resource(resource)
            if count:
                plog.detail(f"Embedded resource into {count} chunks", resource_id=resource.id)
        except Exception as e:
            # Embedding failures should not block the processing pipeline
            plog.step_error(
                PipelineStage.ERROR,
                f"Embedding generation failed for '{resource.filename}': {e}",
            )
            logger.exception("Embedding generation failed for resource %s", resource.id)
