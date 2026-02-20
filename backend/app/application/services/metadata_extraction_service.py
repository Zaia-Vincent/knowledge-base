"""Metadata extraction service — template-driven LLM extraction with normalization.

After a file is classified, this service:
1. Fetches the extraction template for the matched concept
2. Builds an LLM prompt with template fields + document text
3. Parses the LLM JSON response into JSONB-compatible metadata dicts
4. Normalizes dates, amounts, and currencies (language-aware: NL/EN)
"""

import ast
import logging
import re
import time
from datetime import datetime
from typing import Any

from app.application.interfaces import OntologyRepository
from app.application.interfaces.llm_client import (
    LLMClient,
    LLMExtractionRequest,
)
from app.domain.entities import (
    ClassificationResult,
    OntologyConcept,
)
from app.infrastructure.logging.colored_logger import PipelineLogger, PipelineStage

logger = logging.getLogger(__name__)
plog = PipelineLogger("MetadataExtractionService")


class MetadataExtractionService:
    """Application service for template-driven metadata extraction from documents.

    Uses the ontology's extraction templates to determine which fields to extract,
    then delegates to an LLM for actual extraction, and normalizes the results.
    """

    def __init__(
        self,
        ontology_repo: OntologyRepository,
        llm_client: LLMClient | None = None,
        usage_logger=None,
    ):
        self._ontology_repo = ontology_repo
        self._llm_client = llm_client
        self._usage_logger = usage_logger

    async def extract(
        self,
        *,
        text: str,
        classification: ClassificationResult,
        image_base64: str | None = None,
        mime_type: str | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
        """Extract metadata from a classified document.

        Args:
            text: Full extracted text of the document.
            classification: The classification result (concept_id + confidence).
            image_base64: Optional base64-encoded image for vision-based extraction.
            mime_type: Image MIME type (required when image_base64 is set).

        Returns:
            Tuple of (metadata dict, extra_fields list, summary text).
        """
        concept = await self._ontology_repo.get_concept(classification.primary_concept_id)

        if not concept:
            logger.warning(
                "Concept '%s' not found in ontology — skipping extraction",
                classification.primary_concept_id,
            )
            return {}, [], ""

        resolved_properties = await self._resolve_properties(concept)
        if not resolved_properties:
            logger.info(
                "Concept '%s' has no resolved properties — skipping extraction",
                concept.id,
            )
            return {}, [], ""

        # Build template fields from resolved properties (ancestors + mixins + self)
        template_fields = [
            {
                "name": prop.name,
                "type": prop.type,
                "required": prop.required,
                "description": prop.description,
            }
            for prop in resolved_properties
        ]

        # If LLM is available, use it for extraction
        if self._llm_client:
            return await self._extract_with_llm(
                text, concept, template_fields,
                image_base64=image_base64, mime_type=mime_type,
            )

        # Fallback: attempt rule-based extraction for common patterns
        return self._extract_rule_based(text, concept, template_fields), [], ""

    async def _extract_with_llm(
        self,
        text: str,
        concept: OntologyConcept,
        template_fields: list[dict],
        *,
        image_base64: str | None = None,
        mime_type: str | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
        """Use LLM to extract metadata based on the concept's template."""
        try:
            request = LLMExtractionRequest(
                text=text,
                concept_id=concept.id,
                template_fields=template_fields,
                image_base64=image_base64,
                mime_type=mime_type,
            )

            start = time.monotonic()
            response = await self._llm_client.extract_metadata(request)
            duration_ms = int((time.monotonic() - start) * 1000)

            # Log usage if logger available
            if self._usage_logger and response.usage:
                await self._usage_logger.log_request(
                    model=response.model or "unknown",
                    provider="openrouter",
                    feature="extraction",
                    usage=response.usage,
                    duration_ms=duration_ms,
                    request_context=concept.id,
                )

            metadata: dict[str, Any] = {}
            for field in template_fields:
                field_name = field["name"]
                raw_value = response.properties.get(field_name)

                if raw_value is None:
                    continue

                entry = _normalize_value(field_name, field["type"], raw_value)
                if entry:
                    entry["confidence"] = response.confidence
                    metadata[field_name] = entry

            return metadata, [], response.summary

        except Exception:
            logger.exception("LLM extraction failed — falling back to rule-based")
            return self._extract_rule_based(text, concept, template_fields), [], ""

    def _extract_rule_based(
        self,
        text: str,
        concept: OntologyConcept,
        template_fields: list[dict],
    ) -> dict[str, Any]:
        """Fallback: try to extract values using regex patterns."""
        metadata: dict[str, Any] = {}
        text_lower = text.lower()

        for field in template_fields:
            name = field["name"]
            field_type = field["type"]
            value = None

            # Try to find the field name followed by a value in the text
            # Patterns: "Field Name: value" or "Field Name = value"
            name_lower = name.lower().replace("_", " ")
            pattern = rf"(?:{re.escape(name_lower)}|{re.escape(name.lower())})\s*[:=]\s*(.+?)(?:\n|$)"
            match = re.search(pattern, text_lower)

            if match:
                value = match.group(1).strip()

            if value:
                entry = _normalize_value(name, field_type, value)
                if entry:
                    entry["confidence"] = 0.4  # Lower confidence for rule-based
                    metadata[name] = entry

        return metadata

    async def _resolve_properties(self, concept: OntologyConcept) -> list[Any]:
        """Resolve properties for extraction: ancestors + mixins + own fields."""
        ancestors = await self._ontology_repo.get_ancestors(concept.id)
        chain = ancestors + [concept]  # root -> leaf

        mixin_cache: dict[str, Any] = {}
        resolved: dict[str, Any] = {}
        for node in chain:
            for mixin_id in node.mixins:
                if mixin_id not in mixin_cache:
                    mixin_cache[mixin_id] = await self._ontology_repo.get_mixin(mixin_id)
                mixin = mixin_cache.get(mixin_id)
                if mixin:
                    for prop in mixin.properties:
                        resolved[prop.name] = prop
            for prop in node.properties:
                resolved[prop.name] = prop

        return list(resolved.values())


# ── Value Normalization (Language-aware: NL/EN) ──────────────────────


def _normalize_value(
    field_name: str,
    field_type: str,
    raw_value,
) -> dict[str, Any] | None:
    """Normalize a raw extracted value based on the field type.

    Returns a JSONB-compatible dict: {"value": ..., "confidence": 0.0}

    Handles:
    - Dates: ISO 8601, DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD
    - Numbers/Amounts: Dutch (1.250,00) and English (1,250.00) formats
    - Strings: stripped text
    """
    if raw_value is None:
        return None

    # Handle reference types (ref:Vendor, ref:Organisation, etc.)
    if field_type.startswith("ref:"):
        return _normalize_ref(field_name, raw_value)

    # Handle embedded array types (InvoiceLineItem[], etc.)
    if field_type.endswith("[]"):
        return _normalize_array(field_name, raw_value)

    raw_str = str(raw_value).strip()
    if not raw_str or raw_str.lower() in ("null", "none", "n/a", "-"):
        return None

    if field_type in ("date", "datetime"):
        return _normalize_date(field_name, raw_str)
    elif field_type in ("number", "decimal", "float", "integer", "amount", "currency"):
        return _normalize_number(field_name, raw_str)
    else:
        return {"value": raw_str, "confidence": 0.0}


def _normalize_date(field_name: str, raw: str) -> dict[str, Any] | None:
    """Parse dates in various formats to a JSONB-compatible dict."""
    date_formats = [
        # ISO 8601
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        # European
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        # US
        "%m/%d/%Y",
        "%m-%d-%Y",
        # Verbose
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]

    # Clean common prefixes
    cleaned = re.sub(r"^(datum|date|op|van|from|tot|until)\s*[:=]?\s*", "", raw, flags=re.I).strip()

    for fmt in date_formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return {"value": dt.strftime("%Y-%m-%d"), "raw_text": cleaned, "confidence": 0.0}
        except ValueError:
            continue

    # Fallback: store as text
    return {"value": cleaned, "confidence": 0.0}


def _normalize_number(field_name: str, raw: str) -> dict[str, Any] | None:
    """Parse numbers in Dutch or English format to a JSONB-compatible dict.

    Dutch format: 1.250,50 (dots as thousands, comma as decimal)
    English format: 1,250.50 (commas as thousands, dot as decimal)
    """
    # Remove currency symbols and whitespace
    cleaned = re.sub(r"[€$£¥\s]", "", raw)
    cleaned = cleaned.strip()

    if not cleaned:
        return None

    try:
        numeric_value = _parse_numeric(cleaned)
        return {"value": numeric_value, "raw_text": raw, "confidence": 0.0}
    except ValueError:
        return {"value": raw, "confidence": 0.0}


def _parse_numeric(s: str) -> float:
    """Parse a numeric string in either Dutch or English format."""
    # Remove spaces
    s = s.replace(" ", "")

    # Determine if Dutch format (comma as decimal separator)
    # Pattern: digits possibly with dots as thousands, comma, then 1-2 decimal digits
    dutch_pattern = r"^-?\d{1,3}(?:\.\d{3})*,\d{1,2}$"
    english_pattern = r"^-?\d{1,3}(?:,\d{3})*\.\d{1,2}$"

    if re.match(dutch_pattern, s):
        # Dutch: 1.250,50 → 1250.50
        return float(s.replace(".", "").replace(",", "."))

    if re.match(english_pattern, s):
        # English: 1,250.50 → 1250.50
        return float(s.replace(",", ""))

    # Simple formats: just a number with optional comma or dot
    if re.match(r"^-?\d+,\d{1,2}$", s):
        # Simple Dutch: 250,50
        return float(s.replace(",", "."))

    if re.match(r"^-?\d+\.?\d*$", s):
        # Simple number or English decimal
        return float(s)

    if re.match(r"^-?\d+$", s):
        # Integer
        return float(s)

    raise ValueError(f"Cannot parse '{s}' as a number")


# ── Reference & Array Normalization ──────────────────────────────────


def _normalize_ref(
    field_name: str,
    raw_value: Any,
) -> dict[str, Any] | None:
    """Normalize a reference type value to a proper JSON object.

    Handles:
    - Python dicts: {'label': 'Deli Tyres bv'} → {"label": "Deli Tyres bv"}
    - Stringified Python dicts: "{'label': 'Deli Tyres bv'}" → parsed and stored as JSON object
    - Plain strings: "Deli Tyres bv" → {"label": "Deli Tyres bv"}
    """
    if raw_value is None:
        return None

    if isinstance(raw_value, dict):
        # Already a proper dict — use directly
        return {"value": raw_value, "confidence": 0.0}

    raw_str = str(raw_value).strip()
    if not raw_str or raw_str.lower() in ("null", "none", "n/a", "-"):
        return None

    # Try to parse stringified Python dict
    if raw_str.startswith("{") and raw_str.endswith("}"):
        try:
            parsed = ast.literal_eval(raw_str)
            if isinstance(parsed, dict):
                return {"value": parsed, "confidence": 0.0}
        except (ValueError, SyntaxError):
            pass

    # Fallback: wrap plain string as a label
    return {"value": {"label": raw_str}, "confidence": 0.0}


def _normalize_array(
    field_name: str,
    raw_value: Any,
) -> dict[str, Any] | None:
    """Normalize an embedded array type value to a proper JSON array.

    Handles:
    - Python lists: [{'line_total': 159.5, ...}] → stored as JSON array
    - Stringified Python lists: "[{'line_total': 159.5}]" → parsed and stored as JSON array
    - Single dicts: {'line_total': 159.5} → wrapped as [{...}]
    """
    if raw_value is None:
        return None

    if isinstance(raw_value, list):
        # Already a proper list — use directly
        return {"value": raw_value, "confidence": 0.0}

    if isinstance(raw_value, dict):
        # Single item — wrap in array
        return {"value": [raw_value], "confidence": 0.0}

    raw_str = str(raw_value).strip()
    if not raw_str or raw_str.lower() in ("null", "none", "n/a", "-", "[]"):
        return None

    # Try to parse stringified Python list
    if raw_str.startswith("[") and raw_str.endswith("]"):
        try:
            parsed = ast.literal_eval(raw_str)
            if isinstance(parsed, list):
                return {"value": parsed, "confidence": 0.0}
        except (ValueError, SyntaxError):
            pass

    # Fallback: store the raw string as text value in a single-element array
    return {"value": raw_str, "confidence": 0.0}
