"""OpenRouter LLM client — concrete implementation of the LLMClient port.

Reuses the existing OpenRouterClient for API calls,
adding classification, extraction, and tool-based PDF processing prompt engineering.
"""

import json
import logging
from typing import Any

from app.application.interfaces.llm_client import (
    LLMClassificationRequest,
    LLMClassificationResponse,
    LLMClient,
    LLMExtractionRequest,
    LLMExtractionResponse,
    LLMPdfProcessingRequest,
    LLMPdfProcessingResponse,
    LLMVisionOCRRequest,
    LLMVisionOCRResponse,
    ToolHandler,
)
from app.domain.entities import ChatMessage, ContentPart
from app.infrastructure.logging.colored_logger import PipelineLogger, PipelineStage
from app.infrastructure.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)
plog = PipelineLogger("OpenRouterLLMClient")

_CLASSIFICATION_SYSTEM_PROMPT = """You are a document classification expert. Given an excerpt of a document, classify it into one of the provided ontology concepts.

IMPORTANT RULES:
1. Return ONLY valid JSON with these exact keys: concept_id, confidence, reasoning
2. confidence must be a float between 0.0 and 1.0
3. concept_id must be one of the provided concept IDs
4. reasoning must explain why you chose this classification (max 200 characters)
5. If no concept clearly matches, choose the closest one with lower confidence

Example response:
{"concept_id": "Invoice", "confidence": 0.92, "reasoning": "Document contains invoice number, payment terms, and line items typical of an invoice"}"""

_EXTRACTION_SYSTEM_PROMPT = """You are a structured data extraction expert. Given a document and a list of fields to extract, return the extracted values as JSON.

IMPORTANT RULES:
1. Return ONLY valid JSON with the extracted field values
2. Use null for fields that cannot be found in the document
3. For dates, use ISO 8601 format (YYYY-MM-DD)
4. For monetary amounts, use plain numbers without currency symbols
5. Include a "_summary" field with a 2-3 sentence summary of the document
6. Include a "_confidence" field (0.0-1.0) indicating overall extraction quality"""

_OCR_SYSTEM_PROMPT = """Extract all visible text from this image. Maintain the original structure and layout as much as possible. If the image contains a table, represent it with aligned columns. Return only the extracted text, no commentary."""

_PDF_PROCESSING_SYSTEM_PROMPT = """You are a document processing expert. You will receive a PDF file along with a list of document categories (concepts) and their extraction templates.

Your task is to perform TWO operations in a single response:

1. **CLASSIFY** the document — determine which concept/category it belongs to
2. **EXTRACT METADATA** — extract structured fields based on the matched concept's template

IMPORTANT RULES:
1. Return ONLY valid JSON with these exact keys:
   - concept_id: the ID of the best-matching concept (MUST be one of the provided concept IDs)
   - confidence: float between 0.0 and 1.0 indicating classification certainty
   - reasoning: brief explanation of why this classification was chosen (max 200 chars)
   - extracted_properties: object with field_name → value mappings from the matched concept's template
   - summary: 2-3 sentence summary of the document content

2. For extracted_properties:
   - Use null for fields that cannot be found
   - For dates, use ISO 8601 format (YYYY-MM-DD)
   - For monetary amounts, use plain numbers without currency symbols
   - Only extract fields defined in the matched concept's template

3. If no concept matches well, use the closest match with lower confidence

Example response:
{
  "concept_id": "Invoice",
  "confidence": 0.95,
  "reasoning": "Document contains invoice number, line items, and payment terms",
  "extracted_properties": {
    "invoice_number": "INV-2025-001",
    "total_amount": 1250.00,
    "invoice_date": "2025-01-15",
    "vendor_name": "Acme Corp"
  },
  "summary": "This is an invoice from Acme Corp dated January 15, 2025 for consulting services totaling EUR 1,250.00."
}"""

