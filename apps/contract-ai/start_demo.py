#!/usr/bin/env python3
"""
Simplified FastAPI Server for Demo
Demonstrates the system without full authentication
"""
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Create app
app = FastAPI(
    title="Contract AI System - DEMO",
    description="Simplified demo server",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Contract AI System API - Demo Mode",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "api": "/api/v1/"
        }
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "Contract AI System",
        "mode": "demo"
    }

@app.get("/api/v1/info")
async def api_info():
    return {
        "api_version": "v1",
        "features": [
            "Contract Upload (pending)",
            "Contract Analysis (pending)",
            "Contract Generation (pending)",
            "WebSocket Updates (pending)",
            "Email Notifications (configured)",
            "Stripe Payments (configured)"
        ],
        "note": "Full API requires additional dependencies. See requirements.txt"
    }

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("Contract AI System - Demo Server")
    print("=" * 60)
    print("Starting on http://0.0.0.0:8000")
    print("API Docs: http://localhost:8000/docs")
    print("Health Check: http://localhost:8000/health")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8000)
