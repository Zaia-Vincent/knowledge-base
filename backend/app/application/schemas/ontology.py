"""Pydantic schemas for ontology API responses."""

from pydantic import BaseModel


class ConceptPropertySchema(BaseModel):
    name: str
    type: str
    required: bool
    default_value: str | None = None
    description: str


class ConceptRelationshipSchema(BaseModel):
    name: str
    target: str
    cardinality: str
    inverse: str | None = None
    description: str


class ExtractionTemplateSchema(BaseModel):
    classification_hints: list[str]
    file_patterns: list[str]


class EmbeddedTypePropertySchema(BaseModel):
    """A property on an embedded type."""

    name: str
    type: str
    required: bool
    description: str
    values: list[str] = []


class EmbeddedTypeSchema(BaseModel):
    """An embedded type associated with a concept."""

    id: str
    layer: str
    description: str
    applies_to: list[str]
    synonyms: list[str] = []
    properties: list[EmbeddedTypePropertySchema]


class ConceptSummarySchema(BaseModel):
    """Lightweight concept representation for list views."""

    id: str
    layer: str
    label: str
    inherits: str | None = None
    abstract: bool
    pillar: str | None = None
    synonym_count: int = 0
    property_count: int = 0
    has_extraction_template: bool = False


class InheritedPropertyGroupSchema(BaseModel):
    """Properties inherited from a single ancestor concept."""

    source_id: str
    source_label: str
    source_layer: str
    properties: list[ConceptPropertySchema]
    relationships: list[ConceptRelationshipSchema]
    extraction_template: ExtractionTemplateSchema | None = None


class ConceptDetailSchema(BaseModel):
    """Full concept representation for detail view."""

    id: str
    layer: str
    label: str
    inherits: str | None = None
    abstract: bool
    description: str
    pillar: str | None = None
    synonyms: list[str]
    mixins: list[str]
    properties: list[ConceptPropertySchema]
    relationships: list[ConceptRelationshipSchema]
    extraction_template: ExtractionTemplateSchema | None = None
    ancestors: list[ConceptSummarySchema] | None = None
    inherited_properties: list[InheritedPropertyGroupSchema] | None = None
    embedded_types: list[EmbeddedTypeSchema] = []


class ConceptTreeNodeSchema(BaseModel):
    """Recursive tree node for hierarchy display."""

    id: str
    label: str
    layer: str
    abstract: bool
    pillar: str | None = None
    children: list["ConceptTreeNodeSchema"] = []


class OntologyStatsSchema(BaseModel):
    """Ontology statistics."""

    total_concepts: int
    by_layer: dict[str, int]
    by_pillar: dict[str, int]
    abstract_count: int
    classifiable_count: int
    embedded_type_count: int = 0


# ── Request Schemas (L3 Create) ──────────────────────────────────────


class CreateConceptPropertySchema(BaseModel):
    """Property definition in a create-concept request."""

    name: str
    type: str = "string"
    required: bool = False
    default_value: str | None = None
    description: str = ""


class CreateConceptRelationshipSchema(BaseModel):
    """Relationship definition in a create-concept request."""

    name: str
    target: str
    cardinality: str = "0..*"
    inverse: str | None = None
    description: str = ""


class CreateExtractionTemplateSchema(BaseModel):
    """Extraction template in a create-concept request."""

    classification_hints: list[str] = []
    file_patterns: list[str] = []


class CreateConceptSchema(BaseModel):
    """Request body for creating a new L3 concept."""

    id: str
    label: str
    inherits: str
    description: str = ""
    pillar: str | None = None
    abstract: bool = False
    synonyms: list[str] = []
    mixins: list[str] = []
    properties: list[CreateConceptPropertySchema] = []
    relationships: list[CreateConceptRelationshipSchema] = []
    extraction_template: CreateExtractionTemplateSchema | None = None


class UpdateConceptSchema(BaseModel):
    """Request body for updating an existing L3+ concept.

    Only mutable fields are accepted — id, layer, inherits, and abstract
    are immutable after creation.
    """

    label: str | None = None
    description: str | None = None
    synonyms: list[str] | None = None
    properties: list[CreateConceptPropertySchema] | None = None
    relationships: list[CreateConceptRelationshipSchema] | None = None
    extraction_template: CreateExtractionTemplateSchema | None = None


class SuggestOntologyTypeRequestSchema(BaseModel):
    """Request body for AI-assisted L3 concept suggestion."""

    name: str
    description: str = ""
    inherits: str | None = None
    domain_context: str = ""
    style_preferences: list[str] = []
    reference_urls: list[str] = []
    include_internet_research: bool = True


class SuggestionReferenceSchema(BaseModel):
    """External reference used by the ontology assistant."""

    url: str
    title: str = ""
    summary: str = ""
    source_type: str = "web"


class SuggestOntologyTypeResponseSchema(BaseModel):
    """AI-assisted concept suggestion payload + rationale."""

    payload: CreateConceptSchema
    rationale: str = ""
    parent_reasoning: str = ""
    adaptation_tips: list[str] = []
    warnings: list[str] = []
    references: list[SuggestionReferenceSchema] = []
