"""SQLAlchemy implementation of the DataSourceRepository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.data_source_repository import DataSourceRepository
from app.domain.entities.data_source import DataSource, DataSourceType
from app.infrastructure.database.models.data_source_models import DataSourceModel


class SQLAlchemyDataSourceRepository(DataSourceRepository):
    """Concrete data source repository backed by PostgreSQL via SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, source_id: str) -> DataSource | None:
        result = await self._session.execute(
            select(DataSourceModel).where(DataSourceModel.id == source_id)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_all(self) -> list[DataSource]:
        result = await self._session.execute(
            select(DataSourceModel).order_by(DataSourceModel.created_at.desc())
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def create(self, source: DataSource) -> DataSource:
        if not source.id:
            source.id = str(uuid.uuid4())

        model = DataSourceModel(
            id=source.id,
            name=source.name,
            source_type=source.source_type.value,
            description=source.description,
            config=source.config,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return source

    async def update(self, source: DataSource) -> DataSource:
        result = await self._session.execute(
            select(DataSourceModel).where(DataSourceModel.id == source.id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"DataSource with id {source.id} not found")

        model.name = source.name
        model.description = source.description
        model.config = source.config
        model.updated_at = source.updated_at
        await self._session.flush()
        return source

    async def delete(self, source_id: str) -> bool:
        result = await self._session.execute(
            select(DataSourceModel).where(DataSourceModel.id == source_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    # ── Mapping ──────────────────────────────────────────────────────

    @staticmethod
    def _to_domain(model: DataSourceModel) -> DataSource:
        return DataSource(
            id=model.id,
            name=model.name,
            source_type=DataSourceType(model.source_type),
            description=model.description or "",
            config=model.config or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
