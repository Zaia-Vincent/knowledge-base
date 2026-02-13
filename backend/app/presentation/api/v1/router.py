"""V1 API router — aggregates all v1 endpoint routers."""

from fastapi import APIRouter

from app.presentation.api.v1.endpoints.health import router as health_router
from app.presentation.api.v1.endpoints.articles import router as articles_router
from app.presentation.api.v1.endpoints.chat import router as chat_router

router = APIRouter(prefix="/v1")
router.include_router(health_router)
router.include_router(articles_router)
router.include_router(chat_router)
