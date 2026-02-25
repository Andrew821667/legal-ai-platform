#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Contract AI System - Admin Panel (Streamlit)

Simplified admin interface for:
- User management
- Demo link generation
- Analytics
- System settings
- Audit logs
"""

import streamlit as st
import sys
from datetime import datetime, timedelta
from loguru import logger

# Configure page
st.set_page_config(
    page_title="Contract AI - Admin Panel",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True
)
logger.add(
    "admin_panel.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG"
)

# Import models and services
from src.models.database import SessionLocal
from src.models.auth_models import User, DemoToken, AuditLog
from src.services.auth_service import AuthService
from sqlalchemy import func, and_


def init_session_state():
    """Initialize session state"""
    # ✅ ТЕСТОВЫЙ РЕЖИМ: Автоматическая аутентификация без логина
    if 'admin_user' not in st.session_state:
        st.session_state.admin_user = {
            'id': 'test-admin',
            'email': 'admin@test.local',
            'name': 'Test Administrator',
            'role': 'admin'
        }
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = True  # ✅ Всегда авторизован


def show_login():
    """Show admin login form"""
    st.title("🔐 Admin Panel Login")
    st.markdown("---")

    with st.form("admin_login"):
        email = st.text_input("Email", placeholder="admin@contractai.local")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login", use_container_width=True)

        if submit:
            if not email or not password:
                st.error("Please enter email and password")
                return

            db = SessionLocal()
            try:
                auth_service = AuthService(db)

                # Find user
                user = db.query(User).filter(User.email == email, User.active == True).first()

                if not user:
                    st.error("Invalid credentials")
                    return

                # Check password
                if not auth_service.verify_password(password, user.password_hash):
                    st.error("Invalid credentials")
                    return

                # Check if admin
                if user.role != "admin":
                    st.error("Access denied. Admin role required.")
                    return

                # Success
                st.session_state.admin_user = {
                    'id': user.id,
                    'email': user.email,
                    'name': user.name,
                    'role': user.role
                }
                st.session_state.authenticated = True

                # Update last login
                user.last_login = datetime.utcnow()
                user.login_count += 1
                db.commit()

                st.success(f"Welcome, {user.name}!")
                st.rerun()

            except Exception as e:
                logger.error(f"Login error: {e}")
                st.error("Login error occurred")
            finally:
                db.close()


def show_users_page():
    """Show user management page"""
    st.title("👥 User Management")

    db = SessionLocal()
    try:
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            role_filter = st.selectbox(
                "Filter by Role",
                ["All", "admin", "senior_lawyer", "lawyer", "junior_lawyer", "demo"]
            )
        with col2:
            tier_filter = st.selectbox(
                "Filter by Tier",
                ["All", "demo", "basic", "pro", "enterprise"]
            )
        with col3:
            status_filter = st.selectbox(
                "Status",
                ["All", "Active", "Inactive", "Demo Expired"]
            )

        # Query users
        query = db.query(User)

        if role_filter != "All":
            query = query.filter(User.role == role_filter)
        if tier_filter != "All":
            query = query.filter(User.subscription_tier == tier_filter)
        if status_filter == "Active":
            query = query.filter(User.active == True)
        elif status_filter == "Inactive":
            query = query.filter(User.active == False)

        users = query.order_by(User.created_at.desc()).all()

        st.markdown(f"**Total Users:** {len(users)}")
        st.markdown("---")

        # Display users
        for user in users:
            with st.expander(f"📧 {user.email} - {user.name} ({user.role}/{user.subscription_tier})"):
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**ID:** {user.id}")
                    st.write(f"**Email:** {user.email}")
                    st.write(f"**Name:** {user.name}")
                    st.write(f"**Role:** {user.role}")
                    st.write(f"**Tier:** {user.subscription_tier}")

                with col2:
                    st.write(f"**Active:** {'✅' if user.active else '❌'}")
                    st.write(f"**Email Verified:** {'✅' if user.email_verified else '❌'}")
                    st.write(f"**Created:** {user.created_at.strftime('%Y-%m-%d %H:%M')}")
                    st.write(f"**Last Login:** {user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never'}")
                    st.write(f"**Login Count:** {user.login_count}")

                st.write(f"**Usage Today:** {user.contracts_today} contracts, {user.llm_requests_today} LLM requests")

                if user.is_demo:
                    if user.demo_expires:
                        expires_str = user.demo_expires.strftime('%Y-%m-%d %H:%M')
                        is_expired = user.demo_expires < datetime.utcnow()
                        st.write(f"**Demo Expires:** {expires_str} {'🔴 EXPIRED' if is_expired else '🟢 Active'}")

                # Actions
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button(f"{'Deactivate' if user.active else 'Activate'}", key=f"toggle_{user.id}"):
                        user.active = not user.active
                        db.commit()
                        st.success(f"User {'deactivated' if not user.active else 'activated'}")
                        st.rerun()

                with col2:
                    if st.button("Reset Daily Limits", key=f"reset_{user.id}"):
                        user.contracts_today = 0
                        user.llm_requests_today = 0
                        user.last_reset_date = datetime.utcnow()
                        db.commit()
                        st.success("Daily limits reset")
                        st.rerun()

    finally:
        db.close()


def show_demo_tokens_page():
    """Show demo token generation and management"""
    st.title("🔗 Demo Tokens")

    db = SessionLocal()
    try:
        # Generate new token
        st.header("Generate New Demo Token")

        with st.form("generate_token"):
            col1, col2 = st.columns(2)

            with col1:
                max_contracts = st.number_input("Max Contracts", min_value=1, max_value=100, value=3)
                max_llm_requests = st.number_input("Max LLM Requests", min_value=1, max_value=500, value=10)

            with col2:
                expires_hours = st.number_input("Expires in Hours", min_value=1, max_value=720, value=24)
                campaign = st.text_input("Campaign Name (optional)")

            submit = st.form_submit_button("Generate Token", use_container_width=True)

            if submit:
                import secrets

                token_str = f"demo_{secrets.token_urlsafe(16)}"

                demo_token = DemoToken(
                    token=token_str,
                    max_contracts=max_contracts,
                    max_llm_requests=max_llm_requests,
                    expires_in_hours=expires_hours,
                    created_by=st.session_state.admin_user['id'],
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(hours=expires_hours),
                    source="admin_panel",
                    campaign=campaign if campaign else None
                )

                db.add(demo_token)
                db.commit()

                st.success("✅ Demo token generated!")
                st.code(f"http://localhost:3000/demo?token={token_str}", language="text")

        st.markdown("---")

        # List existing tokens
        st.header("Existing Demo Tokens")

        tokens = db.query(DemoToken).order_by(DemoToken.created_at.desc()).limit(50).all()

        for token in tokens:
            is_expired = token.expires_at < datetime.utcnow()
            status = "🔴 Used" if token.used else ("🟠 Expired" if is_expired else "🟢 Active")

            with st.expander(f"{status} - {token.token[:20]}... (Expires: {token.expires_at.strftime('%Y-%m-%d %H:%M')})"):
                st.write(f"**Token:** `{token.token}`")
                st.write(f"**Max Contracts:** {token.max_contracts}")
                st.write(f"**Max LLM Requests:** {token.max_llm_requests}")
                st.write(f"**Created:** {token.created_at.strftime('%Y-%m-%d %H:%M')}")
                st.write(f"**Expires:** {token.expires_at.strftime('%Y-%m-%d %H:%M')}")
                st.write(f"**Campaign:** {token.campaign or 'N/A'}")

                if token.used:
                    st.write(f"**Used At:** {token.used_at.strftime('%Y-%m-%d %H:%M')}")
                    if token.used_by_user_id:
                        user = db.query(User).filter(User.id == token.used_by_user_id).first()
                        if user:
                            st.write(f"**Used By:** {user.email}")

                st.code(f"http://localhost:3000/demo?token={token.token}", language="text")

    finally:
        db.close()


def show_analytics_page():
    """Show analytics and statistics"""
    st.title("📊 Analytics")

    db = SessionLocal()
    try:
        # User statistics
        st.header("User Statistics")

        col1, col2, col3, col4 = st.columns(4)

        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.active == True).count()
        demo_users = db.query(User).filter(User.is_demo == True).count()
        today_logins = db.query(User).filter(
            User.last_login >= datetime.utcnow().replace(hour=0, minute=0, second=0)
        ).count()

        col1.metric("Total Users", total_users)
        col2.metric("Active Users", active_users)
        col3.metric("Demo Users", demo_users)
        col4.metric("Today's Logins", today_logins)

        st.markdown("---")

        # Users by role
        st.header("Users by Role")
        roles = db.query(User.role, func.count(User.id)).group_by(User.role).all()

        for role, count in roles:
            st.write(f"**{role.upper()}:** {count} users")

        st.markdown("---")

        # Users by tier
        st.header("Users by Subscription Tier")
        tiers = db.query(User.subscription_tier, func.count(User.id)).group_by(User.subscription_tier).all()

        for tier, count in tiers:
            st.write(f"**{tier.upper()}:** {count} users")

        st.markdown("---")

        # Demo tokens
        st.header("Demo Token Statistics")

        total_tokens = db.query(DemoToken).count()
        used_tokens = db.query(DemoToken).filter(DemoToken.used == True).count()
        active_tokens = db.query(DemoToken).filter(
            and_(DemoToken.used == False, DemoToken.expires_at > datetime.utcnow())
        ).count()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Tokens", total_tokens)
        col2.metric("Used Tokens", used_tokens)
        col3.metric("Active Tokens", active_tokens)

    finally:
        db.close()


def show_settings_page():
    """Show system settings"""
    st.title("⚙️ System Settings")

    st.info("Settings page coming soon. Will include LLM model configuration, rate limits, and other system parameters.")

    # Read current .env
    st.header("Environment Variables")

    try:
        with open(".env", "r") as f:
            env_content = f.read()
            st.code(env_content, language="bash")
    except FileNotFoundError:
        st.warning(".env file not found")


def main():
    """Main app function"""
    init_session_state()

    # ✅ ТЕСТОВЫЙ РЕЖИМ: Аутентификация отключена
    # Всегда показываем главный интерфейс без логина

    # Sidebar
    st.sidebar.title("🔐 Admin Panel")
    st.sidebar.markdown(f"**User:** {st.session_state.admin_user['name']}")
    st.sidebar.markdown(f"**Email:** {st.session_state.admin_user['email']}")
    st.sidebar.markdown("---")

    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["👥 Users", "🔗 Demo Tokens", "📊 Analytics", "⚙️ Settings"]
    )

    if st.sidebar.button("🚪 Logout"):
        st.session_state.admin_user = None
        st.session_state.authenticated = False
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.info(
        "**Access Points:**\n\n"
        "🌐 Main App: http://localhost:3000\n\n"
        "🔧 API Docs: http://localhost:8000/api/docs\n\n"
        "🔐 Admin Panel: http://localhost:8501"
    )

    # Show selected page
    if page == "👥 Users":
        show_users_page()
    elif page == "🔗 Demo Tokens":
        show_demo_tokens_page()
    elif page == "📊 Analytics":
        show_analytics_page()
    elif page == "⚙️ Settings":
        show_settings_page()


if __name__ == "__main__":
    main()
