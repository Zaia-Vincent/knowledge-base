"""AI-first ontology type assistant service.

Generates an editable L3 concept draft by combining:
1. Existing ontology context (parent + similar concepts)
2. External standards/best-practice references (optional web fetch)
3. LLM reasoning (with deterministic fallback if LLM is unavailable)
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import re
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import httpx
import yaml

from app.application.interfaces import OntologyRepository
from app.application.interfaces.chat_provider import ChatProvider
from app.application.services.llm_usage_logger import LLMUsageLogger
from app.domain.entities import (
    ChatMessage,
    CreateConceptDraft,
    ExtractionTemplate,
    OntologyConcept,
    OntologyTypeSuggestion,
    ReferenceItem,
)

logger = logging.getLogger(__name__)

# ── Module-level constants ────────────────────────────────────────────

LLM_MAX_TOKENS = 2200
"""Maximum tokens for the LLM suggestion completion."""

MAX_SIMILAR_CONCEPTS = 10
"""Maximum number of similar concepts used as blueprint context."""

MAX_REFERENCE_URLS = 10
"""Maximum number of reference URLs to fetch."""

REFERENCE_FETCH_TIMEOUT_S = 8.0
"""Timeout in seconds for individual reference page fetches."""

MAX_REFERENCE_TITLE_CHARS = 180
"""Maximum character length for reference page titles."""

MAX_REFERENCE_SUMMARY_CHARS = 700
"""Maximum character length for reference page summaries."""

MAX_PROMPT_SYNONYMS = 8
"""Maximum synonyms per concept included in the prompt context."""

MAX_PROMPT_PROPERTIES = 12
"""Maximum properties per concept included in the prompt context."""

MAX_PROMPT_RELATIONSHIPS = 8
"""Maximum relationships per concept included in the prompt context."""

MAX_PROMPT_HINTS = 12
"""Maximum classification hints per concept included in the prompt context."""

MAX_PROMPT_FILE_PATTERNS = 8
"""Maximum file patterns per concept included in the prompt context."""

MAX_PROMPT_REFERENCES = 8
"""Maximum external references included in the prompt context."""

# ── Parent inference rules loaded from YAML config ────────────────────

_INFERENCE_RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "parent_inference_rules.yaml"


def _load_parent_inference_rules() -> tuple[list[dict], str]:
    """Load keyword→parent rules from the YAML config file."""
    try:
        with open(_INFERENCE_RULES_PATH, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        rules = data.get("rules", [])
        fallback = data.get("default_fallback", "Document")
        return rules, fallback
    except FileNotFoundError:
        logger.warning("Parent inference rules not found at %s, using empty rules", _INFERENCE_RULES_PATH)
        return [], "Document"

_PARENT_INFERENCE_RULES, _PARENT_DEFAULT_FALLBACK = _load_parent_inference_rules()

_DEFAULT_REFERENCE_URLS = [
    "https://schema.org/Article",
    "https://schema.org/BlogPosting",
    "https://developers.google.com/search/docs/appearance/structured-data/article",
    "https://ogp.me/",
    "https://www.dublincore.org/specifications/dublin-core/dcmi-terms/",
    "https://www.w3.org/TR/skos-reference/",
]

_SUGGESTION_SYSTEM_PROMPT = """You are an enterprise ontology architect.

Design a practical, implementation-ready L3 concept draft.

Return ONLY valid JSON with this exact top-level structure:
{
  "payload": {
    "id": "kebab-case-id",
    "label": "Human Label",
    "inherits": "ParentConceptId",
    "description": "...",
    "abstract": false,
    "synonyms": ["..."],
    "mixins": [],
    "properties": [
      {
        "name": "field_name",
        "type": "string",
        "required": false,
        "default_value": null,
        "description": "..."
      }
    ],
    "relationships": [
      {
        "name": "relationshipName",
        "target": "TargetConcept",
        "cardinality": "0..*",
        "inverse": null,
        "description": "..."
      }
    ],
    "extraction_template": {
      "classification_hints": ["..."],
      "file_patterns": ["..."]
    }
  },
  "rationale": "Why this shape is useful in this ontology",
  "parent_reasoning": "Why this parent was selected",
  "adaptation_tips": ["How user can adapt this draft safely"],
  "warnings": ["Potential risks or ambiguities to review"]
}

