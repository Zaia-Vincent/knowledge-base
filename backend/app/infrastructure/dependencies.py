"""FastAPI dependency injection — wires infrastructure to application layer."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.application.services import ArticleService, ChatCompletionService, ClientRecordService
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories import (
    SQLAlchemyArticleRepository,
    SQLAlchemyChatRequestLogRepository,
    SQLAlchemyClientRecordRepository,
)
from app.infrastructure.openrouter import OpenRouterClient


async def get_article_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[ArticleService, None]:
    """Provides an ArticleService instance with its repository wired up."""
    repository = SQLAlchemyArticleRepository(session)
    yield ArticleService(repository)


async def get_chat_completion_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[ChatCompletionService, None]:
    """Provides a ChatCompletionService with OpenRouter as the default provider.

    The provider can be swapped out for Groq, OpenAI, etc. by creating
    alternative dependency functions or using a provider registry.
    """
    settings = get_settings()
    provider = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        app_name=settings.openrouter_app_name,
    )
    log_repository = SQLAlchemyChatRequestLogRepository(session)
    yield ChatCompletionService(provider=provider, log_repository=log_repository)


async def get_client_record_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[ClientRecordService, None]:
    """Provides a ClientRecordService instance with its repository wired up."""
    repository = SQLAlchemyClientRecordRepository(session)
    yield ClientRecordService(repository)

