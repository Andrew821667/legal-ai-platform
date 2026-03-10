# -*- coding: utf-8 -*-
"""
Authentication and User Management System
"""
import streamlit as st
from enum import Enum
from typing import Optional, Dict, Any
from src.models import SessionLocal
from src.services.auth_service import AuthService


class UserRole(Enum):
    """Роли пользователей"""
    DEMO = "demo"
    FULL = "full"
    VIP = "vip"
    ADMIN = "admin"


class UserPermissions:
    """Права доступа для различных ролей"""

    ROLE_PERMISSIONS = {
        UserRole.DEMO: {
            "contracts_per_day": 3,
            "max_file_size_mb": 5,
            "can_export_pdf": False,
            "can_export_docx": True,
            "can_export_xml": False,
            "can_use_rag": False,
            "can_generate_contracts": True,
            "can_analyze_contracts": True,
            "can_use_onboarding": False,
            "can_use_disagreements": False,
            "can_use_changes_analyzer": False,
            "llm_requests_per_day": 10,
        },
        UserRole.FULL: {
            "contracts_per_day": 50,
            "max_file_size_mb": 20,
            "can_export_pdf": True,
            "can_export_docx": True,
            "can_export_xml": True,
            "can_use_rag": True,
            "can_generate_contracts": True,
            "can_analyze_contracts": True,
            "can_use_onboarding": True,
            "can_use_disagreements": True,
            "can_use_changes_analyzer": True,
            "llm_requests_per_day": 100,
        },
        UserRole.VIP: {
            "contracts_per_day": 1000,
            "max_file_size_mb": 100,
            "can_export_pdf": True,
            "can_export_docx": True,
            "can_export_xml": True,
            "can_use_rag": True,
            "can_generate_contracts": True,
            "can_analyze_contracts": True,
            "can_use_onboarding": True,
            "can_use_disagreements": True,
            "can_use_changes_analyzer": True,
            "llm_requests_per_day": 1000,
            "priority_support": True,
        },
        UserRole.ADMIN: {
            "contracts_per_day": float('inf'),
            "max_file_size_mb": float('inf'),
            "can_export_pdf": True,
            "can_export_docx": True,
            "can_export_xml": True,
            "can_use_rag": True,
            "can_generate_contracts": True,
            "can_analyze_contracts": True,
            "can_use_onboarding": True,
            "can_use_disagreements": True,
            "can_use_changes_analyzer": True,
            "llm_requests_per_day": float('inf'),
            "can_manage_users": True,
            "can_manage_templates": True,
            "can_view_logs": True,
            "priority_support": True,
        }
    }

    @classmethod
    def get_permissions(cls, role: UserRole) -> Dict[str, Any]:
        """Получить права для роли"""
        return cls.ROLE_PERMISSIONS.get(role, cls.ROLE_PERMISSIONS[UserRole.DEMO])

    @classmethod
    def check_permission(cls, role: UserRole, permission: str) -> bool:
        """Проверить наличие права"""
        perms = cls.get_permissions(role)
        return perms.get(permission, False)


def init_session_state():
    """Инициализация состояния сессии"""
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'role' not in st.session_state:
        st.session_state.role = UserRole.DEMO
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False


def login_user(email: str, password: str = None) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user with real password verification.
    """
    if not email or not password:
        return None

    db = SessionLocal()
    try:
        auth_service = AuthService(db)
        login_data, error = auth_service.login_user(email=email, password=password)
        if error or not login_data:
            return None

        user_data = login_data.get("user", {})
        role_map = {
            'admin': UserRole.ADMIN,
            'senior_lawyer': UserRole.VIP,
            'lawyer': UserRole.FULL,
            'junior_lawyer': UserRole.DEMO,
            'demo': UserRole.DEMO,
        }
        role = role_map.get(user_data.get("role"), UserRole.DEMO)

        st.session_state.user = {
            'id': user_data.get('id'),
            'email': user_data.get('email'),
            'name': user_data.get('name'),
            'role': user_data.get('role')
        }
        st.session_state.role = role
        st.session_state.authenticated = True
        return st.session_state.user
    finally:
        db.close()


def logout_user():
    """Выход пользователя"""
    st.session_state.user = None
    st.session_state.role = UserRole.DEMO
    st.session_state.authenticated = False


def get_current_user() -> Optional[Dict[str, Any]]:
    """Получить текущего пользователя"""
    return st.session_state.get('user')


def get_current_role() -> UserRole:
    """Получить текущую роль"""
    return st.session_state.get('role', UserRole.DEMO)


def require_auth(role: Optional[UserRole] = None):
    """
    Декоратор для проверки аутентификации
    Если role указана, проверяет минимальную требуемую роль
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not st.session_state.get('authenticated', False):
                st.warning("⚠️ Требуется авторизация")
                show_login_form()
                return None

            if role:
                current_role = get_current_role()
                role_hierarchy = [UserRole.DEMO, UserRole.FULL, UserRole.VIP, UserRole.ADMIN]

                if role_hierarchy.index(current_role) < role_hierarchy.index(role):
                    st.error(f"❌ Недостаточно прав. Требуется роль: {role.value}")
                    return None

            return func(*args, **kwargs)
        return wrapper
    return decorator


