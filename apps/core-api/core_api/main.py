from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core_api.alerts import send_telegram_alert
from core_api.config import get_settings
from core_api.logging_config import setup_logging
from core_api.routers import admin, automation_controls, contract_jobs, events, health, leads, scheduled_posts, users, workers

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title="Legal AI Core API", version="1.0.0")
app.state.started_at = datetime.now(timezone.utc)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["X-API-Key", "Idempotency-Key", "Content-Type"],
)

app.include_router(health.router)
app.include_router(users.router)
app.include_router(leads.router)
app.include_router(events.router)
app.include_router(automation_controls.router)
app.include_router(scheduled_posts.router)
app.include_router(contract_jobs.router)
app.include_router(workers.router)
app.include_router(admin.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception", extra={"path": str(request.url.path)})
    send_telegram_alert(f"🔴 Legal AI Core API error on {request.url.path}: {type(exc).__name__}")
    return JSONResponse({"detail": "Internal server error"}, status_code=500)
