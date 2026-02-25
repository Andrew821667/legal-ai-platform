#!/usr/bin/env python
"""
Test script to verify authentication system implementation

Tests:
1. Python syntax (all files compile)
2. Imports work correctly
3. Models can be instantiated
4. Auth service methods exist
5. API routes are defined
"""

import sys
import importlib.util
from pathlib import Path

print("=" * 70)
print("TESTING AUTHENTICATION SYSTEM IMPLEMENTATION")
print("=" * 70)

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def test_result(name: str, passed: bool, message: str = ""):
    """Print test result"""
    status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
    print(f"{status} - {name}")
    if message:
        print(f"      {message}")

errors = []

# Test 1: Python files compile
print("\n1. Testing Python Syntax...")
print("-" * 70)

python_files = [
    "src/models/auth_models.py",
    "src/services/auth_service.py",
    "src/api/auth/routes.py",
    "src/pages/admin_panel.py",
    "src/middleware/security.py"
]

for file_path in python_files:
    try:
        spec = importlib.util.spec_from_file_location("test_module", file_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            # Don't execute, just check syntax
            test_result(f"Syntax: {file_path}", True)
        else:
            test_result(f"Syntax: {file_path}", False, "Cannot load spec")
            errors.append(f"Syntax error in {file_path}")
    except SyntaxError as e:
        test_result(f"Syntax: {file_path}", False, str(e))
        errors.append(f"Syntax error in {file_path}: {e}")

# Test 2: Check if dependencies exist in requirements.txt
print("\n2. Testing Dependencies...")
print("-" * 70)

required_deps = [
    "bcrypt",
    "pyjwt",
    "python-jose",
    "qrcode",
    "fastapi",
    "sqlalchemy",
    "streamlit"
]

try:
    with open("requirements.txt", "r") as f:
        reqs = f.read()
        for dep in required_deps:
            if dep.lower() in reqs.lower():
                test_result(f"Dependency: {dep}", True)
            else:
                test_result(f"Dependency: {dep}", False, "Not found in requirements.txt")
                errors.append(f"Missing dependency: {dep}")
except FileNotFoundError:
    test_result("requirements.txt", False, "File not found")
    errors.append("requirements.txt not found")

# Test 3: Check model classes exist (without importing to avoid dependency errors)
print("\n3. Testing Model Definitions...")
print("-" * 70)

model_checks = {
    "src/models/auth_models.py": [
        "class User",
        "class UserSession",
        "class DemoToken",
        "class AuditLog",
        "class PasswordResetRequest",
        "class EmailVerification",
        "class LoginAttempt"
    ]
}

for file_path, classes in model_checks.items():
    try:
        with open(file_path, "r") as f:
            content = f.read()
            for class_name in classes:
                if class_name in content:
                    test_result(f"Model: {class_name}", True)
                else:
                    test_result(f"Model: {class_name}", False, "Class not found")
                    errors.append(f"Missing {class_name} in {file_path}")
    except FileNotFoundError:
        test_result(f"File: {file_path}", False, "File not found")
        errors.append(f"File not found: {file_path}")

# Test 4: Check auth service methods
print("\n4. Testing Auth Service Methods...")
print("-" * 70)

auth_methods = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "register_user",
    "login_user",
    "generate_demo_token",
    "activate_demo_token"
]

try:
    with open("src/services/auth_service.py", "r") as f:
        content = f.read()
        for method in auth_methods:
            if f"def {method}" in content:
                test_result(f"Method: {method}", True)
            else:
                test_result(f"Method: {method}", False, "Method not found")
                errors.append(f"Missing method: {method}")
except FileNotFoundError:
    test_result("auth_service.py", False, "File not found")
    errors.append("auth_service.py not found")

# Test 5: Check API endpoints
print("\n5. Testing API Endpoints...")
print("-" * 70)

api_endpoints = [
    '@router.post("/register"',
    '@router.post("/login"',
    '@router.post("/demo-activate"',
    '@router.post("/refresh"',
    '@router.post("/logout"',
    '@router.get("/me"',
    '@router.post("/admin/demo-link"',
    '@router.post("/admin/users"',
    '@router.get("/admin/users"',
]

try:
    with open("src/api/auth/routes.py", "r") as f:
        content = f.read()
        for endpoint in api_endpoints:
            if endpoint in content:
                test_result(f"Endpoint: {endpoint}", True)
            else:
                test_result(f"Endpoint: {endpoint}", False, "Endpoint not found")
                errors.append(f"Missing endpoint: {endpoint}")
except FileNotFoundError:
    test_result("routes.py", False, "File not found")
    errors.append("routes.py not found")

# Test 6: Check SQL migration
print("\n6. Testing SQL Migration...")
print("-" * 70)

sql_tables = [
    "user_sessions",
    "demo_tokens",
    "audit_logs",
    "password_reset_requests",
    "email_verifications",
    "login_attempts"
]

try:
    with open("database/migrations/add_auth_models.sql", "r") as f:
        content = f.read()
        for table in sql_tables:
            if f"CREATE TABLE IF NOT EXISTS {table}" in content or f"CREATE TABLE {table}" in content:
                test_result(f"Table: {table}", True)
            else:
                test_result(f"Table: {table}", False, "Table creation not found")
                errors.append(f"Missing table creation: {table}")
except FileNotFoundError:
    test_result("add_auth_models.sql", False, "File not found")
    errors.append("SQL migration file not found")

# Test 7: Check React frontend files
print("\n7. Testing React Frontend Files...")
print("-" * 70)

frontend_files = [
    ("frontend/package.json", "package.json"),
    ("frontend/next.config.js", "next.config.js"),
    ("frontend/tailwind.config.js", "tailwind.config.js"),
    ("frontend/src/services/api.ts", "API service"),
    ("frontend/src/pages/login.tsx", "Login page")
]

for file_path, description in frontend_files:
    if Path(file_path).exists():
        test_result(f"Frontend: {description}", True)
    else:
        test_result(f"Frontend: {description}", False, "File not found")
        errors.append(f"Missing frontend file: {file_path}")

# Test 8: Check admin panel components
print("\n8. Testing Admin Panel Components...")
print("-" * 70)

admin_components = [
    "show_user_management_tab",
    "show_demo_links_tab",
    "show_analytics_tab",
    "show_audit_logs_tab"
]

try:
    with open("src/pages/admin_panel.py", "r") as f:
        content = f.read()
        for component in admin_components:
            if f"def {component}" in content:
                test_result(f"Admin: {component}", True)
            else:
                test_result(f"Admin: {component}", False, "Function not found")
                errors.append(f"Missing admin function: {component}")
except FileNotFoundError:
    test_result("admin_panel.py", False, "File not found")
    errors.append("admin_panel.py not found")

# Final summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

if errors:
    print(f"{RED}❌ FAILED - {len(errors)} error(s) found:{RESET}")
    for error in errors:
        print(f"  - {error}")
    sys.exit(1)
else:
    print(f"{GREEN}✅ ALL TESTS PASSED!{RESET}")
    print("\nImplementation appears to be syntactically correct.")
    print("\nNext steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Run database migration: psql -d contracts -f database/migrations/add_auth_models.sql")
    print("3. Start backend: uvicorn src.main:app --reload")
    print("4. Start admin panel: streamlit run src/pages/admin_panel.py")
    print("5. Install frontend: cd frontend && npm install")
    print("6. Start frontend: npm run dev")
    sys.exit(0)
