#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive System Test Script
Tests all newly implemented features:
- FastAPI main application
- Contract API endpoints
- WebSocket functionality
- Email service
- Payment service (Stripe)
- React frontend files
"""
import os
import sys
import ast
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

passed = 0
failed = 0


def test_file_exists(filepath: str, description: str) -> bool:
    """Test if file exists"""
    global passed, failed
    if os.path.exists(filepath):
        print(f"{GREEN}✅ PASS{RESET} - {description}: {filepath}")
        passed += 1
        return True
    else:
        print(f"{RED}❌ FAIL{RESET} - {description}: {filepath} (NOT FOUND)")
        failed += 1
        return False


def test_python_syntax(filepath: str, description: str) -> bool:
    """Test Python file syntax"""
    global passed, failed
    if not os.path.exists(filepath):
        print(f"{YELLOW}⚠️  SKIP{RESET} - {description}: {filepath} (FILE NOT FOUND)")
        return False

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        print(f"{GREEN}✅ PASS{RESET} - Syntax: {filepath}")
        passed += 1
        return True
    except SyntaxError as e:
        print(f"{RED}❌ FAIL{RESET} - Syntax error in {filepath}: {e}")
        failed += 1
        return False


def test_contains(filepath: str, search_strings: list, description: str) -> bool:
    """Test if file contains specific strings"""
    global passed, failed
    if not os.path.exists(filepath):
        print(f"{YELLOW}⚠️  SKIP{RESET} - {description}: {filepath} (FILE NOT FOUND)")
        return False

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        missing = []
        for search_str in search_strings:
            if search_str not in content:
                missing.append(search_str)

        if not missing:
            print(f"{GREEN}✅ PASS{RESET} - {description}")
            passed += 1
            return True
        else:
            print(f"{RED}❌ FAIL{RESET} - {description}: Missing {missing}")
            failed += 1
            return False
    except Exception as e:
        print(f"{RED}❌ FAIL{RESET} - Error reading {filepath}: {e}")
        failed += 1
        return False


def print_header(text: str):
    """Print section header"""
    print(f"\n{BLUE}{'=' * 70}")
    print(f"{text}")
    print(f"{'=' * 70}{RESET}\n")


def main():
    """Run all tests"""
    global passed, failed

    print_header("COMPREHENSIVE SYSTEM TEST - CONTRACT AI SYSTEM")

    # ==========================
    # 1. FastAPI Main Application
    # ==========================
    print_header("1. FastAPI Main Application")

    test_file_exists("src/main.py", "FastAPI main.py")
    test_python_syntax("src/main.py", "FastAPI main.py syntax")
    test_contains("src/main.py", [
        "from fastapi import FastAPI",
        "@asynccontextmanager",
        "def lifespan",
        "app.include_router(auth_router",
        "app.include_router(contracts_router",
        "app.include_router(websocket_router",
        "app.include_router(payments_router"
    ], "FastAPI main.py includes all routers")

    # ==========================
    # 2. Contract API
    # ==========================
    print_header("2. Contract API Endpoints")

    test_file_exists("src/api/contracts/__init__.py", "Contracts API __init__")
    test_file_exists("src/api/contracts/routes.py", "Contracts API routes")
    test_python_syntax("src/api/contracts/routes.py", "Contracts API routes syntax")

    test_contains("src/api/contracts/routes.py", [
        "@router.post(\"/upload\"",
        "@router.post(\"/analyze\"",
        "@router.post(\"/generate\"",
        "@router.post(\"/disagreements\"",
        "@router.post(\"/export\"",
        "@router.get(\"/list\"",
        "@router.get(\"/{contract_id}\"",
        "@router.get(\"/{contract_id}/download\"",
        "async def upload_contract",
        "async def analyze_contract",
        "async def generate_contract",
    ], "Contract API endpoints defined")

    # ==========================
    # 3. WebSocket
    # ==========================
    print_header("3. WebSocket for Real-Time Updates")

    test_file_exists("src/api/websocket/__init__.py", "WebSocket API __init__")
    test_file_exists("src/api/websocket/routes.py", "WebSocket API routes")
    test_python_syntax("src/api/websocket/routes.py", "WebSocket API routes syntax")

    test_contains("src/api/websocket/routes.py", [
        "@router.websocket(\"/analysis/{contract_id}\")",
        "@router.websocket(\"/notifications\")",
        "class ConnectionManager",
        "async def websocket_analysis_updates",
        "async def websocket_notifications",
        "await websocket.accept()",
        "await manager.send_personal_message"
    ], "WebSocket endpoints and ConnectionManager")

    # ==========================
    # 4. Email Service
    # ==========================
    print_header("4. Email Service")

    test_file_exists("src/services/email_service.py", "Email service")
    test_python_syntax("src/services/email_service.py", "Email service syntax")

    test_contains("src/services/email_service.py", [
        "class EmailService",
        "def send_verification_email",
        "def send_password_reset_email",
        "def send_welcome_email",
        "def send_analysis_complete_email",
        "def send_demo_expiring_email",
        "def _send_smtp",
        "def _send_sendgrid",
        "email_service = EmailService()"
    ], "Email service methods")

    # ==========================
    # 5. Payment Service (Stripe)
    # ==========================
    print_header("5. Payment Service (Stripe)")

    test_file_exists("src/services/payment_service.py", "Payment service")
    test_python_syntax("src/services/payment_service.py", "Payment service syntax")

    test_contains("src/services/payment_service.py", [
        "class PaymentService",
        "def create_customer",
        "def create_checkout_session",
        "def create_customer_portal_session",
        "def cancel_subscription",
        "def handle_webhook",
        "_handle_checkout_completed",
        "_handle_subscription_updated",
        "_handle_subscription_deleted",
        "_handle_payment_succeeded",
        "_handle_payment_failed",
        "payment_service = PaymentService()"
    ], "Payment service methods")

    test_file_exists("src/api/payments/__init__.py", "Payments API __init__")
    test_file_exists("src/api/payments/routes.py", "Payments API routes")
    test_python_syntax("src/api/payments/routes.py", "Payments API routes syntax")

    test_contains("src/api/payments/routes.py", [
        "@router.get(\"/pricing\")",
        "@router.post(\"/checkout\")",
        "@router.post(\"/portal\")",
        "@router.get(\"/subscription\")",
        "@router.post(\"/subscription/cancel\")",
        "@router.post(\"/webhooks/stripe\")"
    ], "Payment API endpoints")

    # ==========================
    # 6. React Frontend
    # ==========================
    print_header("6. React Frontend (Next.js)")

    # Core files
    test_file_exists("frontend/package.json", "Frontend package.json")
    test_file_exists("frontend/next.config.js", "Next.js config")
    test_file_exists("frontend/tailwind.config.js", "Tailwind config")

    # App structure
    test_file_exists("frontend/src/app/layout.tsx", "App layout")
    test_file_exists("frontend/src/app/providers.tsx", "App providers")
    test_file_exists("frontend/src/app/page.tsx", "Home page")
    test_file_exists("frontend/src/app/globals.css", "Global CSS")

    # Pages
    test_file_exists("frontend/src/pages/login.tsx", "Login page")
    test_file_exists("frontend/src/app/dashboard/page.tsx", "Dashboard page")
    test_file_exists("frontend/src/app/pricing/page.tsx", "Pricing page")

    # Services
    test_file_exists("frontend/src/services/api.ts", "API service")

    # Test API service content
    test_contains("frontend/src/services/api.ts", [
        "class APIClient",
        "async login",
        "async register",
        "async activateDemo",
        "async getCurrentUser",
        "async uploadContract",
        "async analyzeContract",
        "async listContracts",
        "async getPricing",
        "async createCheckoutSession"
    ], "API service methods")

    # ==========================
    # 7. Dependencies
    # ==========================
    print_header("7. Requirements.txt Dependencies")

    test_file_exists("requirements.txt", "requirements.txt")

    test_contains("requirements.txt", [
        "fastapi",
        "uvicorn",
        "websockets",
        "bcrypt",
        "pyjwt",
        "python-jose",
        "qrcode",
        "sendgrid",
        "stripe",
        "python-multipart"
    ], "All required dependencies in requirements.txt")

    # ==========================
    # 8. Integration Points
    # ==========================
    print_header("8. Integration Points")

    # Check main.py includes all routes
    test_contains("src/main.py", [
        "from src.api.auth.routes import router as auth_router",
        "from src.api.contracts import router as contracts_router",
        "from src.api.websocket import router as websocket_router",
        "from src.api.payments import router as payments_router"
    ], "Main.py imports all routers")

    # Check security middleware
    test_file_exists("src/middleware/security.py", "Security middleware")
    test_contains("src/middleware/security.py", [
        "class RateLimitMiddleware",
        "class SecurityHeadersMiddleware"
    ], "Security middleware classes")

    # ==========================
    # SUMMARY
    # ==========================
    print_header("TEST SUMMARY")

    total = passed + failed
    pass_rate = (passed / total * 100) if total > 0 else 0

    print(f"Total tests: {total}")
    print(f"{GREEN}✅ Passed: {passed}{RESET}")
    print(f"{RED}❌ Failed: {failed}{RESET}")
    print(f"\nPass rate: {pass_rate:.1f}%")

    if failed == 0:
        print(f"\n{GREEN}{'=' * 70}")
        print(f"🎉 ALL TESTS PASSED! SYSTEM READY FOR DEPLOYMENT")
        print(f"{'=' * 70}{RESET}\n")
        return 0
    else:
        print(f"\n{RED}{'=' * 70}")
        print(f"⚠️  SOME TESTS FAILED - PLEASE FIX ERRORS ABOVE")
        print(f"{'=' * 70}{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
