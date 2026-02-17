"""FastAPI dependency injection — wires infrastructure to application layer."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.application.interfaces.llm_client import LLMClient
from app.application.services import (
    ArticleService,
    ChatCompletionService,
    ClassificationService,
    ClientRecordService,
    FileProcessingService,
    LLMUsageLogger,
    MetadataExtractionService,
    OntologyService,
    OntologyTypeAssistantService,
)
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories import (
    SQLAlchemyArticleRepository,
    SQLAlchemyServiceRequestLogRepository,
    SQLAlchemyClientRecordRepository,
    SQLAlchemyFileRepository,
    SQLAlchemyOntologyRepository,
)
from app.infrastructure.extractors.multi_format_text_extractor import MultiFormatTextExtractor
from app.infrastructure.llm.openrouter_llm_client import OpenRouterLLMClient
from app.infrastructure.openrouter import OpenRouterClient
from app.infrastructure.storage.local_file_storage import LocalFileStorage



async def get_article_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[ArticleService, None]:
    """Provides an ArticleService instance with its repository wired up."""
    repository = SQLAlchemyArticleRepository(session)
    yield ArticleService(repository)


async def get_chat_completion_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[ChatCompletionService, None]:
    """Provides a ChatCompletionService with OpenRouter as the default provider."""
    settings = get_settings()
    provider = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        app_name=settings.openrouter_app_name,
    )
    log_repository = SQLAlchemyServiceRequestLogRepository(session)
    usage_logger = LLMUsageLogger(log_repository)
    yield ChatCompletionService(
        provider=provider,
        log_repository=log_repository,
        usage_logger=usage_logger,
    )


async def get_client_record_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[ClientRecordService, None]:
    """Provides a ClientRecordService instance with its repository wired up."""
    repository = SQLAlchemyClientRecordRepository(session)
    yield ClientRecordService(repository)


async def get_ontology_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[OntologyService, None]:
    """Provides an OntologyService with the ontology repository wired up."""
    repository = SQLAlchemyOntologyRepository(session)
    yield OntologyService(repository)


async def get_ontology_type_assistant_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[OntologyTypeAssistantService, None]:
    """Provides AI-assisted ontology type suggestion service."""
    settings = get_settings()

    ontology_repository = SQLAlchemyOntologyRepository(session)
    log_repository = SQLAlchemyServiceRequestLogRepository(session)
    usage_logger = LLMUsageLogger(log_repository)

    provider = None
    if settings.openrouter_api_key.strip():
        try:
            provider = OpenRouterClient(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                app_name=settings.openrouter_app_name,
            )
        except Exception:
            provider = None

    yield OntologyTypeAssistantService(
        ontology_repo=ontology_repository,
        chat_provider=provider,
        model=settings.ontology_assistant_model,
        usage_logger=usage_logger,
    )


async def get_file_processing_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[FileProcessingService, None]:
    """Provides a FileProcessingService with storage, extraction, classification, and metadata."""
    settings = get_settings()

    # File infrastructure
    file_repository = SQLAlchemyFileRepository(session)
    storage = LocalFileStorage(upload_dir=settings.upload_dir)
    extractor = MultiFormatTextExtractor()

    # Classification & extraction infrastructure (shared ontology repo + LLM client)
    ontology_repository = SQLAlchemyOntologyRepository(session)

    # Shared usage logger for all LLM-consuming services
    log_repository = SQLAlchemyServiceRequestLogRepository(session)
    usage_logger = LLMUsageLogger(log_repository)

    llm_client: LLMClient | None = None
    try:
        openrouter = OpenRouterClient(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            app_name=settings.openrouter_app_name,
        )
        llm_client = OpenRouterLLMClient(
            openrouter_client=openrouter,
            model=settings.classification_model,
            pdf_model=settings.pdf_processing_model,
        )
    except Exception:
        pass  # LLM not configured — services will work without it

    classifier = ClassificationService(
        ontology_repo=ontology_repository,
        llm_client=llm_client,
        usage_logger=usage_logger,
    )

    metadata_extractor = MetadataExtractionService(
        ontology_repo=ontology_repository,
        llm_client=llm_client,
        usage_logger=usage_logger,
    )

    ontology_service = OntologyService(ontology_repository)

    yield FileProcessingService(
        file_repository=file_repository,
        file_storage=storage,
        text_extractor=extractor,
        classification_service=classifier,
        metadata_extractor=metadata_extractor,
        llm_client=llm_client,
        ontology_repo=ontology_repository,
        ontology_service=ontology_service,
        usage_logger=usage_logger,
    )


async def get_query_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator["QueryService", None]:
    """Provides a QueryService with ChatProvider, ontology, file repos, and usage logger."""
    from app.application.services.query_service import QueryService

    settings = get_settings()

    provider = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        app_name=settings.openrouter_app_name,
    )

    ontology_repo = SQLAlchemyOntologyRepository(session)
    file_repo = SQLAlchemyFileRepository(session)
    log_repo = SQLAlchemyServiceRequestLogRepository(session)
    usage_logger = LLMUsageLogger(log_repo)

    yield QueryService(
        chat_provider=provider,
        ontology_repo=ontology_repo,
        file_repo=file_repo,
        usage_logger=usage_logger,
        model=settings.classification_model,
    )
