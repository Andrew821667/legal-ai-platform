"""
Compatibility exports for the legacy handlers package.

The package used to eagerly import the whole runtime tree on `import handlers`.
That kept `test_bot.py` compatibility, but also recreated the old god-module
boundary and pulled most of the bot into memory at import time. Keep the public
surface, but resolve attributes lazily.
"""

from __future__ import annotations

from importlib import import_module

_ATTR_TO_MODULE = {
    # constants
    "MAIN_MENU": "handlers.constants",
    "ADMIN_MENU": "handlers.constants",
    "LEAD_MAGNET_MENU": "handlers.constants",
    "DOCUMENTS_MENU": "handlers.constants",
    "CONSULTATION_CTA_MENU": "handlers.constants",
    "ADMIN_PANEL_MENU": "handlers.constants",
    "ADMIN_LEADS_MENU": "handlers.constants",
    "ADMIN_USERS_MENU": "handlers.constants",
    "ADMIN_EXPORT_MENU": "handlers.constants",
    "ADMIN_SECURITY_MENU": "handlers.constants",
    "ADMIN_RUNTIME_MENU": "handlers.constants",
    "ADMIN_CLEANUP_MENU": "handlers.constants",
    # helpers
    "extract_email": "handlers.helpers",
    "send_message_gradually": "handlers.helpers",
    "send_lead_magnet_email": "handlers.helpers",
    "notify_admin_new_lead": "handlers.helpers",
    # user
    "ai_policy_command": "handlers.user",
    "consent_status_command": "handlers.user",
    "correct_data_command": "handlers.user",
    "delete_data_command": "handlers.user",
    "documents_command": "handlers.user",
    "export_data_command": "handlers.user",
    "start_command": "handlers.user",
    "help_command": "handlers.user",
    "marketing_consent_command": "handlers.user",
    "reset_command": "handlers.user",
    "menu_command": "handlers.user",
    "profile_command": "handlers.user",
    "privacy_command": "handlers.user",
    "revoke_consent_command": "handlers.user",
    "transborder_consent_command": "handlers.user",
    "user_agreement_command": "handlers.user",
    "handle_message": "handlers.user",
    "handle_menu_button": "handlers.user",
    "offer_lead_magnet": "handlers.user",
    "handle_handoff_request": "handlers.user",
    # admin
    "edit_pdn_command": "handlers.admin",
    "stats_command": "handlers.admin",
    "leads_command": "handlers.admin",
    "export_command": "handlers.admin",
    "pdn_user_command": "handlers.admin",
    "revoke_user_consent_command": "handlers.admin",
    "view_conversation_command": "handlers.admin",
    "security_stats_command": "handlers.admin",
    "blacklist_command": "handlers.admin",
    "unblacklist_command": "handlers.admin",
    "show_admin_panel": "handlers.admin",
    # callbacks
    "handle_consent_callback": "handlers.callbacks",
    "handle_documents_callback": "handlers.callbacks",
    "handle_business_menu_callback": "handlers.callbacks",
    "handle_profile_callback": "handlers.callbacks",
    "handle_lead_magnet_callback": "handlers.callbacks",
    "handle_admin_panel_callback": "handlers.callbacks",
    "handle_cleanup_callback": "handlers.callbacks",
    # business
    "handle_business_connection": "handlers.business",
    "handle_business_message": "handlers.business",
    # common
    "error_handler": "handlers.common",
}

__all__ = sorted(_ATTR_TO_MODULE)


def __getattr__(name: str):
    module_name = _ATTR_TO_MODULE.get(name)
    if not module_name:
        raise AttributeError(f"module 'handlers' has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
