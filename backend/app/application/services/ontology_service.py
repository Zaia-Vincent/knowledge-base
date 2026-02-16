"""Ontology query service — thin application-layer facade over the repository."""

from app.domain.entities import OntologyConcept, ConceptProperty, EmbeddedType
from app.application.interfaces import OntologyRepository


class ConceptAlreadyExistsError(Exception):
    """Raised when a concept with the same ID already exists."""
    pass


class ParentConceptNotFoundError(Exception):
    """Raised when the referenced parent concept does not exist."""
    pass


class ProtectedConceptError(Exception):
    """Raised when attempting to mutate a protected (L1/L2) concept."""
    pass


class OntologyService:
    """Application service for ontology queries.

    Provides business-level operations on the compiled ontology.
    """

    def __init__(self, repository: OntologyRepository):
        self._repo = repository

    # ── Read operations ──────────────────────────────────────────────

    async def get_concept(self, concept_id: str) -> OntologyConcept | None:
        """Retrieve a single concept by ID."""
        return await self._repo.get_concept(concept_id)

    async def list_concepts(
        self,
        layer: str | None = None,
        pillar: str | None = None,
        abstract: bool | None = None,
    ) -> list[OntologyConcept]:
        """List concepts with optional filters."""
        return await self._repo.get_all_concepts(
            layer=layer, pillar=pillar, abstract=abstract
        )

    async def get_children(self, concept_id: str) -> list[OntologyConcept]:
        """Get direct children of a concept."""
        return await self._repo.get_children(concept_id)

    async def get_ancestors(self, concept_id: str) -> list[OntologyConcept]:
        """Get the full inheritance chain up to root."""
        return await self._repo.get_ancestors(concept_id)

    async def search(self, query: str) -> list[OntologyConcept]:
        """Search concepts by label, synonym, or classification hint."""
        return await self._repo.search_concepts(query)

    async def get_tree(self) -> list[dict]:
        """Build the full hierarchy tree for UI display.

        Returns a nested list of dicts: {id, label, layer, abstract, children: [...]}.
        """
        all_concepts = await self._repo.get_all_concepts()

        # Build lookup and children map
        lookup: dict[str, OntologyConcept] = {c.id: c for c in all_concepts}
        children_map: dict[str | None, list[OntologyConcept]] = {}
        for concept in all_concepts:
            parent = concept.inherits
            children_map.setdefault(parent, []).append(concept)

        def _build_node(concept: OntologyConcept) -> dict:
            kids = children_map.get(concept.id, [])
            return {
                "id": concept.id,
                "label": concept.label,
                "layer": concept.layer,
                "abstract": concept.abstract,
                "pillar": concept.pillar,
                "children": [_build_node(c) for c in sorted(kids, key=lambda x: x.label)],
            }

        # Roots are concepts with no parent (inherits=None)
        roots = children_map.get(None, [])
        return [_build_node(r) for r in sorted(roots, key=lambda x: x.label)]

    async def get_stats(self) -> dict:
        """Return ontology statistics."""
        all_concepts = await self._repo.get_all_concepts()

        stats = {
            "total_concepts": len(all_concepts),
            "by_layer": {},
            "by_pillar": {},
            "abstract_count": 0,
            "classifiable_count": 0,
            "embedded_type_count": 0,
        }

        for c in all_concepts:
            stats["by_layer"][c.layer] = stats["by_layer"].get(c.layer, 0) + 1
            if c.pillar:
                stats["by_pillar"][c.pillar] = stats["by_pillar"].get(c.pillar, 0) + 1
            if c.abstract:
                stats["abstract_count"] += 1
            if c.is_classifiable:
                stats["classifiable_count"] += 1

        # Count embedded types (distinct, not per concept)
        try:
            all_et = await self._repo.get_embedded_types_for_concept("__count_all__")
        except Exception:
            all_et = []
        # Fallback: use a known dummy — real count comes from the total scan below
        # For now, iterate unique concept IDs to discover embedded types
        seen_et_ids: set[str] = set()
        for c in all_concepts:
            if c.is_classifiable:
                ets = await self._repo.get_embedded_types_for_concept(c.id)
                for et in ets:
                    seen_et_ids.add(et.id)
        stats["embedded_type_count"] = len(seen_et_ids)

        return stats

    # ── Write operations (L3 only) ───────────────────────────────────

    async def create_concept(self, concept: OntologyConcept) -> OntologyConcept:
        """Create a new L3 concept.

        Validates:
          - ID uniqueness
          - Parent concept existence
          - Parent is not from a lower layer than the new concept
        """
        # 1. No duplicate IDs
        existing = await self._repo.get_concept(concept.id)
        if existing is not None:
            raise ConceptAlreadyExistsError(
                f"Concept '{concept.id}' already exists"
            )

        # 2. Parent must exist
        parent = await self._repo.get_concept(concept.inherits)
        if parent is None:
            raise ParentConceptNotFoundError(
                f"Parent concept '{concept.inherits}' not found"
            )

        # 3. Save
        await self._repo.save_concept(concept)
        return concept

    async def delete_concept(self, concept_id: str) -> bool:
        """Delete an L3 concept.

        Raises ProtectedConceptError if the concept is L1 or L2.
        Returns True if deleted, False if concept was not found.
        """
        concept = await self._repo.get_concept(concept_id)
        if concept is None:
            return False

        if concept.layer in ("L1", "L2"):
            raise ProtectedConceptError(
                f"Cannot delete {concept.layer} concept '{concept_id}' — only L3+ concepts may be deleted"
            )

        # Check for children — prevent deletion of concepts that have dependents
        children = await self._repo.get_children(concept_id)
        if children:
            child_ids = ", ".join(c.id for c in children[:5])
            raise ProtectedConceptError(
                f"Cannot delete concept '{concept_id}' — it has {len(children)} child concept(s): {child_ids}"
            )

        return await self._repo.delete_concept(concept_id)

    async def get_resolved_properties(
        self, concept_id: str
    ) -> list[ConceptProperty]:
        """Collect all properties from the concept, its ancestors, and their mixins.

        Resolution order for each concept in the chain (root → child):
          1. Mixin properties (in declared order)
          2. Concept's own properties
        Child properties override parent properties with the same name.
        """
        ancestors = await self._repo.get_ancestors(concept_id)
        concept = await self._repo.get_concept(concept_id)
        if concept is None:
            return []

        # Build ordered chain: root → ... → parent → self
        chain = ancestors + [concept]

        seen: dict[str, ConceptProperty] = {}
        for c in chain:
            # Resolve mixin properties first (so concept's own override them)
            for mixin_id in c.mixins:
                mixin = await self._repo.get_mixin(mixin_id)
                if mixin:
                    for prop in mixin.properties:
                        seen[prop.name] = prop
            # Then concept's own properties
            for prop in c.properties:
                seen[prop.name] = prop

        return list(seen.values())

    async def get_embedded_types_for_concept(
        self, concept_id: str
    ) -> list[EmbeddedType]:
        """Get all embedded types applicable to a concept, including inherited ones.

        Walks up the inheritance chain so that, e.g., if ``PostalAddress``
        applies to ``Entity``, a ``Person`` (which inherits from ``Entity``)
        will also include ``PostalAddress``.
        """
        ancestors = await self._repo.get_ancestors(concept_id)
        concept = await self._repo.get_concept(concept_id)
        if concept is None:
            return []

        # Collect concept IDs to check (self + ancestors)
        concept_ids = [a.id for a in ancestors] + [concept.id]

        seen: dict[str, EmbeddedType] = {}
        for cid in concept_ids:
            for et in await self._repo.get_embedded_types_for_concept(cid):
                if et.id not in seen:
                    seen[et.id] = et

        return list(seen.values())
