# -*- coding: utf-8 -*-
"""
FastAPI Main Application
Contract AI System Backend Server
"""
import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True
)
logger.add(
    "logs/api.log",
    rotation="10 MB",
    retention="30 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
)

# Import settings
from config.settings import settings

# Import database
from src.models.database import engine, Base, SessionLocal

# Import middleware
from src.middleware.security import setup_security_middleware

# Import routers
from src.api.auth.routes import router as auth_router
from src.api.contracts import router as contracts_router
from src.api.websocket import router as websocket_router
from src.api.payments import router as payments_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("🚀 Starting Contract AI System Backend...")

    # Create tables
    logger.info("📊 Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}")

    # Initialize services
    logger.info("🔧 Initializing services...")

    yield

    # Shutdown
    logger.info("👋 Shutting down Contract AI System Backend...")


# Create FastAPI app
app = FastAPI(
    title="Contract AI System API",
    description="Backend API for Contract AI System with authentication, contract analysis, and document generation",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React frontend
        "http://localhost:8501",  # Streamlit admin
        settings.frontend_url if hasattr(settings, 'frontend_url') else "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware setup
setup_security_middleware(app)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred"
        }
    )


# Health check
@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "Contract AI System API"
    }


# API info
@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    """Root endpoint with API information"""
    return {
        "name": "Contract AI System API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/health"
    }


# Include routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(contracts_router, prefix="/api/v1/contracts", tags=["Contracts"])
app.include_router(websocket_router, prefix="/api/v1/ws", tags=["WebSocket"])
app.include_router(payments_router, prefix="/api/v1/payments", tags=["Payments"])


# Static files for uploaded documents (with authentication)
if os.path.exists("data/contracts"):
    app.mount("/static", StaticFiles(directory="data/contracts"), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    )
