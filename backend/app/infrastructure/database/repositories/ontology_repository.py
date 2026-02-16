"""SQLAlchemy implementation of the OntologyRepository for SQLite."""

import json

from sqlalchemy import select, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces import OntologyRepository
from app.domain.entities import (
    OntologyConcept,
    ConceptProperty,
    ConceptRelationship,
    ExtractionTemplate,
    Mixin,
    EmbeddedType,
    EmbeddedTypeProperty,
)
from app.infrastructure.database.models.ontology_models import (
    ConceptModel,
    ConceptPropertyModel,
    ConceptRelationshipModel,
    ExtractionTemplateModel,
    MixinModel,
    MixinPropertyModel,
    EmbeddedTypeModel,
    EmbeddedTypePropertyModel,
)


class SQLAlchemyOntologyRepository(OntologyRepository):
    """Concrete ontology repository backed by SQLite via SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Read Operations ──────────────────────────────────────────────

    async def get_concept(self, concept_id: str) -> OntologyConcept | None:
        result = await self._session.execute(
            select(ConceptModel).where(ConceptModel.id == concept_id)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_all_concepts(
        self,
        layer: str | None = None,
        pillar: str | None = None,
        abstract: bool | None = None,
    ) -> list[OntologyConcept]:
        stmt = select(ConceptModel)
        if layer is not None:
            stmt = stmt.where(ConceptModel.layer == layer)
        if pillar is not None:
            stmt = stmt.where(ConceptModel.pillar == pillar)
        if abstract is not None:
            stmt = stmt.where(ConceptModel.abstract == abstract)
        stmt = stmt.order_by(ConceptModel.label)

        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_children(self, concept_id: str) -> list[OntologyConcept]:
        result = await self._session.execute(
            select(ConceptModel)
            .where(ConceptModel.inherits == concept_id)
            .order_by(ConceptModel.label)
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_ancestors(self, concept_id: str) -> list[OntologyConcept]:
        ancestors: list[OntologyConcept] = []
        current_id = concept_id

        while current_id:
            result = await self._session.execute(
                select(ConceptModel).where(ConceptModel.id == current_id)
            )
            model = result.scalar_one_or_none()
            if model is None:
                break
            if model.id != concept_id:  # Don't include self
                ancestors.append(self._to_domain(model))
            current_id = model.inherits

        return list(reversed(ancestors))  # Root first

    async def search_concepts(self, query: str) -> list[OntologyConcept]:
        q = f"%{query.lower()}%"
        # Search in label, description, and synonyms JSON
        stmt = (
            select(ConceptModel)
            .where(
                or_(
                    ConceptModel.label.ilike(q),
                    ConceptModel.description.ilike(q),
                    ConceptModel.synonyms_json.ilike(q),
                )
            )
            .order_by(ConceptModel.label)
            .limit(50)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_concepts_by_pillar(self, pillar: str) -> list[OntologyConcept]:
        return await self.get_all_concepts(pillar=pillar)

    async def get_classifiable_concepts(self) -> list[OntologyConcept]:
        """Get non-abstract concepts that have extraction templates."""
        stmt = (
            select(ConceptModel)
            .where(ConceptModel.abstract == False)  # noqa: E712
            .join(ExtractionTemplateModel)
            .order_by(ConceptModel.label)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_mixin(self, mixin_id: str) -> Mixin | None:
        result = await self._session.execute(
            select(MixinModel).where(MixinModel.id == mixin_id)
        )
        model = result.scalar_one_or_none()
        return self._mixin_to_domain(model) if model else None

    # ── Write Operations ─────────────────────────────────────────────

    async def save_concept(self, concept: OntologyConcept) -> None:
        # Delete existing concept if present (recompilation)
        await self._session.execute(
            delete(ConceptModel).where(ConceptModel.id == concept.id)
        )
        await self._session.flush()

        model = ConceptModel(
            id=concept.id,
            layer=concept.layer,
            inherits=concept.inherits,
            abstract=concept.abstract,
            label=concept.label,
            description=concept.description,
            pillar=concept.pillar,
            synonyms_json=json.dumps(concept.synonyms),
            mixins_json=json.dumps(concept.mixins),
        )

        # Properties
        for prop in concept.properties:
            model.properties.append(
                ConceptPropertyModel(
                    name=prop.name,
                    type=prop.type,
                    required=prop.required,
                    default_value=str(prop.default_value) if prop.default_value is not None else None,
                    description=prop.description,
                )
            )

        # Relationships
        for rel in concept.relationships:
            model.relationships_list.append(
                ConceptRelationshipModel(
                    name=rel.name,
                    target=rel.target,
                    cardinality=rel.cardinality,
                    inverse=rel.inverse,
                    description=rel.description,
                )
            )

        # Extraction template
        if concept.extraction_template:
            model.extraction_template = ExtractionTemplateModel(
                classification_hints_json=json.dumps(
                    concept.extraction_template.classification_hints
                ),
                file_patterns_json=json.dumps(
                    concept.extraction_template.file_patterns
                ),
            )

        self._session.add(model)
        await self._session.flush()

    async def save_mixin(self, mixin: Mixin) -> None:
        await self._session.execute(
            delete(MixinModel).where(MixinModel.id == mixin.id)
        )
        await self._session.flush()

        model = MixinModel(
            id=mixin.id,
            layer=mixin.layer,
            label=mixin.label,
            description=mixin.description,
        )

        for prop in mixin.properties:
            model.properties.append(
                MixinPropertyModel(
                    name=prop.name,
                    type=prop.type,
                    required=prop.required,
                    default_value=str(prop.default_value) if prop.default_value is not None else None,
                    description=prop.description,
                )
            )

        self._session.add(model)
        await self._session.flush()

    # ── Embedded Type Operations ──────────────────────────────────────

    async def save_embedded_type(self, embedded_type: EmbeddedType) -> None:
        await self._session.execute(
            delete(EmbeddedTypeModel).where(EmbeddedTypeModel.id == embedded_type.id)
        )
        await self._session.flush()

        model = EmbeddedTypeModel(
            id=embedded_type.id,
            layer=embedded_type.layer,
            description=embedded_type.description,
            applies_to_json=json.dumps(embedded_type.applies_to),
            synonyms_json=json.dumps(embedded_type.synonyms),
        )

        for prop in embedded_type.properties:
            model.properties.append(
                EmbeddedTypePropertyModel(
                    name=prop.name,
                    type=prop.type,
                    required=prop.required,
                    description=prop.description,
                    values_json=json.dumps(prop.values) if prop.values else None,
                )
            )

        self._session.add(model)
        await self._session.flush()

    async def get_embedded_type(self, type_id: str) -> EmbeddedType | None:
        result = await self._session.execute(
            select(EmbeddedTypeModel).where(EmbeddedTypeModel.id == type_id)
        )
        model = result.scalar_one_or_none()
        return self._embedded_type_to_domain(model) if model else None

    async def get_embedded_types_for_concept(self, concept_id: str) -> list[EmbeddedType]:
        # Search for concept_id inside the JSON-encoded applies_to list
        pattern = f'%"{concept_id}"%'
        stmt = (
            select(EmbeddedTypeModel)
            .where(EmbeddedTypeModel.applies_to_json.like(pattern))
            .order_by(EmbeddedTypeModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._embedded_type_to_domain(m) for m in result.scalars().all()]

    # ── Delete / Clear ────────────────────────────────────────────────

    async def delete_concept(self, concept_id: str) -> bool:
        """Delete a concept by its ID. Returns True if deleted."""
        result = await self._session.execute(
            select(ConceptModel).where(ConceptModel.id == concept_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def clear_all(self) -> None:
        await self._session.execute(delete(EmbeddedTypePropertyModel))
        await self._session.execute(delete(EmbeddedTypeModel))
        await self._session.execute(delete(ExtractionTemplateModel))
        await self._session.execute(delete(ConceptRelationshipModel))
        await self._session.execute(delete(ConceptPropertyModel))
        await self._session.execute(delete(ConceptModel))
        await self._session.execute(delete(MixinPropertyModel))
        await self._session.execute(delete(MixinModel))
        await self._session.flush()

    # ── Mapping Helpers ──────────────────────────────────────────────

    def _to_domain(self, model: ConceptModel) -> OntologyConcept:
        """Map a SQLAlchemy model to a domain entity."""
        properties = [
            ConceptProperty(
                name=p.name,
                type=p.type,
                required=p.required,
                default_value=p.default_value,
                description=p.description or "",
            )
            for p in (model.properties or [])
        ]

        relationships = [
            ConceptRelationship(
                name=r.name,
                target=r.target,
                cardinality=r.cardinality,
                inverse=r.inverse,
                description=r.description or "",
            )
            for r in (model.relationships_list or [])
        ]

        extraction_template = None
        if model.extraction_template:
            extraction_template = ExtractionTemplate(
                classification_hints=model.extraction_template.classification_hints,
                file_patterns=model.extraction_template.file_patterns,
            )

        return OntologyConcept(
            id=model.id,
            layer=model.layer,
            label=model.label,
            inherits=model.inherits,
            abstract=model.abstract,
            description=model.description or "",
            synonyms=model.synonyms,
            mixins=model.mixins,
            properties=properties,
            relationships=relationships,
            extraction_template=extraction_template,
            pillar=model.pillar,
        )

    def _mixin_to_domain(self, model: MixinModel) -> Mixin:
        """Map a SQLAlchemy MixinModel to a domain entity."""
        properties = [
            ConceptProperty(
                name=p.name,
                type=p.type,
                required=p.required,
                default_value=p.default_value,
                description=p.description or "",
            )
            for p in (model.properties or [])
        ]

        return Mixin(
            id=model.id,
            layer=model.layer,
            label=model.label,
            description=model.description or "",
            properties=properties,
        )

    def _embedded_type_to_domain(self, model: EmbeddedTypeModel) -> EmbeddedType:
        """Map a SQLAlchemy EmbeddedTypeModel to a domain entity."""
        properties = [
            EmbeddedTypeProperty(
                name=p.name,
                type=p.type,
                required=p.required,
                description=p.description or "",
                values=p.values,
            )
            for p in (model.properties or [])
        ]

        return EmbeddedType(
            id=model.id,
            layer=model.layer,
            description=model.description or "",
            applies_to=model.applies_to,
            synonyms=model.synonyms,
            properties=properties,
        )
