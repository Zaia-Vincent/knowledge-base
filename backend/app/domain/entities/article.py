"""Domain entities — pure Python business objects, no framework dependencies."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Article:
    """Core domain entity representing a knowledge article."""

    title: str
    content: str
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def update(self, title: str | None = None, content: str | None = None) -> None:
        """Update article fields and refresh the updated_at timestamp."""
        if title is not None:
            self.title = title
        if content is not None:
            self.content = content
        self.updated_at = datetime.now(timezone.utc)
