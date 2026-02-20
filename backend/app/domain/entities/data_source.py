"""Domain entity for data sources — registered origins for document ingestion."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DataSourceType(str, Enum):
    """Supported data source types."""

    FILE_UPLOAD = "file_upload"
    WEBSITE = "website"
    TEXT = "text"


@dataclass
class DataSource:
    """A registered data source from which documents are ingested.

    Config examples:
        FILE_UPLOAD: {}
        WEBSITE:     {"urls": ["https://example.com/page1", ...]}
        TEXT:        {"texts": [{"id": "...", "title": "...", "content": "...", ...}]}
    """

    name: str
    source_type: DataSourceType
    config: dict[str, Any] = field(default_factory=dict)
    id: str | None = None
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
