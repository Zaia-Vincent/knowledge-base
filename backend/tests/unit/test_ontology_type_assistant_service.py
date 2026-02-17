"""Unit tests for OntologyTypeAssistantService."""

import pytest

from app.application.services.ontology_type_assistant_service import (
    OntologyTypeAssistantService,
)
from app.domain.entities import (
    ChatCompletionResult,
    ChatMessage,
    ConceptProperty,
    ExtractionTemplate,
    OntologyConcept,
    TokenUsage,
)


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
    ]
    return FakeOntologyRepository(concepts)


@pytest.mark.asyncio
async def test_suggest_type_fallback_without_llm(repo):
    service = OntologyTypeAssistantService(
        ontology_repo=repo,
        chat_provider=None,
        model="",
    )

    result = await service.suggest_type(
        name="Blog Post",
        description="Public website article",
        include_internet_research=False,
    )

    assert result["payload"]["label"] == "Blog Post"
    assert result["payload"]["inherits"] == "Document"
    assert result["payload"]["id"] == "blog-post"
    assert result["payload"]["extraction_template"]["classification_hints"]
    assert result["references"], "Expected default references even when web fetch is disabled"


@pytest.mark.asyncio
async def test_suggest_type_llm_normalizes_unknown_parent(repo):
    service = OntologyTypeAssistantService(
        ontology_repo=repo,
        chat_provider=FakeChatProvider(),
        model="fake-model",
    )

    result = await service.suggest_type(
        name="Blog Post",
        description="Public website article",
        include_internet_research=False,
    )

    assert result["payload"]["inherits"] == "Document"
    assert any("replaced" in w for w in result["warnings"])
    assert result["payload"]["properties"]
