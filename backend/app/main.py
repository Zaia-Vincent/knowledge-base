"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.infrastructure.database import Base, engine
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.database.repositories import (
    SQLAlchemyOntologyRepository,
    SQLAlchemyResourceRepository,
    SQLAlchemyServiceRequestLogRepository,
)
from app.application.services import (
    OntologyCompiler,
    OntologyService,
    ResourceProcessingService,
    BackgroundProcessor,
    ClassificationService,
    MetadataExtractionService,
    LLMUsageLogger,
)
from app.infrastructure.capture.website_capture_service import WebsiteCaptureService
from app.infrastructure.dependencies import get_sse_manager
from app.infrastructure.extractors.multi_format_text_extractor import MultiFormatTextExtractor
from app.infrastructure.llm.openrouter_llm_client import OpenRouterLLMClient
from app.infrastructure.openrouter import OpenRouterClient, OpenRouterEmbeddingProvider
from app.infrastructure.storage.local_file_storage import LocalFileStorage
from app.infrastructure.logging.log_config import setup_logging
from app.presentation.api.router import router as api_router
from app.application.services.embedding_service import EmbeddingService
from app.infrastructure.database.repositories.chunk_repository import PgChunkRepository

logger = logging.getLogger(__name__)


async def _ensure_database_exists() -> None:
    """Create the PostgreSQL database if it does not yet exist.

    Connects to the default ``postgres`` maintenance database, checks for the
    target database name, and issues ``CREATE DATABASE`` when missing.
    """
    from urllib.parse import urlparse

    import asyncpg

    settings = get_settings()
    parsed = urlparse(settings.database_url)
    db_name = parsed.path.lstrip("/")
    if not db_name:
        return

    # Build a connection URL pointing at the default 'postgres' database
    maintenance_url = settings.database_url.rsplit("/", 1)[0] + "/postgres"

    try:
        conn = await asyncpg.connect(maintenance_url)
        try:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", db_name
            )
            if not exists:
                # CREATE DATABASE cannot run inside a transaction block
                await conn.execute(f'CREATE DATABASE "{db_name}"')
                logger.info("Created database '%s'", db_name)
            else:
                logger.debug("Database '%s' already exists", db_name)
        finally:
            await conn.close()
    except Exception as exc:
        logger.warning("Could not auto-create database '%s': %s", db_name, exc)


