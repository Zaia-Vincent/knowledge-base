"""Ontology compiler — parses L1/L2 YAML files and persists them to SQLite.

Executed once at application startup via the FastAPI lifespan.
"""

import logging
from pathlib import Path

import yaml

from app.domain.entities import (
    OntologyConcept,
    ConceptProperty,
    ConceptRelationship,
    ExtractionTemplate,
    Mixin,
    EmbeddedType,
    EmbeddedTypeProperty,
)
from app.application.interfaces import OntologyRepository

logger = logging.getLogger(__name__)

# Pillar mapping: L2 filename → pillar name
_PILLAR_MAP = {
    "entities.yaml": "entities",
    "artifacts.yaml": "artifacts",
    "processes.yaml": "processes",
    "domain-knowledge.yaml": "domain-knowledge",
}


class OntologyCompiler:
    """Compiles L1+L2 YAML definitions to the ontology repository."""

    def __init__(
        self,
        l1_dir: str,
        l2_dir: str,
        repository: OntologyRepository,
        embedded_types_file: str | None = None,
    ):
        self._l1_dir = Path(l1_dir)
        self._l2_dir = Path(l2_dir)
        self._repo = repository
        self._embedded_types_file = Path(embedded_types_file) if embedded_types_file else None

    async def compile(self) -> int:
        """Parse all YAML files and persist concepts + mixins.

        Returns the total number of concepts compiled.
        L3+ concepts created by users are preserved across recompilation.
        """
        logger.info("Starting ontology compilation…")

        # Snapshot user-created L3+ concepts before clearing
        existing_l3: list[OntologyConcept] = []
        try:
            all_existing = await self._repo.get_all_concepts()
            existing_l3 = [c for c in all_existing if c.layer not in ("L1", "L2")]
            if existing_l3:
                logger.info("Preserving %d L3+ concepts across recompilation", len(existing_l3))
        except Exception:
            logger.debug("No existing concepts to preserve")

        # Clear previous compilation
        await self._repo.clear_all()

        total = 0

        # 1. Parse L1 foundation concepts
        foundation_path = self._l1_dir / "foundation.yaml"
        if foundation_path.exists():
            count = await self._parse_concepts_file(foundation_path, "L1", pillar=None)
            logger.info("Compiled %d L1 foundation concepts", count)
            total += count

        # 2. Parse L1 mixins
        mixins_path = self._l1_dir / "mixins.yaml"
        if mixins_path.exists():
            mixin_count = await self._parse_mixins_file(mixins_path)
            logger.info("Compiled %d L1 mixins", mixin_count)

        # 3. Parse L2 concept files
        if self._l2_dir.exists():
            for yaml_file in sorted(self._l2_dir.glob("*.yaml")):
                pillar = _PILLAR_MAP.get(yaml_file.name)
                count = await self._parse_concepts_file(yaml_file, "L2", pillar=pillar)
                logger.info("Compiled %d L2 concepts from %s", count, yaml_file.name)
                total += count

        # 4. Parse embedded types
        embedded_count = 0
        if self._embedded_types_file and self._embedded_types_file.exists():
            embedded_count = await self._parse_embedded_types_file(self._embedded_types_file)
            logger.info("Compiled %d embedded types", embedded_count)

        # 5. Restore preserved L3+ concepts
        for concept in existing_l3:
            await self._repo.save_concept(concept)
            total += 1
        if existing_l3:
            logger.info("Restored %d L3+ concepts", len(existing_l3))

        logger.info(
            "Ontology compilation complete: %d concepts, %d embedded types",
            total, embedded_count,
        )
        return total

    async def _parse_concepts_file(
        self, path: Path, layer: str, pillar: str | None
    ) -> int:
        """Parse a single YAML file containing concept definitions."""
        data = self._load_yaml(path)
        if data is None:
            return 0

        concepts_data = data.get("concepts", [])
        if not concepts_data:
            return 0

        count = 0
        for entry in concepts_data:
            concept = self._build_concept(entry, layer, pillar)
            await self._repo.save_concept(concept)
            count += 1

        return count

    async def _parse_mixins_file(self, path: Path) -> int:
        """Parse the mixins YAML file."""
        data = self._load_yaml(path)
        if data is None:
            return 0

        mixins_data = data.get("mixins", [])
        count = 0
        for entry in mixins_data:
            mixin = self._build_mixin(entry)
            await self._repo.save_mixin(mixin)
            count += 1

        return count

    def _build_concept(
        self, entry: dict, layer: str, pillar: str | None
    ) -> OntologyConcept:
        """Map a raw YAML dict to an OntologyConcept domain entity."""
        # Parse properties
        properties = [
            ConceptProperty(
                name=p["name"],
                type=p.get("type", "string"),
                required=p.get("required", False),
                default_value=p.get("default"),
                description=p.get("description", ""),
            )
            for p in entry.get("properties", [])
        ]

        # Parse relationships
        relationships = [
            ConceptRelationship(
                name=r["name"],
                target=r["target"],
                cardinality=r.get("cardinality", "0..*"),
                inverse=r.get("inverse"),
                description=r.get("description", ""),
            )
            for r in entry.get("relationships", [])
        ]

        # Parse extraction template
        extraction_template = None
        et_data = entry.get("extraction_template")
        if et_data:
            extraction_template = ExtractionTemplate(
                classification_hints=et_data.get("classification_hints", []),
                file_patterns=et_data.get("file_patterns", []),
            )

        return OntologyConcept(
            id=entry["id"],
            layer=layer,
            label=entry.get("label", entry["id"]),
            inherits=entry.get("inherits"),
            abstract=entry.get("abstract", False),
            description=entry.get("description", "").strip(),
            synonyms=entry.get("synonyms", []),
            mixins=entry.get("mixins", []),
            properties=properties,
            relationships=relationships,
            extraction_template=extraction_template,
            pillar=pillar,
        )

    def _build_mixin(self, entry: dict) -> Mixin:
        """Map a raw YAML dict to a Mixin domain entity."""
        properties = [
            ConceptProperty(
                name=p["name"],
                type=p.get("type", "string"),
                required=p.get("required", False),
                default_value=p.get("default"),
                description=p.get("description", ""),
            )
            for p in entry.get("properties", [])
        ]

        return Mixin(
            id=entry["id"],
            layer=entry.get("layer", "L1"),
            label=entry.get("label", entry["id"]),
            description=entry.get("description", "").strip(),
            properties=properties,
        )

    def _load_yaml(self, path: Path) -> dict | None:
        """Load and parse a YAML file, returning None on error."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception:
            logger.exception("Failed to parse YAML file: %s", path)
            return None

    # ── Embedded Types ───────────────────────────────────────────────

    async def _parse_embedded_types_file(self, path: Path) -> int:
        """Parse the embedded-types.yaml file.

        The file groups embedded types under category keys like
        ``foundation_value_types``, ``entity_embedded_types``, etc.
        Each group contains a list of embedded type definitions.
        """
        data = self._load_yaml(path)
        if data is None:
            return 0

        count = 0
        # Iterate over all top-level keys — each is a category of embedded types
        for section_key, type_list in data.items():
            if not isinstance(type_list, list):
                continue
            for entry in type_list:
                if not isinstance(entry, dict) or "id" not in entry:
                    continue
                et = self._build_embedded_type(entry)
                await self._repo.save_embedded_type(et)
                count += 1

        return count

    def _build_embedded_type(self, entry: dict) -> EmbeddedType:
        """Map a raw YAML dict to an EmbeddedType domain entity."""
        properties = [
            EmbeddedTypeProperty(
                name=p["name"],
                type=p.get("type", "string"),
                required=p.get("required", False),
                description=p.get("description", ""),
                values=p.get("values", []),
            )
            for p in entry.get("properties", [])
        ]

        return EmbeddedType(
            id=entry["id"],
            layer=entry.get("layer", "L1"),
            description=entry.get("description", "").strip(),
            applies_to=entry.get("applies_to", []),
            synonyms=entry.get("synonyms", []),
            properties=properties,
        )
