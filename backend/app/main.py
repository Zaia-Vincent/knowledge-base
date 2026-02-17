"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.infrastructure.database import Base, engine
from app.infrastructure.database.session import async_session_factory
from app.infrastructure.database.repositories import SQLAlchemyOntologyRepository
from app.application.services import OntologyCompiler
from app.infrastructure.logging.log_config import setup_logging
from app.presentation.api.router import router as api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — create tables + compile ontology on startup."""
    settings = get_settings()
    setup_logging()

    # 1. Create all database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Compile ontology YAML → SQLite
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

    # 3. Ensure upload directory exists
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    yield


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
