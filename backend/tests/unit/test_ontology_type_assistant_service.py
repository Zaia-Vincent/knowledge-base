"""Unit tests for OntologyTypeAssistantService."""

import json

import pytest

from app.application.services.ontology_type_assistant_service import (
    OntologyTypeAssistantService,
    _to_kebab_case,
    _dedupe_list,
    _dedupe_records_by_key,
    _dedupe_relationships,
)
from app.domain.entities import (
    ChatCompletionResult,
    ChatMessage,
    ConceptProperty,
    CreateConceptDraft,
    ExtractionTemplate,
    OntologyConcept,
    OntologyTypeSuggestion,
    ReferenceItem,
    TokenUsage,
)


# ── Fakes ────────────────────────────────────────────────────────────


class FakeOntologyRepository:
    """Minimal in-memory ontology repo for assistant tests."""

    def __init__(self, concepts: list[OntologyConcept]):
        self._concepts = {c.id: c for c in concepts}

    async def get_concept(self, concept_id: str):
        return self._concepts.get(concept_id)

    async def get_all_concepts(self, layer=None, pillar=None, abstract=None):
        result = list(self._concepts.values())
        if layer is not None:
            result = [c for c in result if c.layer == layer]
        if pillar is not None:
            result = [c for c in result if c.pillar == pillar]
        if abstract is not None:
            result = [c for c in result if c.abstract == abstract]
        return result

    async def get_ancestors(self, concept_id: str):
        out = []
        current = self._concepts.get(concept_id)
        while current and current.inherits:
            parent = self._concepts.get(current.inherits)
            if parent is None:
                break
            out.append(parent)
            current = parent
        return list(reversed(out))

    async def search_concepts(self, query: str):
        q = query.lower()
        return [
            c for c in self._concepts.values()
            if q in c.label.lower() or q in c.description.lower() or q in c.id.lower()
        ]

    async def get_children(self, concept_id: str):
        return [c for c in self._concepts.values() if c.inherits == concept_id]


class FakeChatProvider:
    """Deterministic provider returning fixed suggestion JSON."""

    @property
    def provider_name(self) -> str:
        return "fake"

    async def complete(self, messages: list[ChatMessage], model: str, *, temperature=None, max_tokens=None):
        _ = (messages, model, temperature, max_tokens)
        content = """
{
  "payload": {
    "id": "blogpost",
    "label": "Blog Post",
    "inherits": "UnknownParent",
    "description": "A blog-style article.",
    "abstract": false,
    "synonyms": ["blog article", "post"],
    "mixins": [],
    "properties": [
      {"name": "title", "type": "string", "required": true, "description": "Headline"},
      {"name": "reading_time_minutes", "type": "integer", "required": false, "description": "Estimated time"}
    ],
    "relationships": [],
    "extraction_template": {
      "classification_hints": ["blog post", "article"],
      "file_patterns": ["**/blog/**"]
    }
  },
  "rationale": "Use web publishing metadata conventions.",
  "parent_reasoning": "Document is the closest abstraction.",
  "adaptation_tips": ["Add only fields with strong extraction confidence."],
  "warnings": ["Review inheritance conflicts."]
}
"""
        return ChatCompletionResult(
            model=model,
            content=content,
            finish_reason="stop",
            usage=TokenUsage(total_tokens=42),
            provider="fake",
        )

    async def stream(self, messages, model, *, temperature=None, max_tokens=None):  # pragma: no cover
        _ = (messages, model, temperature, max_tokens)
        if False:
            yield ""


class FailingChatProvider:
    """Chat provider that always raises an exception."""

    @property
    def provider_name(self) -> str:
        return "failing"

    async def complete(self, messages, model, *, temperature=None, max_tokens=None):
        raise RuntimeError("LLM exploded!")

    async def stream(self, messages, model, *, temperature=None, max_tokens=None):  # pragma: no cover
        if False:
            yield ""


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def repo():
    concepts = [
        OntologyConcept(
            id="Thing",
            layer="L1",
            label="Thing",
            abstract=True,
        ),
        OntologyConcept(
            id="Resource",
            layer="L1",
            label="Resource",
            inherits="Thing",
            abstract=True,
        ),
        OntologyConcept(
            id="Document",
            layer="L1",
            label="Document",
            inherits="Resource",
            abstract=False,
            properties=[
                ConceptProperty(
                    name="document_date",
                    type="date",
                    required=True,
                    description="Date of document",
                ),
            ],
            extraction_template=ExtractionTemplate(
                classification_hints=["document", "file"],
                file_patterns=["**/*"],
            ),
        ),
        OntologyConcept(
            id="Report",
            layer="L2",
            label="Report",
            inherits="Document",
            abstract=False,
            description="Operational report",
        ),
        OntologyConcept(
            id="Message",
            layer="L1",
            label="Message",
            inherits="Resource",
            abstract=False,
            description="A communication message.",
        ),
        OntologyConcept(
            id="DataSet",
            layer="L1",
            label="Data Set",
            inherits="Resource",
            abstract=False,
            description="A structured data set.",
        ),
    ]
    return FakeOntologyRepository(concepts)


