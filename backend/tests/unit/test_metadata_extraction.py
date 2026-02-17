"""Unit tests for MetadataExtractionService and value normalizer (JSONB version)."""

import pytest

from app.application.interfaces import OntologyRepository
from app.application.interfaces.llm_client import (
    LLMClient,
    LLMClassificationRequest,
    LLMClassificationResponse,
    LLMExtractionRequest,
    LLMExtractionResponse,
    LLMPdfProcessingRequest,
    LLMPdfProcessingResponse,
    LLMVisionOCRRequest,
    LLMVisionOCRResponse,
)
from app.application.services.metadata_extraction_service import (
    MetadataExtractionService,
    _normalize_array,
    _normalize_ref,
    _normalize_value,
    _parse_numeric,
)
from app.domain.entities import (
    ClassificationResult,
    ConceptProperty,
    ExtractionTemplate,
    Mixin,
    OntologyConcept,
)


# ── Fake Ontology Repository ────────────────────────────────────────

class FakeOntologyRepo(OntologyRepository):
    """In-memory ontology repo for metadata extraction tests."""

    def __init__(
        self,
        concepts: list[OntologyConcept] | None = None,
        mixins: list[Mixin] | None = None,
    ):
        self._concepts = {c.id: c for c in (concepts or [])}
        self._mixins = {m.id: m for m in (mixins or [])}

    async def get_concept(self, concept_id: str):
        return self._concepts.get(concept_id)

    async def get_all_concepts(self, **kwargs):
        return list(self._concepts.values())

    async def get_children(self, concept_id: str):
        return []

    async def get_ancestors(self, concept_id: str):
        ancestors = []
        current = self._concepts.get(concept_id)
        while current and current.inherits:
            parent = self._concepts.get(current.inherits)
            if not parent:
                break
            ancestors.append(parent)
            current = parent
        return list(reversed(ancestors))

    async def search_concepts(self, query: str):
        return []

    async def get_concepts_by_pillar(self, pillar: str):
        return []

    async def get_classifiable_concepts(self):
        return [c for c in self._concepts.values() if c.is_classifiable]

    async def get_mixin(self, mixin_id: str):
        return self._mixins.get(mixin_id)

    async def save_concept(self, concept):
        self._concepts[concept.id] = concept

    async def save_mixin(self, mixin):
        pass

    async def clear_all(self):
        self._concepts.clear()

    async def delete_concept(self, concept_id: str) -> bool:
        if concept_id in self._concepts:
            del self._concepts[concept_id]
            return True
        return False

    async def get_embedded_type(self, type_id: str):
        return None

    async def get_embedded_types_for_concept(self, concept_id: str):
        return []

    async def save_embedded_type(self, embedded_type):
        pass


# ── Fake LLM Client ─────────────────────────────────────────────────

class FakeExtractionLLMClient(LLMClient):
    """Returns deterministic extraction results."""

    def __init__(self, properties: dict, summary: str = "Test summary", confidence: float = 0.9):
        self._properties = properties
        self._summary = summary
        self._confidence = confidence

    async def classify_document(self, request):
        return LLMClassificationResponse(concept_id="", confidence=0.0, reasoning="")

    async def extract_metadata(self, request: LLMExtractionRequest) -> LLMExtractionResponse:
        return LLMExtractionResponse(
            properties=self._properties,
            summary=self._summary,
            confidence=self._confidence,
        )

    async def ocr_image(self, request):
        return LLMVisionOCRResponse(text="", confidence=0.0)

    async def process_pdf(self, request: LLMPdfProcessingRequest) -> LLMPdfProcessingResponse:
        return LLMPdfProcessingResponse(concept_id="", confidence=0.0)

    async def process_pdf_with_tools(self, pdf_base64, filename, available_concepts, tool_handler):
        return []


# ── Fixtures ─────────────────────────────────────────────────────────

def _make_invoice_concept() -> OntologyConcept:
    return OntologyConcept(
        id="Invoice",
        layer="L2",
        label="Factuur",
        abstract=False,
        properties=[
            ConceptProperty(name="invoice_number", type="string", required=True, description="Factuurnummer"),
            ConceptProperty(name="invoice_date", type="date", required=True, description="Factuurdatum"),
            ConceptProperty(name="total_amount", type="currency", required=True, description="Totaalbedrag"),
            ConceptProperty(name="vat_amount", type="currency", required=False, description="BTW bedrag"),
            ConceptProperty(name="supplier_name", type="string", required=False, description="Leveranciersnaam"),
        ],
    )


@pytest.fixture
def invoice_concept():
    return _make_invoice_concept()


@pytest.fixture
def repo(invoice_concept):
    return FakeOntologyRepo([invoice_concept])


@pytest.fixture
def invoice_classification():
    return ClassificationResult(
        primary_concept_id="Invoice",
        confidence=0.9,
        signals=[],
    )


# ── Normalization Tests ──────────────────────────────────────────────

