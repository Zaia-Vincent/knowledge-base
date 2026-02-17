"""Unit tests for the QueryService — intent resolution and query execution."""

import json
import pytest

from app.application.services.query_service import QueryService
from app.domain.entities import (
    ChatCompletionResult,
    ChatMessage,
    ClassificationResult,
    ClassificationSignal,
    ContentPart,
    OntologyConcept,
    ConceptProperty,
    Mixin,
    ProcessedFile,
    ProcessingStatus,
    TokenUsage,
)
from app.domain.entities.query import MetadataFilter, QueryIntent


# ── Fakes ────────────────────────────────────────────────────────────


class FakeChatProvider:
    """Fake chat provider returning canned JSON responses."""

    provider_name = "fake"

    def __init__(self, response_json: dict | None = None, raw_response: str | None = None):
        self._response_json = response_json
        self._raw_response = raw_response
        self.last_messages: list[ChatMessage] = []

    async def complete(self, messages, model="", temperature=0.7, max_tokens=None):
        self.last_messages = messages
        content = self._raw_response or json.dumps(self._response_json or {})
        return ChatCompletionResult(
            content=content,
            model=model or "test-model",
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )

    async def stream(self, messages, model="", temperature=0.7, max_tokens=None):
        raise NotImplementedError("Streaming not needed for tests")


class FakeOntologyRepo:
    """Minimal fake ontology repository."""

    def __init__(
        self,
        concepts: list[OntologyConcept] | None = None,
        mixins: list[Mixin] | None = None,
    ):
        self._concepts = concepts or []
        self._concept_map = {c.id: c for c in self._concepts}
        self._mixins = {m.id: m for m in (mixins or [])}

    async def get_all_concepts(self, **kwargs) -> list[OntologyConcept]:
        return self._concepts

    # remaining abstract methods — not needed for query tests
    async def get_concept(self, concept_id): return self._concept_map.get(concept_id)
    async def get_children(self, concept_id): return []
    async def get_ancestors(self, concept_id):
        ancestors = []
        current = self._concept_map.get(concept_id)
        while current and current.inherits:
            parent = self._concept_map.get(current.inherits)
            if not parent:
                break
            ancestors.append(parent)
            current = parent
        return list(reversed(ancestors))
    async def search_concepts(self, query): return []
    async def get_concepts_by_pillar(self, pillar): return []
    async def get_classifiable_concepts(self): return []
    async def get_mixin(self, mixin_id): return self._mixins.get(mixin_id)
    async def save_concept(self, concept): pass
    async def save_mixin(self, mixin): pass
    async def delete_concept(self, concept_id): return False
    async def clear_all(self): pass
    async def save_embedded_type(self, et): pass
    async def get_embedded_type(self, type_id): return None
    async def get_embedded_types_for_concept(self, concept_id): return []


class FakeFileRepo:
    """Minimal fake file repository that supports search."""

    def __init__(self, files: list[ProcessedFile] | None = None):
        self._files = files or []
        self.last_search: dict | None = None
        self.search_calls: list[dict] = []

    async def search(
        self,
        concept_ids=None,
        metadata_filters=None,
        text_query=None,
        limit=50,
    ) -> list[ProcessedFile]:
        self.last_search = {
            "concept_ids": concept_ids,
            "metadata_filters": metadata_filters,
            "text_query": text_query,
            "limit": limit,
        }
        self.search_calls.append(dict(self.last_search))
        results = list(self._files)
        if concept_ids:
            results = [
                f for f in results
                if f.classification and f.classification.primary_concept_id in concept_ids
            ]
        if text_query:
            needle = text_query.lower()
            results = [
                f for f in results
                if needle in f.filename.lower() or needle in (f.summary or "").lower()
            ]
        return results[:limit]

    # remaining abstract methods — not needed
    async def get_by_id(self, file_id): return None
    async def get_all(self, skip=0, limit=100): return self._files
    async def create(self, pf): return pf
    async def update(self, pf): return pf
    async def delete(self, file_id): return False
    async def count(self): return len(self._files)


class FakeUsageLogger:
    """No-op LLM usage logger."""

    def __init__(self):
        self.logged_requests: list[dict] = []
        self.logged_errors: list[dict] = []

    async def log_request(self, **kwargs):
        self.logged_requests.append(kwargs)

    async def log_error(self, **kwargs):
        self.logged_errors.append(kwargs)


# ── Fixtures ─────────────────────────────────────────────────────────


def _make_concept(
    id: str,
    label: str | None = None,
    synonyms: list[str] | None = None,
    properties: list[ConceptProperty] | None = None,
    abstract: bool = False,
    inherits: str | None = None,
    mixins: list[str] | None = None,
) -> OntologyConcept:
    return OntologyConcept(
        id=id,
        layer="L2",
        label=label or id,
        inherits=inherits,
        abstract=abstract,
        synonyms=synonyms or [],
        mixins=mixins or [],
        properties=properties or [],
    )