Rules:
- Keep properties focused and avoid obvious duplicates with inherited fields.
- Use concrete extraction hints and file patterns that improve classification.
- Prefer common web metadata conventions where applicable.
- Keep the draft editable and realistic for production systems.
"""


class OntologyTypeAssistantService:
    """Builds AI-assisted ontology type suggestions for the L3 wizard."""

    def __init__(
        self,
        ontology_repo: OntologyRepository,
        chat_provider: ChatProvider | None = None,
        model: str = "",
        usage_logger: LLMUsageLogger | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self._ontology_repo = ontology_repo
        self._chat_provider = chat_provider
        self._model = model
        self._usage_logger = usage_logger
        self._http_client = http_client

    async def suggest_type(
        self,
        *,
        name: str,
        description: str = "",
        inherits: str | None = None,
        domain_context: str = "",
        style_preferences: list[str] | None = None,
        reference_urls: list[str] | None = None,
        include_internet_research: bool = True,
    ) -> OntologyTypeSuggestion:
        """Generate an editable L3 concept draft with rationale."""
        if not name.strip():
            raise ValueError("name is required")

        style_preferences = style_preferences or []
        reference_urls = reference_urls or []

        parent = await self._resolve_parent(name=name, description=description, inherits=inherits)
        ancestors = await self._ontology_repo.get_ancestors(parent.id)
        inherited_property_names = {
            p.name.lower()
            for node in [*ancestors, parent]
            for p in node.properties
        }
        similar = await self._find_similar_concepts(name=name, description=description, parent_id=parent.id)
        references = await self._collect_reference_material(
            extra_urls=reference_urls,
            include_internet_research=include_internet_research,
        )

        if self._chat_provider and self._model:
            try:
                return await self._suggest_with_llm(
                    name=name,
                    description=description,
                    parent=parent,
                    ancestors=ancestors,
                    inherited_property_names=inherited_property_names,
                    similar_concepts=similar,
                    style_preferences=style_preferences,
                    domain_context=domain_context,
                    references=references,
                )
            except (json.JSONDecodeError, httpx.HTTPError, ValueError, RuntimeError) as exc:
                logger.exception("LLM suggestion failed, falling back to deterministic draft")
                fallback = self._suggest_without_llm(
                    name=name,
                    description=description,
                    parent=parent,
                    inherited_property_names=inherited_property_names,
                )
                fallback.warnings.append(
                    f"AI generation failed and fallback was used: {str(exc)[:200]}"
                )
                fallback.references = references
                return fallback

        fallback = self._suggest_without_llm(
            name=name,
            description=description,
            parent=parent,
            inherited_property_names=inherited_property_names,
        )
        fallback.warnings.append("LLM provider is not configured; deterministic draft used.")
        fallback.references = references
        return fallback

    async def _suggest_with_llm(
        self,
        *,
        name: str,
        description: str,
        parent: OntologyConcept,
        ancestors: list[OntologyConcept],
        inherited_property_names: set[str],
        similar_concepts: list[OntologyConcept],
        style_preferences: list[str],
        domain_context: str,
        references: list[ReferenceItem],
    ) -> OntologyTypeSuggestion:
        """Generate suggestion via chat provider and normalize output."""
        lineage = [*ancestors, parent]
        references_dicts = [{"url": r.url, "title": r.title, "summary": r.summary} for r in references]
        context_payload = {
            "goal": {
                "name": name,
                "description": description,
                "domain_context": domain_context,
                "style_preferences": style_preferences,
            },
            "parent": {
                "id": parent.id,
                "label": parent.label,
                "description": parent.description,
                "properties": [self._property_to_dict(p) for p in parent.properties],
            },
            "ancestor_chain": [
                {
                    "id": c.id,
                    "label": c.label,
                    "properties": [self._property_to_dict(p) for p in c.properties],
                }
                for c in lineage
            ],
            "inherited_property_names": sorted(inherited_property_names),
            "similar_concepts": [
                {
                    "id": c.id,
                    "label": c.label,
                    "inherits": c.inherits,
                    "description": c.description,
                    "synonyms": c.synonyms[:MAX_PROMPT_SYNONYMS],
                    "properties": [self._property_to_dict(p) for p in c.properties[:MAX_PROMPT_PROPERTIES]],
                    "relationships": [self._relationship_to_dict(r) for r in c.relationships[:MAX_PROMPT_RELATIONSHIPS]],
                    "classification_hints": (
                        c.extraction_template.classification_hints[:MAX_PROMPT_HINTS]
                        if c.extraction_template
                        else []
                    ),
                    "file_patterns": (
                        c.extraction_template.file_patterns[:MAX_PROMPT_FILE_PATTERNS]
                        if c.extraction_template
                        else []
                    ),
                }
                for c in similar_concepts
            ],
            "external_references": references_dicts[:MAX_PROMPT_REFERENCES],
        }

        messages = [
            ChatMessage(role="system", content=_SUGGESTION_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=(
                    "Create a draft ontology concept for this request context:\n\n"
                    + json.dumps(context_payload, ensure_ascii=True, indent=2)
                ),
            ),
        ]

        start = time.monotonic()
        result = await self._chat_provider.complete(
            messages=messages,
            model=self._model,
            temperature=0.15,
            max_tokens=LLM_MAX_TOKENS,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        if self._usage_logger:
            await self._usage_logger.log_request(
                model=result.model,
                provider=result.provider or self._chat_provider.provider_name,
                feature="ontology_type_assistant",
                usage=result.usage,
                duration_ms=duration_ms,
                request_context=name,
            )

        parsed = json.loads(self._extract_json(result.content))
        draft = self._normalize_payload(
            raw_payload=parsed.get("payload", {}),
            fallback_name=name,
            fallback_description=description,
            fallback_parent_id=parent.id,
            inherited_property_names=inherited_property_names,
        )

        warnings = _dedupe_list(parsed.get("warnings", []))
        resolved_parent = await self._ontology_repo.get_concept(draft.inherits)
        if resolved_parent is None:
            warnings.append(
                f"Suggested parent '{draft.inherits}' was unknown and was replaced by '{parent.id}'."
            )
            draft.inherits = parent.id

        return OntologyTypeSuggestion(
            payload=draft,
            rationale=str(parsed.get("rationale", "")).strip(),
            parent_reasoning=str(parsed.get("parent_reasoning", "")).strip(),
            adaptation_tips=_dedupe_list(parsed.get("adaptation_tips", [])),
            warnings=warnings,
            references=references,
        )

    def _suggest_without_llm(
        self,
        *,
        name: str,
        description: str,
        parent: OntologyConcept,
        inherited_property_names: set[str],
    ) -> OntologyTypeSuggestion:
        """Deterministic fallback suggestion when no LLM is configured."""
        slug = _to_kebab_case(name)
        hints = _dedupe_list([name, slug, name.lower().replace("-", " ")])

        default_properties = [
            {
                "name": "title",
                "type": "string",
                "required": True,
                "default_value": None,
                "description": "Primary heading/title of the resource.",
            },
            {
                "name": "canonical_url",
                "type": "string",
                "required": False,
                "default_value": None,
                "description": "Canonical URL for stable reference and de-duplication.",
            },
            {
                "name": "date_modified",
                "type": "date",
                "required": False,
                "default_value": None,
                "description": "Last meaningful update date.",
            },
            {
                "name": "language",
                "type": "string",
                "required": False,
                "default_value": None,
                "description": "Language code (for example 'en', 'nl').",
            },
            {
                "name": "keywords",
                "type": "string[]",
                "required": False,
                "default_value": None,
                "description": "Tags or keywords used for search and grouping.",
            },
        ]

        filtered_properties = [
            p for p in default_properties if p["name"].lower() not in inherited_property_names
        ]

        draft = CreateConceptDraft(
            id=slug,
            label=name.strip(),
            inherits=parent.id,
            description=(
                description.strip()
                or f"A specialized {parent.label} concept for '{name.strip()}' content."
            ),
            abstract=False,
            synonyms=_dedupe_list([name.lower(), slug.replace("-", " ")]),
            mixins=[],
            properties=filtered_properties,
            relationships=[],
            extraction_template=ExtractionTemplate(
                classification_hints=hints,
                file_patterns=[f"**/{slug}/**", f"**/{slug}s/**"],
            ),
        )

        return OntologyTypeSuggestion(
            payload=draft,
            rationale=(
                "Generated from ontology parent context with a deterministic template "
                "because AI suggestions were unavailable."
            ),
            parent_reasoning=f"Selected parent '{parent.id}' based on ontology context.",
            adaptation_tips=[
                "Adjust required flags based on actual extraction confidence.",
                "Keep only fields that are consistently observable in source documents.",
                "Refine classification hints to reduce overlap with sibling concepts.",
            ],
        )

    async def _resolve_parent(
        self,
        *,
        name: str,
        description: str,
        inherits: str | None,
    ) -> OntologyConcept:
        """Resolve parent concept (provided explicitly or inferred heuristically)."""
        if inherits:
            concept = await self._ontology_repo.get_concept(inherits)
            if concept is None:
                raise ValueError(f"Parent concept '{inherits}' not found")
            return concept

        all_concepts = await self._ontology_repo.get_all_concepts()
        by_id = {c.id: c for c in all_concepts}

        text = f"{name} {description}".lower()

        # Apply keyword rules from YAML config
        for rule in _PARENT_INFERENCE_RULES:
            keywords = rule.get("keywords", [])
            candidates = rule.get("candidates", [])
            if any(kw in text for kw in keywords):
                for candidate_id in candidates:
                    if candidate_id in by_id:
                        return by_id[candidate_id]

        # Default fallback from config
        if _PARENT_DEFAULT_FALLBACK in by_id:
            return by_id[_PARENT_DEFAULT_FALLBACK]

        non_abstract = [c for c in all_concepts if not c.abstract]
        if non_abstract:
            return sorted(non_abstract, key=lambda c: c.label)[0]

        if all_concepts:
            return sorted(all_concepts, key=lambda c: c.label)[0]

        raise ValueError("Ontology is empty; cannot infer parent concept")

    async def _find_similar_concepts(
        self,
        *,
        name: str,
        description: str,
        parent_id: str,
    ) -> list[OntologyConcept]:
        """Find concepts likely useful as blueprints."""
        results: list[OntologyConcept] = []
        seen: set[str] = set()

        search_terms = [name.strip()]
        if description.strip():
            search_terms.append(description.strip()[:60])
        search_terms.append(parent_id)

        for term in search_terms:
            if not term:
                continue
            for concept in await self._ontology_repo.search_concepts(term):
                if concept.id in seen:
                    continue
                seen.add(concept.id)
                results.append(concept)
                if len(results) >= MAX_SIMILAR_CONCEPTS:
                    return results

        children = await self._ontology_repo.get_children(parent_id)
        for child in children:
            if child.id in seen:
                continue
            seen.add(child.id)
            results.append(child)
            if len(results) >= MAX_SIMILAR_CONCEPTS:
                break

        return results

    async def _collect_reference_material(
        self,
        *,
        extra_urls: list[str],
        include_internet_research: bool,
    ) -> list[ReferenceItem]:
        """Fetch concise external references used in the suggestion prompt."""
        urls = _dedupe_list([*_DEFAULT_REFERENCE_URLS, *extra_urls])[:MAX_REFERENCE_URLS]

        if not include_internet_research:
            return [ReferenceItem(url=u) for u in urls]

        if self._http_client:
            tasks = [self._fetch_reference(self._http_client, u) for u in urls]
            results = await _gather_safe(tasks)
            return [r for r in results if r is not None]

        async with httpx.AsyncClient(timeout=REFERENCE_FETCH_TIMEOUT_S, follow_redirects=True) as client:
            tasks = [self._fetch_reference(client, u) for u in urls]
            results = await _gather_safe(tasks)
        return [r for r in results if r is not None]

    async def _fetch_reference(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> ReferenceItem | None:
        """Fetch and summarize a reference page."""
        try:
            response = await client.get(url)
            if response.status_code >= 400:
                return None

            body = response.text
            title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
            title = html.unescape(title_match.group(1)).strip() if title_match else ""

            cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", body)
            cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
            cleaned = html.unescape(cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()

            return ReferenceItem(
                url=url,
                title=title[:MAX_REFERENCE_TITLE_CHARS],
                summary=cleaned[:MAX_REFERENCE_SUMMARY_CHARS],
            )
        except Exception:
            return None

    def _normalize_payload(
        self,
        *,
        raw_payload: dict[str, Any],
        fallback_name: str,
        fallback_description: str,
        fallback_parent_id: str,
        inherited_property_names: set[str],
    ) -> CreateConceptDraft:
        """Normalize and harden LLM payload into API-safe shape."""
        if not isinstance(raw_payload, dict):
            raw_payload = {}

        label = str(raw_payload.get("label") or fallback_name).strip() or fallback_name
        concept_id = _to_kebab_case(str(raw_payload.get("id") or label))
        inherits = str(raw_payload.get("inherits") or fallback_parent_id).strip() or fallback_parent_id

        properties: list[dict[str, Any]] = []
        for p in raw_payload.get("properties", []) if isinstance(raw_payload.get("properties"), list) else []:
            if not isinstance(p, dict):
                continue
            name = str(p.get("name", "")).strip()
            if not name:
                continue
            prop = {
                "name": name,
                "type": str(p.get("type") or "string").strip() or "string",
                "required": bool(p.get("required", False)),
                "default_value": (
                    None if p.get("default_value") is None else str(p.get("default_value"))
                ),
                "description": str(p.get("description") or "").strip(),
            }
            properties.append(prop)
        properties = _dedupe_records_by_key(properties, key="name")

        relationships: list[dict[str, Any]] = []
        for r in raw_payload.get("relationships", []) if isinstance(raw_payload.get("relationships"), list) else []:
            if not isinstance(r, dict):
                continue
            name = str(r.get("name", "")).strip()
            target = str(r.get("target", "")).strip()
            if not name or not target:
                continue
            rel = {
                "name": name,
                "target": target,
                "cardinality": str(r.get("cardinality") or "0..*").strip() or "0..*",
                "inverse": (str(r.get("inverse")).strip() if r.get("inverse") is not None else None),
                "description": str(r.get("description") or "").strip(),
            }
            relationships.append(rel)
        relationships = _dedupe_relationships(relationships)

        extraction_template_raw = raw_payload.get("extraction_template", {})
        if not isinstance(extraction_template_raw, dict):
            extraction_template_raw = {}
        hints = _dedupe_list(extraction_template_raw.get("classification_hints", []))
        patterns = _dedupe_list(extraction_template_raw.get("file_patterns", []))

        synonyms = _dedupe_list(raw_payload.get("synonyms", []))
        mixins = _dedupe_list(raw_payload.get("mixins", []))

        # If the LLM omitted extraction hints, derive baseline hints.
        if not hints:
            hints = _dedupe_list([label, concept_id, label.lower()])

        # If no file pattern is provided, add one conservative default.
        if not patterns:
            patterns = [f"**/{concept_id}/**"]

        # Reduce accidental inheritance overrides in auto-generated drafts.
        cleaned_properties = [
            p for p in properties if p["name"].lower() not in inherited_property_names
        ]
        if cleaned_properties:
            properties = cleaned_properties

        return CreateConceptDraft(
            id=concept_id,
            label=label,
            inherits=inherits,
            description=str(raw_payload.get("description") or fallback_description).strip(),
            abstract=False,
            synonyms=synonyms,
            mixins=mixins,
            properties=properties,
            relationships=relationships,
            extraction_template=ExtractionTemplate(
                classification_hints=hints,
                file_patterns=patterns,
            ),
        )

    @staticmethod
    def _property_to_dict(prop) -> dict[str, Any]:
        return {
            "name": prop.name,
            "type": prop.type,
            "required": prop.required,
            "description": prop.description,
        }

    @staticmethod
    def _relationship_to_dict(rel) -> dict[str, Any]:
        return {
            "name": rel.name,
            "target": rel.target,
            "cardinality": rel.cardinality,
            "inverse": rel.inverse,
            "description": rel.description,
        }

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from plain text or fenced blocks."""
        content = text.strip()

        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.S | re.I)
        if fence_match:
            return fence_match.group(1).strip()

        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return content[start:end + 1]

        return content


