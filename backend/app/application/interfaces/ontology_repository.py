"""Abstract repository interface (port) for ontology queries."""

from abc import ABC, abstractmethod

from app.domain.entities import OntologyConcept, Mixin, EmbeddedType


class OntologyRepository(ABC):
    """Port for ontology persistence — implemented in the infrastructure layer."""

    @abstractmethod
    async def get_concept(self, concept_id: str) -> OntologyConcept | None:
        """Retrieve a single concept by its ID."""
        ...

    @abstractmethod
    async def get_all_concepts(
        self,
        layer: str | None = None,
        pillar: str | None = None,
        abstract: bool | None = None,
    ) -> list[OntologyConcept]:
        """Retrieve concepts with optional filters."""
        ...

    @abstractmethod
    async def get_children(self, concept_id: str) -> list[OntologyConcept]:
        """Retrieve the direct children of a concept."""
        ...

    @abstractmethod
    async def get_ancestors(self, concept_id: str) -> list[OntologyConcept]:
        """Retrieve the full inheritance chain from concept up to root."""
        ...

    @abstractmethod
    async def search_concepts(self, query: str) -> list[OntologyConcept]:
        """Search concepts by label, synonym, or classification hint."""
        ...

    @abstractmethod
    async def get_concepts_by_pillar(self, pillar: str) -> list[OntologyConcept]:
        """Retrieve all concepts belonging to a pillar."""
        ...

    @abstractmethod
    async def get_classifiable_concepts(self) -> list[OntologyConcept]:
        """Retrieve all non-abstract concepts with extraction templates."""
        ...

    @abstractmethod
    async def get_mixin(self, mixin_id: str) -> Mixin | None:
        """Retrieve a mixin by its ID."""
        ...

    # ── Embedded types ───────────────────────────────────────────────

    @abstractmethod
    async def save_embedded_type(self, embedded_type: EmbeddedType) -> None:
        """Persist an embedded type (insert or replace)."""
        ...

    @abstractmethod
    async def get_embedded_type(self, type_id: str) -> EmbeddedType | None:
        """Retrieve a single embedded type by its ID."""
        ...

    @abstractmethod
    async def get_embedded_types_for_concept(self, concept_id: str) -> list[EmbeddedType]:
        """Retrieve all embedded types whose ``applies_to`` includes this concept."""
        ...

    # ── Mutations ────────────────────────────────────────────────────

    @abstractmethod
    async def save_concept(self, concept: OntologyConcept) -> None:
        """Persist a concept (insert or replace)."""
        ...

    @abstractmethod
    async def save_mixin(self, mixin: Mixin) -> None:
        """Persist a mixin (insert or replace)."""
        ...

    @abstractmethod
    async def delete_concept(self, concept_id: str) -> bool:
        """Delete a concept by ID. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    async def clear_all(self) -> None:
        """Remove all concepts, mixins, and embedded types (for recompilation)."""
        ...

