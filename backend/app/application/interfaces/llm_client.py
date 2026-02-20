"""Abstract interface (port) for LLM operations used in classification and extraction."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Awaitable
from dataclasses import dataclass, field
from typing import Any

from app.domain.entities.chat_message import TokenUsage

# Type alias for tool handler callbacks used in tool-calling workflows
ToolHandler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class LLMClassificationRequest:
    """Request payload for LLM-based document classification."""

    text_excerpt: str
    available_concepts: list[dict[str, Any]]  # [{id, label, synonyms, hints}]


@dataclass
class LLMClassificationResponse:
    """Response from LLM classification."""

    concept_id: str
    confidence: float
    reasoning: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ""


@dataclass
class LLMExtractionRequest:
    """Request payload for LLM-based metadata extraction."""

    text: str
    concept_id: str
    template_fields: list[dict[str, Any]]  # [{name, type, required, description}]
    image_base64: str | None = None  # Optional: base64-encoded image for vision-based extraction
    mime_type: str | None = None  # e.g. "image/jpeg" — required when image_base64 is set


@dataclass
class LLMExtractionResponse:
    """Response from LLM metadata extraction."""

    properties: dict[str, Any]  # {field_name: extracted_value}
    summary: str = ""
    confidence: float = 0.0
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ""


@dataclass
class LLMVisionOCRRequest:
    """Request payload for LLM vision-based OCR."""

    image_base64: str
    mime_type: str = "image/png"


@dataclass
class LLMVisionOCRResponse:
    """Response from LLM vision OCR."""

    text: str
    confidence: float = 0.0


@dataclass
class LLMPdfProcessingRequest:
    """Request payload for integrated PDF processing (classify + extract in one call)."""

    pdf_base64: str
    filename: str
    available_concepts: list[dict[str, Any]]  # [{id, label, description, synonyms, hints}]
    template_fields_by_concept: dict[str, list[dict[str, Any]]]  # {concept_id: [{name, type, ...}]}


@dataclass
class LLMPdfProcessingResponse:
    """Response from integrated PDF processing (one per detected document)."""

    concept_id: str
    confidence: float
    reasoning: str = ""
    extracted_properties: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    page_range: str | None = None  # e.g. "1-2", "3-3" — set by multi-doc detection
    usage: TokenUsage = field(default_factory=TokenUsage)  # Aggregated across tool-calling loop
    model: str = ""
    tools_called: list[str] = field(default_factory=list)
    tool_call_count: int = 0


class LLMClient(ABC):
    """Port for LLM interactions — implemented in infrastructure layer."""

    @abstractmethod
    async def classify_document(
        self, request: LLMClassificationRequest
    ) -> LLMClassificationResponse:
        """Classify a document against the ontology concepts."""
        ...

    @abstractmethod
    async def extract_metadata(
        self, request: LLMExtractionRequest
    ) -> LLMExtractionResponse:
        """Extract structured metadata from a document using a template."""
        ...

    @abstractmethod
    async def ocr_image(
        self, request: LLMVisionOCRRequest
    ) -> LLMVisionOCRResponse:
        """Extract text from an image using LLM vision capabilities."""
        ...

    @abstractmethod
    async def process_pdf(
        self, request: LLMPdfProcessingRequest
    ) -> LLMPdfProcessingResponse:
        """Process a PDF file: classify and extract metadata in one integrated call."""
        ...

    @abstractmethod
    async def process_pdf_with_tools(
        self,
        pdf_base64: str,
        filename: str,
        available_concepts: list[dict[str, Any]],
        tool_handler: ToolHandler,
    ) -> list[LLMPdfProcessingResponse]:
        """Process a PDF using tool calling for schema resolution and multi-doc extraction.

        The LLM drives the workflow:
        1. Reads the PDF and identifies document type(s)
        2. Calls get_extraction_schema to fetch the resolved property list
        3. Calls submit_document for each document found

        Args:
            pdf_base64: Base64-encoded PDF content.
            filename: Original filename.
            available_concepts: Concept catalogue [{id, label, description, synonyms, hints}].
            tool_handler: Callback to handle tool calls (get_extraction_schema, submit_document).

        Returns:
            List of processing results, one per detected document.
        """
        ...

    @abstractmethod
    async def process_image_with_tools(
        self,
        image_base64: str,
        mime_type: str,
        source_url: str,
        available_concepts: list[dict[str, Any]],
        tool_handler: ToolHandler,
    ) -> list[LLMPdfProcessingResponse]:
        """Process a webpage screenshot using vision + tool calling.

        Same workflow as process_pdf_with_tools but with an image instead of PDF:
        1. LLM sees the screenshot and identifies content type(s)
        2. Calls get_extraction_schema to fetch properties for the matched concept
        3. Calls submit_document for each piece of content found

        Args:
            image_base64: Base64-encoded screenshot (PNG/JPEG).
            mime_type: Image MIME type (e.g. "image/png").
            source_url: Original URL the screenshot was taken from.
            available_concepts: Concept catalogue.
            tool_handler: Callback for get_extraction_schema tool calls.

        Returns:
            List of processing results, one per detected content item.
        """
        ...
