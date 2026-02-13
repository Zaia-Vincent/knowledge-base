"""Article CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.schemas import ArticleCreate, ArticleUpdate, ArticleResponse
from app.application.services import ArticleService
from app.domain.exceptions import EntityNotFoundError
from app.infrastructure.dependencies import get_article_service

router = APIRouter(prefix="/articles", tags=["Articles"])


@router.get("", response_model=list[ArticleResponse])
async def list_articles(
    skip: int = 0,
    limit: int = 100,
    service: ArticleService = Depends(get_article_service),
) -> list[ArticleResponse]:
    """Retrieve a paginated list of articles."""
    articles = await service.list_articles(skip=skip, limit=limit)
    return [ArticleResponse.model_validate(a, from_attributes=True) for a in articles]


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: int,
    service: ArticleService = Depends(get_article_service),
) -> ArticleResponse:
    """Retrieve a single article by ID."""
    try:
        article = await service.get_article(article_id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return ArticleResponse.model_validate(article, from_attributes=True)


@router.post("", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_article(
    data: ArticleCreate,
    service: ArticleService = Depends(get_article_service),
) -> ArticleResponse:
    """Create a new article."""
    article = await service.create_article(data)
    return ArticleResponse.model_validate(article, from_attributes=True)


@router.put("/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: int,
    data: ArticleUpdate,
    service: ArticleService = Depends(get_article_service),
) -> ArticleResponse:
    """Update an existing article."""
    try:
        article = await service.update_article(article_id, data)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return ArticleResponse.model_validate(article, from_attributes=True)


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    article_id: int,
    service: ArticleService = Depends(get_article_service),
) -> None:
    """Delete an article by ID."""
    try:
        await service.delete_article(article_id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
