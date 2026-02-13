"""Unit tests for the ArticleService."""

import pytest

from app.application.schemas import ArticleCreate, ArticleUpdate
from app.application.services import ArticleService
from app.domain.entities import Article
from app.domain.exceptions import EntityNotFoundError
from app.application.interfaces import ArticleRepository


class FakeArticleRepository(ArticleRepository):
    """In-memory fake repository for unit testing."""

    def __init__(self):
        self._articles: dict[int, Article] = {}
        self._next_id = 1

    async def get_by_id(self, article_id: int) -> Article | None:
        return self._articles.get(article_id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Article]:
        articles = list(self._articles.values())
        return articles[skip : skip + limit]

    async def create(self, article: Article) -> Article:
        article.id = self._next_id
        self._next_id += 1
        self._articles[article.id] = article
        return article

    async def update(self, article: Article) -> Article:
        if article.id not in self._articles:
            raise ValueError(f"Article {article.id} not found")
        self._articles[article.id] = article
        return article

    async def delete(self, article_id: int) -> bool:
        if article_id in self._articles:
            del self._articles[article_id]
            return True
        return False


@pytest.fixture
def service() -> ArticleService:
    return ArticleService(FakeArticleRepository())


@pytest.mark.asyncio
async def test_create_article(service: ArticleService):
    data = ArticleCreate(title="Test Article", content="Some content")
    article = await service.create_article(data)
    assert article.id is not None
    assert article.title == "Test Article"


@pytest.mark.asyncio
async def test_get_article_not_found(service: ArticleService):
    with pytest.raises(EntityNotFoundError):
        await service.get_article(999)


@pytest.mark.asyncio
async def test_list_articles(service: ArticleService):
    await service.create_article(ArticleCreate(title="A1", content="C1"))
    await service.create_article(ArticleCreate(title="A2", content="C2"))
    articles = await service.list_articles()
    assert len(articles) == 2


@pytest.mark.asyncio
async def test_update_article(service: ArticleService):
    created = await service.create_article(ArticleCreate(title="Old", content="Old content"))
    updated = await service.update_article(created.id, ArticleUpdate(title="New"))
    assert updated.title == "New"
    assert updated.content == "Old content"


@pytest.mark.asyncio
async def test_delete_article(service: ArticleService):
    created = await service.create_article(ArticleCreate(title="Delete Me", content="..."))
    result = await service.delete_article(created.id)
    assert result is True
    with pytest.raises(EntityNotFoundError):
        await service.get_article(created.id)
