"""Application service (use case) for Article operations."""

from app.application.interfaces import ArticleRepository
from app.application.schemas import ArticleCreate, ArticleUpdate
from app.domain.entities import Article
from app.domain.exceptions import EntityNotFoundError


class ArticleService:
    """Orchestrates article business logic. Depends on the repository port (DI)."""

    def __init__(self, repository: ArticleRepository):
        self._repository = repository

    async def get_article(self, article_id: int) -> Article:
        article = await self._repository.get_by_id(article_id)
        if article is None:
            raise EntityNotFoundError("Article", article_id)
        return article

    async def list_articles(self, skip: int = 0, limit: int = 100) -> list[Article]:
        return await self._repository.get_all(skip=skip, limit=limit)

    async def create_article(self, data: ArticleCreate) -> Article:
        article = Article(title=data.title, content=data.content)
        return await self._repository.create(article)

    async def update_article(self, article_id: int, data: ArticleUpdate) -> Article:
        article = await self.get_article(article_id)
        article.update(title=data.title, content=data.content)
        return await self._repository.update(article)

    async def delete_article(self, article_id: int) -> bool:
        exists = await self._repository.get_by_id(article_id)
        if exists is None:
            raise EntityNotFoundError("Article", article_id)
        return await self._repository.delete(article_id)
