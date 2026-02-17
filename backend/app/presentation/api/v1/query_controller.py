"""Query API controller — endpoints for natural-language knowledge queries."""

from fastapi import APIRouter, Depends

from app.application.schemas.query import (
    QueryIntentSchema,
    QueryMatchSchema,
    QueryRequest,
    QueryResultSchema,
    MetadataFilterSchema,
)
from app.application.services.query_service import QueryService
from app.domain.entities.query import QueryResult
from app.infrastructure.dependencies import get_query_service

router = APIRouter(prefix="/query", tags=["query"])


# ── Helpers ──────────────────────────────────────────────────────────


def _to_result_schema(result: QueryResult) -> QueryResultSchema:
    """Map domain QueryResult to response schema."""
    return QueryResultSchema(
        intent=QueryIntentSchema(
            original_question=result.intent.original_question,
            resolved_language=result.intent.resolved_language,
            concept_ids=result.intent.concept_ids,
            concept_labels=result.intent.concept_labels,
            metadata_filters=[
                MetadataFilterSchema(
                    field_name=f.field_name,
                    value=f.value,
                    operator=f.operator,
                )
                for f in result.intent.metadata_filters
            ],
            keywords=result.intent.keywords,
            text_query=result.intent.text_query,
            reasoning=result.intent.reasoning,
        ),
        matches=[
            QueryMatchSchema(
                file_id=m.file_id,
                filename=m.filename,
                concept_id=m.concept_id,
                concept_label=m.concept_label,
                confidence=m.confidence,
                summary=m.summary,
                metadata=m.metadata,
                relevance_score=m.relevance_score,
            )
            for m in result.matches
        ],
        total_matches=result.total_matches,
    )


# ── Endpoints ────────────────────────────────────────────────────────


@router.post("", response_model=QueryResultSchema)
async def execute_query(
    body: QueryRequest,
    service: QueryService = Depends(get_query_service),
):
    """Execute a full query: translate NL question → search knowledge base."""
    result = await service.query(
        question=body.question,
        max_results=body.max_results,
    )
    return _to_result_schema(result)


@router.post("/intent", response_model=QueryIntentSchema)
async def resolve_intent(
    body: QueryRequest,
    service: QueryService = Depends(get_query_service),
):
    """Resolve a query intent only (no search) — useful for debugging."""
    intent = await service.resolve_intent(body.question)
    return QueryIntentSchema(
        original_question=intent.original_question,
        resolved_language=intent.resolved_language,
        concept_ids=intent.concept_ids,
        concept_labels=intent.concept_labels,
        metadata_filters=[
            MetadataFilterSchema(
                field_name=f.field_name,
                value=f.value,
                operator=f.operator,
            )
            for f in intent.metadata_filters
        ],
        keywords=intent.keywords,
        text_query=intent.text_query,
        reasoning=intent.reasoning,
    )