def _make_file(
    file_id: str,
    filename: str,
    concept_id: str | None = None,
    confidence: float = 0.9,
    metadata: dict | None = None,
    summary: str | None = None,
) -> ProcessedFile:
    classification = None
    if concept_id:
        classification = ClassificationResult(
            primary_concept_id=concept_id,
            confidence=confidence,
            signals=[],
        )
    return ProcessedFile(
        id=file_id,
        filename=filename,
        original_path=f"/uploads/{filename}",
        file_size=1024,
        mime_type="application/pdf",
        stored_path=f"/storage/{filename}",
        status=ProcessingStatus.DONE,
        classification=classification,
        metadata=metadata or {},
        summary=summary,
    )


# ── Tests ────────────────────────────────────────────────────────────


class TestIntentResolution:
    """Tests for LLM-based query intent resolution."""

    async def test_parses_valid_json_from_llm(self):
        """Should correctly parse structured JSON from the LLM response."""
        provider = FakeChatProvider(response_json={
            "concept_ids": ["Invoice"],
            "concept_labels": ["Invoice"],
            "metadata_filters": [
                {"field_name": "vendor_name", "value": "Acme", "operator": "contains"}
            ],
            "keywords": ["factuur", "Acme"],
            "text_query": None,
            "resolved_language": "nl",
            "reasoning": "The user is asking about invoices from Acme.",
        })
        ontology_repo = FakeOntologyRepo([
            _make_concept(
                "Invoice",
                synonyms=["factuur"],
                properties=[ConceptProperty(name="vendor", type="ref:Vendor")],
            ),
            _make_concept("Contract", synonyms=["overeenkomst"]),
        ])

        service = QueryService(
            chat_provider=provider,
            ontology_repo=ontology_repo,
            file_repo=FakeFileRepo(),
            usage_logger=FakeUsageLogger(),
        )

        intent = await service.resolve_intent("Welke facturen zijn er van Acme?")

        assert intent.original_question == "Welke facturen zijn er van Acme?"
        assert intent.concept_ids == ["Invoice"]
        assert intent.resolved_language == "nl"
        assert len(intent.metadata_filters) == 1
        assert intent.metadata_filters[0].field_name == "vendor"
        assert intent.metadata_filters[0].value == "Acme"

    async def test_maps_concept_labels_to_ids(self):
        """Concept labels returned by the LLM should resolve to concept IDs."""
        provider = FakeChatProvider(response_json={
            "concept_ids": [],
            "concept_labels": ["Factuur"],
            "metadata_filters": [],
            "keywords": ["factuur"],
            "text_query": None,
            "resolved_language": "nl",
            "reasoning": "test",
        })
        ontology_repo = FakeOntologyRepo([
            _make_concept("Invoice", label="Factuur"),
        ])

        service = QueryService(
            chat_provider=provider,
            ontology_repo=ontology_repo,
            file_repo=FakeFileRepo(),
            usage_logger=FakeUsageLogger(),
        )

        intent = await service.resolve_intent("Welke facturen zijn er?")
        assert intent.concept_ids == ["Invoice"]

    async def test_ontology_context_includes_inherited_and_mixin_properties(self):
        """Prompt context should expose resolved properties (ancestor + mixin + own)."""
        provider = FakeChatProvider(response_json={
            "concept_ids": [],
            "metadata_filters": [],
            "keywords": [],
            "text_query": None,
            "resolved_language": "en",
            "reasoning": "test",
        })
        concepts = [
            _make_concept(
                "Document",
                abstract=True,
                properties=[ConceptProperty(name="document_date", type="date")],
            ),
            _make_concept(
                "Invoice",
                inherits="Document",
                properties=[ConceptProperty(name="vendor", type="ref:Vendor")],
                mixins=["HasMonetaryValue"],
            ),
        ]
        mixins = [
            Mixin(
                id="HasMonetaryValue",
                layer="L1",
                label="HasMonetaryValue",
                properties=[ConceptProperty(name="amount", type="decimal")],
            )
        ]
        ontology_repo = FakeOntologyRepo(concepts=concepts, mixins=mixins)

        service = QueryService(
            chat_provider=provider,
            ontology_repo=ontology_repo,
            file_repo=FakeFileRepo(),
            usage_logger=FakeUsageLogger(),
        )

        await service.resolve_intent("Show invoices")

        system_msg = provider.last_messages[0].content
        assert '"name": "document_date"' in system_msg
        assert '"name": "amount"' in system_msg
        assert '"name": "vendor"' in system_msg

    async def test_parses_json_with_markdown_fences(self):
        """Should strip markdown code fences around JSON."""
        raw = '```json\n{"concept_ids": ["Contract"], "keywords": ["contract"], "resolved_language": "en", "reasoning": "test"}\n```'
        provider = FakeChatProvider(raw_response=raw)
        ontology_repo = FakeOntologyRepo([_make_concept("Contract")])

        service = QueryService(
            chat_provider=provider,
            ontology_repo=ontology_repo,
            file_repo=FakeFileRepo(),
            usage_logger=FakeUsageLogger(),
        )

        intent = await service.resolve_intent("Show me all contracts")
        assert intent.concept_ids == ["Contract"]

    async def test_fallback_on_invalid_json(self):
        """Should return a fallback intent when LLM returns invalid JSON."""
        provider = FakeChatProvider(raw_response="I don't understand this query, sorry!")
        ontology_repo = FakeOntologyRepo()

        service = QueryService(
            chat_provider=provider,
            ontology_repo=ontology_repo,
            file_repo=FakeFileRepo(),
            usage_logger=FakeUsageLogger(),
        )

        intent = await service.resolve_intent("some broken query")
        assert intent.original_question == "some broken query"
        assert intent.text_query == "some broken query"
        assert "Fallback" in intent.reasoning

    async def test_ontology_context_excludes_abstract(self):
        """Abstract concepts should be excluded from the ontology context."""
        provider = FakeChatProvider(response_json={
            "concept_ids": [],
            "keywords": ["test"],
            "resolved_language": "en",
            "reasoning": "test",
        })
        ontology_repo = FakeOntologyRepo([
            _make_concept("Thing", abstract=True),
            _make_concept("Invoice"),
        ])

        service = QueryService(
            chat_provider=provider,
            ontology_repo=ontology_repo,
            file_repo=FakeFileRepo(),
            usage_logger=FakeUsageLogger(),
        )

        await service.resolve_intent("test query")

        # Check the system prompt sent to LLM
        system_msg = provider.last_messages[0]
        assert "Invoice" in system_msg.content
        assert "Thing" not in system_msg.content

    async def test_usage_is_logged(self):
        """Intent resolution should log LLM usage."""
        provider = FakeChatProvider(response_json={
            "concept_ids": [],
            "keywords": [],
            "resolved_language": "en",
            "reasoning": "",
        })
        usage_logger = FakeUsageLogger()

        service = QueryService(
            chat_provider=provider,
            ontology_repo=FakeOntologyRepo(),
            file_repo=FakeFileRepo(),
            usage_logger=usage_logger,
        )

        await service.resolve_intent("test query")
        assert len(usage_logger.logged_requests) == 1
        assert usage_logger.logged_requests[0]["feature"] == "query_intent"

    async def test_maps_received_from_phrase_to_vendor_filter(self):
        """If LLM misses a filter, relation phrase should map to vendor."""
        provider = FakeChatProvider(response_json={
            "concept_ids": ["Invoice"],
            "concept_labels": ["Invoice"],
            "metadata_filters": [],
            "keywords": ["invoice", "donckers"],
            "text_query": None,
            "resolved_language": "en",
            "reasoning": "User asks for invoices.",
        })
        ontology_repo = FakeOntologyRepo([
            _make_concept(
                "Invoice",
                synonyms=["factuur"],
                properties=[ConceptProperty(name="vendor", type="ref:Vendor")],
            ),
        ])

        service = QueryService(
            chat_provider=provider,
            ontology_repo=ontology_repo,
            file_repo=FakeFileRepo(),
            usage_logger=FakeUsageLogger(),
        )

        intent = await service.resolve_intent("get all invoices received from DONCKERS")
        assert intent.concept_ids == ["Invoice"]
        assert len(intent.metadata_filters) == 1
        assert intent.metadata_filters[0].field_name == "vendor"
        assert intent.metadata_filters[0].value == "DONCKERS"
        assert intent.metadata_filters[0].operator == "contains"


