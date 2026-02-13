"""Concrete repository for chat request logs backed by SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces import ChatRequestLogRepository
from app.domain.entities import ChatRequestLog
from app.infrastructure.database.models.chat_request_log import ChatRequestLogModel


class SQLAlchemyChatRequestLogRepository(ChatRequestLogRepository):
    """Implements the ChatRequestLogRepository port using SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: ChatRequestLogModel) -> ChatRequestLog:
        """Map ORM model → domain entity."""
        return ChatRequestLog(
            id=model.id,
            model=model.model,
            provider=model.provider,
            prompt_tokens=model.prompt_tokens,
            completion_tokens=model.completion_tokens,
            total_tokens=model.total_tokens,
            cost=model.cost,
            duration_ms=model.duration_ms,
            status=model.status,
            error_message=model.error_message,
            created_at=model.created_at,
        )

    def _to_model(self, entity: ChatRequestLog) -> ChatRequestLogModel:
        """Map domain entity → ORM model."""
        return ChatRequestLogModel(
            model=entity.model,
            provider=entity.provider,
            prompt_tokens=entity.prompt_tokens,
            completion_tokens=entity.completion_tokens,
            total_tokens=entity.total_tokens,
            cost=entity.cost,
            duration_ms=entity.duration_ms,
            status=entity.status,
            error_message=entity.error_message,
        )

    async def create(self, log: ChatRequestLog) -> ChatRequestLog:
        model = self._to_model(log)
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def get_all(
        self, *, skip: int = 0, limit: int = 100
    ) -> list[ChatRequestLog]:
        stmt = (
            select(ChatRequestLogModel)
            .offset(skip)
            .limit(limit)
            .order_by(ChatRequestLogModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]
