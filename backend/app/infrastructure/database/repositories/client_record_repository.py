"""Concrete repository implementation for ClientRecord backed by SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces import ClientRecordRepository
from app.domain.entities import ClientRecord
from app.infrastructure.database.models import ClientRecordModel


class SQLAlchemyClientRecordRepository(ClientRecordRepository):
    """Implements the ClientRecordRepository port using SQLAlchemy async sessions."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: ClientRecordModel) -> ClientRecord:
        """Map ORM model → domain entity."""
        return ClientRecord(
            id=model.id,
            module_name=model.module_name,
            entity_type=model.entity_type,
            data=model.data,
            parent_id=model.parent_id,
            user_id=model.user_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: ClientRecord) -> ClientRecordModel:
        """Map domain entity → ORM model (for creation)."""
        return ClientRecordModel(
            id=entity.id,
            module_name=entity.module_name,
            entity_type=entity.entity_type,
            data=entity.data,
            parent_id=entity.parent_id,
            user_id=entity.user_id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def get_by_id(self, record_id: str) -> ClientRecord | None:
        result = await self._session.get(ClientRecordModel, record_id)
        return self._to_entity(result) if result else None

    async def get_all(
        self,
        *,
        module_name: str | None = None,
        entity_type: str | None = None,
        parent_id: str | None = None,
        user_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ClientRecord]:
        stmt = select(ClientRecordModel)

        if module_name is not None:
            stmt = stmt.where(ClientRecordModel.module_name == module_name)
        if entity_type is not None:
            stmt = stmt.where(ClientRecordModel.entity_type == entity_type)
        if parent_id is not None:
            stmt = stmt.where(ClientRecordModel.parent_id == parent_id)
        if user_id is not None:
            stmt = stmt.where(ClientRecordModel.user_id == user_id)

        stmt = stmt.offset(skip).limit(limit).order_by(
            ClientRecordModel.created_at.desc()
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]

    async def create(self, record: ClientRecord) -> ClientRecord:
        model = self._to_model(record)
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, record: ClientRecord) -> ClientRecord:
        model = await self._session.get(ClientRecordModel, record.id)
        if model is None:
            raise ValueError(f"ClientRecord {record.id} not found in database")
        model.data = record.data
        model.parent_id = record.parent_id
        model.updated_at = record.updated_at
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, record_id: str) -> bool:
        model = await self._session.get(ClientRecordModel, record_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True
