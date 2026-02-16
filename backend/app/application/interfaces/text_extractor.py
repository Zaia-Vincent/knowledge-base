"""Abstract interface (port) for text extraction from various file formats."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TextExtractionResult:
    """Result of extracting text from a file."""

    text: str
    page_count: int | None = None
    language: str | None = None
    needs_ocr: bool = False  # True if only images/scans were found
    ocr_image_base64: str | None = None  # base64 image for LLM vision OCR
    ocr_mime_type: str | None = None


class TextExtractor(ABC):
    """Port for text extraction — implemented in the infrastructure layer."""

    @abstractmethod
    async def extract(self, file_path: str, mime_type: str) -> TextExtractionResult:
        """Extract text content from a file.

        Args:
            file_path: Absolute path to the file on disk.
            mime_type: MIME type of the file.

        Returns:
            TextExtractionResult with extracted text or OCR data.
        """
        ...

    @abstractmethod
    def supports(self, mime_type: str) -> bool:
        """Check if the extractor supports the given MIME type."""
        ...
