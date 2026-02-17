"""Concrete repository for service request logs backed by SQLAlchemy."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces import ServiceRequestLogRepository
from app.domain.entities import ServiceRequestLog
from app.infrastructure.database.models.service_request_log import ServiceRequestLogModel


class SQLAlchemyServiceRequestLogRepository(ServiceRequestLogRepository):
    """Implements the ServiceRequestLogRepository port using SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: ServiceRequestLogModel) -> ServiceRequestLog:
        """Map ORM model → domain entity."""
        tools: list[str] | None = None
        if model.tools_called:
            try:
                tools = json.loads(model.tools_called)
            except json.JSONDecodeError:
                tools = None

        return ServiceRequestLog(
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
            feature=model.feature,
            tools_called=tools,
            tool_call_count=model.tool_call_count,
            request_context=model.request_context,
            created_at=model.created_at,
        )

    def _to_model(self, entity: ServiceRequestLog) -> ServiceRequestLogModel:
        """Map domain entity → ORM model."""
        return ServiceRequestLogModel(
            model=entity.model,
            provider=entity.provider,
            prompt_tokens=entity.prompt_tokens,
            completion_tokens=entity.completion_tokens,
            total_tokens=entity.total_tokens,
            cost=entity.cost,
            duration_ms=entity.duration_ms,
            status=entity.status,
            error_message=entity.error_message,
            feature=entity.feature,
            tools_called=json.dumps(entity.tools_called) if entity.tools_called else None,
            tool_call_count=entity.tool_call_count,
            request_context=entity.request_context,
        )

    async def create(self, log: ServiceRequestLog) -> ServiceRequestLog:
        model = self._to_model(log)
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def get_all(
        self, *, skip: int = 0, limit: int = 100
    ) -> list[ServiceRequestLog]:
        stmt = (
            select(ServiceRequestLogModel)
            .offset(skip)
            .limit(limit)
            .order_by(ServiceRequestLogModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]
