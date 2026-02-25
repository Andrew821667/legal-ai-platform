#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Initialization Script
Creates initial users and demo tokens for Contract AI System
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from src.models.database import engine, Base
from src.models.auth_models import User, DemoToken
from src.services.auth_service import AuthService
from loguru import logger


def create_initial_users(db: Session) -> dict:
    """
    Create initial users with different roles and tiers

    Returns:
        dict: Dictionary of created users with credentials
    """

    auth_service = AuthService(db)
    credentials = {}

    users_to_create = [
        {
            "email": "admin@contractai.local",
            "name": "System Administrator",
            "password": "Admin123!",
            "role": "admin",
            "subscription_tier": "enterprise",
            "is_demo": False,
            "description": "Full system administrator with unlimited access"
        },
        {
            "email": "demo1@example.com",
            "name": "Demo User 1",
            "password": "Demo123!",
            "role": "demo",
            "subscription_tier": "demo",
            "is_demo": True,
            "demo_expires": datetime.utcnow() + timedelta(days=7),
            "description": "Demo user via link (7 days trial)"
        },
        {
            "email": "demo2@example.com",
            "name": "Demo User 2",
            "password": "Demo123!",
            "role": "demo",
            "subscription_tier": "demo",
            "is_demo": True,
            "demo_expires": datetime.utcnow() + timedelta(days=7),
            "description": "Demo user via link (7 days trial)"
        },
        {
            "email": "trial@example.com",
            "name": "Trial User",
            "password": "Trial123!",
            "role": "junior_lawyer",
            "subscription_tier": "basic",
            "is_demo": False,
            "subscription_expires": datetime.utcnow() + timedelta(days=30),
            "description": "Trial user with 30 days basic access"
        },
        {
            "email": "junior@contractai.local",
            "name": "Junior Lawyer",
            "password": "Junior123!",
            "role": "junior_lawyer",
            "subscription_tier": "basic",
            "is_demo": False,
            "description": "Junior lawyer with basic tier access"
        },
        {
            "email": "lawyer@contractai.local",
            "name": "Regular Lawyer",
            "password": "Lawyer123!",
            "role": "lawyer",
            "subscription_tier": "pro",
            "is_demo": False,
            "description": "Regular lawyer with pro tier access"
        },
        {
            "email": "senior@contractai.local",
            "name": "Senior Lawyer",
            "password": "Senior123!",
            "role": "senior_lawyer",
            "subscription_tier": "pro",
            "is_demo": False,
            "description": "Senior lawyer with pro tier access"
        },
        {
            "email": "vip@contractai.local",
            "name": "VIP Client",
            "password": "Vip123!",
            "role": "senior_lawyer",
            "subscription_tier": "enterprise",
            "is_demo": False,
            "description": "VIP client with enterprise unlimited access"
        },
    ]

    logger.info(f"Creating {len(users_to_create)} initial users...")

    for user_data in users_to_create:
        email = user_data["email"]

        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            logger.warning(f"User {email} already exists, skipping...")
            continue

        # Hash password
        password = user_data.pop("password")
        description = user_data.pop("description")
        password_hash = auth_service.hash_password(password)

        # Create user
        user = User(
            **user_data,
            password_hash=password_hash,
            email_verified=True,  # Auto-verify initial users
            active=True,
            created_at=datetime.utcnow(),
            contracts_today=0,
            llm_requests_today=0,
            last_reset_date=datetime.utcnow()
        )

        db.add(user)
        db.flush()

        # Store credentials
        credentials[email] = {
            "email": email,
            "password": password,
            "name": user_data["name"],
            "role": user_data["role"],
            "tier": user_data["subscription_tier"],
            "description": description
        }

        logger.info(f"✅ Created user: {email} ({user_data['role']}/{user_data['subscription_tier']})")

    db.commit()
    logger.info(f"Successfully created {len(credentials)} users")

    return credentials


def create_demo_tokens(db: Session) -> list:
    """
    Create initial demo tokens for testing

    Returns:
        list: List of created demo tokens
    """

    # Get admin user
    admin = db.query(User).filter(User.role == "admin").first()
    if not admin:
        logger.error("Admin user not found! Create users first.")
        return []

    tokens_to_create = [
        {
            "token": f"demo_token_basic_{datetime.utcnow().strftime('%Y%m%d')}",
            "max_contracts": 3,
            "max_llm_requests": 10,
            "max_file_size_mb": 5,
            "expires_in_hours": 24,
            "source": "init_script",
            "campaign": "initial_setup",
            "description": "Basic demo: 3 contracts, 10 LLM requests, 24 hours"
        },
        {
            "token": f"demo_token_medium_{datetime.utcnow().strftime('%Y%m%d')}",
            "max_contracts": 5,
            "max_llm_requests": 20,
            "max_file_size_mb": 10,
            "expires_in_hours": 72,
            "source": "init_script",
            "campaign": "initial_setup",
            "description": "Medium demo: 5 contracts, 20 LLM requests, 72 hours"
        },
        {
            "token": f"demo_token_extended_{datetime.utcnow().strftime('%Y%m%d')}",
            "max_contracts": 10,
            "max_llm_requests": 50,
            "max_file_size_mb": 20,
            "expires_in_hours": 168,  # 7 days
            "source": "init_script",
            "campaign": "initial_setup",
            "description": "Extended demo: 10 contracts, 50 LLM requests, 7 days"
        },
    ]

    created_tokens = []

    logger.info(f"Creating {len(tokens_to_create)} demo tokens...")

    for token_data in tokens_to_create:
        description = token_data.pop("description")

        demo_token = DemoToken(
            **token_data,
            created_by=admin.id,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=token_data["expires_in_hours"]),
            used=False,
            uses_count=0,
            max_uses=1
        )

        db.add(demo_token)
        db.flush()

        created_tokens.append({
            "token": token_data["token"],
            "contracts": token_data["max_contracts"],
            "llm_requests": token_data["max_llm_requests"],
            "expires_hours": token_data["expires_in_hours"],
            "description": description
        })

        logger.info(f"✅ Created demo token: {description}")

    db.commit()
    logger.info(f"Successfully created {len(created_tokens)} demo tokens")

    return created_tokens


