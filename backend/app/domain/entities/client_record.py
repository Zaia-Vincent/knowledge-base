"""Domain entity — pure Python business object for generic client data storage."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class ClientRecord:
    """Core domain entity for storing arbitrary frontend JSON data.

    Records are scoped by module_name and entity_type so the frontend
    can organise and retrieve its own data without backend-specific logic.
    """

    module_name: str
    entity_type: str
    data: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    parent_id: str | None = None
    user_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def update(
        self,
        data: dict[str, Any] | None = None,
        parent_id: str | None = ...,  # type: ignore[assignment]
    ) -> None:
        """Update mutable fields and refresh the updated_at timestamp."""
        if data is not None:
            self.data = data
        if parent_id is not ...:
            self.parent_id = parent_id
        self.updated_at = datetime.now(timezone.utc)