class TestQueryExecution:
    """Tests for database search execution."""

    async def test_search_by_concept_ids(self):
        """Should delegate concept_ids to file repository search."""
        invoice_file = _make_file("f1", "invoice_001.pdf", concept_id="Invoice")
        contract_file = _make_file("f2", "contract_001.pdf", concept_id="Contract")

        service = QueryService(
            chat_provider=FakeChatProvider(),
            ontology_repo=FakeOntologyRepo(),
            file_repo=FakeFileRepo([invoice_file, contract_file]),
            usage_logger=FakeUsageLogger(),
        )

        intent = QueryIntent(
            original_question="Show invoices",
            concept_ids=["Invoice"],
        )

        result = await service.execute_query(intent)
        assert result.total_matches == 1
        assert result.matches[0].file_id == "f1"
        assert result.matches[0].concept_id == "Invoice"

    async def test_empty_intent_returns_all(self):
        """An intent with no filters should return all done files."""
        files = [
            _make_file("f1", "a.pdf", concept_id="Invoice"),
            _make_file("f2", "b.pdf", concept_id="Contract"),
        ]

        service = QueryService(
            chat_provider=FakeChatProvider(),
            ontology_repo=FakeOntologyRepo(),
            file_repo=FakeFileRepo(files),
            usage_logger=FakeUsageLogger(),
        )

        intent = QueryIntent(original_question="Show me everything")
        result = await service.execute_query(intent)
        assert result.total_matches == 2

    async def test_max_results_limits_output(self):
        """Should respect the max_results parameter."""
        files = [_make_file(f"f{i}", f"file_{i}.pdf", concept_id="Invoice") for i in range(10)]

        service = QueryService(
            chat_provider=FakeChatProvider(),
            ontology_repo=FakeOntologyRepo(),
            file_repo=FakeFileRepo(files),
            usage_logger=FakeUsageLogger(),
        )

        intent = QueryIntent(original_question="Show invoices", concept_ids=["Invoice"])
        result = await service.execute_query(intent, max_results=3)
        assert result.total_matches == 3

    async def test_retries_without_text_query_when_phrase_blocks_structured_match(self):
        """If text_query yields zero, service retries with structured filters only."""
        files = [
            _make_file("f1", "factuur_001.pdf", concept_id="Invoice", summary="Factuur van DONCKERS"),
        ]
        file_repo = FakeFileRepo(files)
        service = QueryService(
            chat_provider=FakeChatProvider(),
            ontology_repo=FakeOntologyRepo(),
            file_repo=file_repo,
            usage_logger=FakeUsageLogger(),
        )

        intent = QueryIntent(
            original_question="invoices from DONCKERS",
            concept_ids=["Invoice"],
            metadata_filters=[MetadataFilter(field_name="vendor", value="DONCKERS", operator="contains")],
            text_query="invoices from DONCKERS",
        )
        result = await service.execute_query(intent)

        assert result.total_matches == 1
        assert len(file_repo.search_calls) == 2
        assert file_repo.search_calls[0]["text_query"] == "invoices from DONCKERS"
        assert file_repo.search_calls[1]["text_query"] is None