_PDF_TOOL_SYSTEM_PROMPT = """You are a document processing expert. You will receive a PDF file and a catalogue of document categories (concepts).

YOUR WORKFLOW — follow these steps precisely:
1. Read the entire PDF and determine how many DISTINCT documents it contains.
   A PDF may contain one or more separate documents (e.g. 3 invoices stapled together).
2. For each document you identify, determine the best-matching concept from the catalogue.
3. Call the `get_extraction_schema` tool with the concept ID to get the full list of properties to extract.
4. Extract all available properties from the document.
5. Call the `submit_document` tool once per document with the extracted data.

IMPORTANT RULES:
- If the PDF contains multiple documents of the same type, call `get_extraction_schema` only ONCE for that type, then call `submit_document` separately for each document.
- For dates, use ISO 8601 format (YYYY-MM-DD).
- For monetary amounts, use plain numbers without currency symbols.
- Use null for properties that cannot be found in the document.
- Indicate page ranges (e.g. "1-2", "3-3") for each document.
- After submitting all documents, respond with a brief summary of what you processed."""

# Tool definitions for LLM tool calling
_TOOL_GET_EXTRACTION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_extraction_schema",
        "description": "Get the full property schema (including inherited and mixin properties) for a document category. Call this to know which fields to extract.",
        "parameters": {
            "type": "object",
            "properties": {
                "concept_id": {
                    "type": "string",
                    "description": "The ID of the concept/category to get the schema for",
                },
            },
            "required": ["concept_id"],
        },
    },
}

_TOOL_SUBMIT_DOCUMENT = {
    "type": "function",
    "function": {
        "name": "submit_document",
        "description": "Submit the extracted data for one document found in the PDF. Call this once per distinct document.",
        "parameters": {
            "type": "object",
            "properties": {
                "concept_id": {
                    "type": "string",
                    "description": "The ID of the matched concept/category",
                },
                "confidence": {
                    "type": "number",
                    "description": "Classification confidence (0.0 to 1.0)",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of why this classification was chosen (max 200 chars)",
                },
                "page_range": {
                    "type": "string",
                    "description": "Page range of this document in the PDF (e.g. '1-2', '3-3')",
                },
                "extracted_properties": {
                    "type": "object",
                    "description": "Object with field_name → extracted value mappings",
                    "additionalProperties": True,
                },
                "summary": {
                    "type": "string",
                    "description": "2-3 sentence summary of this document's content",
                },
            },
            "required": ["concept_id", "confidence", "reasoning", "extracted_properties", "summary"],
        },
    },
}


