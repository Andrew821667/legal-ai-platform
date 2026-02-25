"""
Security Middleware for FastAPI

Features:
- Rate limiting (token bucket algorithm)
- CORS configuration
- Security headers
- IP blocking/whitelisting
"""

from fastapi import Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Dict, Optional, List
from collections import defaultdict
from datetime import datetime, timedelta
import time


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using token bucket algorithm

    Limits:
    - Default: 1000 requests per minute per IP
    - Login: 20 requests per minute per IP
    - Register: 20 requests per minute per IP
    - Demo Activate: 50 requests per minute per IP
    """

    # Rate limiting settings
    requests_per_minute: int = 1000  # Increased from 100
    burst_limit: int = 50

    def __init__(self, app, requests_per_minute: int = 1000):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.buckets: Dict[str, Dict] = defaultdict(lambda: {
            'tokens': requests_per_minute,
            'last_update': time.time()
        })

        # Specific limits for endpoints
        self.endpoint_limits = {
            '/api/v1/auth/login': 20,
            '/api/v1/auth/register': 20,
            '/api/v1/auth/demo-activate': 50,
        }

    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check rate limit
        path = request.url.path
        limit = self.endpoint_limits.get(path, self.requests_per_minute)

        if not self._allow_request(client_ip, limit):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Please try again later.",
                    "retry_after": 60
                },
                headers={"Retry-After": "60"}
            )

        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _allow_request(self, client_ip: str, limit: int) -> bool:
        """
        Token bucket algorithm for rate limiting

        Args:
            client_ip: Client IP address
            limit: Requests per minute

        Returns:
            True if request allowed, False if rate limit exceeded
        """
        bucket = self.buckets[client_ip]
        now = time.time()

        # Refill tokens based on time passed
        time_passed = now - bucket['last_update']
        bucket['tokens'] = min(
            limit,
            bucket['tokens'] + time_passed * (limit / 60)
        )
        bucket['last_update'] = now

        # Check if we have tokens
        if bucket['tokens'] >= 1:
            bucket['tokens'] -= 1
            return True

        return False


class IPFilterMiddleware(BaseHTTPMiddleware):
    """
    IP filtering middleware

    Features:
    - Blacklist: Block specific IPs
    - Whitelist: Allow only specific IPs (if enabled)
    """

    def __init__(
        self,
        app,
        blacklist: Optional[List[str]] = None,
        whitelist: Optional[List[str]] = None,
        whitelist_enabled: bool = False
    ):
        super().__init__(app)
        self.blacklist = set(blacklist or [])
        self.whitelist = set(whitelist or [])
        self.whitelist_enabled = whitelist_enabled

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)

        # Check blacklist
        if client_ip in self.blacklist:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Access denied",
                    "message": "Your IP address has been blocked"
                }
            )

        # Check whitelist (if enabled)
        if self.whitelist_enabled and client_ip not in self.whitelist:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Access denied",
                    "message": "Your IP address is not authorized"
                }
            )

        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Security headers middleware

    Adds security-related HTTP headers:
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Strict-Transport-Security (HSTS)
    - Content-Security-Policy (CSP)
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.openai.com https://api.anthropic.com"
        )

        # Remove server header (security through obscurity)
        if "server" in response.headers:
            del response.headers["server"]

        return response


def setup_cors(app):
    """
    Setup CORS middleware

    Allows:
    - Specific origins (production domains)
    - Credentials (cookies, authorization headers)
    - Common HTTP methods
    - Common headers
    """
    from config.settings import settings

    allowed_origins = [
        "http://localhost:3000",  # React development
        "http://localhost:8000",  # FastAPI development
        "https://contract-ai.example.com",  # Production frontend
        "https://legal-ai-website.example.com",  # Legal AI website
    ]

    # Add production origins from settings if available
    if hasattr(settings, 'allowed_origins'):
        allowed_origins.extend(settings.allowed_origins)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "User-Agent",
            "DNT",
            "Cache-Control",
            "X-Requested-With"
        ],
        expose_headers=["Content-Length", "X-Total-Count"],
        max_age=600,  # Cache preflight requests for 10 minutes
    )


def setup_security_middleware(app):
    """
    Setup all security middleware

    Call this in your FastAPI app initialization:

    ```python
    from fastapi import FastAPI
    from src.middleware.security import setup_security_middleware

    app = FastAPI()
    setup_security_middleware(app)
    ```
    """

    # CORS (must be first)
    setup_cors(app)

    # Rate limiting
    app.add_middleware(RateLimitMiddleware, requests_per_minute=1000)

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # IP filtering (optional - disabled by default)
    # app.add_middleware(
    #     IPFilterMiddleware,
    #     blacklist=["192.168.1.100"],  # Example
    #     whitelist_enabled=False
    # )

    return app