def save_credentials_to_file(credentials: dict, tokens: list):
    """Save credentials to a file for easy access"""

    output_file = Path(__file__).parent.parent / "CREDENTIALS.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("CONTRACT AI SYSTEM - INITIAL CREDENTIALS\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")

        f.write("USERS:\n")
        f.write("-" * 80 + "\n\n")

        # Sort by role priority
        role_priority = {"admin": 0, "senior_lawyer": 1, "lawyer": 2, "junior_lawyer": 3, "demo": 4}
        sorted_creds = sorted(credentials.items(), key=lambda x: role_priority.get(x[1]["role"], 99))

        for email, cred in sorted_creds:
            f.write(f"Email:    {cred['email']}\n")
            f.write(f"Password: {cred['password']}\n")
            f.write(f"Name:     {cred['name']}\n")
            f.write(f"Role:     {cred['role']}\n")
            f.write(f"Tier:     {cred['tier']}\n")
            f.write(f"Info:     {cred['description']}\n")
            f.write("-" * 80 + "\n")

        if tokens:
            f.write("\n\nDEMO TOKENS:\n")
            f.write("-" * 80 + "\n\n")

            for token in tokens:
                f.write(f"Token:        {token['token']}\n")
                f.write(f"Contracts:    {token['contracts']}\n")
                f.write(f"LLM Requests: {token['llm_requests']}\n")
                f.write(f"Expires:      {token['expires_hours']} hours\n")
                f.write(f"Description:  {token['description']}\n")
                f.write("-" * 80 + "\n")

        f.write("\n\nUSAGE:\n")
        f.write("-" * 80 + "\n")
        f.write("1. Main Interface (Users): http://localhost:3000\n")
        f.write("2. Admin Panel (Admin only): http://localhost:8501\n")
        f.write("3. API Documentation: http://localhost:8000/api/docs\n\n")
        f.write("⚠️  IMPORTANT: Change these passwords in production!\n")
        f.write("=" * 80 + "\n")

    logger.info(f"📄 Credentials saved to: {output_file}")


def print_credentials_table(credentials: dict):
    """Print credentials in a nice table format"""

    print("\n" + "=" * 120)
    print("CONTRACT AI SYSTEM - INITIAL CREDENTIALS")
    print("=" * 120 + "\n")

    # Header
    print(f"{'#':<3} {'Email':<30} {'Password':<15} {'Role':<20} {'Tier':<12} {'Description':<30}")
    print("-" * 120)

    # Sort by role priority
    role_priority = {"admin": 0, "senior_lawyer": 1, "lawyer": 2, "junior_lawyer": 3, "demo": 4}
    sorted_creds = sorted(credentials.items(), key=lambda x: role_priority.get(x[1]["role"], 99))

    for idx, (email, cred) in enumerate(sorted_creds, 1):
        print(f"{idx:<3} {cred['email']:<30} {cred['password']:<15} {cred['role']:<20} {cred['tier']:<12} {cred['description']:<30}")

    print("=" * 120 + "\n")


def main():
    """Main initialization function"""

    logger.info("🚀 Starting database initialization...")

    # Create tables
    logger.info("📊 Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables created")

    # Create session
    from src.models.database import SessionLocal
    db = SessionLocal()

    try:
        # Create users
        credentials = create_initial_users(db)

        if not credentials:
            logger.error("❌ No users created (they may already exist)")
            return

        # Create demo tokens
        tokens = create_demo_tokens(db)

        # Save to file
        save_credentials_to_file(credentials, tokens)

        # Print to console
        print_credentials_table(credentials)

        if tokens:
            print("\n📋 DEMO TOKENS CREATED:")
            print("-" * 80)
            for token in tokens:
                print(f"  • {token['description']}")
                print(f"    Token: {token['token']}")
            print("-" * 80 + "\n")

        logger.info("✅ Database initialization completed successfully!")
        logger.info(f"📄 Credentials saved to CREDENTIALS.txt")

        print("\n🎉 SUCCESS! Contract AI System is ready to use.")
        print("\n📍 ACCESS POINTS:")
        print("  • Main Interface: http://localhost:3000")
        print("  • Admin Panel: http://localhost:8501")
        print("  • API Docs: http://localhost:8000/api/docs")
        print("\n⚠️  Don't forget to change passwords in production!\n")

    except Exception as e:
        logger.error(f"❌ Error during initialization: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
