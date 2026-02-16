"""Unit tests for Sprint 3: ClassificationService (multi-signal classification engine)."""

import pytest

from app.application.interfaces import OntologyRepository
from app.application.interfaces.llm_client import (
    LLMClassificationRequest,
    LLMClassificationResponse,
    LLMClient,
    LLMExtractionRequest,
    LLMExtractionResponse,
    LLMPdfProcessingRequest,
    LLMPdfProcessingResponse,
    LLMVisionOCRRequest,
    LLMVisionOCRResponse,
)
from app.application.services.classification_service import ClassificationService
from app.domain.entities import (
    ConceptProperty,
    ExtractionTemplate,
    Mixin,
    OntologyConcept,
)


# ── Fake Ontology Repository ────────────────────────────────────────

class FakeOntologyRepository(OntologyRepository):
    """In-memory ontology repository for classification tests."""

    def __init__(self, concepts: list[OntologyConcept] | None = None):
        self._concepts = {c.id: c for c in (concepts or [])}

    async def get_concept(self, concept_id: str) -> OntologyConcept | None:
        return self._concepts.get(concept_id)

    async def get_all_concepts(self, layer=None, pillar=None, abstract=None):
        result = list(self._concepts.values())
        if layer:
            result = [c for c in result if c.layer == layer]
        if pillar:
            result = [c for c in result if c.pillar == pillar]
        if abstract is not None:
            result = [c for c in result if c.abstract == abstract]
        return result

    async def get_children(self, concept_id: str):
        return [c for c in self._concepts.values() if c.inherits == concept_id]

    async def get_ancestors(self, concept_id: str):
        chain = []
        current = self._concepts.get(concept_id)
        while current and current.inherits:
            parent = self._concepts.get(current.inherits)
            if parent:
                chain.append(parent)
            current = parent
        return chain

    async def search_concepts(self, query: str):
        q = query.lower()
        return [c for c in self._concepts.values() if q in c.label.lower()]

    async def get_concepts_by_pillar(self, pillar: str):
        return [c for c in self._concepts.values() if c.pillar == pillar]

    async def get_classifiable_concepts(self):
        return [c for c in self._concepts.values() if c.is_classifiable]

    async def get_mixin(self, mixin_id: str):
        return None

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


# ── Fake LLM Client ─────────────────────────────────────────────────

class FakeLLMClient(LLMClient):
    """Deterministic LLM client for testing — always picks the given concept."""

    def __init__(self, concept_id: str = "Invoice", confidence: float = 0.9):
        self._concept_id = concept_id
        self._confidence = confidence

    async def classify_document(self, request: LLMClassificationRequest) -> LLMClassificationResponse:
        return LLMClassificationResponse(
            concept_id=self._concept_id,
            confidence=self._confidence,
            reasoning="Test LLM classification",
        )

    async def extract_metadata(self, request: LLMExtractionRequest) -> LLMExtractionResponse:
        return LLMExtractionResponse(properties={}, summary="", confidence=0.0)

    async def ocr_image(self, request: LLMVisionOCRRequest) -> LLMVisionOCRResponse:
        return LLMVisionOCRResponse(text="", confidence=0.0)

    async def process_pdf(self, request: LLMPdfProcessingRequest) -> LLMPdfProcessingResponse:
        return LLMPdfProcessingResponse(concept_id="", confidence=0.0)

    async def process_pdf_with_tools(self, pdf_base64, filename, available_concepts, tool_handler):
        return []


# ── Test Fixtures ────────────────────────────────────────────────────

def _make_concept(
    id: str,
    label: str,
    synonyms: list[str] | None = None,
    hints: list[str] | None = None,
    file_patterns: list[str] | None = None,
) -> OntologyConcept:
    """Helper to create classifiable concepts."""
    return OntologyConcept(
        id=id,
        layer="L2",
        label=label,
        abstract=False,
        synonyms=synonyms or [],
        extraction_template=ExtractionTemplate(
            classification_hints=hints or [],
            file_patterns=file_patterns or [],
        ),
    )


@pytest.fixture
def concepts():
    return [
        _make_concept(
            "Invoice",
            "Factuur",
            synonyms=["factuur", "invoice", "rekening"],
            hints=["factuurnummer", "btw-bedrag", "payment terms"],
            file_patterns=["*factuur*", "*invoice*"],
        ),
        _make_concept(
            "Contract",
            "Contract",
            synonyms=["contract", "overeenkomst", "agreement"],
            hints=["partijen", "looptijd", "handtekening"],
            file_patterns=["*contract*", "*agreement*"],
        ),
        _make_concept(
            "Report",
            "Rapport",
            synonyms=["rapport", "report", "verslag"],
            hints=["conclusie", "samenvatting", "resultaten"],
            file_patterns=["*rapport*", "*report*"],
        ),
    ]


@pytest.fixture
def repo(concepts):
    return FakeOntologyRepository(concepts)


# ── Tests ────────────────────────────────────────────────────────────

