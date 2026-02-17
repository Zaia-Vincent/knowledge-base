"""Query service — translates natural-language questions into ontology search.

Two-stage flow:
  1. Intent Resolution: LLM maps the user's question to structured ontology terms.
  2. Database Search: FileRepository queries processed files using resolved filters.
"""

import json
import logging
import re
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
   → concept "Invoice", metadata filter vendor contains "Acme").
3. Extract a text search query if the user is looking for specific content.
4. Detect the language of the question.
5. Provide brief reasoning for your choices.
6. Use ONLY property names that appear in the ontology context.
7. Do not invent fields like "vendor_name" when the ontology property is "vendor".
8. Map relationship phrases to ontology fields when possible:
   - "invoices from Donckers" / "received from Donckers" / "facturen van Donckers"
     usually means metadata filter on vendor (or supplier-like field).

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
        logger.info(
            "Query intent start: question=%r, ontology_concepts=%d",
            question,
            len(concepts_summary),
        )
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

            logger.info("Query intent raw LLM response: %s", self._clip(result.content, 1200))

            intent = self._parse_intent(question, result.content)
            logger.info("Query intent parsed: %s", self._intent_as_dict(intent))
            intent = self._canonicalize_intent(intent, concepts_summary)
            intent = self._apply_question_fallbacks(intent, question, concepts_summary)

            logger.info(
                "Query intent resolved: %s",
                self._intent_as_dict(intent),
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
        has_structured_filters = bool(intent.concept_ids or intent.metadata_filters)
        logger.info(
            "Executing query search: concepts=%s filters=%s text_query=%r limit=%d",
            intent.concept_ids,
            self._filters_as_dict(intent.metadata_filters),
            intent.text_query,
            max_results,
        )
        files = await self._file_repo.search(
            concept_ids=intent.concept_ids or None,
            metadata_filters=intent.metadata_filters or None,
            text_query=intent.text_query,
            limit=max_results,
        )

        # If strict free-text phrase produced no results, retry with only
        # structured ontology filters. This avoids false negatives for
        # natural-language text_query values like "invoices from DONCKERS".
        if not files and intent.text_query and has_structured_filters:
            logger.info(
                "Query retry without text_query after zero results. "
                "original_text_query=%r concepts=%s filters=%s",
                intent.text_query,
                intent.concept_ids,
                self._filters_as_dict(intent.metadata_filters),
            )
            files = await self._file_repo.search(
                concept_ids=intent.concept_ids or None,
                metadata_filters=intent.metadata_filters or None,
                text_query=None,
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

        logger.info(
            "Query search complete: total_matches=%d sample_files=%s",
            len(matches),
            [m.filename for m in matches[:5]],
        )

        return QueryResult(
            intent=intent,
            matches=matches,
            total_matches=len(matches),
        )

    # ── Private helpers ──────────────────────────────────────────────

    async def _build_ontology_context(self) -> list[dict[str, Any]]:
        """Build a slim ontology summary for the LLM prompt."""
        concepts = await self._ontology_repo.get_all_concepts()
        concepts_by_id = {c.id: c for c in concepts}
        mixin_cache: dict[str, Any] = {}
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

            # Include resolved property names (inherited + mixins) so LLM can
            # create valid metadata filters for concrete concepts.
            resolved_props = await self._resolve_properties_for_context(
                c, concepts_by_id, mixin_cache
            )
            if resolved_props:
                entry["properties"] = [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description or "",
                    }
                    for p in resolved_props
                ]

            summary.append(entry)

        return summary

    async def _resolve_properties_for_context(
        self,
        concept,
        concepts_by_id: dict[str, Any],
        mixin_cache: dict[str, Any],
    ) -> list[Any]:
        """Resolve properties for prompt context: ancestors + mixins + self."""
        chain = []
        current = concept
        seen_ids: set[str] = set()
        while current and current.id not in seen_ids:
            seen_ids.add(current.id)
            chain.append(current)
            parent_id = current.inherits
            current = concepts_by_id.get(parent_id) if parent_id else None
        chain.reverse()  # root -> leaf

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

    @staticmethod
    def _canonicalize_intent(
        intent: QueryIntent,
        concepts_summary: list[dict[str, Any]],
    ) -> QueryIntent:
        """Normalize concept IDs and metadata field names to ontology terms."""
        if not concepts_summary:
            return intent

        # ── Concept ID normalization ────────────────────────────────
        concept_aliases: dict[str, str] = {}
        for c in concepts_summary:
            concept_id = c.get("id", "")
            if not concept_id:
                continue
            concept_aliases[concept_id.lower()] = concept_id
            label = (c.get("label") or "").strip().lower()
            if label:
                concept_aliases[label] = concept_id
            for synonym in c.get("synonyms", []):
                syn = str(synonym).strip().lower()
                if syn:
                    concept_aliases[syn] = concept_id

        normalized_concepts: list[str] = []
        for raw in intent.concept_ids:
            key = str(raw).strip().lower()
            mapped = concept_aliases.get(key, raw)
            if mapped and mapped not in normalized_concepts:
                normalized_concepts.append(mapped)

        # If concept_ids were weak/empty but labels are present, try labels.
        if not normalized_concepts and intent.concept_labels:
            for raw in intent.concept_labels:
                key = str(raw).strip().lower()
                mapped = concept_aliases.get(key)
                if mapped and mapped not in normalized_concepts:
                    normalized_concepts.append(mapped)

        intent.concept_ids = normalized_concepts

        # ── Metadata field normalization ────────────────────────────
        candidate_concepts = [
            c for c in concepts_summary if c.get("id") in intent.concept_ids
        ] or concepts_summary

        field_specs: dict[str, dict[str, Any]] = {}
        for concept in candidate_concepts:
            for prop in concept.get("properties", []):
                name = prop.get("name")
                if name:
                    field_specs[name] = prop

        alias_map: dict[str, str] = {}
        for name, spec in field_specs.items():
            key = name.lower()
            alias_map[key] = name
            alias_map[key.replace("-", "_")] = name
            field_type = str(spec.get("type", ""))
            if field_type.startswith("ref:"):
                alias_map[f"{key}_name"] = name
                alias_map[f"{key}_label"] = name
                alias_map[f"{key}.label"] = name

        # Common legacy aliases used in older docs/examples.
        for legacy, target in {
            "vendor_name": "vendor",
            "supplier_name": "vendor",
            "vendor_label": "vendor",
        }.items():
            if target in field_specs:
                alias_map[legacy] = target

        allowed_ops = {"contains", "equals", "gte", "lte"}
        normalized_filters: list[MetadataFilter] = []
        for mf in intent.metadata_filters:
            raw_field = str(mf.field_name).strip()
            field_key = raw_field.lower()
            canonical_field = alias_map.get(field_key)

            if not canonical_field and field_key.endswith("_name"):
                canonical_field = alias_map.get(field_key[: -len("_name")])
            if not canonical_field and "." in field_key:
                canonical_field = alias_map.get(field_key.split(".", 1)[0])

            operator = str(mf.operator).strip().lower()
            if operator not in allowed_ops:
                operator = "contains"

            normalized_filters.append(
                MetadataFilter(
                    field_name=canonical_field or raw_field,
                    value=str(mf.value).strip(),
                    operator=operator,
                )
            )

        intent.metadata_filters = normalized_filters
        return intent

    @classmethod
    def _apply_question_fallbacks(
        cls,
        intent: QueryIntent,
        question: str,
        concepts_summary: list[dict[str, Any]],
    ) -> QueryIntent:
        """Apply deterministic fallback mappings when LLM intent is incomplete."""
        if not question.strip():
            return intent

        # Fallback 1: infer concept IDs from ontology labels/synonyms if needed.
        if not intent.concept_ids:
            inferred = cls._infer_concepts_from_question(question, concepts_summary)
            if inferred:
                intent.concept_ids = inferred
                logger.info("Applied concept fallback from question text: %s", inferred)

        # Fallback 2: map "from/van X" party phrases to vendor-like fields.
        party_value = cls._extract_party_value_from_question(question)
        if not party_value:
            return intent

        candidate_concepts = [
            c for c in concepts_summary if c.get("id") in intent.concept_ids
        ] or concepts_summary
        party_field = cls._pick_party_field(candidate_concepts)
        if not party_field:
            return intent

        already_present = any(
            f.field_name.lower() == party_field.lower()
            for f in intent.metadata_filters
        )
        if already_present:
            return intent

        intent.metadata_filters.append(
            MetadataFilter(
                field_name=party_field,
                value=party_value,
                operator="contains",
            )
        )
        logger.info(
            "Applied party fallback: mapped %r to metadata filter %s contains %r",
            question,
            party_field,
            party_value,
        )
        return intent

    @staticmethod
    def _infer_concepts_from_question(
        question: str,
        concepts_summary: list[dict[str, Any]],
    ) -> list[str]:
        """Infer concept IDs by matching question text against labels/synonyms."""
        q = question.lower()
        inferred: list[str] = []
        for concept in concepts_summary:
            concept_id = concept.get("id")
            if not concept_id:
                continue
            aliases = [
                str(concept_id),
                str(concept.get("label") or ""),
                *[str(s) for s in concept.get("synonyms", [])],
            ]
            for alias in aliases:
                token = alias.strip().lower()
                if token and token in q:
                    if concept_id not in inferred:
                        inferred.append(concept_id)
                    break
        return inferred

    @staticmethod
    def _extract_party_value_from_question(question: str) -> str | None:
        """Extract a likely party name from relation phrases like 'from X' or 'van X'."""
        patterns = [
            r"\breceived\s+from\s+([^\n,.;!?]+)",
            r"\bfrom\s+([^\n,.;!?]+)",
            r"\bvan\s+([^\n,.;!?]+)",
            r"\bafkomstig\s+van\s+([^\n,.;!?]+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, question, flags=re.IGNORECASE)
            if not m:
                continue
            value = m.group(1).strip().strip("\"'")
            # Trim common continuation words.
            value = re.split(
                r"\s+(?:that|which|where|with|voor|met|die|waar)\s+",
                value,
                flags=re.IGNORECASE,
                maxsplit=1,
            )[0].strip()
            if len(value) >= 2:
                return value
        return None

    @staticmethod
    def _pick_party_field(candidate_concepts: list[dict[str, Any]]) -> str | None:
        """Pick the best ontology field for party/vendor-like constraints."""
        fields: dict[str, str] = {}
        for concept in candidate_concepts:
            for prop in concept.get("properties", []):
                name = str(prop.get("name") or "").strip()
                ptype = str(prop.get("type") or "").strip().lower()
                if name:
                    fields[name] = ptype

        if not fields:
            return None

        preferred_exact = [
            "vendor",
            "supplier",
            "issuer",
            "seller",
            "counterparty",
            "related_party",
        ]
        lowered = {name.lower(): name for name in fields}

        for key in preferred_exact:
            if key in lowered:
                return lowered[key]

        for name, ptype in fields.items():
            lname = name.lower()
            if (
                ptype.startswith("ref:")
                and any(tok in lname for tok in ("vendor", "supplier", "issuer", "party"))
            ):
                return name

        return None

    @staticmethod
    def _clip(text: str, limit: int = 300) -> str:
        """Clip long text for concise logs."""
        raw = (text or "").strip()
        if len(raw) <= limit:
            return raw
        return f"{raw[:limit]}... (truncated {len(raw) - limit} chars)"

    @staticmethod
    def _filters_as_dict(filters: list[MetadataFilter]) -> list[dict[str, str]]:
        """Serialize metadata filters for readable logs."""
        return [
            {
                "field_name": f.field_name,
                "value": f.value,
                "operator": f.operator,
            }
            for f in filters
        ]

    @classmethod
    def _intent_as_dict(cls, intent: QueryIntent) -> dict[str, Any]:
        """Serialize intent for readable logs."""
        return {
            "question": intent.original_question,
            "resolved_language": intent.resolved_language,
            "concept_ids": intent.concept_ids,
            "concept_labels": intent.concept_labels,
            "metadata_filters": cls._filters_as_dict(intent.metadata_filters),
            "keywords": intent.keywords,
            "text_query": intent.text_query,
            "reasoning": intent.reasoning,
        }

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