class TestFullQueryFlow:
    """Tests for end-to-end query flow (resolve + search)."""

    async def test_full_query_combines_intent_and_search(self):
        """Full query should resolve intent then search files."""
        provider = FakeChatProvider(response_json={
            "concept_ids": ["Invoice"],
            "concept_labels": ["Invoice"],
            "metadata_filters": [],
            "keywords": ["invoices"],
            "text_query": None,
            "resolved_language": "en",
            "reasoning": "User asks for invoices.",
        })

        files = [
            _make_file("f1", "invoice_001.pdf", concept_id="Invoice", summary="Acme invoice Q1"),
            _make_file("f2", "contract.pdf", concept_id="Contract"),
        ]

        service = QueryService(
            chat_provider=provider,
            ontology_repo=FakeOntologyRepo([_make_concept("Invoice"), _make_concept("Contract")]),
            file_repo=FakeFileRepo(files),
            usage_logger=FakeUsageLogger(),
        )

        result = await service.query("Show me all invoices")

        assert result.intent.concept_ids == ["Invoice"]
        assert result.total_matches == 1
        assert result.matches[0].filename == "invoice_001.pdf"
        assert result.matches[0].summary == "Acme invoice Q1"

    async def test_logs_query_trace_and_passes_filters_to_search(self, caplog):
        """Service should log trace details and pass mapped filters to repository."""
        provider = FakeChatProvider(response_json={
            "concept_ids": ["Invoice"],
            "concept_labels": ["Invoice"],
            "metadata_filters": [],
            "keywords": ["invoice", "donckers"],
            "text_query": None,
            "resolved_language": "en",
            "reasoning": "User asks for invoices.",
        })
        file_repo = FakeFileRepo([
            _make_file("f1", "invoice_001.pdf", concept_id="Invoice", summary="Donckers invoice"),
        ])
        service = QueryService(
            chat_provider=provider,
            ontology_repo=FakeOntologyRepo([
                _make_concept(
                    "Invoice",
                    properties=[ConceptProperty(name="vendor", type="ref:Vendor")],
                ),
            ]),
            file_repo=file_repo,
            usage_logger=FakeUsageLogger(),
        )

        with caplog.at_level("INFO", logger="app.application.services.query_service"):
            result = await service.query("get all invoices received from DONCKERS")

        assert result.total_matches == 1
        assert file_repo.last_search is not None
        filters = file_repo.last_search["metadata_filters"] or []
        assert any(f.field_name == "vendor" and f.value == "DONCKERS" for f in filters)

        messages = [r.message for r in caplog.records]
        assert any("Query intent start" in m for m in messages)
        assert any("Query intent resolved" in m for m in messages)
        assert any("Executing query search" in m for m in messages)
