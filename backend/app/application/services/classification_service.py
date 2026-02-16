"""Multi-signal classification service — classifies files against the ontology.

Combines three signal sources with weighted aggregation:
  1. File pattern matching  (folder/filename hints)  → weight 0.25
  2. Synonym/hint matching  (text ↔ synonyms/hints)  → weight 0.35
  3. LLM content analysis   (Claude Sonnet excerpt)  → weight 0.40
"""

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.application.interfaces import OntologyRepository
from app.application.interfaces.llm_client import (
    LLMClassificationRequest,
    LLMClassificationResponse,
    LLMClient,
)
from app.domain.entities import (
    ClassificationResult,
    ClassificationSignal,
    OntologyConcept,
)
from app.infrastructure.logging.colored_logger import PipelineLogger, PipelineStage

logger = logging.getLogger(__name__)
plog = PipelineLogger("ClassificationService")

# Signal weights
_W_FILE_PATTERN = 0.25
_W_HINT_MATCH = 0.35
_W_LLM = 0.40

# Max chars to send to LLM for classification
_LLM_EXCERPT_LENGTH = 3000


@dataclass
class _ConceptScore:
    """Accumulated score for one concept across signal sources."""

    concept_id: str
    weighted_score: float = 0.0
    signals: list[ClassificationSignal] = field(default_factory=list)


class ClassificationService:
    """Application service that classifies documents against the ontology.

    Uses a multi-signal pipeline: file patterns → synonym/hint matching → LLM.
    """

    def __init__(
        self,
        ontology_repo: OntologyRepository,
        llm_client: LLMClient | None = None,
        usage_logger=None,
    ):
        self._ontology_repo = ontology_repo
        self._llm_client = llm_client
        self._usage_logger = usage_logger

    async def classify(
        self,
        *,
        text: str,
        filename: str,
        original_path: str = "",
    ) -> ClassificationResult:
        """Run the full classification pipeline and return the best match.

        Args:
            text: Extracted text content of the file.
            filename: Original filename.
            original_path: Full original path (with folder structure from ZIP).

        Returns:
            ClassificationResult with the best-matching concept and all signals.
        """
        classifiable = await self._ontology_repo.get_classifiable_concepts()

        if not classifiable:
            logger.warning("No classifiable concepts in ontology — returning unclassified")
            return ClassificationResult(
                primary_concept_id="Unknown",
                confidence=0.0,
                signals=[],
            )

        # Accumulate scores per concept
        scores: dict[str, _ConceptScore] = {
            c.id: _ConceptScore(concept_id=c.id) for c in classifiable
        }

        # Signal 1: File pattern matching
        self._apply_file_pattern_signals(
            scores, classifiable, filename, original_path
        )

        # Signal 2: Synonym / hint matching
        self._apply_hint_signals(scores, classifiable, text)

        # Signal 3: LLM content analysis (only if client available)
        if self._llm_client and text.strip():
            await self._apply_llm_signal(scores, classifiable, text)

        # Find best match
        best = max(scores.values(), key=lambda s: s.weighted_score)

        # Collect all non-zero signals for transparency
        all_signals: list[ClassificationSignal] = []
        for score in scores.values():
            all_signals.extend(score.signals)

        return ClassificationResult(
            primary_concept_id=best.concept_id,
            confidence=min(best.weighted_score, 1.0),
            signals=all_signals,
        )

    # ── Signal 1: File Pattern Matching ──────────────────────────────

    def _apply_file_pattern_signals(
        self,
        scores: dict[str, _ConceptScore],
        concepts: list[OntologyConcept],
        filename: str,
        original_path: str,
    ) -> None:
        """Match file/folder patterns against extraction template file_patterns."""
        path_lower = (original_path or filename).lower()
        filename_lower = filename.lower()

        for concept in concepts:
            if not concept.extraction_template or not concept.extraction_template.file_patterns:
                continue

            for pattern in concept.extraction_template.file_patterns:
                pattern_lower = pattern.lower().replace("*", "")

                # Check if pattern appears in path or filename
                if pattern_lower in path_lower or pattern_lower in filename_lower:
                    raw_score = 0.8
                    signal = ClassificationSignal(
                        method="file_pattern",
                        concept_id=concept.id,
                        score=raw_score,
                        details=f"Pattern '{pattern}' matches path '{original_path or filename}'",
                    )
                    scores[concept.id].signals.append(signal)
                    scores[concept.id].weighted_score += raw_score * _W_FILE_PATTERN
                    break  # One match per concept is enough

    # ── Signal 2: Synonym / Hint Matching ────────────────────────────

    def _apply_hint_signals(
        self,
        scores: dict[str, _ConceptScore],
        concepts: list[OntologyConcept],
        text: str,
    ) -> None:
        """Match synonyms and classification hints against document text."""
        # Use a lowered excerpt for matching
        text_lower = text[:5000].lower()

        for concept in concepts:
            hints = concept.get_all_hints()
            if not hints:
                continue

            matches = []
            for hint in hints:
                hint_lower = hint.lower()
                # Use word boundary matching to avoid partial matches
                pattern = r"\b" + re.escape(hint_lower) + r"\b"
                if re.search(pattern, text_lower):
                    matches.append(hint)

            if matches:
                # Score based on how many hints matched
                raw_score = min(len(matches) * 0.3, 1.0)
                signal = ClassificationSignal(
                    method="hint_match",
                    concept_id=concept.id,
                    score=raw_score,
                    details=f"Matched hints: {', '.join(matches[:5])}",
                )
                scores[concept.id].signals.append(signal)
                scores[concept.id].weighted_score += raw_score * _W_HINT_MATCH

    # ── Signal 3: LLM Content Analysis ───────────────────────────────

    async def _apply_llm_signal(
        self,
        scores: dict[str, _ConceptScore],
        concepts: list[OntologyConcept],
        text: str,
    ) -> None:
        """Use LLM to classify the document content."""
        excerpt = text[:_LLM_EXCERPT_LENGTH]

        # Build concept list for the LLM
        available_concepts = [
            {
                "id": c.id,
                "label": c.label,
                "description": c.description[:200] if c.description else "",
                "synonyms": c.synonyms[:5],
                "hints": (
                    c.extraction_template.classification_hints[:5]
                    if c.extraction_template
                    else []
                ),
            }
            for c in concepts
        ]

        try:
            request = LLMClassificationRequest(
                text_excerpt=excerpt,
                available_concepts=available_concepts,
            )
            start = time.monotonic()
            response: LLMClassificationResponse = await self._llm_client.classify_document(request)
            duration_ms = int((time.monotonic() - start) * 1000)

            # Log usage if logger available
            if self._usage_logger and response.usage:
                await self._usage_logger.log_request(
                    model=response.model or "unknown",
                    provider="openrouter",
                    feature="classification",
                    usage=response.usage,
                    duration_ms=duration_ms,
                )

            if response.concept_id in scores:
                signal = ClassificationSignal(
                    method="llm_analysis",
                    concept_id=response.concept_id,
                    score=response.confidence,
                    details=response.reasoning[:200] if response.reasoning else "LLM classification",
                )
                scores[response.concept_id].signals.append(signal)
                scores[response.concept_id].weighted_score += response.confidence * _W_LLM
            else:
                logger.warning(
                    "LLM returned unknown concept_id '%s' — ignoring", response.concept_id
                )

        except Exception:
            logger.exception("LLM classification failed — continuing with rule-based signals only")