@pytest.fixture
def service_no_llm(repo):
    return OntologyTypeAssistantService(
        ontology_repo=repo,
        chat_provider=None,
        model="",
    )


@pytest.fixture
def service_with_llm(repo):
    return OntologyTypeAssistantService(
        ontology_repo=repo,
        chat_provider=FakeChatProvider(),
        model="fake-model",
    )


@pytest.fixture
def service_failing_llm(repo):
    return OntologyTypeAssistantService(
        ontology_repo=repo,
        chat_provider=FailingChatProvider(),
        model="fail-model",
    )


# ── suggest_type: original tests (updated for typed returns) ─────────


@pytest.mark.asyncio
async def test_suggest_type_fallback_without_llm(service_no_llm):
    result = await service_no_llm.suggest_type(
        name="Blog Post",
        description="Public website article",
        include_internet_research=False,
    )

    assert isinstance(result, OntologyTypeSuggestion)
    assert result.payload.label == "Blog Post"
    assert result.payload.inherits == "Document"
    assert result.payload.id == "blog-post"
    assert result.payload.extraction_template is not None
    assert result.payload.extraction_template.classification_hints
    assert result.references, "Expected default references even when web fetch is disabled"


@pytest.mark.asyncio
async def test_suggest_type_llm_normalizes_unknown_parent(service_with_llm):
    result = await service_with_llm.suggest_type(
        name="Blog Post",
        description="Public website article",
        include_internet_research=False,
    )

    assert result.payload.inherits == "Document"
    assert any("replaced" in w for w in result.warnings)
    assert result.payload.properties


# ── suggest_type: typed return structure ──────────────────────────────


@pytest.mark.asyncio
async def test_suggest_type_returns_typed_suggestion(service_no_llm):
    """Verify the return value is a fully typed OntologyTypeSuggestion."""
    result = await service_no_llm.suggest_type(
        name="Invoice",
        description="A financial invoice",
        include_internet_research=False,
    )
    assert isinstance(result, OntologyTypeSuggestion)
    assert isinstance(result.payload, CreateConceptDraft)
    assert isinstance(result.references, list)
    assert all(isinstance(r, ReferenceItem) for r in result.references)
    assert isinstance(result.adaptation_tips, list)
    assert isinstance(result.warnings, list)


# ── suggest_type: input validation ───────────────────────────────────


@pytest.mark.asyncio
async def test_suggest_type_empty_name_raises_value_error(service_no_llm):
    with pytest.raises(ValueError, match="name is required"):
        await service_no_llm.suggest_type(name="   ", description="")


@pytest.mark.asyncio
async def test_suggest_type_whitespace_name_raises(service_no_llm):
    with pytest.raises(ValueError):
        await service_no_llm.suggest_type(name="\t\n", description="")


# ── suggest_type: LLM fallback on error ──────────────────────────────


@pytest.mark.asyncio
async def test_suggest_type_llm_failure_falls_back(service_failing_llm):
    """When the LLM throws, we should still get a deterministic result."""
    result = await service_failing_llm.suggest_type(
        name="Blog Post",
        description="An article",
        include_internet_research=False,
    )
    assert isinstance(result, OntologyTypeSuggestion)
    assert any("fallback" in w.lower() for w in result.warnings)
    assert result.payload.label == "Blog Post"


# ── _suggest_without_llm: edge cases ────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_with_special_chars_in_name(service_no_llm):
    result = await service_no_llm.suggest_type(
        name="Blog Post (2025 Edition)",
        description="",
        include_internet_research=False,
    )
    assert result.payload.id == "blog-post-2025-edition"
    assert result.payload.label == "Blog Post (2025 Edition)"


@pytest.mark.asyncio
async def test_fallback_generates_description_when_empty(service_no_llm):
    result = await service_no_llm.suggest_type(
        name="Newsletter",
        description="",
        include_internet_research=False,
    )
    assert "Newsletter" in result.payload.description
    assert result.payload.description != ""