def show_login_form():
    """Показать форму входа"""
    st.markdown("### 🔐 Вход в систему")
    st.markdown("Введите email и пароль пользователя с правами доступа.")

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="user@example.com")
        password = st.text_input("Пароль", type="password", placeholder="••••••••")
        submit = st.form_submit_button("Войти", use_container_width=True)

        if submit:
            if email:
                user = login_user(email, password)
                if user:
                    st.success(f"✅ Добро пожаловать, {user['name']}!")
                    st.rerun()
                else:
                    st.error("❌ Неверный email или пароль")
            else:
                st.error("❌ Введите email")


def show_user_info():
    """Показать информацию о пользователе в сайдбаре"""
    if st.session_state.get('authenticated', False):
        user = get_current_user()
        role = get_current_role()
        perms = UserPermissions.get_permissions(role)

        st.sidebar.markdown("---")
        st.sidebar.markdown(f"### 👤 {user['name']}")

        # Показать роль с цветным индикатором
        role_colors = {
            UserRole.DEMO: "🔵",
            UserRole.FULL: "🟢",
            UserRole.VIP: "🟡",
            UserRole.ADMIN: "🔴"
        }
        role_indicator = role_colors.get(role, "⚪")
        st.sidebar.markdown(f"**Роль:** {role_indicator} {role.value.upper()}")

        # Показать лимиты
        with st.sidebar.expander("📊 Лимиты и возможности"):
            contracts_limit = perms['contracts_per_day']
            if contracts_limit == float('inf'):
                st.write("**Договоров/день:** ♾️ Безлимит")
            else:
                st.write(f"**Договоров/день:** {contracts_limit}")

            llm_limit = perms['llm_requests_per_day']
            if llm_limit == float('inf'):
                st.write("**LLM запросов/день:** ♾️ Безлимит")
            else:
                st.write(f"**LLM запросов/день:** {llm_limit}")

            file_size = perms['max_file_size_mb']
            if file_size == float('inf'):
                st.write("**Макс. размер файла:** ♾️ Безлимит")
            else:
                st.write(f"**Макс. размер файла:** {file_size} MB")

            st.write("---")
            st.write("**Доступные функции:**")
            if perms.get('can_export_pdf'):
                st.write("✅ Экспорт в PDF")
            if perms.get('can_export_xml'):
                st.write("✅ Экспорт в XML")
            if perms.get('can_use_rag'):
                st.write("✅ RAG поиск")
            if perms.get('priority_support'):
                st.write("⭐ Приоритетная поддержка")

        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("🔄 Сменить", use_container_width=True):
                logout_user()
                st.session_state.current_page = 'login'
                st.rerun()
        with col2:
            if st.button("🚪 Выйти", use_container_width=True):
                logout_user()
                st.rerun()
    else:
        st.sidebar.markdown("---")
        st.sidebar.warning("⚠️ Демо-режим\n\nОграниченный функционал")
        if st.sidebar.button("🔐 Войти", use_container_width=True):
            st.session_state.current_page = 'login'
            st.rerun()


def check_feature_access(feature: str) -> bool:
    """Проверить доступ к функции"""
    role = get_current_role()
    return UserPermissions.check_permission(role, feature)


def show_upgrade_message(feature: str):
    """Показать сообщение об улучшении тарифа"""
    st.warning(f"""
    ⚠️ **Функция "{feature}" недоступна в вашем тарифе**

    Обновите тариф для доступа к расширенным возможностям:
    - **FULL** - полный функционал
    - **VIP** - приоритетная поддержка и безлимитный доступ
    """)
