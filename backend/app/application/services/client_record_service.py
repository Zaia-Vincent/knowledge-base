"""Application service (use case) for ClientRecord operations."""

from typing import Any

from app.application.interfaces import ClientRecordRepository
from app.application.schemas.client_record import ClientRecordCreate, ClientRecordUpdate
from app.domain.entities import ClientRecord
from app.domain.exceptions import EntityNotFoundError


class ClientRecordService:
    """Orchestrates client record CRUD logic. Depends on the repository port (DI)."""

    def __init__(self, repository: ClientRecordRepository):
        self._repository = repository

    async def get_record(self, record_id: str) -> ClientRecord:
        record = await self._repository.get_by_id(record_id)
        if record is None:
            raise EntityNotFoundError("ClientRecord", record_id)
        return record

    async def list_records(
        self,
        *,
        module_name: str | None = None,
        entity_type: str | None = None,
        parent_id: str | None = None,
        user_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ClientRecord]:
        return await self._repository.get_all(
            module_name=module_name,
            entity_type=entity_type,
            parent_id=parent_id,
            user_id=user_id,
            skip=skip,
            limit=limit,
        )

    async def create_record(self, data: ClientRecordCreate) -> ClientRecord:
        record = ClientRecord(
            module_name=data.module_name,
            entity_type=data.entity_type,
            data=data.data,
            parent_id=data.parent_id,
            user_id=data.user_id,
        )
        return await self._repository.create(record)

    async def update_record(
        self, record_id: str, data: ClientRecordUpdate
    ) -> ClientRecord:
        record = await self.get_record(record_id)

        # Build kwargs, using ... sentinel to distinguish None from absent
        kwargs: dict[str, Any] = {}
        if data.data is not None:
            kwargs["data"] = data.data
        if data.parent_id is not None:
            kwargs["parent_id"] = data.parent_id

        record.update(**kwargs)
        return await self._repository.update(record)

    async def delete_record(self, record_id: str) -> bool:
        exists = await self._repository.get_by_id(record_id)
        if exists is None:
            raise EntityNotFoundError("ClientRecord", record_id)
        return await self._repository.delete(record_id)