class TestValueNormalization:

    def test_normalize_string(self):
        entry = _normalize_value("supplier_name", "string", "Acme Corp")
        assert entry["value"] == "Acme Corp"

    def test_normalize_null_returns_none(self):
        assert _normalize_value("x", "string", None) is None
        assert _normalize_value("x", "string", "null") is None
        assert _normalize_value("x", "string", "n/a") is None

    def test_normalize_date_iso(self):
        entry = _normalize_value("date", "date", "2025-03-15")
        assert entry["value"] == "2025-03-15"

    def test_normalize_date_european(self):
        entry = _normalize_value("date", "date", "15-03-2025")
        assert entry["value"] == "2025-03-15"

    def test_normalize_date_slash_european(self):
        entry = _normalize_value("date", "date", "15/03/2025")
        assert entry["value"] == "2025-03-15"

    def test_normalize_date_dot_european(self):
        entry = _normalize_value("date", "date", "15.03.2025")
        assert entry["value"] == "2025-03-15"

    def test_normalize_date_unparseable_stored_as_text(self):
        entry = _normalize_value("date", "date", "maart 2025")
        assert entry["value"] == "maart 2025"

    def test_normalize_dutch_number(self):
        entry = _normalize_value("amount", "currency", "1.250,50")
        assert entry["value"] == 1250.50

    def test_normalize_english_number(self):
        entry = _normalize_value("amount", "currency", "1,250.50")
        assert entry["value"] == 1250.50

    def test_normalize_simple_dutch_decimal(self):
        entry = _normalize_value("amount", "currency", "250,50")
        assert entry["value"] == 250.50

    def test_normalize_currency_with_symbol(self):
        entry = _normalize_value("amount", "currency", "€ 1.250,00")
        assert entry["value"] == 1250.00

    def test_normalize_integer(self):
        entry = _normalize_value("count", "number", "42")
        assert entry["value"] == 42.0

    def test_normalize_negative_number(self):
        entry = _normalize_value("amount", "number", "-250,50")
        assert entry["value"] == -250.50


class TestParseNumeric:

    def test_dutch_thousands(self):
        assert _parse_numeric("1.250,50") == 1250.50

    def test_english_thousands(self):
        assert _parse_numeric("1,250.50") == 1250.50

    def test_simple_integer(self):
        assert _parse_numeric("42") == 42.0

    def test_simple_decimal(self):
        assert _parse_numeric("250.5") == 250.5

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _parse_numeric("abc")


# ── Reference Normalization Tests ────────────────────────────────────

class TestNormalizeRef:

    def test_ref_from_dict(self):
        """Python dict is stored as proper JSON object."""
        entry = _normalize_ref("vendor", {"label": "Deli Tyres bv"})
        assert entry["value"] == {"label": "Deli Tyres bv"}

    def test_ref_from_stringified_dict(self):
        """Stringified Python dict is parsed into a proper JSON object."""
        entry = _normalize_ref("vendor", "{'label': 'Deli Tyres bv'}")
        assert entry["value"] == {"label": "Deli Tyres bv"}

    def test_ref_from_plain_string(self):
        """Plain string is wrapped as {"label": "..."}."""
        entry = _normalize_ref("vendor", "Deli Tyres bv")
        assert entry["value"] == {"label": "Deli Tyres bv"}

    def test_ref_null_returns_none(self):
        assert _normalize_ref("vendor", None) is None
        assert _normalize_ref("vendor", "null") is None


# ── Array Normalization Tests ────────────────────────────────────────

class TestNormalizeArray:

    def test_array_from_list(self):
        """Python list is stored as proper JSON array."""
        items = [{"line_total": 159.5, "description": "Item 1"}]
        entry = _normalize_array("line_items", items)
        assert entry["value"] == items

    def test_array_from_stringified_list(self):
        """Stringified Python list is parsed into a proper JSON array."""
        entry = _normalize_array("line_items", "[{'line_total': 159.5}]")
        assert entry["value"] == [{"line_total": 159.5}]

    def test_array_from_single_dict(self):
        """Single dict is wrapped into a one-element array."""
        item = {"line_total": 159.5}
        entry = _normalize_array("line_items", item)
        assert entry["value"] == [item]

    def test_array_null_returns_none(self):
        assert _normalize_array("line_items", None) is None
        assert _normalize_array("line_items", "[]") is None


# ── MetadataExtractionService Tests ──────────────────────────────────

