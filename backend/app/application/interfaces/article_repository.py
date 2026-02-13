"""Abstract repository interfaces (ports) — define the contract, not the implementation."""

from abc import ABC, abstractmethod

from app.domain.entities import Article


class ArticleRepository(ABC):
    """Port for article persistence — implemented in the infrastructure layer."""

    @abstractmethod
    async def get_by_id(self, article_id: int) -> Article | None:
        """Retrieve a single article by its ID."""
        ...

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Article]:
        """Retrieve a paginated list of articles."""
        ...

    @abstractmethod
    async def create(self, article: Article) -> Article:
        """Persist a new article and return it with the generated ID."""
        ...

    @abstractmethod
    async def update(self, article: Article) -> Article:
        """Update an existing article."""
        ...

    @abstractmethod
    async def delete(self, article_id: int) -> bool:
        """Delete an article. Returns True if deleted, False if not found."""
        ...
