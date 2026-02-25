"""
Main Application
FastAPI приложение с healthcheck endpoints и инициализацией.
"""

import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import (
    init_db,
    close_db,
    get_db,
    check_db_connection,
    AsyncSessionLocal,
    RawArticle,
    PostDraft,
    Publication
)
from app.api.miniapp import router as miniapp_router
import structlog

# Настройка логирования
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


# ====================
# Lifespan Events
# ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # Startup
    logger.info("application_startup", app_name=settings.app_name)

    # Инициализация базы данных
    try:
        await init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_init_error", error=str(e))

    # Инициализация дефолтных настроек
    try:
        from app.modules.settings_manager import init_default_settings

        async with AsyncSessionLocal() as db:
            await init_default_settings(db)
            await db.commit()
        logger.info("default_settings_initialized")
    except Exception as e:
        logger.error("settings_init_error", error=str(e))

    yield

    # Shutdown
    logger.info("application_shutdown")

    # Закрытие соединений с БД
    try:
        await close_db()
        logger.info("database_closed")
    except Exception as e:
        logger.error("database_close_error", error=str(e))


# ====================
# FastAPI Application
# ====================

app = FastAPI(
    title=settings.app_name,
    description="AI-News Aggregator для LegalTech - полуавтоматизированная система сбора и публикации новостей",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Include API routers
app.include_router(miniapp_router)

# Add CORS middleware for Mini App
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ====================
# Routes
# ====================

@app.get("/")
async def root():
    """Корневой endpoint."""
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "status": "running",
        "environment": settings.app_env,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """
    Healthcheck endpoint для Docker и мониторинга.

    Проверяет:
    - Соединение с БД
    - Redis (опционально)
    - Статус компонентов
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }

    # Проверка БД
    try:
        db_healthy = await check_db_connection()
        health_status["components"]["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "type": "PostgreSQL"
        }
    except Exception as e:
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"

    # Проверка Redis (через попытку подключения)
    try:
        import redis
        r = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2
        )
        r.ping()
        health_status["components"]["redis"] = {
            "status": "healthy",
            "type": "Redis"
        }
    except Exception as e:
        health_status["components"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"

    # Проверка Celery (опционально)
    try:
        from app.tasks.celery_tasks import app as celery_app
        inspect = celery_app.control.inspect(timeout=2)
        active_workers = inspect.active()

        health_status["components"]["celery"] = {
            "status": "healthy" if active_workers else "unhealthy",
            "workers": list(active_workers.keys()) if active_workers else []
        }
    except Exception as e:
        health_status["components"]["celery"] = {
            "status": "unknown",
            "error": str(e)
        }

    # Определяем общий статус
    component_statuses = [c["status"] for c in health_status["components"].values()]
    if "unhealthy" in component_statuses:
        health_status["status"] = "unhealthy"
    elif "degraded" in component_statuses:
        health_status["status"] = "degraded"

    status_code = 200 if health_status["status"] in ["healthy", "degraded"] else 503

    return JSONResponse(content=health_status, status_code=status_code)


@app.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """
    Получить статистику системы.

    Returns:
        Статистика по статьям, драфтам и публикациям
    """
    try:
        # Количество статей
        articles_total = await db.scalar(select(func.count(RawArticle.id)))
        articles_new = await db.scalar(
            select(func.count(RawArticle.id)).where(RawArticle.status == 'new')
        )
        articles_filtered = await db.scalar(
            select(func.count(RawArticle.id)).where(RawArticle.status == 'filtered')
        )

        # Количество драфтов
        drafts_total = await db.scalar(select(func.count(PostDraft.id)))
        drafts_pending = await db.scalar(
            select(func.count(PostDraft.id)).where(PostDraft.status == 'pending_review')
        )
        drafts_approved = await db.scalar(
            select(func.count(PostDraft.id)).where(PostDraft.status == 'approved')
        )

        # Количество публикаций
        publications_total = await db.scalar(select(func.count(Publication.id)))

        # Последняя активность
        last_fetch = await db.scalar(
            select(func.max(RawArticle.fetched_at))
        )
        last_draft = await db.scalar(
            select(func.max(PostDraft.created_at))
        )
        last_publication = await db.scalar(
            select(func.max(Publication.published_at))
        )

        return {
            "articles": {
                "total": articles_total,
                "new": articles_new,
                "filtered": articles_filtered,
            },
            "drafts": {
                "total": drafts_total,
                "pending": drafts_pending,
                "approved": drafts_approved,
            },
            "publications": {
                "total": publications_total,
            },
            "last_activity": {
                "fetch": last_fetch.isoformat() if last_fetch else None,
                "draft": last_draft.isoformat() if last_draft else None,
                "publication": last_publication.isoformat() if last_publication else None,
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error("stats_error", error=str(e))
        return JSONResponse(
            content={"error": "Failed to retrieve statistics"},
            status_code=500
        )


@app.get("/config")
async def get_config():
    """
    Получить конфигурацию (только публичные параметры).

    Returns:
        Публичные настройки приложения
    """
    return {
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "debug": settings.debug,
        "fetcher_enabled": settings.fetcher_enabled,
        "ai_enabled": settings.ai_ranking_enabled,
        "publisher_auto_publish": settings.publisher_auto_publish,
        "publisher_require_approval": settings.publisher_require_approval,
        "analytics_enabled": settings.analytics_enabled,
        "timezone": settings.tz,
    }


# ====================
# Error Handlers
# ====================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Глобальный обработчик ошибок."""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An error occurred"
        }
    )


# ====================
# Main Entry Point
# ====================

if __name__ == "__main__":
    import uvicorn

    logger.info(
        "starting_application",
        host="0.0.0.0",
        port=8000,
        environment=settings.app_env
    )

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