class TestClassificationService:

    async def test_hint_matching_picks_invoice(self, repo):
        """Hint matching: text containing invoice keywords → Invoice."""
        service = ClassificationService(ontology_repo=repo, llm_client=None)

        result = await service.classify(
            text="Factuurnummer: F-2025-001. BTW-bedrag: €250,00. Betaaltermijn: 30 dagen.",
            filename="document.pdf",
        )

        assert result.primary_concept_id == "Invoice"
        assert result.confidence > 0.0
        assert any(s.method == "hint_match" for s in result.signals)

    async def test_hint_matching_picks_contract(self, repo):
        """Hint matching: text about contract terms → Contract."""
        service = ClassificationService(ontology_repo=repo, llm_client=None)

        result = await service.classify(
            text="De partijen komen overeen dat de looptijd van deze overeenkomst 12 maanden bedraagt.",
            filename="document.pdf",
        )

        assert result.primary_concept_id == "Contract"
        assert result.confidence > 0.0

    async def test_file_pattern_matching(self, repo):
        """File pattern: filename containing 'invoice' → boosts Invoice score."""
        service = ClassificationService(ontology_repo=repo, llm_client=None)

        result = await service.classify(
            text="Some generic text without hints",
            filename="invoice_2025_001.pdf",
        )

        assert result.primary_concept_id == "Invoice"
        assert any(s.method == "file_pattern" for s in result.signals)

    async def test_folder_path_pattern(self, repo):
        """File pattern: folder structure containing 'contracts' → boosts Contract."""
        service = ClassificationService(ontology_repo=repo, llm_client=None)

        result = await service.classify(
            text="Generic document content",
            filename="doc.pdf",
            original_path="contracts/2025/doc.pdf",
        )

        assert result.primary_concept_id == "Contract"

    async def test_combined_signals(self, repo):
        """Multiple matching signals should boost confidence."""
        service = ClassificationService(ontology_repo=repo, llm_client=None)

        result = await service.classify(
            text="Factuurnummer F-001. Btw-bedrag: €100. Dit is een factuur.",
            filename="factuur_jan_2025.pdf",
        )

        assert result.primary_concept_id == "Invoice"
        # Both file pattern and hint match should fire
        methods = {s.method for s in result.signals if s.concept_id == "Invoice"}
        assert "file_pattern" in methods
        assert "hint_match" in methods

    async def test_llm_signal_applied(self, repo):
        """LLM classification signal should be included when LLM client is available."""
        llm = FakeLLMClient(concept_id="Invoice", confidence=0.92)
        service = ClassificationService(ontology_repo=repo, llm_client=llm)

        result = await service.classify(
            text="This is a tax document with amounts and dates.",
            filename="unknown.pdf",
        )

        assert any(s.method == "llm_analysis" for s in result.signals)

    async def test_llm_failure_graceful(self, repo):
        """Service should still return a result when LLM fails."""

        class FailingLLMClient(LLMClient):
            async def classify_document(self, request):
                raise ConnectionError("API unavailable")

            async def extract_metadata(self, request):
                raise NotImplementedError

            async def ocr_image(self, request):
                raise NotImplementedError

            async def process_pdf(self, request):
                raise NotImplementedError

            async def process_pdf_with_tools(self, pdf_base64, filename, available_concepts, tool_handler):
                raise NotImplementedError

        service = ClassificationService(
            ontology_repo=repo,
            llm_client=FailingLLMClient(),
        )

        # Should not raise — falls back to rule-based signals
        result = await service.classify(
            text="Factuurnummer: F-2025-001",
            filename="doc.pdf",
        )
        assert result.primary_concept_id is not None

    async def test_no_classifiable_concepts(self):
        """If the ontology has no classifiable concepts, return 'Unknown'."""
        empty_repo = FakeOntologyRepository([])
        service = ClassificationService(ontology_repo=empty_repo)

        result = await service.classify(text="Hello world", filename="test.txt")

        assert result.primary_concept_id == "Unknown"
        assert result.confidence == 0.0

    async def test_signals_contain_details(self, repo):
        """All signals should have non-empty details for transparency."""
        service = ClassificationService(ontology_repo=repo, llm_client=None)

        result = await service.classify(
            text="Factuurnummer: F-2025. BTW: €100. Invoice document.",
            filename="factuur.pdf",
        )

        for signal in result.signals:
            assert signal.details, f"Signal {signal.method} on {signal.concept_id} has no details"
            assert signal.score > 0.0

    async def test_confidence_capped_at_one(self, repo):
        """Even with all signals firing hard, confidence should not exceed 1.0."""
        llm = FakeLLMClient(concept_id="Invoice", confidence=1.0)
        service = ClassificationService(ontology_repo=repo, llm_client=llm)

        result = await service.classify(
            text="Factuurnummer factuur invoice rekening btw-bedrag payment terms",
            filename="invoice_factuur.pdf",
        )

        assert result.confidence <= 1.0
