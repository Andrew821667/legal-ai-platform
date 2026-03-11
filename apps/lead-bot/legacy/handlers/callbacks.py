"""
Facade module for legacy callback handlers.

Bot/router imports stay stable while the actual flows live in narrower modules.
"""
from __future__ import annotations

from handlers.admin_callbacks import handle_admin_panel_callback
from handlers.business_menu_callbacks import handle_business_menu_callback
from handlers.callback_flows import (
    handle_consent_callback,
    handle_documents_callback,
    handle_lead_magnet_callback,
    handle_profile_callback,
)
from handlers.cleanup_callbacks import handle_cleanup_callback

__all__ = [
    "handle_admin_panel_callback",
    "handle_business_menu_callback",
    "handle_cleanup_callback",
    "handle_consent_callback",
    "handle_documents_callback",
    "handle_lead_magnet_callback",
    "handle_profile_callback",
]