class OpenRouterLLMClient(LLMClient):
    """Concrete LLM client using OpenRouter API.

    Wraps the existing OpenRouterClient with classification, extraction,
    and tool-based PDF processing prompts. Supports a separate model for PDF processing.
    """

    def __init__(
        self,
        openrouter_client: OpenRouterClient,
        model: str,
        pdf_model: str | None = None,
    ):
        self._client = openrouter_client
        self._model = model
        self._pdf_model = pdf_model or model

    async def classify_document(
        self, request: LLMClassificationRequest
    ) -> LLMClassificationResponse:
        """Classify a document by sending excerpt + concept list to the LLM."""
        plog.step_start(
            PipelineStage.CLASSIFICATION,
            "Sending document excerpt to LLM for classification",
            model=self._model,
            excerpt_length=len(request.text_excerpt),
            num_concepts=len(request.available_concepts),
        )

        # Format the concept list for the prompt
        concepts_text = "\n".join(
            f"- **{c['id']}** ({c['label']}): {c.get('description', '')}"
            f"  Synonyms: {', '.join(c.get('synonyms', []))}"
            f"  Hints: {', '.join(c.get('hints', []))}"
            for c in request.available_concepts
        )

        user_message = (
            f"Classify the following document excerpt into one of these concepts:\n\n"
            f"## Available Concepts\n{concepts_text}\n\n"
            f"## Document Excerpt\n{request.text_excerpt}\n\n"
            f"Return your classification as JSON."
        )

        messages = [
            ChatMessage(role="system", content=_CLASSIFICATION_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_message),
        ]

        result = await self._client.complete(messages, self._model, temperature=0.1, max_tokens=300)
        response_text = result.content.strip()

        plog.detail(f"LLM response received", tokens=result.usage.total_tokens)

        # Parse JSON from response (handle markdown code blocks)
        json_str = self._extract_json(response_text)
        data = json.loads(json_str)

        response = LLMClassificationResponse(
            concept_id=data.get("concept_id", "Unknown"),
            confidence=float(data.get("confidence", 0.0)),
            reasoning=data.get("reasoning", ""),
            usage=result.usage,
            model=result.model,
        )

        plog.step_complete(
            PipelineStage.CLASSIFICATION,
            f"LLM classified as '{response.concept_id}'",
            confidence=f"{response.confidence:.2f}",
        )
        return response

    async def extract_metadata(
        self, request: LLMExtractionRequest
    ) -> LLMExtractionResponse:
        """Extract structured metadata using the concept's template fields."""
        plog.step_start(
            PipelineStage.METADATA,
            f"Sending document to LLM for metadata extraction",
            model=self._model,
            concept=request.concept_id,
            num_fields=len(request.template_fields),
        )

        fields_text = "\n".join(
            f"- **{f['name']}** (type: {f['type']}, required: {f.get('required', False)}): "
            f"{f.get('description', '')}"
            for f in request.template_fields
        )

        user_message = (
            f"Extract the following fields from this {request.concept_id} document:\n\n"
            f"## Fields to Extract\n{fields_text}\n\n"
            f"## Document Content\n{request.text[:8000]}\n\n"
            f"Return the extracted values as JSON."
        )

        messages = [
            ChatMessage(role="system", content=_EXTRACTION_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_message),
        ]

        result = await self._client.complete(messages, self._model, temperature=0.1, max_tokens=2000)
        response_text = result.content.strip()

        plog.detail(f"LLM extraction response received", tokens=result.usage.total_tokens)

        json_str = self._extract_json(response_text)
        data = json.loads(json_str)

        summary = data.pop("_summary", "")
        confidence = float(data.pop("_confidence", 0.0))

        response = LLMExtractionResponse(
            properties=data,
            summary=summary,
            confidence=confidence,
            usage=result.usage,
            model=result.model,
        )

        plog.step_complete(
            PipelineStage.METADATA,
            f"Extracted {len(data)} properties via LLM",
            confidence=f"{response.confidence:.2f}",
        )
        return response

    async def ocr_image(
        self, request: LLMVisionOCRRequest
    ) -> LLMVisionOCRResponse:
        """Extract text from an image using LLM vision capabilities."""
        plog.step_start(
            PipelineStage.TEXT_EXTRACTION,
            "Sending image to LLM for OCR",
            model=self._model,
            mime_type=request.mime_type,
        )

        messages = [
            ChatMessage(role="system", content=_OCR_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=[
                    ContentPart(
                        type="image_url",
                        image_url={
                            "url": f"data:{request.mime_type};base64,{request.image_base64}"
                        },
                    ),
                    ContentPart(type="text", text="Extract all text from this image."),
                ],
            ),
        ]

        result = await self._client.complete(messages, self._model, temperature=0.0, max_tokens=4000)

        plog.step_complete(
            PipelineStage.TEXT_EXTRACTION,
            f"OCR completed — {len(result.content)} chars extracted",
            tokens=result.usage.total_tokens,
        )
        return LLMVisionOCRResponse(text=result.content.strip(), confidence=0.85)

    async def process_pdf(
        self, request: LLMPdfProcessingRequest
    ) -> LLMPdfProcessingResponse:
        """Process a PDF file: classify and extract metadata in one integrated call.

        Sends the PDF as a base64 file via OpenRouter's file content type.
        The LLM receives the parsed PDF content and performs both classification
        and metadata extraction in a single response.
        """
        plog.step_start(
            PipelineStage.PDF_LLM,
            f"Sending PDF to LLM for integrated processing",
            model=self._pdf_model,
            filename=request.filename,
            num_concepts=len(request.available_concepts),
            pdf_size_kb=f"{len(request.pdf_base64) * 3 // 4 // 1024}",
        )

        # Build concept descriptions with their extraction templates
        concepts_text_parts = []
        for concept in request.available_concepts:
            cid = concept["id"]
            desc = (
                f"### Concept: **{cid}** ({concept['label']})\n"
                f"Description: {concept.get('description', 'N/A')}\n"
                f"Synonyms: {', '.join(concept.get('synonyms', []))}\n"
                f"Classification hints: {', '.join(concept.get('hints', []))}\n"
            )

            # Add extraction template fields if available
            fields = request.template_fields_by_concept.get(cid, [])
            if fields:
                fields_text = "\n".join(
                    f"  - {f['name']} (type: {f['type']}, required: {f.get('required', False)}): "
                    f"{f.get('description', '')}"
                    for f in fields
                )
                desc += f"Fields to extract:\n{fields_text}\n"
            else:
                desc += "Fields to extract: (none defined)\n"

            concepts_text_parts.append(desc)

        concepts_text = "\n".join(concepts_text_parts)

        user_prompt = (
            f"Process the attached PDF file '{request.filename}'.\n\n"
            f"## Available Document Categories\n\n{concepts_text}\n\n"
            f"Classify this document into the best matching category, then extract "
            f"the metadata fields defined in that category's template.\n\n"
            f"Return your response as a single JSON object."
        )

        plog.detail(f"Prompt constructed with {len(request.available_concepts)} concepts")
        for concept in request.available_concepts:
            fields = request.template_fields_by_concept.get(concept["id"], [])
            plog.detail(f"  Concept '{concept['id']}': {len(fields)} template fields")

        # Construct multimodal message with PDF file
        messages = [
            ChatMessage(role="system", content=_PDF_PROCESSING_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=[
                    ContentPart(
                        type="file",
                        file_data={
                            "file_data": f"data:application/pdf;base64,{request.pdf_base64}",
                            "filename": request.filename,
                        },
                    ),
                    ContentPart(type="text", text=user_prompt),
                ],
            ),
        ]

        plog.detail("Sending request to OpenRouter with PDF file attachment")

        result = await self._client.complete(
            messages, self._pdf_model, temperature=0.1, max_tokens=4000
        )
        response_text = result.content.strip()

        plog.detail(
            f"LLM response received",
            tokens=result.usage.total_tokens,
            finish_reason=result.finish_reason,
        )

        # Parse JSON response
        json_str = self._extract_json(response_text)
        data = json.loads(json_str)

        response = LLMPdfProcessingResponse(
            concept_id=data.get("concept_id", "Unknown"),
            confidence=float(data.get("confidence", 0.0)),
            reasoning=data.get("reasoning", ""),
            extracted_properties=data.get("extracted_properties", {}),
            summary=data.get("summary", ""),
        )

        plog.step_complete(
            PipelineStage.PDF_LLM,
            f"PDF processed — classified as '{response.concept_id}'",
            confidence=f"{response.confidence:.2f}",
            properties_count=len(response.extracted_properties),
            tokens=result.usage.total_tokens,
        )

        return response

    async def process_pdf_with_tools(
        self,
        pdf_base64: str,
        filename: str,
        available_concepts: list[dict[str, Any]],
        tool_handler: ToolHandler,
    ) -> list[LLMPdfProcessingResponse]:
        """Process a PDF using tool calling for schema resolution and multi-doc extraction.

        The LLM drives the workflow by calling tools to:
        1. Fetch the resolved extraction schema for a concept
        2. Submit extracted data for each document found
        """
        plog.step_start(
            PipelineStage.PDF_LLM,
            f"Starting tool-based PDF processing for '{filename}'",
            model=self._pdf_model,
            num_concepts=len(available_concepts),
            pdf_size_kb=f"{len(pdf_base64) * 3 // 4 // 1024}",
        )

        # Build the concept catalogue for the prompt (no template fields — LLM fetches on demand)
        concepts_text_parts = []
        for concept in available_concepts:
            desc = (
                f"- **{concept['id']}** ({concept['label']}): "
                f"{concept.get('description', 'N/A')}. "
                f"Synonyms: {', '.join(concept.get('synonyms', []))}. "
                f"Hints: {', '.join(concept.get('hints', []))}"
            )
            concepts_text_parts.append(desc)

        concepts_text = "\n".join(concepts_text_parts)

        user_prompt = (
            f"Process the attached PDF file '{filename}'.\n\n"
            f"## Available Document Categories\n\n{concepts_text}\n\n"
            f"Follow your workflow: identify all documents, fetch schemas, "
            f"extract properties, and submit each document."
        )

        messages = [
            ChatMessage(role="system", content=_PDF_TOOL_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=[
                    ContentPart(
                        type="file",
                        file_data={
                            "file_data": f"data:application/pdf;base64,{pdf_base64}",
                            "filename": filename,
                        },
                    ),
                    ContentPart(type="text", text=user_prompt),
                ],
            ),
        ]

        tools = [_TOOL_GET_EXTRACTION_SCHEMA, _TOOL_SUBMIT_DOCUMENT]

        # Collect submitted documents via the tool handler
        submitted_documents: list[LLMPdfProcessingResponse] = []

        async def _internal_tool_handler(
            tool_name: str, args: dict[str, Any]
        ) -> dict[str, Any]:
            """Dispatch tool calls, collecting submit_document results."""
            if tool_name == "submit_document":
                doc = LLMPdfProcessingResponse(
                    concept_id=args.get("concept_id", "Unknown"),
                    confidence=float(args.get("confidence", 0.0)),
                    reasoning=args.get("reasoning", ""),
                    extracted_properties=args.get("extracted_properties", {}),
                    summary=args.get("summary", ""),
                    page_range=args.get("page_range"),
                )
                submitted_documents.append(doc)
                plog.detail(
                    f"Document submitted via tool",
                    concept=doc.concept_id,
                    confidence=f"{doc.confidence:.2f}",
                    page_range=doc.page_range,
                    properties=len(doc.extracted_properties),
                )
                return {
                    "status": "accepted",
                    "document_index": len(submitted_documents),
                }

            # Delegate all other tools (get_extraction_schema) to the external handler
            return await tool_handler(tool_name, args)

        plog.detail("Starting tool-calling loop with LLM")

        result = await self._client.complete_with_tools(
            messages,
            self._pdf_model,
            tools=tools,
            tool_handler=_internal_tool_handler,
            temperature=0.1,
            max_tokens=8000,
            max_iterations=10,
        )

        plog.step_complete(
            PipelineStage.PDF_LLM,
            f"Tool-based processing complete for '{filename}'",
            documents_found=len(submitted_documents),
            total_tokens=result.usage.total_tokens,
            final_message=result.content[:100] if result.content else "(none)",
        )

        # Collect tool-calling metadata for logging
        all_tools: list[str] = []
        total_tool_calls = 0
        for doc in submitted_documents:
            total_tool_calls += 1  # Each submit_document is a tool call
        # Count get_extraction_schema calls from the conversation
        # Each submitted doc means at least one get_extraction_schema + one submit_document
        unique_tools = set()
        for msg in result.tool_calls:
            unique_tools.add(msg.function.name)
        # Simple heuristic: unique tool names used in the session
        tool_names = sorted(set(
            ["get_extraction_schema", "submit_document"]
        )) if submitted_documents else []

        # Attach usage/tool metadata to each submitted document for upstream logging
        for doc in submitted_documents:
            doc.usage = result.usage
            doc.model = result.model
            doc.tools_called = tool_names
            doc.tool_call_count = total_tool_calls

        return submitted_documents

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from a response that might be wrapped in markdown code blocks."""
        # Try to extract from ```json ... ``` blocks
        if "```" in text:
            import re
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
            if match:
                return match.group(1).strip()

        # Try the raw text as JSON
        text = text.strip()
        if text.startswith("{"):
            return text

        raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")


