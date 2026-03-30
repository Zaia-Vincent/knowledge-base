"""Unit tests for OpenRouterLLMClient._extract_json helper."""

import json

import pytest

from app.infrastructure.llm.openrouter_llm_client import OpenRouterLLMClient


class TestExtractJson:
    """Verifies that _extract_json handles all common LLM response formats."""

    @staticmethod
    def _extract(text: str) -> str:
        return OpenRouterLLMClient._extract_json(text)


    # ── Code-fenced JSON ─────────────────────────────────────────────

    def test_fenced_json_with_newlines(self):
        """Standard ```json ... ``` with newlines before/after content."""
        raw = '```json\n{"key": "value"}\n```'
        parsed = json.loads(self._extract(raw))
        assert parsed["key"] == "value"

    def test_fenced_json_without_trailing_newline(self):
        """Closing ``` immediately after JSON (the bug case)."""
        raw = '```json\n{"key": "value"}```'
        parsed = json.loads(self._extract(raw))
        assert parsed["key"] == "value"

    def test_fenced_json_multiline_no_trailing_newline(self):
        """Multi-line JSON where closing } is directly followed by ```."""
        raw = '```json\n{\n  "a": 1,\n  "b": 2\n}```'
        parsed = json.loads(self._extract(raw))
        assert parsed == {"a": 1, "b": 2}

    def test_fenced_json_with_extra_whitespace(self):
        """Closing ``` has leading whitespace."""
        raw = '```json\n{"key": "value"}\n  ```'
        parsed = json.loads(self._extract(raw))
        assert parsed["key"] == "value"

    def test_fenced_without_json_label(self):
        """``` block without 'json' language specifier."""
        raw = '```\n{"key": "value"}\n```'
        parsed = json.loads(self._extract(raw))
        assert parsed["key"] == "value"

    def test_fenced_json_with_surrounding_text(self):
        """Code block embedded in explanatory text."""
        raw = 'Here is the result:\n```json\n{"key": "value"}\n```\nDone.'
        parsed = json.loads(self._extract(raw))
        assert parsed["key"] == "value"

    # ── Plain JSON ───────────────────────────────────────────────────

    def test_plain_json_object(self):
        """Raw JSON object without code block wrapping."""
        raw = '{"key": "value"}'
        parsed = json.loads(self._extract(raw))
        assert parsed["key"] == "value"

    def test_plain_json_array(self):
        """Raw JSON array."""
        raw = '[{"key": "value"}]'
        parsed = json.loads(self._extract(raw))
        assert parsed[0]["key"] == "value"

    def test_plain_json_with_whitespace(self):
        """JSON with surrounding whitespace."""
        raw = '  \n{"key": "value"}\n  '
        parsed = json.loads(self._extract(raw))
        assert parsed["key"] == "value"

    # ── Fallback: { ... } boundary detection ─────────────────────────

    def test_json_with_surrounding_text_no_fence(self):
        """JSON embedded in text without code blocks."""
        raw = 'Some explanation. {"id": "test"} More text.'
        parsed = json.loads(self._extract(raw))
        assert parsed["id"] == "test"

    # ── Error case ───────────────────────────────────────────────────

    def test_no_json_raises_value_error(self):
        """When no JSON is found at all, raise ValueError."""
        with pytest.raises(ValueError, match="Could not extract JSON"):
            self._extract("no json here at all")

    # ── Complex extraction cases ─────────────────────────────────────

    def test_extraction_response_format(self):
        """Realistic metadata extraction response with _summary and _confidence."""
        raw = '''```json
{
  "document_date": "2025-03-15",
  "document_type": "Regulation",
  "summary": "EU AI Act compliance guidance",
  "issuing_body": "European Commission",
  "_summary": "An article on EU AI Act compliance.",
  "_confidence": 0.85
}
```'''
        parsed = json.loads(self._extract(raw))
        assert parsed["document_type"] == "Regulation"
        assert parsed["_confidence"] == 0.85