@pytest.mark.asyncio
async def test_fallback_filters_inherited_properties(repo):
    """Properties already defined on the parent should not appear in fallback."""
    service = OntologyTypeAssistantService(ontology_repo=repo, chat_provider=None, model="")
    result = await service.suggest_type(
        name="Term Paper",
        description="Academic document",
        inherits="Document",
        include_internet_research=False,
    )
    own_names = [p["name"] for p in result.payload.properties]
    # 'document_date' is inherited from Document and should be filtered
    assert "document_date" not in own_names


# ── _resolve_parent: heuristic matching ──────────────────────────────


@pytest.mark.asyncio
async def test_resolve_parent_explicit(service_no_llm):
    result = await service_no_llm.suggest_type(
        name="Executive Summary",
        description="High-level report summary",
        inherits="Report",
        include_internet_research=False,
    )
    assert result.payload.inherits == "Report"


@pytest.mark.asyncio
async def test_resolve_parent_keyword_document(service_no_llm):
    """'article' keyword should resolve to Document parent."""
    result = await service_no_llm.suggest_type(
        name="News Article",
        description="Published news article",
        include_internet_research=False,
    )
    assert result.payload.inherits == "Document"


@pytest.mark.asyncio
async def test_resolve_parent_keyword_email(service_no_llm):
    """'email' keyword should resolve to Message parent."""
    result = await service_no_llm.suggest_type(
        name="Customer Email",
        description="Email from a customer",
        include_internet_research=False,
    )
    assert result.payload.inherits == "Message"


@pytest.mark.asyncio
async def test_resolve_parent_keyword_dataset(service_no_llm):
    """'dataset' keyword maps to DataRecord heuristic; when DataRecord is
    absent, it falls to the default Document fallback."""
    result = await service_no_llm.suggest_type(
        name="Customer Dataset",
        description="A dataset of customer records",
        include_internet_research=False,
    )
    # No DataRecord in fixtures → falls back to Document
    assert result.payload.inherits == "Document"


@pytest.mark.asyncio
async def test_resolve_parent_unknown_falls_to_first_nonabstract(service_no_llm):
    """When no keyword matches, should still pick a reasonable parent."""
    result = await service_no_llm.suggest_type(
        name="Widget Specification",
        description="Specs for widgets",
        include_internet_research=False,
    )
    # Should still have a valid parent (not abstract)
    assert result.payload.inherits is not None
    assert result.payload.inherits != ""


# ── _normalize_payload ────────────────────────────────────────────────


class TestNormalizePayload:
    """Tests for _normalize_payload via a service instance."""

    @pytest.fixture
    def service(self, repo):
        return OntologyTypeAssistantService(ontology_repo=repo, chat_provider=None, model="")

    def test_empty_payload_uses_fallbacks(self, service):
        result = service._normalize_payload(
            raw_payload={},
            fallback_name="Test",
            fallback_description="A test concept",
            fallback_parent_id="Document",
            inherited_property_names=set(),
        )
        assert isinstance(result, CreateConceptDraft)
        assert result.label == "Test"
        assert result.id == "test"
        assert result.inherits == "Document"
        assert result.description == "A test concept"

    def test_non_dict_payload_uses_fallbacks(self, service):
        result = service._normalize_payload(
            raw_payload="not a dict",
            fallback_name="Fallback",
            fallback_description="Desc",
            fallback_parent_id="Document",
            inherited_property_names=set(),
        )
        assert result.label == "Fallback"
        assert result.id == "fallback"

    def test_corrupt_properties_are_filtered(self, service):
        result = service._normalize_payload(
            raw_payload={
                "label": "X",
                "properties": [
                    "not a dict",
                    {"name": "", "type": "string"},
                    {"name": "valid_prop", "type": "string", "description": "ok"},
                    42,
                ],
            },
            fallback_name="X",
            fallback_description="",
            fallback_parent_id="Document",
            inherited_property_names=set(),
        )
        assert len(result.properties) == 1
        assert result.properties[0]["name"] == "valid_prop"

    def test_corrupt_relationships_are_filtered(self, service):
        result = service._normalize_payload(
            raw_payload={
                "label": "X",
                "relationships": [
                    {"name": "has_author", "target": "Person"},
                    {"name": "", "target": "Person"},
                    {"name": "no_target", "target": ""},
                    "not a dict",
                ],
            },
            fallback_name="X",
            fallback_description="",
            fallback_parent_id="Document",
            inherited_property_names=set(),
        )
        assert len(result.relationships) == 1
        assert result.relationships[0]["name"] == "has_author"

    def test_inherited_properties_excluded(self, service):
        result = service._normalize_payload(
            raw_payload={
                "label": "Special Doc",
                "properties": [
                    {"name": "document_date", "type": "date", "description": "dup"},
                    {"name": "author", "type": "string", "description": "new"},
                ],
            },
            fallback_name="Special Doc",
            fallback_description="",
            fallback_parent_id="Document",
            inherited_property_names={"document_date"},
        )
        names = [p["name"] for p in result.properties]
        assert "document_date" not in names
        assert "author" in names

    def test_extraction_hints_generated_when_missing(self, service):
        result = service._normalize_payload(
            raw_payload={"label": "FAQ"},
            fallback_name="FAQ",
            fallback_description="",
            fallback_parent_id="Document",
            inherited_property_names=set(),
        )
        assert result.extraction_template is not None
        assert len(result.extraction_template.classification_hints) > 0

    def test_file_patterns_default_when_missing(self, service):
        result = service._normalize_payload(
            raw_payload={"label": "FAQ", "id": "faq"},
            fallback_name="FAQ",
            fallback_description="",
            fallback_parent_id="Document",
            inherited_property_names=set(),
        )
        assert result.extraction_template is not None
        assert any("faq" in p for p in result.extraction_template.file_patterns)

    def test_deduplicate_properties(self, service):
        result = service._normalize_payload(
            raw_payload={
                "properties": [
                    {"name": "title", "type": "string", "description": "a"},
                    {"name": "title", "type": "string", "description": "b"},
                ],
            },
            fallback_name="X",
            fallback_description="",
            fallback_parent_id="Document",
            inherited_property_names=set(),
        )
        names = [p["name"] for p in result.properties]
        assert names.count("title") == 1


