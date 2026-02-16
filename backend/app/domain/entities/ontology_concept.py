"""Domain entities for ontology concepts — pure Python, no framework dependencies."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConceptProperty:
    """A typed property defined on an ontology concept."""

    name: str
    type: str
    required: bool = False
    default_value: Any = None
    description: str = ""


@dataclass
class ConceptRelationship:
    """A typed directional relationship between concepts."""

    name: str
    target: str
    cardinality: str = "0..*"
    inverse: str | None = None
    description: str = ""


@dataclass
class ExtractionTemplate:
    """Defines how to classify and extract metadata for a concept."""

    classification_hints: list[str] = field(default_factory=list)
    file_patterns: list[str] = field(default_factory=list)


@dataclass
class Mixin:
    """A reusable set of properties that can be mixed into any concept."""

    id: str
    layer: str
    label: str
    description: str = ""
    properties: list[ConceptProperty] = field(default_factory=list)


@dataclass
class EmbeddedTypeProperty:
    """A typed property on an embedded type definition.

    Supports enum types via the ``values`` field, which lists the allowed
    choices (e.g. ``["Phone", "Email", "Fax"]``).
    """

    name: str
    type: str
    required: bool = False
    description: str = ""
    values: list[str] = field(default_factory=list)


@dataclass
class EmbeddedType:
    """A structured value object that exists only within a parent concept.

    Embedded types have no independent identity — they are always extracted
    as part of a parent document.  The ``applies_to`` list specifies which
    ontology concepts may contain instances of this type (e.g. an
    ``InvoiceLineItem`` applies to ``Invoice`` and ``CreditNote``).
    """

    id: str
    layer: str
    description: str = ""
    applies_to: list[str] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    properties: list[EmbeddedTypeProperty] = field(default_factory=list)


@dataclass
class OntologyConcept:
    """Core domain entity: a single node in the ontology hierarchy.

    Represents both L1 foundation concepts (Thing, Entity, Object…) and
    L2 enterprise concepts (Invoice, Contract, Person…).
    """

    id: str
    layer: str
    label: str
    inherits: str | None = None
    abstract: bool = False
    description: str = ""
    synonyms: list[str] = field(default_factory=list)
    mixins: list[str] = field(default_factory=list)
    properties: list[ConceptProperty] = field(default_factory=list)
    relationships: list[ConceptRelationship] = field(default_factory=list)
    extraction_template: ExtractionTemplate | None = None
    pillar: str | None = None

    @property
    def is_classifiable(self) -> bool:
        """True if this concept can be used as a classification target."""
        return not self.abstract and self.extraction_template is not None

    def get_all_hints(self) -> list[str]:
        """Return all classification hints including synonyms."""
        hints = list(self.synonyms)
        if self.extraction_template:
            hints.extend(self.extraction_template.classification_hints)
        return hints
