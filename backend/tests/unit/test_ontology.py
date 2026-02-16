"""Unit tests for the OntologyCompiler and OntologyService."""

import pytest
from dataclasses import dataclass, field

from app.application.services.ontology_compiler import OntologyCompiler
from app.application.services.ontology_service import (
    OntologyService,
    ConceptAlreadyExistsError,
    ParentConceptNotFoundError,
    ProtectedConceptError,
)
from app.application.interfaces import OntologyRepository
from app.domain.entities import (
    OntologyConcept,
    ConceptProperty,
    Mixin,
    ExtractionTemplate,
    EmbeddedType,
    EmbeddedTypeProperty,
)


class FakeOntologyRepository(OntologyRepository):
    """In-memory fake repository for unit testing."""

    def __init__(self):
        self._concepts: dict[str, OntologyConcept] = {}
        self._mixins: dict[str, Mixin] = {}
        self._embedded_types: dict[str, EmbeddedType] = {}

    async def get_concept(self, concept_id: str) -> OntologyConcept | None:
        return self._concepts.get(concept_id)

    async def get_all_concepts(
        self,
        layer: str | None = None,
        pillar: str | None = None,
        abstract: bool | None = None,
    ) -> list[OntologyConcept]:
        result = list(self._concepts.values())
        if layer is not None:
            result = [c for c in result if c.layer == layer]
        if pillar is not None:
            result = [c for c in result if c.pillar == pillar]
        if abstract is not None:
            result = [c for c in result if c.abstract == abstract]
        return sorted(result, key=lambda c: c.label)

    async def get_children(self, concept_id: str) -> list[OntologyConcept]:
        return sorted(
            [c for c in self._concepts.values() if c.inherits == concept_id],
            key=lambda c: c.label,
        )

    async def get_ancestors(self, concept_id: str) -> list[OntologyConcept]:
        ancestors = []
        current_id = concept_id
        while current_id:
            concept = self._concepts.get(current_id)
            if concept is None:
                break
            if concept.id != concept_id:
                ancestors.append(concept)
            current_id = concept.inherits
        return list(reversed(ancestors))

    async def search_concepts(self, query: str) -> list[OntologyConcept]:
        q = query.lower()
        return [
            c
            for c in self._concepts.values()
            if q in c.label.lower() or q in c.description.lower() or any(q in s.lower() for s in c.synonyms)
        ]

    async def get_concepts_by_pillar(self, pillar: str) -> list[OntologyConcept]:
        return await self.get_all_concepts(pillar=pillar)

    async def get_classifiable_concepts(self) -> list[OntologyConcept]:
        return [c for c in self._concepts.values() if c.is_classifiable]

    async def get_mixin(self, mixin_id: str) -> Mixin | None:
        return self._mixins.get(mixin_id)

    async def save_embedded_type(self, embedded_type: EmbeddedType) -> None:
        self._embedded_types[embedded_type.id] = embedded_type

    async def get_embedded_type(self, type_id: str) -> EmbeddedType | None:
        return self._embedded_types.get(type_id)

    async def get_embedded_types_for_concept(self, concept_id: str) -> list[EmbeddedType]:
        return [
            et for et in self._embedded_types.values()
            if concept_id in et.applies_to
        ]

    async def save_concept(self, concept: OntologyConcept) -> None:
        self._concepts[concept.id] = concept

    async def save_mixin(self, mixin: Mixin) -> None:
        self._mixins[mixin.id] = mixin

    async def delete_concept(self, concept_id: str) -> bool:
        if concept_id in self._concepts:
            del self._concepts[concept_id]
            return True
        return False

    async def clear_all(self) -> None:
        self._concepts.clear()
        self._mixins.clear()
        self._embedded_types.clear()


# ── Fixtures ─────────────────────────────────────────────────────────

