"""SQLAlchemy ORM models for the ontology database.

These models represent the compiled L1/L2 ontology in SQLite.
They are rebuilt every time the application starts.
"""

import json

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.infrastructure.database.base import Base


class ConceptModel(Base):
    """Compiled ontology concept."""

    __tablename__ = "concepts"

    id = Column(String(100), primary_key=True)
    layer = Column(String(10), nullable=False, index=True)
    inherits = Column(String(100), nullable=True, index=True)
    abstract = Column(Boolean, nullable=False, default=False)
    label = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    pillar = Column(String(50), nullable=True, index=True)

    # JSON-encoded lists stored as text (SQLite-friendly)
    synonyms_json = Column(Text, nullable=True)
    mixins_json = Column(Text, nullable=True)

    # Related collections
    properties = relationship(
        "ConceptPropertyModel",
        back_populates="concept",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    relationships_list = relationship(
        "ConceptRelationshipModel",
        back_populates="concept",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    extraction_template = relationship(
        "ExtractionTemplateModel",
        back_populates="concept",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    @property
    def synonyms(self) -> list[str]:
        return json.loads(self.synonyms_json) if self.synonyms_json else []

    @synonyms.setter
    def synonyms(self, value: list[str]) -> None:
        self.synonyms_json = json.dumps(value)

    @property
    def mixins(self) -> list[str]:
        return json.loads(self.mixins_json) if self.mixins_json else []

    @mixins.setter
    def mixins(self, value: list[str]) -> None:
        self.mixins_json = json.dumps(value)


class ConceptPropertyModel(Base):
    """Property definition on a concept."""

    __tablename__ = "concept_properties"

    id = Column(Integer, primary_key=True, autoincrement=True)
    concept_id = Column(
        String(100), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)
    type = Column(String(100), nullable=False, default="string")
    required = Column(Boolean, nullable=False, default=False)
    default_value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    concept = relationship("ConceptModel", back_populates="properties")


class ConceptRelationshipModel(Base):
    """Relationship definition on a concept."""

    __tablename__ = "concept_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    concept_id = Column(
        String(100), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)
    target = Column(String(100), nullable=False)
    cardinality = Column(String(20), nullable=False, default="0..*")
    inverse = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)

    concept = relationship("ConceptModel", back_populates="relationships_list")


class ExtractionTemplateModel(Base):
    """Extraction template associated with a concept."""

    __tablename__ = "extraction_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    concept_id = Column(
        String(100),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    classification_hints_json = Column(Text, nullable=True)
    file_patterns_json = Column(Text, nullable=True)

    concept = relationship("ConceptModel", back_populates="extraction_template")

    @property
    def classification_hints(self) -> list[str]:
        return json.loads(self.classification_hints_json) if self.classification_hints_json else []

    @classification_hints.setter
    def classification_hints(self, value: list[str]) -> None:
        self.classification_hints_json = json.dumps(value)

    @property
    def file_patterns(self) -> list[str]:
        return json.loads(self.file_patterns_json) if self.file_patterns_json else []

    @file_patterns.setter
    def file_patterns(self, value: list[str]) -> None:
        self.file_patterns_json = json.dumps(value)


class MixinModel(Base):
    """Reusable property set (mixin)."""

    __tablename__ = "mixins"

    id = Column(String(100), primary_key=True)
    layer = Column(String(10), nullable=False)
    label = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    properties = relationship(
        "MixinPropertyModel",
        back_populates="mixin",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class MixinPropertyModel(Base):
    """Property definition on a mixin."""

    __tablename__ = "mixin_properties"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mixin_id = Column(
        String(100), ForeignKey("mixins.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)
    type = Column(String(100), nullable=False, default="string")
    required = Column(Boolean, nullable=False, default=False)
    default_value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    mixin = relationship("MixinModel", back_populates="properties")


class EmbeddedTypeModel(Base):
    """Structured value object that exists only within parent concepts."""

    __tablename__ = "embedded_types"

    id = Column(String(100), primary_key=True)
    layer = Column(String(10), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # JSON-encoded lists stored as text (SQLite-friendly)
    applies_to_json = Column(Text, nullable=True)
    synonyms_json = Column(Text, nullable=True)

    properties = relationship(
        "EmbeddedTypePropertyModel",
        back_populates="embedded_type",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def applies_to(self) -> list[str]:
        return json.loads(self.applies_to_json) if self.applies_to_json else []

    @applies_to.setter
    def applies_to(self, value: list[str]) -> None:
        self.applies_to_json = json.dumps(value)

    @property
    def synonyms(self) -> list[str]:
        return json.loads(self.synonyms_json) if self.synonyms_json else []

    @synonyms.setter
    def synonyms(self, value: list[str]) -> None:
        self.synonyms_json = json.dumps(value)


class EmbeddedTypePropertyModel(Base):
    """Property definition on an embedded type."""

    __tablename__ = "embedded_type_properties"

    id = Column(Integer, primary_key=True, autoincrement=True)
    embedded_type_id = Column(
        String(100),
        ForeignKey("embedded_types.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    type = Column(String(100), nullable=False, default="string")
    required = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)
    values_json = Column(Text, nullable=True)  # Enum values

    embedded_type = relationship("EmbeddedTypeModel", back_populates="properties")

    @property
    def values(self) -> list[str]:
        return json.loads(self.values_json) if self.values_json else []

    @values.setter
    def values(self, value: list[str]) -> None:
        self.values_json = json.dumps(value)
