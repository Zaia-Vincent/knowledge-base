"""File processing service — orchestrates the full document processing pipeline."""

import base64
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.application.interfaces import FileRepository, OntologyRepository
from app.application.interfaces.llm_client import (
    LLMClient,
    LLMPdfProcessingRequest,
)
from app.application.services.ontology_service import OntologyService
from app.domain.entities import (
    ClassificationResult,
    ClassificationSignal,
    ProcessedFile,
    ProcessingStatus,
)
from app.infrastructure.extractors.multi_format_text_extractor import MultiFormatTextExtractor
from app.infrastructure.logging.colored_logger import PipelineLogger, PipelineStage
from app.infrastructure.storage.local_file_storage import LocalFileStorage, StoredFile

logger = logging.getLogger(__name__)
plog = PipelineLogger("FileProcessingService")


class FileProcessingService:
    """Application service that orchestrates the file upload + processing pipeline.

    Pipeline (non-PDF): Store → Extract Text → Classify → Extract Metadata → Done
    Pipeline (PDF):     Store → Send PDF to LLM (tool-calling) → Classify + Extract → Done
    """

    def __init__(
        self,
        file_repository: FileRepository,
        file_storage: LocalFileStorage,
        text_extractor: MultiFormatTextExtractor,
        classification_service=None,
        metadata_extractor=None,
        llm_client: LLMClient | None = None,
        ontology_repo: OntologyRepository | None = None,
        ontology_service: OntologyService | None = None,
        usage_logger=None,
    ):
        self._file_repo = file_repository
        self._storage = file_storage
        self._extractor = text_extractor
        self._classifier = classification_service
        self._metadata_extractor = metadata_extractor
        self._llm_client = llm_client
        self._ontology_repo = ontology_repo
        self._ontology_service = ontology_service
        self._usage_logger = usage_logger

    # ── Upload Operations ────────────────────────────────────────────

    async def upload_file(self, content: bytes, filename: str) -> ProcessedFile:
        """Upload a single file: store, extract text, classify, and extract metadata."""
        plog.separator(f"Processing: {filename}")
        plog.step_start(PipelineStage.UPLOAD, f"Received file '{filename}'", size_bytes=len(content))

        stored = await self._storage.store_file(content, filename)
        plog.step_complete(
            PipelineStage.STORAGE, f"Stored '{filename}'",
            path=stored.stored_path, mime_type=stored.mime_type,
        )

        pf = await self._create_file_record(stored)
        plog.detail(f"Database record created", id=pf.id)

        await self._process_file(pf)
        return pf

    async def upload_zip(self, content: bytes, zip_filename: str) -> list[ProcessedFile]:
        """Upload a ZIP archive: extract, store each file, and process them."""
        plog.separator(f"Processing ZIP: {zip_filename}")
        plog.step_start(PipelineStage.UPLOAD, f"Received ZIP '{zip_filename}'", size_bytes=len(content))

        stored_files = await self._storage.store_zip(content, zip_filename)
        plog.step_complete(PipelineStage.STORAGE, f"Extracted {len(stored_files)} files from ZIP")

        results: list[ProcessedFile] = []
        for i, stored in enumerate(stored_files, 1):
            plog.separator(f"ZIP file {i}/{len(stored_files)}: {stored.filename}")
            pf = await self._create_file_record(stored)
            await self._process_file(pf)
            results.append(pf)

        plog.step_complete(
            PipelineStage.PIPELINE,
            f"ZIP processing complete",
            total_files=len(results),
        )
        return results

    # ── Query Operations ─────────────────────────────────────────────

    async def get_file(self, file_id: str) -> ProcessedFile | None:
        """Get a single processed file by ID."""
        return await self._file_repo.get_by_id(file_id)

    async def list_files(self, skip: int = 0, limit: int = 100) -> list[ProcessedFile]:
        """List all processed files in reverse chronological order."""
        return await self._file_repo.get_all(skip=skip, limit=limit)

    async def get_file_count(self) -> int:
        """Get total number of processed files."""
        return await self._file_repo.count()

    async def delete_file(self, file_id: str) -> bool:
        """Delete a processed file group: remove related rows and file from disk.

        Returns True if the file was found and deleted, False if not found.
        """
        plog.step_start(PipelineStage.PIPELINE, f"Deleting file", file_id=file_id)

        pf = await self._file_repo.get_by_id(file_id)
        if pf is None:
            plog.step_error(PipelineStage.ERROR, f"File not found for deletion: {file_id}")
            return False

        # Determine the logical group root.
        # If a child is deleted, remove all siblings + parent as one group.
        root_id = pf.origin_file_id or pf.id

        total_count = await self._file_repo.count()
        all_files = await self._file_repo.get_all(skip=0, limit=max(total_count, 1))
        group_files = [
            f for f in all_files
            if (f.id == root_id) or (f.origin_file_id == root_id)
        ]

        # Fallback: if root no longer exists, still delete all files sharing origin_file_id.
        if not group_files and pf.origin_file_id:
            group_files = [
                f for f in all_files
                if f.origin_file_id == pf.origin_file_id
            ]

        # Always include the requested file itself.
        if pf.id and all(f.id != pf.id for f in group_files):
            group_files.append(pf)

        group_ids = [f.id for f in group_files if f.id]

        # Step 1: Remove from database
        deleted_ids: list[str] = []
        for gid in group_ids:
            if await self._file_repo.delete(gid):
                deleted_ids.append(gid)

        # Step 2: Remove underlying file(s) from disk only if not referenced elsewhere
        group_paths = {f.stored_path for f in group_files if f.stored_path}
        remaining_files = [f for f in all_files if f.id not in set(group_ids)]
        for path in group_paths:
            still_referenced = any(f.stored_path == path for f in remaining_files)
            if not still_referenced:
                await self._storage.delete_file(path)
                plog.detail(f"Removed from disk: {path}")

        plog.step_complete(
            PipelineStage.COMPLETE,
            f"Deleted '{pf.filename}' group",
            file_id=file_id,
            deleted_records=len(deleted_ids),
        )
        return True

    # ── Internal Pipeline ────────────────────────────────────────────

    async def _create_file_record(self, stored: StoredFile) -> ProcessedFile:
        """Create a new ProcessedFile record in the database."""
        pf = ProcessedFile(
            id=str(uuid.uuid4()),
            filename=stored.filename,
            original_path=stored.original_path,
            file_size=stored.file_size,
            mime_type=stored.mime_type,
            stored_path=stored.stored_path,
            status=ProcessingStatus.PENDING,
        )
        return await self._file_repo.create(pf)

    async def _process_file(self, pf: ProcessedFile) -> None:
        """Run the processing pipeline, routing PDFs to the LLM path."""
        try:
            if pf.mime_type == "application/pdf" and self._llm_client and self._ontology_repo:
                plog.step_start(
                    PipelineStage.PIPELINE,
                    f"Using PDF→LLM pipeline for '{pf.filename}'",
                )
                await self._process_pdf_via_llm(pf)
            else:
                if pf.mime_type == "application/pdf":
                    plog.detail("LLM client not available — falling back to text extraction pipeline")
                plog.step_start(
                    PipelineStage.PIPELINE,
                    f"Using text extraction pipeline for '{pf.filename}'",
                    mime_type=pf.mime_type,
                )
                await self._process_via_text_extraction(pf)

        except Exception as e:
            plog.step_error(PipelineStage.ERROR, f"Pipeline failed for '{pf.filename}'", error=e)
            pf.mark_error(str(e))
            await self._file_repo.update(pf)

    # ── PDF → LLM Pipeline (Tool-Calling) ──────────────────────────────

    async def _process_pdf_via_llm(self, pf: ProcessedFile) -> None:
        """Process a PDF using tool-calling: the LLM drives classification and extraction.

        The LLM receives the PDF + concept catalogue and uses tools:
        - get_extraction_schema(concept_id) → returns resolved properties
        - submit_document(concept_id, ...) → submits one extracted document

        For multi-document PDFs, additional ProcessedFile records are created
        linked to the original via origin_file_id.
        """
        assert self._llm_client is not None
        assert self._ontology_repo is not None

        pf.status = ProcessingStatus.CLASSIFYING
        await self._file_repo.update(pf)

        # Step 1: Read and encode the PDF
        plog.step_start(PipelineStage.PDF_LLM, f"Reading PDF from disk: {pf.stored_path}")
        pdf_path = Path(pf.stored_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pf.stored_path}")

        pdf_bytes = pdf_path.read_bytes()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("ascii")
        plog.detail(f"PDF encoded", size_kb=f"{len(pdf_bytes) // 1024}", base64_length=len(pdf_base64))

        # Step 2: Fetch classifiable concepts (catalogue only — no template fields)
        plog.step_start(PipelineStage.PDF_LLM, "Fetching ontology concepts for classification")
        classifiable = await self._ontology_repo.get_classifiable_concepts()

        if not classifiable:
            plog.step_error(PipelineStage.PDF_LLM, "No classifiable concepts in ontology — cannot process PDF")
            pf.mark_done()
            await self._file_repo.update(pf)
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
        plog.step_start(PipelineStage.PDF_LLM, f"Starting tool-based processing for '{pf.filename}'")

        start = time.monotonic()
        results = await self._llm_client.process_pdf_with_tools(
            pdf_base64=pdf_base64,
            filename=pf.filename,
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
                request_context=pf.filename,
            )

        if not results:
            plog.step_error(PipelineStage.PDF_LLM, "LLM returned no documents")
            pf.mark_error("LLM did not submit any documents")
            await self._file_repo.update(pf)
            return

        # Step 5: Map results to domain entities
        plog.step_start(PipelineStage.PDF_LLM, f"Mapping {len(results)} document(s) to domain entities")

        if len(results) == 1:
            # Single document — update the existing ProcessedFile
            await self._apply_llm_result_to_file(pf, results[0])
        else:
            # Multi-document — first result updates the original, rest create new records
            plog.detail(f"Multi-document PDF: {len(results)} documents detected")

            for i, doc_result in enumerate(results):
                if i == 0:
                    pf.page_range = doc_result.page_range
                    await self._apply_llm_result_to_file(pf, doc_result)
                else:
                    sub_pf = ProcessedFile(
                        filename=f"{pf.filename} (document {i + 1})",
                        original_path=pf.original_path,
                        file_size=pf.file_size,
                        mime_type=pf.mime_type,
                        stored_path=pf.stored_path,
                        origin_file_id=pf.id,
                        page_range=doc_result.page_range,
                    )
                    sub_pf = await self._file_repo.create(sub_pf)
                    await self._apply_llm_result_to_file(sub_pf, doc_result)
                    plog.detail(
                        f"Created sub-document {i + 1}: '{sub_pf.filename}'",
                        id=sub_pf.id,
                        concept=doc_result.concept_id,
                        page_range=doc_result.page_range,
                    )

        plog.step_complete(
            PipelineStage.COMPLETE,
            f"PDF processing complete for '{pf.filename}'",
            total_documents=len(results),
        )

    async def _apply_llm_result_to_file(self, pf: ProcessedFile, result) -> None:
        """Apply a single LLM document result to a ProcessedFile entity."""
        from app.application.services.metadata_extraction_service import _normalize_value

        # Classification
        pf.classification = ClassificationResult(
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

            pf.metadata = metadata

        # Embedded items (e.g. line items, clauses) extracted by LLM
        embedded_items = getattr(result, "embedded_items", None)
        if embedded_items and isinstance(embedded_items, dict):
            # Store under a special key in metadata
            if not pf.metadata:
                pf.metadata = {}
            pf.metadata["_embedded_items"] = embedded_items

        # Summary
        if result.summary:
            pf.summary = result.summary

        pf.mark_done()
        await self._file_repo.update(pf)

    # ── Text Extraction Pipeline (non-PDF) ───────────────────────────

    async def _process_via_text_extraction(self, pf: ProcessedFile) -> None:
        """Run the existing pipeline: extract text → classify → extract metadata."""
        # Step 1: Text extraction
        await self._extract_text(pf)

        # Step 2: Classification
        if self._classifier and pf.extracted_text:
            await self._classify(pf)

        # Step 3: Metadata extraction
        if (
            self._metadata_extractor
            and pf.classification
            and pf.extracted_text
        ):
            await self._extract_metadata(pf)
        else:
            # No metadata extractor or no classification — mark done
            pf.mark_done()
            await self._file_repo.update(pf)

    async def _extract_text(self, pf: ProcessedFile) -> None:
        """Step 1: Extract text content from the file."""
        if not self._extractor.can_extract(pf.mime_type):
            plog.step_error(
                PipelineStage.TEXT_EXTRACTION,
                f"No extractor for MIME type '{pf.mime_type}' ({pf.filename})",
            )
            pf.extracted_text = ""
            return

        pf.status = ProcessingStatus.EXTRACTING_TEXT
        await self._file_repo.update(pf)

        with plog.timed_step(PipelineStage.TEXT_EXTRACTION, f"Extracting text from '{pf.filename}'"):
            text = await self._extractor.extract_text(pf.stored_path, pf.mime_type)
            pf.extracted_text = text

        plog.stats(chars_extracted=len(text), mime_type=pf.mime_type)

    async def _classify(self, pf: ProcessedFile) -> None:
        """Step 2: Classify the file against the ontology."""
        pf.status = ProcessingStatus.CLASSIFYING
        await self._file_repo.update(pf)

        with plog.timed_step(PipelineStage.CLASSIFICATION, f"Classifying '{pf.filename}'"):
            result = await self._classifier.classify(
                text=pf.extracted_text or "",
                filename=pf.filename,
                original_path=pf.original_path,
            )

        pf.classification = result
        await self._file_repo.update(pf)

        plog.stats(
            concept=result.primary_concept_id,
            confidence=f"{result.confidence:.2f}",
            signals=len(result.signals),
        )

    async def _extract_metadata(self, pf: ProcessedFile) -> None:
        """Step 3: Extract structured metadata using the concept's template."""
        pf.status = ProcessingStatus.EXTRACTING_METADATA
        await self._file_repo.update(pf)

        with plog.timed_step(
            PipelineStage.METADATA,
            f"Extracting metadata for '{pf.filename}' (concept: {pf.classification.primary_concept_id})",
        ):
            metadata, extra_fields, summary = await self._metadata_extractor.extract(
                text=pf.extracted_text or "",
                classification=pf.classification,
            )

        pf.metadata = metadata
        pf.extra_fields = extra_fields
        pf.summary = summary if summary else None
        pf.mark_done()
        await self._file_repo.update(pf)

        plog.stats(
            properties_extracted=len(metadata),
            has_summary=bool(summary),
        )