# ── _extract_json ─────────────────────────────────────────────────────


class TestExtractJson:

    _svc = OntologyTypeAssistantService  # for accessing static methods

    def test_plain_json(self):
        raw = '{"payload": {"id": "x"}}'
        parsed = json.loads(self._svc._extract_json(raw))
        assert parsed["payload"]["id"] == "x"

    def test_fenced_json(self):
        raw = "Here is the result:\n```json\n{\"key\": \"value\"}\n```\nDone."
        parsed = json.loads(self._svc._extract_json(raw))
        assert parsed["key"] == "value"

    def test_json_with_surrounding_text(self):
        raw = 'Some explanation. {"id": "test"} More text.'
        parsed = json.loads(self._svc._extract_json(raw))
        assert parsed["id"] == "test"

    def test_no_json_returns_raw_text(self):
        """When no JSON is found, _extract_json returns the raw text (caller handles parsing errors)."""
        raw = "no json here at all"
        result = self._svc._extract_json(raw)
        assert isinstance(result, str)


# ── Utility functions ────────────────────────────────────────────────


class TestToKebabCase:

    def test_simple(self):
        assert _to_kebab_case("Blog Post") == "blog-post"

    def test_camelCase(self):
        assert _to_kebab_case("BlogPost") == "blog-post"

    def test_already_kebab(self):
        assert _to_kebab_case("already-kebab") == "already-kebab"

    def test_special_chars(self):
        assert _to_kebab_case("Hello (World)!") == "hello-world"

    def test_unicode_and_accents(self):
        result = _to_kebab_case("Café  Résumé")
        assert "--" not in result  # no double hyphens


class TestDedupeList:

    def test_empty(self):
        assert _dedupe_list([]) == []

    def test_dedup_preserves_order(self):
        assert _dedupe_list(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]

    def test_case_insensitive(self):
        result = _dedupe_list(["Blog", "blog", "BLOG"])
        assert len(result) == 1

    def test_non_strings_coerced(self):
        """_dedupe_list converts non-strings to strings."""
        result = _dedupe_list(["ok", 42, None, "ok"])
        assert "ok" in result
        assert len(result) == 3  # ok, 42, None — all coerced to strings


class TestDedupeRecordsByKey:

    def test_basic(self):
        records = [
            {"name": "a", "val": 1},
            {"name": "b", "val": 2},
            {"name": "a", "val": 3},
        ]
        result = _dedupe_records_by_key(records, key="name")
        assert len(result) == 2
        assert result[0]["name"] == "a"
        assert result[0]["val"] == 1  # first occurrence wins


class TestDedupeRelationships:

    def test_basic(self):
        rels = [
            {"name": "has_author", "target": "Person"},
            {"name": "has_author", "target": "Person"},
            {"name": "has_author", "target": "Organization"},
        ]
        result = _dedupe_relationships(rels)
        assert len(result) == 2  # same name+target deduped