async def _seed_default_data_sources() -> None:
    """Ensure the built-in 'Files' data source exists.

    Queries the ``data_sources`` table for any source with type
    ``file_upload``.  If none is found a new one named *Files* is created.
    This is idempotent — safe to call on every startup.
    """
    from app.infrastructure.database.models.data_source_models import DataSourceModel
    from app.domain.entities.data_source import DataSourceType

    try:
        async with async_session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(DataSourceModel).where(
                    DataSourceModel.source_type == DataSourceType.FILE_UPLOAD.value
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                import uuid
                from datetime import datetime, timezone

                model = DataSourceModel(
                    id=str(uuid.uuid4()),
                    name="Files",
                    source_type=DataSourceType.FILE_UPLOAD.value,
                    description="Default file upload data source",
                    config={},
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(model)
                await session.commit()
                logger.info("Seeded default 'Files' data source")
            else:
                logger.debug("Default file_upload data source already exists")
    except Exception as exc:
        logger.warning("Could not seed default data sources: %s", exc)

async def _build_resource_processing_service(session: AsyncSession) -> ResourceProcessingService:
    """Build a ResourceProcessingService wired to the given session.

    Used as the BackgroundProcessor's service_factory so each job
    gets a ResourceProcessingService bound to its own session/transaction.
    """
    settings = get_settings()

    resource_repo = SQLAlchemyResourceRepository(session)
    ontology_repo = SQLAlchemyOntologyRepository(session)
    log_repo = SQLAlchemyServiceRequestLogRepository(session)

    storage = LocalFileStorage(upload_dir=settings.upload_dir)
    extractor = MultiFormatTextExtractor()
    usage_logger = LLMUsageLogger(log_repo)

    llm_client = None
    openrouter_api_key = settings.openrouter_api_key.strip()
    if openrouter_api_key:
        try:
            openrouter = OpenRouterClient(
                api_key=openrouter_api_key,
                base_url=settings.openrouter_base_url,
                app_name=settings.openrouter_app_name,
            )
            llm_client = OpenRouterLLMClient(
                openrouter_client=openrouter,
                model=settings.classification_model,
                pdf_model=settings.pdf_processing_model,
            )
        except Exception:
            logger.exception("Failed to initialize OpenRouterLLMClient")
    else:
        logger.warning(
            "OPENROUTER_API_KEY is not configured; URL/image LLM extraction is disabled."
        )

    classifier = ClassificationService(
        ontology_repo=ontology_repo,
        llm_client=llm_client,
        usage_logger=usage_logger,
    )
    metadata_extractor = MetadataExtractionService(
        ontology_repo=ontology_repo,
        llm_client=llm_client,
        usage_logger=usage_logger,
    )
    ontology_service = OntologyService(ontology_repo)

    # Optional: embedding service for vector search
    embedding_service = None
    openrouter_api_key = settings.openrouter_api_key.strip()
    if openrouter_api_key:
        try:
            embedding_provider = OpenRouterEmbeddingProvider(
                api_key=openrouter_api_key,
                base_url=settings.openrouter_base_url,
                app_name=settings.openrouter_app_name,
                model=settings.embedding_model,
                model_dimensions=settings.embedding_dimensions,
            )
            chunk_repo = PgChunkRepository(session)
            embedding_service = EmbeddingService(
                embedding_provider=embedding_provider,
                chunk_repository=chunk_repo,
            )
        except Exception:
            logger.warning("Failed to initialize EmbeddingService")

    return ResourceProcessingService(
        file_repository=resource_repo,
        file_storage=storage,
        text_extractor=extractor,
        classification_service=classifier,
        metadata_extractor=metadata_extractor,
        llm_client=llm_client,
        ontology_repo=ontology_repo,
        ontology_service=ontology_service,
        usage_logger=usage_logger,
        embedding_service=embedding_service,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — create tables, compile ontology, start services."""
    settings = get_settings()
    setup_logging()

    # 0. Ensure the PostgreSQL database exists (auto-create if missing)
    await _ensure_database_exists()

    # 1. Create all database tables (enable pgvector extension first)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    # 2. Seed default data sources (e.g. built-in "Files" source)
    await _seed_default_data_sources()

    # 3. Compile ontology YAML → DB
    try:
        async with async_session_factory() as session:
            repository = SQLAlchemyOntologyRepository(session)
            compiler = OntologyCompiler(
                l1_dir=settings.ontology_l1_dir,
                l2_dir=settings.ontology_l2_dir,
                repository=repository,
                embedded_types_file=settings.embedded_types_file,
            )
            total = await compiler.compile()
            await session.commit()
            logger.info("Ontology compiled: %d concepts loaded", total)
    except Exception:
        logger.exception("Failed to compile ontology — continuing without it")

    # 4. Ensure upload directory exists
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    # 5. Start WebsiteCaptureService (Playwright browser)
    capture_service = WebsiteCaptureService(
        viewport_width=settings.website_capture_viewport_width,
        viewport_height=settings.website_capture_viewport_height,
        timeout_ms=settings.website_capture_timeout * 1000,
    )
    await capture_service.start()

    # 6. Start background processor
    processor = BackgroundProcessor(
        sse_manager=get_sse_manager(),
        service_factory=_build_resource_processing_service,
        capture_service=capture_service,
    )
    await processor.start()

    yield

    # Shutdown
    await processor.stop()
    await capture_service.stop()
    sse = get_sse_manager()
    await sse.shutdown()


def create_app() -> FastAPI:
    """Factory function that builds and configures the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routes
    app.include_router(api_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8020,
        reload=True,
    )
