"""V1 API router — aggregates all v1 endpoint routers."""

from fastapi import APIRouter

from app.presentation.api.v1.endpoints.health import router as health_router
from app.presentation.api.v1.endpoints.articles import router as articles_router
from app.presentation.api.v1.endpoints.chat import router as chat_router
from app.presentation.api.v1.endpoints.client_records import router as client_records_router
from app.presentation.api.v1.ontology_controller import router as ontology_router
from app.presentation.api.v1.resources_controller import router as resources_router
from app.presentation.api.v1.query_controller import router as query_router
from app.presentation.api.v1.data_sources_controller import router as data_sources_router
from app.presentation.api.v1.settings_controller import router as settings_router

router = APIRouter(prefix="/v1")
router.include_router(health_router)
router.include_router(articles_router)
router.include_router(chat_router)
router.include_router(client_records_router)
router.include_router(ontology_router)
router.include_router(resources_router)
router.include_router(query_router)
router.include_router(data_sources_router)
router.include_router(settings_router)
