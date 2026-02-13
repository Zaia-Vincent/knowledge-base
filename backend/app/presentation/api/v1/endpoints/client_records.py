"""Client record CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.schemas.client_record import (
    ClientRecordCreate,
    ClientRecordResponse,
    ClientRecordUpdate,
)
from app.application.services import ClientRecordService
from app.domain.exceptions import EntityNotFoundError
from app.infrastructure.dependencies import get_client_record_service

router = APIRouter(prefix="/client-records", tags=["Client Records"])


@router.get("", response_model=list[ClientRecordResponse])
async def list_records(
    module_name: str | None = Query(None, description="Filter by module name"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    parent_id: str | None = Query(None, description="Filter by parent record ID"),
    user_id: str | None = Query(None, description="Filter by user ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    service: ClientRecordService = Depends(get_client_record_service),
) -> list[ClientRecordResponse]:
    """Retrieve a filtered, paginated list of client records."""
    records = await service.list_records(
        module_name=module_name,
        entity_type=entity_type,
        parent_id=parent_id,
        user_id=user_id,
        skip=skip,
        limit=limit,
    )
    return [
        ClientRecordResponse.model_validate(r, from_attributes=True) for r in records
    ]


@router.get("/{record_id}", response_model=ClientRecordResponse)
async def get_record(
    record_id: str,
    service: ClientRecordService = Depends(get_client_record_service),
) -> ClientRecordResponse:
    """Retrieve a single client record by ID."""
    try:
        record = await service.get_record(record_id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return ClientRecordResponse.model_validate(record, from_attributes=True)


@router.post("", response_model=ClientRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_record(
    data: ClientRecordCreate,
    service: ClientRecordService = Depends(get_client_record_service),
) -> ClientRecordResponse:
    """Create a new client record."""
    record = await service.create_record(data)
    return ClientRecordResponse.model_validate(record, from_attributes=True)


@router.put("/{record_id}", response_model=ClientRecordResponse)
async def update_record(
    record_id: str,
    data: ClientRecordUpdate,
    service: ClientRecordService = Depends(get_client_record_service),
) -> ClientRecordResponse:
    """Update an existing client record."""
    try:
        record = await service.update_record(record_id, data)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return ClientRecordResponse.model_validate(record, from_attributes=True)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_record(
    record_id: str,
    service: ClientRecordService = Depends(get_client_record_service),
) -> None:
    """Delete a client record by ID."""
    try:
        await service.delete_record(record_id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
