"""Ontology API controller — endpoints for querying and managing the ontology."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.schemas.ontology import (
    ConceptDetailSchema,
    ConceptPropertySchema,
    ConceptRelationshipSchema,
    ConceptSummarySchema,
    ConceptTreeNodeSchema,
    CreateConceptSchema,
    EmbeddedTypePropertySchema,
    EmbeddedTypeSchema,
    ExtractionTemplateSchema,
    InheritedPropertyGroupSchema,
    OntologyStatsSchema,
)
from app.application.services.ontology_service import (
    ConceptAlreadyExistsError,
    OntologyService,
    ParentConceptNotFoundError,
    ProtectedConceptError,
)
from app.domain.entities import (
    ConceptProperty,
    ConceptRelationship,
    ExtractionTemplate,
    OntologyConcept,
)
from app.infrastructure.dependencies import get_ontology_service

router = APIRouter(prefix="/ontology", tags=["ontology"])


# ── Helpers ──────────────────────────────────────────────────────────

def _to_summary(c) -> ConceptSummarySchema:
    """Map a domain OntologyConcept to a summary schema."""
    return ConceptSummarySchema(
        id=c.id,
        layer=c.layer,
        label=c.label,
        inherits=c.inherits,
        abstract=c.abstract,
        pillar=c.pillar,
        synonym_count=len(c.synonyms),
        property_count=len(c.properties),
        has_extraction_template=c.extraction_template is not None,
    )


def _map_properties(props) -> list[ConceptPropertySchema]:
    return [
        ConceptPropertySchema(
            name=p.name,
            type=p.type,
            required=p.required,
            default_value=str(p.default_value) if p.default_value is not None else None,
            description=p.description,
        )
        for p in props
    ]


def _map_relationships(rels) -> list[ConceptRelationshipSchema]:
    return [
        ConceptRelationshipSchema(
            name=r.name,
            target=r.target,
            cardinality=r.cardinality,
            inverse=r.inverse,
            description=r.description,
        )
        for r in rels
    ]


def _map_extraction_template(et) -> ExtractionTemplateSchema | None:
    if et is None:
        return None
    return ExtractionTemplateSchema(
        classification_hints=et.classification_hints,
        file_patterns=et.file_patterns,
    )


def _to_detail(c, ancestors=None, embedded_types=None) -> ConceptDetailSchema:
    """Map a domain OntologyConcept to a detail schema."""

    # Build inherited property groups from ancestors (only those with content)
    inherited = None
    if ancestors:
        inherited = []
        for a in ancestors:
            has_content = a.properties or a.relationships or a.extraction_template
            if has_content:
                inherited.append(
                    InheritedPropertyGroupSchema(
                        source_id=a.id,
                        source_label=a.label,
                        source_layer=a.layer,
                        properties=_map_properties(a.properties),
                        relationships=_map_relationships(a.relationships),
                        extraction_template=_map_extraction_template(a.extraction_template),
                    )
                )

    # Map embedded types to schema
    et_schemas = []
    if embedded_types:
        for et in embedded_types:
            et_schemas.append(
                EmbeddedTypeSchema(
                    id=et.id,
                    layer=et.layer,
                    description=et.description,
                    applies_to=et.applies_to,
                    synonyms=et.synonyms,
                    properties=[
                        EmbeddedTypePropertySchema(
                            name=p.name,
                            type=p.type,
                            required=p.required,
                            description=p.description,
                            values=p.values,
                        )
                        for p in et.properties
                    ],
                )
            )

    return ConceptDetailSchema(
        id=c.id,
        layer=c.layer,
        label=c.label,
        inherits=c.inherits,
        abstract=c.abstract,
        description=c.description,
        pillar=c.pillar,
        synonyms=c.synonyms,
        mixins=c.mixins,
        properties=_map_properties(c.properties),
        relationships=_map_relationships(c.relationships),
        extraction_template=_map_extraction_template(c.extraction_template),
        ancestors=[_to_summary(a) for a in ancestors] if ancestors else None,
        inherited_properties=inherited,
        embedded_types=et_schemas,
    )


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/concepts", response_model=list[ConceptSummarySchema])
async def list_concepts(
    layer: str | None = Query(None, description="Filter by layer (L1 or L2)"),
    pillar: str | None = Query(None, description="Filter by pillar"),
    abstract: bool | None = Query(None, description="Filter by abstract flag"),
    service: OntologyService = Depends(get_ontology_service),
):
    """List all ontology concepts with optional filters."""
    concepts = await service.list_concepts(layer=layer, pillar=pillar, abstract=abstract)
    return [_to_summary(c) for c in concepts]


@router.get("/concepts/{concept_id}", response_model=ConceptDetailSchema)
async def get_concept(
    concept_id: str,
    service: OntologyService = Depends(get_ontology_service),
):
    """Get detailed information about a single concept, including its ancestry."""
    concept = await service.get_concept(concept_id)
    if concept is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Concept '{concept_id}' not found",
        )
    ancestors = await service.get_ancestors(concept_id)
    embedded_types = await service.get_embedded_types_for_concept(concept_id)
    return _to_detail(concept, ancestors=ancestors, embedded_types=embedded_types)


@router.get("/concepts/{concept_id}/children", response_model=list[ConceptSummarySchema])
async def get_children(
    concept_id: str,
    service: OntologyService = Depends(get_ontology_service),
):
    """Get direct children of a concept."""
    children = await service.get_children(concept_id)
    return [_to_summary(c) for c in children]


@router.get("/tree", response_model=list[ConceptTreeNodeSchema])
async def get_tree(
    service: OntologyService = Depends(get_ontology_service),
):
    """Get the full ontology hierarchy as a tree."""
    return await service.get_tree()


@router.get("/search", response_model=list[ConceptSummarySchema])
async def search_concepts(
    q: str = Query(..., min_length=1, description="Search query"),
    service: OntologyService = Depends(get_ontology_service),
):
    """Search concepts by label, synonym, or classification hint."""
    results = await service.search(q)
    return [_to_summary(c) for c in results]


@router.get("/stats", response_model=OntologyStatsSchema)
async def get_stats(
    service: OntologyService = Depends(get_ontology_service),
):
    """Get ontology statistics — concept counts by layer, pillar, etc."""
    return await service.get_stats()


@router.post(
    "/concepts",
    response_model=ConceptDetailSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_concept(
    body: CreateConceptSchema,
    service: OntologyService = Depends(get_ontology_service),
):
    """Create a new L3 ontology concept."""
    # Map schema → domain entity
    properties = [
        ConceptProperty(
            name=p.name,
            type=p.type,
            required=p.required,
            default_value=p.default_value,
            description=p.description,
        )
        for p in body.properties
    ]

    relationships = [
        ConceptRelationship(
            name=r.name,
            target=r.target,
            cardinality=r.cardinality,
            inverse=r.inverse,
            description=r.description,
        )
        for r in body.relationships
    ]

    extraction_template = None
    if body.extraction_template:
        extraction_template = ExtractionTemplate(
            classification_hints=body.extraction_template.classification_hints,
            file_patterns=body.extraction_template.file_patterns,
        )

    concept = OntologyConcept(
        id=body.id,
        layer="L3",
        label=body.label,
        inherits=body.inherits,
        abstract=body.abstract,
        description=body.description,
        pillar=body.pillar,
        synonyms=body.synonyms,
        mixins=body.mixins,
        properties=properties,
        relationships=relationships,
        extraction_template=extraction_template,
    )

    try:
        created = await service.create_concept(concept)
    except ConceptAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except ParentConceptNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return _to_detail(created)


@router.delete(
    "/concepts/{concept_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_concept(
    concept_id: str,
    service: OntologyService = Depends(get_ontology_service),
):
    """Delete an L3+ ontology concept. L1/L2 concepts cannot be deleted."""
    try:
        deleted = await service.delete_concept(concept_id)
    except ProtectedConceptError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Concept '{concept_id}' not found",
        )