def _make_concept(
    id: str,
    layer: str = "L1",
    label: str | None = None,
    inherits: str | None = None,
    abstract: bool = False,
    pillar: str | None = None,
    synonyms: list[str] | None = None,
    has_template: bool = False,
    properties: list[ConceptProperty] | None = None,
) -> OntologyConcept:
    return OntologyConcept(
        id=id,
        layer=layer,
        label=label or id,
        inherits=inherits,
        abstract=abstract,
        pillar=pillar,
        synonyms=synonyms or [],
        extraction_template=ExtractionTemplate(classification_hints=["test"]) if has_template else None,
        properties=properties or [],
    )


@pytest.fixture
def repo():
    return FakeOntologyRepository()


@pytest.fixture
def service(repo):
    return OntologyService(repo)


@pytest.fixture
async def populated_repo(repo):
    """Repo with a small but realistic concept hierarchy."""
    # L1 foundation
    await repo.save_concept(_make_concept("Thing", abstract=True))
    await repo.save_concept(_make_concept("Entity", inherits="Thing", abstract=True))
    await repo.save_concept(_make_concept("Object", inherits="Thing", abstract=True))

    # L2 enterprise concepts
    await repo.save_concept(
        _make_concept("Document", layer="L2", inherits="Object", abstract=True, pillar="artifacts")
    )
    await repo.save_concept(
        _make_concept(
            "Invoice",
            layer="L2",
            inherits="Document",
            pillar="artifacts",
            synonyms=["factuur", "facture"],
            has_template=True,
        )
    )
    await repo.save_concept(
        _make_concept(
            "Contract",
            layer="L2",
            inherits="Document",
            pillar="artifacts",
            synonyms=["overeenkomst"],
            has_template=True,
        )
    )
    await repo.save_concept(
        _make_concept("Person", layer="L2", inherits="Entity", pillar="entities", has_template=True)
    )

    return repo


# ── OntologyCompiler Tests ───────────────────────────────────────────

