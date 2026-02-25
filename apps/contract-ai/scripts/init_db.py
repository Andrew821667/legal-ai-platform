#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Initialize Database - Create all tables and setup initial data
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models import init_db, get_db, User, DemoToken
from src.services.auth_service import AuthService
from loguru import logger
from datetime import datetime, timedelta


def main():
    """Initialize database with all tables and test data"""
    logger.info("🚀 Initializing database...")

    try:
        # Create all tables
        init_db()
        logger.info("✅ Database tables created")

        # Create test admin user
        db = next(get_db())
        auth_service = AuthService(db)

        # Check if admin exists
        admin = db.query(User).filter(User.email == "admin@contract-ai.com").first()

        if not admin:
            # Create admin user
            user, temp_password, error = auth_service.create_user_as_admin(
                email="admin@contract-ai.com",
                name="Admin User",
                role="admin",
                subscription_tier="enterprise",
                admin_user_id=None
            )

            if error:
                logger.error(f"❌ Failed to create admin: {error}")
            else:
                logger.info(f"✅ Admin user created: admin@contract-ai.com")
                logger.info(f"🔑 Temporary password: {temp_password}")
                logger.info("⚠️  Please change this password after first login!")
        else:
            logger.info("ℹ️  Admin user already exists")

        # Create demo user
        demo = db.query(User).filter(User.email == "demo@contract-ai.com").first()

        if not demo:
            user, temp_password, error = auth_service.create_user_as_admin(
                email="demo@contract-ai.com",
                name="Demo User",
                role="junior_lawyer",
                subscription_tier="basic",
                admin_user_id=None
            )

            if error:
                logger.error(f"❌ Failed to create demo user: {error}")
            else:
                logger.info(f"✅ Demo user created: demo@contract-ai.com")
                logger.info(f"🔑 Temporary password: {temp_password}")
        else:
            logger.info("ℹ️  Demo user already exists")

        # Create demo token
        existing_token = db.query(DemoToken).filter(DemoToken.campaign == "local-dev").first()

        if not existing_token:
            # Get admin user for created_by field
            admin = db.query(User).filter(User.email == "admin@contract-ai.com").first()

            demo_token = DemoToken(
                token="demo-local-dev-token-12345",
                campaign="local-dev",
                max_contracts=10,
                expires_at=datetime.utcnow() + timedelta(days=365),
                used=False,
                created_by=admin.id if admin else None
            )
            db.add(demo_token)
            db.commit()

            logger.info(f"✅ Demo token created: {demo_token.token}")
            logger.info(f"🎟️  Token expires: {demo_token.expires_at}")
        else:
            logger.info("ℹ️  Demo token already exists")

        logger.info("\n" + "="*60)
        logger.info("🎉 Database initialized successfully!")
        logger.info("="*60)
        logger.info("\n📋 Login Credentials:")
        logger.info("\n👤 Admin User:")
        logger.info("   Email: admin@contract-ai.com")
        logger.info("   Password: (check output above)")
        logger.info("\n👤 Demo User:")
        logger.info("   Email: demo@contract-ai.com")
        logger.info("   Password: (check output above)")
        logger.info("\n🎟️  Demo Token: demo-local-dev-token-12345")
        logger.info("="*60 + "\n")

        db.close()

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
