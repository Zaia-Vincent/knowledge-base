"""Concrete repository implementation backed by SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces import ArticleRepository
from app.domain.entities import Article
from app.infrastructure.database.models import ArticleModel


class SQLAlchemyArticleRepository(ArticleRepository):
    """Implements the ArticleRepository port using SQLAlchemy async sessions."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: ArticleModel) -> Article:
        """Map ORM model → domain entity."""
        return Article(
            id=model.id,
            title=model.title,
            content=model.content,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Article) -> ArticleModel:
        """Map domain entity → ORM model (for creation)."""
        return ArticleModel(
            title=entity.title,
            content=entity.content,
        )

    async def get_by_id(self, article_id: int) -> Article | None:
        result = await self._session.get(ArticleModel, article_id)
        return self._to_entity(result) if result else None

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Article]:
        stmt = select(ArticleModel).offset(skip).limit(limit).order_by(ArticleModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]

    async def create(self, article: Article) -> Article:
        model = self._to_model(article)
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def update(self, article: Article) -> Article:
        model = await self._session.get(ArticleModel, article.id)
        if model is None:
            raise ValueError(f"Article {article.id} not found in database")
        model.title = article.title
        model.content = article.content
        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, article_id: int) -> bool:
        model = await self._session.get(ArticleModel, article_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True