class TestOntologyCompiler:
    """Tests for compiling YAML files to domain entities."""

    async def test_compile_from_l1_directory(self, repo, tmp_path):
        """Compiler should parse foundation.yaml and create L1 concepts."""
        l1_dir = tmp_path / "l1"
        l1_dir.mkdir()

        (l1_dir / "foundation.yaml").write_text("""
concepts:
  - id: Thing
    label: Thing
    abstract: true
    description: Root of all concepts
    properties:
      - name: label
        type: string
        required: true
  - id: Entity
    label: Entity
    inherits: Thing
    abstract: true
    description: A living or abstract entity
""")

        compiler = OntologyCompiler(
            l1_dir=str(l1_dir),
            l2_dir=str(tmp_path / "l2"),
            repository=repo,
        )
        total = await compiler.compile()

        assert total == 2
        thing = await repo.get_concept("Thing")
        assert thing is not None
        assert thing.abstract is True
        assert thing.layer == "L1"
        assert len(thing.properties) == 1
        assert thing.properties[0].name == "label"

        entity = await repo.get_concept("Entity")
        assert entity is not None
        assert entity.inherits == "Thing"

    async def test_compile_mixins(self, repo, tmp_path):
        """Compiler should parse mixins.yaml."""
        l1_dir = tmp_path / "l1"
        l1_dir.mkdir()

        (l1_dir / "mixins.yaml").write_text("""
mixins:
  - id: HasMonetaryValue
    label: Has Monetary Value
    description: Mixin for monetary items
    properties:
      - name: amount
        type: decimal
        required: true
      - name: currency
        type: string
        required: true
        default: EUR
""")

        compiler = OntologyCompiler(
            l1_dir=str(l1_dir),
            l2_dir=str(tmp_path / "l2"),
            repository=repo,
        )
        await compiler.compile()

        mixin = await repo.get_mixin("HasMonetaryValue")
        assert mixin is not None
        assert len(mixin.properties) == 2
        assert mixin.properties[0].name == "amount"
        assert mixin.properties[1].default_value == "EUR"

    async def test_compile_l2_with_extraction_template(self, repo, tmp_path):
        """L2 concepts with extraction templates should be parsed correctly."""
        l1_dir = tmp_path / "l1"
        l1_dir.mkdir()

        l2_dir = tmp_path / "l2"
        l2_dir.mkdir()

        (l2_dir / "artifacts.yaml").write_text("""
concepts:
  - id: Invoice
    label: Invoice
    inherits: Document
    synonyms:
      - factuur
      - facture
    properties:
      - name: invoice_number
        type: string
        required: true
    relationships:
      - name: issuedBy
        target: Organization
        cardinality: "1"
    extraction_template:
      classification_hints:
        - invoice
        - factuur
        - rechnung
      file_patterns:
        - "**/invoices/**"
""")

        compiler = OntologyCompiler(
            l1_dir=str(l1_dir),
            l2_dir=str(l2_dir),
            repository=repo,
        )
        total = await compiler.compile()

        assert total == 1
        invoice = await repo.get_concept("Invoice")
        assert invoice is not None
        assert invoice.layer == "L2"
        assert invoice.pillar == "artifacts"
        assert "factuur" in invoice.synonyms
        assert len(invoice.properties) == 1
        assert len(invoice.relationships) == 1
        assert invoice.extraction_template is not None
        assert "factuur" in invoice.extraction_template.classification_hints
        assert "**/invoices/**" in invoice.extraction_template.file_patterns

    async def test_compile_missing_l1_dir(self, repo, tmp_path):
        """Compiler should handle missing L1 directory gracefully."""
        compiler = OntologyCompiler(
            l1_dir=str(tmp_path / "nonexistent"),
            l2_dir=str(tmp_path / "nonexistent2"),
            repository=repo,
        )
        total = await compiler.compile()
        assert total == 0

    async def test_compile_resets_previous_data(self, repo, tmp_path):
        """Recompilation should clear old L1/L2 data first."""
        await repo.save_concept(_make_concept("OldConcept"))
        assert await repo.get_concept("OldConcept") is not None

        compiler = OntologyCompiler(
            l1_dir=str(tmp_path),
            l2_dir=str(tmp_path),
            repository=repo,
        )
        await compiler.compile()

        # Old concept should be gone
        assert await repo.get_concept("OldConcept") is None

    async def test_compile_preserves_l3_concepts(self, repo, tmp_path):
        """Recompilation should preserve L3 concepts created by users."""
        # Pre-populate with an L3 concept
        l3_concept = _make_concept("AcmeInvoice", layer="L3", inherits="Invoice")
        await repo.save_concept(l3_concept)

        l1_dir = tmp_path / "l1"
        l1_dir.mkdir()
        (l1_dir / "foundation.yaml").write_text("""
concepts:
  - id: Thing
    label: Thing
    abstract: true
""")

        compiler = OntologyCompiler(
            l1_dir=str(l1_dir),
            l2_dir=str(tmp_path / "l2"),
            repository=repo,
        )
        total = await compiler.compile()

        # L1 Thing (1) + preserved L3 AcmeInvoice (1) = 2
        assert total == 2
        assert await repo.get_concept("AcmeInvoice") is not None
        assert await repo.get_concept("Thing") is not None


# ── OntologyService Tests ────────────────────────────────────────────

