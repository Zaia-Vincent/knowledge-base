"""Query service — translates natural-language questions into ontology search.

Two-stage flow:
  1. Intent Resolution: LLM maps the user's question to structured ontology terms.
  2. Database Search: FileRepository queries processed files using resolved filters.
"""

import json
import logging
import time
from typing import Any

from app.application.interfaces.chat_provider import ChatProvider
from app.application.interfaces.file_repository import FileRepository
from app.application.interfaces.ontology_repository import OntologyRepository
from app.application.services.llm_usage_logger import LLMUsageLogger
from app.domain.entities.query import (
    MetadataFilter,
    QueryIntent,
    QueryMatch,
    QueryResult,
)

logger = logging.getLogger(__name__)

# ── System prompt for intent resolution ─────────────────────────────

_INTENT_SYSTEM_PROMPT = """\
You are an ontology-aware query interpreter for a knowledge management system.

Your task: translate the user's natural-language question into a structured JSON
search intent that can be used to query a document database.

The knowledge database contains processed files. Each file has been classified
against an ontology concept and has extracted metadata properties.

## Available Ontology Concepts

{concepts_json}

## Rules

1. Identify which ontology concept(s) the question refers to.
2. Extract any metadata filters the user implies (e.g. "invoices from Acme"
   → concept "Invoice", metadata filter vendor_name contains "Acme").
3. Extract a text search query if the user is looking for specific content.
4. Detect the language of the question.
5. Provide brief reasoning for your choices.

## Response Format (strict JSON, no markdown)

{{
  "concept_ids": ["ConceptId1"],
  "concept_labels": ["Human Label 1"],
  "metadata_filters": [
    {{"field_name": "property_name", "value": "search_value", "operator": "contains"}}
  ],
  "keywords": ["keyword1", "keyword2"],
  "text_query": "optional full-text search string or null",
  "resolved_language": "nl",
  "reasoning": "Brief explanation of how you interpreted the question"
}}

Valid operators: "contains", "equals", "gte", "lte"

If the question is too vague to determine specific concepts, return an empty
concept_ids list and put relevant keywords in the keywords field.
Respond ONLY with valid JSON. No markdown fences, no explanation outside the JSON.
"""


class QueryService:
    """Application service for natural-language knowledge queries.

    Orchestrates LLM-based intent resolution and database search.
    """

    def __init__(
        self,
        chat_provider: ChatProvider,
        ontology_repo: OntologyRepository,
        file_repo: FileRepository,
        usage_logger: LLMUsageLogger,
        *,
        model: str = "",
    ):
        self._chat_provider = chat_provider
        self._ontology_repo = ontology_repo
        self._file_repo = file_repo
        self._usage_logger = usage_logger
        self._model = model

    async def query(
        self,
        question: str,
        *,
        max_results: int = 20,
    ) -> QueryResult:
        """Full query flow: resolve intent → search database → return results."""
        intent = await self.resolve_intent(question)
        return await self.execute_query(intent, max_results=max_results)

    async def resolve_intent(self, question: str) -> QueryIntent:
        """Stage 1: Use LLM to translate question into structured search intent."""
        from app.domain.entities import ChatMessage

        # Build ontology context (slim representation for the prompt)
        concepts_summary = await self._build_ontology_context()
        system_prompt = _INTENT_SYSTEM_PROMPT.format(
            concepts_json=json.dumps(concepts_summary, indent=2, ensure_ascii=False),
        )

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=question),
        ]

        start = time.monotonic()

        try:
            result = await self._chat_provider.complete(
                messages=messages,
                model=self._model,
                temperature=0.1,
                max_tokens=1024,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            await self._usage_logger.log_request(
                model=result.model or self._model,
                provider=result.provider or self._chat_provider.provider_name,
                feature="query_intent",
                usage=result.usage,
                duration_ms=duration_ms,
            )

            intent = self._parse_intent(question, result.content)
            logger.info(
                "Resolved query intent: concepts=%s, filters=%d, keywords=%s",
                intent.concept_ids,
                len(intent.metadata_filters),
                intent.keywords,
            )
            return intent

        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error("Intent resolution failed: %s", e)
            await self._usage_logger.log_error(
                model=self._model,
                provider=self._chat_provider.provider_name,
                feature="query_intent",
                duration_ms=duration_ms,
                error=e,
            )
            # Fallback: return a basic intent with the original question as text query
            return QueryIntent(
                original_question=question,
                text_query=question,
                reasoning="Fallback: LLM intent resolution failed.",
            )

    async def execute_query(
        self,
        intent: QueryIntent,
        *,
        max_results: int = 20,
    ) -> QueryResult:
        """Stage 2: Search the knowledge database using the resolved intent."""
        files = await self._file_repo.search(
            concept_ids=intent.concept_ids or None,
            metadata_filters=intent.metadata_filters or None,
            text_query=intent.text_query,
            limit=max_results,
        )

        matches = [
            QueryMatch(
                file_id=f.id or "",
                filename=f.filename,
                concept_id=f.classification.primary_concept_id if f.classification else None,
                concept_label=None,
                confidence=f.classification.confidence if f.classification else 0.0,
                summary=f.summary,
                metadata=f.metadata,
                relevance_score=f.classification.confidence if f.classification else 0.0,
            )
            for f in files
        ]

        return QueryResult(
            intent=intent,
            matches=matches,
            total_matches=len(matches),
        )

    # ── Private helpers ──────────────────────────────────────────────

    async def _build_ontology_context(self) -> list[dict[str, Any]]:
        """Build a slim ontology summary for the LLM prompt."""
        concepts = await self._ontology_repo.get_all_concepts()
        summary = []
        for c in concepts:
            if c.abstract:
                continue  # Skip abstract concepts — not searchable

            entry: dict[str, Any] = {
                "id": c.id,
                "label": c.label,
                "description": c.description[:200] if c.description else "",
                "synonyms": c.synonyms,
            }

            # Include property names so LLM can create metadata filters
            if c.properties:
                entry["properties"] = [
                    {"name": p.name, "type": p.type}
                    for p in c.properties
                ]

            summary.append(entry)

        return summary

    @staticmethod
    def _parse_intent(question: str, llm_response: str) -> QueryIntent:
        """Parse the LLM's JSON response into a QueryIntent."""
        # Strip potential markdown fences
        text = llm_response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (the fences)
            text = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:])
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # LLMs (especially Gemini) may wrap JSON in thinking tokens
            # e.g. "start_thought\n{...}\nend_thought" — extract the JSON object.
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                try:
                    data = json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    data = None
            else:
                data = None

            if data is None:
                logger.warning("Failed to parse LLM intent response: %s", text[:200])
                return QueryIntent(
                    original_question=question,
                    text_query=question,
                    reasoning="Fallback: could not parse LLM response as JSON.",
                )

        metadata_filters = [
            MetadataFilter(
                field_name=f.get("field_name", ""),
                value=f.get("value", ""),
                operator=f.get("operator", "contains"),
            )
            for f in data.get("metadata_filters", [])
            if f.get("field_name") and f.get("value")
        ]

        return QueryIntent(
            original_question=question,
            resolved_language=data.get("resolved_language", "en"),
            concept_ids=data.get("concept_ids", []),
            concept_labels=data.get("concept_labels", []),
            metadata_filters=metadata_filters,
            keywords=data.get("keywords", []),
            text_query=data.get("text_query"),
            reasoning=data.get("reasoning", ""),
        )