class TestMetadataExtractionService:

    async def test_extract_with_llm(self, repo, invoice_classification):
        """LLM extraction returns JSONB-compatible metadata dict."""
        llm = FakeExtractionLLMClient(
            properties={
                "invoice_number": "F-2025-001",
                "invoice_date": "2025-03-15",
                "total_amount": "1.250,50",
                "vat_amount": "262,60",
                "supplier_name": "Acme BV",
            },
            summary="Factuur van Acme BV voor IT-diensten",
        )
        service = MetadataExtractionService(ontology_repo=repo, llm_client=llm)

        metadata, extra_fields, summary = await service.extract(
            text="Factuurnummer: F-2025-001. Datum: 15-03-2025. Totaal: €1.250,50.",
            classification=invoice_classification,
        )

        assert len(metadata) == 5
        assert summary == "Factuur van Acme BV voor IT-diensten"

        # Check specific entries
        assert metadata["invoice_number"]["value"] == "F-2025-001"
        assert metadata["total_amount"]["value"] == 1250.50
        assert metadata["supplier_name"]["value"] == "Acme BV"

    async def test_extract_with_null_values_skipped(self, repo, invoice_classification):
        """Properties with null values from LLM are not included."""
        llm = FakeExtractionLLMClient(
            properties={
                "invoice_number": "F-2025-001",
                "invoice_date": None,
                "total_amount": "500",
                "vat_amount": None,
                "supplier_name": None,
            },
        )
        service = MetadataExtractionService(ontology_repo=repo, llm_client=llm)

        metadata, _, _ = await service.extract(
            text="Some text",
            classification=invoice_classification,
        )

        assert len(metadata) == 2  # Only invoice_number and total_amount

    async def test_extract_without_llm_falls_back_to_rules(self, repo, invoice_classification):
        """Without LLM, rule-based extraction finds key: value patterns."""
        service = MetadataExtractionService(ontology_repo=repo, llm_client=None)

        metadata, extra_fields, summary = await service.extract(
            text="invoice_number: F-2025-001\ntotal_amount: 500\n",
            classification=invoice_classification,
        )

        assert summary == ""
        assert "invoice_number" in metadata

    async def test_extract_concept_not_found(self, invoice_classification):
        """Unknown concept in classif result → empty extraction."""
        repo = FakeOntologyRepo([])  # No concepts
        service = MetadataExtractionService(ontology_repo=repo, llm_client=None)

        metadata, extra_fields, summary = await service.extract(
            text="Some text",
            classification=invoice_classification,
        )

        assert metadata == {}
        assert summary == ""

    async def test_extract_concept_without_properties(self, invoice_classification):
        """Concept with no properties → nothing to extract."""
        concept = OntologyConcept(
            id="Invoice",
            layer="L2",
            label="Factuur",
            abstract=False,
            properties=[],
        )
        repo = FakeOntologyRepo([concept])
        service = MetadataExtractionService(ontology_repo=repo, llm_client=None)

        metadata, extra_fields, summary = await service.extract(
            text="Some text",
            classification=invoice_classification,
        )

        assert metadata == {}

    async def test_extract_uses_inherited_and_mixin_properties(self):
        """Extraction template should include ancestor and mixin properties."""
        concepts = [
            OntologyConcept(
                id="Document",
                layer="L1",
                label="Document",
                abstract=False,
                properties=[
                    ConceptProperty(name="document_number", type="string", required=False),
                ],
            ),
            OntologyConcept(
                id="Invoice",
                layer="L2",
                label="Invoice",
                inherits="Document",
                abstract=False,
                mixins=["HasMonetaryValue"],
                properties=[],
            ),
        ]
        mixins = [
            Mixin(
                id="HasMonetaryValue",
                layer="L1",
                label="HasMonetaryValue",
                properties=[
                    ConceptProperty(name="amount", type="decimal", required=False),
                    ConceptProperty(name="currency", type="string", required=False),
                ],
            )
        ]
        repo = FakeOntologyRepo(concepts=concepts, mixins=mixins)
        llm = FakeExtractionLLMClient(
            properties={
                "document_number": "2408484",
                "amount": "307.19",
                "currency": "EUR",
            },
            summary="Invoice summary",
            confidence=0.97,
        )
        service = MetadataExtractionService(ontology_repo=repo, llm_client=llm)

        classification = ClassificationResult(
            primary_concept_id="Invoice",
            confidence=0.9,
            signals=[],
        )
        metadata, _, _ = await service.extract(
            text="Invoice #2408484 total EUR 307.19",
            classification=classification,
        )

        assert metadata["document_number"]["value"] == "2408484"
        assert metadata["amount"]["value"] == 307.19
        assert metadata["currency"]["value"] == "EUR"

    async def test_extract_llm_failure_falls_back(self, repo, invoice_classification):
        """LLM exception → graceful fallback to rule-based."""

        class FailingLLM(LLMClient):
            async def classify_document(self, req):
                raise NotImplementedError

            async def extract_metadata(self, req):
                raise ConnectionError("API down")

            async def ocr_image(self, req):
                raise NotImplementedError

            async def process_pdf(self, req):
                raise NotImplementedError

            async def process_pdf_with_tools(self, pdf_base64, filename, available_concepts, tool_handler):
                raise NotImplementedError

        service = MetadataExtractionService(ontology_repo=repo, llm_client=FailingLLM())

        # Should not raise
        metadata, extra_fields, summary = await service.extract(
            text="invoice_number: F-001\n",
            classification=invoice_classification,
        )

        assert isinstance(metadata, dict)