class TestOntologyService:
    """Tests for the ontology query service."""

    async def test_list_concepts_all(self, populated_repo):
        service = OntologyService(populated_repo)
        concepts = await service.list_concepts()
        assert len(concepts) == 7

    async def test_list_concepts_by_layer(self, populated_repo):
        service = OntologyService(populated_repo)
        l2 = await service.list_concepts(layer="L2")
        assert all(c.layer == "L2" for c in l2)
        assert len(l2) == 4

    async def test_list_concepts_non_abstract(self, populated_repo):
        service = OntologyService(populated_repo)
        concrete = await service.list_concepts(abstract=False)
        assert all(not c.abstract for c in concrete)
        assert len(concrete) == 3

    async def test_get_children(self, populated_repo):
        service = OntologyService(populated_repo)
        children = await service.get_children("Document")
        ids = {c.id for c in children}
        assert ids == {"Invoice", "Contract"}

    async def test_get_ancestors(self, populated_repo):
        service = OntologyService(populated_repo)
        ancestors = await service.get_ancestors("Invoice")
        ids = [a.id for a in ancestors]
        assert ids == ["Thing", "Object", "Document"]

    async def test_search_by_synonym(self, populated_repo):
        service = OntologyService(populated_repo)
        results = await service.search("factuur")
        assert any(c.id == "Invoice" for c in results)

    async def test_search_by_label(self, populated_repo):
        service = OntologyService(populated_repo)
        results = await service.search("Person")
        assert any(c.id == "Person" for c in results)

    async def test_get_tree(self, populated_repo):
        service = OntologyService(populated_repo)
        tree = await service.get_tree()
        # Root should be Thing
        assert len(tree) == 1
        assert tree[0]["id"] == "Thing"
        # Thing has two children: Entity and Object
        child_ids = {c["id"] for c in tree[0]["children"]}
        assert child_ids == {"Entity", "Object"}

    async def test_get_stats(self, populated_repo):
        service = OntologyService(populated_repo)
        stats = await service.get_stats()
        assert stats["total_concepts"] == 7
        assert stats["by_layer"]["L1"] == 3
        assert stats["by_layer"]["L2"] == 4
        assert stats["abstract_count"] == 4
        assert stats["classifiable_count"] == 3


# ── L3 CRUD Tests ────────────────────────────────────────────────────