async def _gather_safe(tasks: Iterable[Any]) -> list[Any]:
    """Run awaitables concurrently with per-task fault isolation."""
    raw = await asyncio.gather(*tasks, return_exceptions=True)
    results: list[Any] = []
    for item in raw:
        if isinstance(item, Exception):
            results.append(None)
        else:
            results.append(item)
    return results


def _to_kebab_case(value: str) -> str:
    """Normalize free text to kebab-case identifiers."""
    out = value.strip()
    out = re.sub(r"([a-z])([A-Z])", r"\1-\2", out)
    out = re.sub(r"[\s_]+", "-", out)
    out = re.sub(r"[^a-zA-Z0-9-]+", "", out)
    out = out.strip("-").lower()
    return out or "new-concept"


def _dedupe_list(values: Any) -> list[str]:
    """Return normalized unique string list."""
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = str(raw).strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _dedupe_records_by_key(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Deduplicate dict records by a case-insensitive key field."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for record in records:
        raw = str(record.get(key, "")).strip()
        if not raw:
            continue
        norm = raw.lower()
        if norm in seen:
            continue
        seen.add(norm)
        out.append(record)
    return out


def _dedupe_relationships(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate relationships by (name, target)."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for record in records:
        name = str(record.get("name", "")).strip().lower()
        target = str(record.get("target", "")).strip().lower()
        if not name or not target:
            continue
        key = f"{name}::{target}"
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out
