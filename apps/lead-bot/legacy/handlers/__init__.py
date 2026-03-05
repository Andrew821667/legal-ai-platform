"""
Handlers package - модульная структура обработчиков
"""
# Константы
from handlers.constants import (
    MAIN_MENU,
    ADMIN_MENU,
    LEAD_MAGNET_MENU,
    DOCUMENTS_MENU,
    CONSULTATION_CTA_MENU,
    ADMIN_PANEL_MENU,
    ADMIN_LEADS_MENU,
    ADMIN_USERS_MENU,
    ADMIN_EXPORT_MENU,
    ADMIN_SECURITY_MENU,
    ADMIN_RUNTIME_MENU,
    ADMIN_CLEANUP_MENU,
)

# Вспомогательные функции
from handlers.helpers import (
    extract_email,
    send_message_gradually,
    send_lead_magnet_email,
    notify_admin_new_lead
)

# Пользовательские обработчики
from handlers.user import (
    ai_policy_command,
    consent_status_command,
    correct_data_command,
    delete_data_command,
    documents_command,
    export_data_command,
    start_command,
    help_command,
    marketing_consent_command,
    reset_command,
    menu_command,
    profile_command,
    privacy_command,
    revoke_consent_command,
    transborder_consent_command,
    user_agreement_command,
    handle_message,
    handle_menu_button,
    offer_lead_magnet,
    handle_handoff_request
)

# Админские обработчики
from handlers.admin import (
    edit_pdn_command,
    stats_command,
    leads_command,
    export_command,
    pdn_user_command,
    revoke_user_consent_command,
    view_conversation_command,
    security_stats_command,
    blacklist_command,
    unblacklist_command,
    show_admin_panel
)

# Callback обработчики
from handlers.callbacks import (
    handle_consent_callback,
    handle_documents_callback,
    handle_business_menu_callback,
    handle_profile_callback,
    handle_lead_magnet_callback,
    handle_admin_panel_callback,
    handle_cleanup_callback
)

# Business обработчики
from handlers.business import (
    handle_business_connection,
    handle_business_message
)

# Общие обработчики
from handlers.common import (
    error_handler
)

__all__ = [
    # Константы
    'MAIN_MENU',
    'ADMIN_MENU',
    'LEAD_MAGNET_MENU',
    'DOCUMENTS_MENU',
    'CONSULTATION_CTA_MENU',
    'ADMIN_PANEL_MENU',
    'ADMIN_LEADS_MENU',
    'ADMIN_USERS_MENU',
    'ADMIN_EXPORT_MENU',
    'ADMIN_SECURITY_MENU',
    'ADMIN_RUNTIME_MENU',
    'ADMIN_CLEANUP_MENU',
    # Helpers
    'extract_email',
    'send_message_gradually',
    'send_lead_magnet_email',
    'notify_admin_new_lead',
    # User
    'start_command',
    'help_command',
    'privacy_command',
    'transborder_consent_command',
    'user_agreement_command',
    'ai_policy_command',
    'marketing_consent_command',
    'consent_status_command',
    'export_data_command',
    'correct_data_command',
    'revoke_consent_command',
    'delete_data_command',
    'reset_command',
    'menu_command',
    'profile_command',
    'documents_command',
    'handle_message',
    'handle_menu_button',
    'offer_lead_magnet',
    'handle_handoff_request',
    # Admin
    'stats_command',
    'leads_command',
    'export_command',
    'pdn_user_command',
    'edit_pdn_command',
    'revoke_user_consent_command',
    'view_conversation_command',
    'security_stats_command',
    'blacklist_command',
    'unblacklist_command',
    'show_admin_panel',
    # Callbacks
    'handle_consent_callback',
    'handle_documents_callback',
    'handle_business_menu_callback',
    'handle_profile_callback',
    'handle_lead_magnet_callback',
    'handle_admin_panel_callback',
    'handle_cleanup_callback',
    # Business
    'handle_business_connection',
    'handle_business_message',
    # Common
    'error_handler',
]