class TestOntologyServiceL3:
    """Tests for L3 concept creation and deletion."""

    async def test_create_concept_l3_success(self, populated_repo):
        """Creating a valid L3 concept inheriting from L2 should succeed."""
        service = OntologyService(populated_repo)
        concept = _make_concept(
            "AcmeInvoice", layer="L3", inherits="Invoice", pillar="artifacts"
        )
        created = await service.create_concept(concept)
        assert created.id == "AcmeInvoice"
        assert created.layer == "L3"

        # Should be retrievable
        fetched = await service.get_concept("AcmeInvoice")
        assert fetched is not None
        assert fetched.inherits == "Invoice"

    async def test_create_concept_duplicate_id_fails(self, populated_repo):
        """Creating a concept with an existing ID should raise."""
        service = OntologyService(populated_repo)
        concept = _make_concept("Invoice", layer="L3", inherits="Document")

        with pytest.raises(ConceptAlreadyExistsError, match="already exists"):
            await service.create_concept(concept)

    async def test_create_concept_missing_parent_fails(self, populated_repo):
        """Creating a concept with a non-existent parent should raise."""
        service = OntologyService(populated_repo)
        concept = _make_concept("Orphan", layer="L3", inherits="NonExistent")

        with pytest.raises(ParentConceptNotFoundError, match="not found"):
            await service.create_concept(concept)

    async def test_delete_l3_concept_success(self, populated_repo):
        """Deleting an L3 concept should succeed."""
        service = OntologyService(populated_repo)

        # First create an L3 concept
        concept = _make_concept("AcmeInvoice", layer="L3", inherits="Invoice")
        await service.create_concept(concept)
        assert await service.get_concept("AcmeInvoice") is not None

        # Delete it
        result = await service.delete_concept("AcmeInvoice")
        assert result is True
        assert await service.get_concept("AcmeInvoice") is None

    async def test_delete_l1_concept_fails(self, populated_repo):
        """Deleting an L1 concept should raise ProtectedConceptError."""
        service = OntologyService(populated_repo)
        with pytest.raises(ProtectedConceptError, match="L1"):
            await service.delete_concept("Thing")

    async def test_delete_l2_concept_fails(self, populated_repo):
        """Deleting an L2 concept should raise ProtectedConceptError."""
        service = OntologyService(populated_repo)
        with pytest.raises(ProtectedConceptError, match="L2"):
            await service.delete_concept("Invoice")

    async def test_delete_nonexistent_returns_false(self, populated_repo):
        """Deleting a non-existent concept should return False."""
        service = OntologyService(populated_repo)
        result = await service.delete_concept("DoesNotExist")
        assert result is False

    async def test_delete_concept_with_children_fails(self, populated_repo):
        """Deleting a concept with children should raise ProtectedConceptError."""
        service = OntologyService(populated_repo)

        # Create L3 parent and child
        parent = _make_concept("AcmeDoc", layer="L3", inherits="Document")
        child = _make_concept("AcmeReport", layer="L3", inherits="AcmeDoc")
        await service.create_concept(parent)
        await service.create_concept(child)

        # Cannot delete parent while child exists
        with pytest.raises(ProtectedConceptError, match="child concept"):
            await service.delete_concept("AcmeDoc")

    async def test_get_resolved_properties(self, populated_repo):
        """Resolved properties should include inherited properties from ancestors."""
        service = OntologyService(populated_repo)

        # Add properties to Document (L2)
        doc = await service.get_concept("Document")
        doc.properties = [
            ConceptProperty(name="title", type="string", required=True),
            ConceptProperty(name="created_date", type="date"),
        ]
        await populated_repo.save_concept(doc)

        # Add properties to Invoice (L2)
        inv = await service.get_concept("Invoice")
        inv.properties = [
            ConceptProperty(name="invoice_number", type="string", required=True),
            ConceptProperty(name="amount", type="decimal"),
        ]
        await populated_repo.save_concept(inv)

        # Resolved properties for Invoice should include Document's + Invoice's own
        resolved = await service.get_resolved_properties("Invoice")
        names = [p.name for p in resolved]
        assert "title" in names
        assert "created_date" in names
        assert "invoice_number" in names
        assert "amount" in names

    async def test_resolved_properties_child_overrides_parent(self, populated_repo):
        """A child property with the same name should override the parent's."""
        service = OntologyService(populated_repo)

        # Document has a 'status' property
        doc = await service.get_concept("Document")
        doc.properties = [
            ConceptProperty(name="status", type="string", description="General status"),
        ]
        await populated_repo.save_concept(doc)

        # Invoice overrides 'status' with more specific definition
        inv = await service.get_concept("Invoice")
        inv.properties = [
            ConceptProperty(name="status", type="enum", description="Invoice status"),
        ]
        await populated_repo.save_concept(inv)

        resolved = await service.get_resolved_properties("Invoice")
        status_prop = next(p for p in resolved if p.name == "status")
        assert status_prop.type == "enum"
        assert status_prop.description == "Invoice status"


# ── Embedded Type Tests ─────────────────────────────────────────────


class TestEmbeddedTypeCompiler:
    """Tests for compiling embedded types from YAML."""

    async def test_compile_embedded_types(self, repo, tmp_path):
        """Compiler should parse embedded-types.yaml and persist types."""
        et_file = tmp_path / "embedded-types.yaml"
        et_file.write_text("""
foundation_value_types:
  - id: PostalAddress
    layer: L1
    description: A structured mailing address.
    applies_to:
      - Person
      - Organization
    synonyms:
      - address
    properties:
      - name: street
        type: string
        required: true
        description: Street name and number
      - name: city
        type: string
        required: true
      - name: postal_code
        type: string

entity_embedded_types:
  - id: ContactMethod
    layer: L2
    description: A way to contact an entity.
    applies_to:
      - Person
    properties:
      - name: type
        type: enum
        required: true
        values:
          - Phone
          - Email
      - name: value
        type: string
        required: true
""")

        compiler = OntologyCompiler(
            l1_dir=str(tmp_path / "l1"),
            l2_dir=str(tmp_path / "l2"),
            repository=repo,
            embedded_types_file=str(et_file),
        )
        await compiler.compile()

        address = await repo.get_embedded_type("PostalAddress")
        assert address is not None
        assert address.layer == "L1"
        assert "Person" in address.applies_to
        assert "Organization" in address.applies_to
        assert len(address.properties) == 3
        assert address.properties[0].name == "street"
        assert address.properties[0].required is True

        contact = await repo.get_embedded_type("ContactMethod")
        assert contact is not None
        assert contact.layer == "L2"
        assert len(contact.properties) == 2
        assert contact.properties[0].values == ["Phone", "Email"]

    async def test_compile_no_embedded_types_file(self, repo, tmp_path):
        """Compiler should work fine without embedded types file."""
        compiler = OntologyCompiler(
            l1_dir=str(tmp_path),
            l2_dir=str(tmp_path),
            repository=repo,
        )
        total = await compiler.compile()
        assert total == 0

    async def test_embedded_types_cleared_on_recompile(self, repo, tmp_path):
        """Recompilation should clear previousembedded types."""
        await repo.save_embedded_type(
            EmbeddedType(id="OldType", layer="L1", applies_to=["Thing"])
        )
        assert await repo.get_embedded_type("OldType") is not None

        compiler = OntologyCompiler(
            l1_dir=str(tmp_path),
            l2_dir=str(tmp_path),
            repository=repo,
        )
        await compiler.compile()
        assert await repo.get_embedded_type("OldType") is None


class TestEmbeddedTypeService:
    """Tests for embedded type resolution via OntologyService."""

    async def test_get_embedded_types_direct(self, populated_repo):
        """Should find embedded types that directly apply to a concept."""
        service = OntologyService(populated_repo)

        await populated_repo.save_embedded_type(
            EmbeddedType(
                id="InvoiceLineItem",
                layer="L2",
                applies_to=["Invoice"],
                properties=[
                    EmbeddedTypeProperty(name="description", type="string", required=True),
                    EmbeddedTypeProperty(name="amount", type="decimal", required=True),
                ],
            )
        )

        types = await service.get_embedded_types_for_concept("Invoice")
        assert len(types) == 1
        assert types[0].id == "InvoiceLineItem"
        assert len(types[0].properties) == 2

    async def test_get_embedded_types_inherited(self, populated_repo):
        """Should find embedded types from ancestor concepts."""
        service = OntologyService(populated_repo)

        # PostalAddress applies to Entity
        await populated_repo.save_embedded_type(
            EmbeddedType(
                id="PostalAddress",
                layer="L1",
                applies_to=["Entity"],
                properties=[
                    EmbeddedTypeProperty(name="street", type="string"),
                ],
            )
        )

        # Person inherits from Entity, so should inherit PostalAddress
        types = await service.get_embedded_types_for_concept("Person")
        assert len(types) == 1
        assert types[0].id == "PostalAddress"

    async def test_get_embedded_types_nonexistent_concept(self, populated_repo):
        """Should return empty list for non-existent concept."""
        service = OntologyService(populated_repo)
        types = await service.get_embedded_types_for_concept("DoesNotExist")
        assert types == []

    async def test_stats_include_embedded_type_count(self, populated_repo):
        """Stats should include count of embedded types."""
        service = OntologyService(populated_repo)

        await populated_repo.save_embedded_type(
            EmbeddedType(
                id="InvoiceLineItem",
                layer="L2",
                applies_to=["Invoice"],
            )
        )
        await populated_repo.save_embedded_type(
            EmbeddedType(
                id="ContractClause",
                layer="L2",
                applies_to=["Contract"],
            )
        )

        stats = await service.get_stats()
        assert stats["embedded_type_count"] == 2
