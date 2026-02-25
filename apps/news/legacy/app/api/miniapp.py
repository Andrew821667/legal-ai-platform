"""
Mini App API Router
Endpoints for Telegram Mini App interface.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
import structlog
import json
import hmac
import hashlib
from urllib.parse import parse_qsl

from app.models.database import (
    get_db,
    PostDraft,
    Publication,
    RawArticle,
    SystemSettings,
    LeadProfile,
    Source,
)
from app.modules.settings_manager import get_setting, set_setting
from app.config import settings as app_settings

logger = structlog.get_logger()

router = APIRouter(prefix="/api/miniapp", tags=["miniapp"])

# ====================
# Auth Middleware
# ====================

async def verify_telegram_user(
    x_telegram_init_data: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Verify Telegram WebApp init data signature.

    According to Telegram WebApp documentation:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing Telegram auth data")

    # Check for development fallback data
    try:
        dev_data = json.loads(x_telegram_init_data)
        if (isinstance(dev_data, dict) and
            dev_data.get('user', {}).get('id') == 0 and
            dev_data.get('user', {}).get('username') == 'dev_user'):
            logger.info("development_fallback_auth_used")
            return dev_data['user']
    except (json.JSONDecodeError, KeyError):
        pass  # Not development data, continue with normal verification

    try:
        # Parse init_data
        parsed_data = dict(parse_qsl(x_telegram_init_data))
        received_hash = parsed_data.pop('hash', None)

        if not received_hash:
            raise HTTPException(status_code=401, detail="Missing signature hash")

        # Create data-check-string
        data_check_arr = sorted([f"{k}={v}" for k, v in parsed_data.items()])
        data_check_string = '\n'.join(data_check_arr)

        # Calculate secret key: HMAC_SHA256("WebAppData", bot_token)
        secret_key = hmac.new(
            b"WebAppData",
            app_settings.telegram_bot_token.encode(),
            hashlib.sha256
        ).digest()

        # Calculate hash: HMAC_SHA256(secret_key, data_check_string)
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        # Verify signature
        if not hmac.compare_digest(calculated_hash, received_hash):
            logger.warning("telegram_signature_verification_failed",
                          received_hash=received_hash[:10],
                          calculated_hash=calculated_hash[:10])
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse user data
        user_data_raw = parsed_data.get('user')
        if not user_data_raw:
            raise HTTPException(status_code=401, detail="Missing user data")

        user = json.loads(user_data_raw)

        logger.info("telegram_user_verified", user_id=user.get('id'), username=user.get('username'))
        return user

    except json.JSONDecodeError as e:
        logger.error("telegram_auth_json_error", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid auth data format")
    except Exception as e:
        logger.error("telegram_auth_error", error=str(e))
        raise HTTPException(status_code=401, detail="Authentication failed")


# ====================
# Dashboard
# ====================

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    user: Dict = Depends(verify_telegram_user)
):
    """Get dashboard statistics."""
    try:
        # Total drafts pending review
        total_drafts = await db.scalar(
            select(func.count(PostDraft.id)).where(
                PostDraft.status == 'pending_review'
            )
        )

        # Total published
        total_published = await db.scalar(
            select(func.count(Publication.id))
        )

        # Average quality score - ПОЛЕ ОТСУТСТВУЕТ В МОДЕЛИ!
        avg_quality = 0.0

        # Total views and reactions
        total_views = await db.scalar(
            select(func.sum(Publication.views)).where(
                Publication.views.isnot(None)
            )
        ) or 0

        total_reactions = 0  # JSONB field, cannot sum

        # Engagement rate
        if total_views > 0:
            engagement_rate = (total_reactions / total_views) * 100
        else:
            engagement_rate = 0

        # Articles published today
        today = datetime.utcnow().date()
        articles_today = await db.scalar(
            select(func.count(Publication.id)).where(
                func.date(Publication.published_at) == today
            )
        )

        # Top sources
        source_stats = await db.execute(
            select(
                RawArticle.source_name,
                func.count(RawArticle.id).label('count')
            ).group_by(RawArticle.source_name).order_by(desc('count')).limit(5)
        )

        top_sources = [
            {"source": source, "count": count}
            for source, count in source_stats
        ]

        return {
            "total_drafts": total_drafts or 0,
            "total_published": total_published or 0,
            "avg_quality_score": round(avg_quality, 2),
            "total_views": int(total_views),
            "total_reactions": int(total_reactions),
            "engagement_rate": round(engagement_rate, 2),
            "articles_today": articles_today or 0,
            "top_sources": top_sources
        }

    except Exception as e:
        logger.error("get_dashboard_stats_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get dashboard stats")


# ====================
# Settings
# ====================

@router.get("/settings")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user: Dict = Depends(verify_telegram_user)
):
    """Get all system settings."""
    try:
        # Get all sources - both from settings and database
        sources = {}

        # Add hardcoded sources from settings
        hardcoded_sources = [
            ("google_news_ru", "Google News RSS (RU)", True),
            ("google_news_en", "Google News RSS (EN)", True),
            ("google_news_rss_ru", "Google News RU", True),
            ("google_news_rss_en", "Google News EN", True),
            ("habr", "Habr - Новости", True),
            ("perplexity_ru", "Perplexity Search (RU)", True),
            ("perplexity_en", "Perplexity Search (EN)", True),
            ("telegram_channels", "Telegram Channels", False),
            ("interfax", "Interfax - Наука и технологии", True),
            ("lenta", "Lenta.ru - Технологии", True),
            ("rbc", "RBC - Технологии", True),
            ("tass", "TASS - Наука и технологии", True),
        ]

        for source_key, description, default_enabled in hardcoded_sources:
            sources[source_key] = await get_setting(f"sources.{source_key}.enabled", db, default_enabled)

        # Add dynamic sources from database
        result = await db.execute(
            select(Source).where(Source.enabled == True)
        )
        db_sources = result.scalars().all()

        for db_source in db_sources:
            # Use source name as key, but make it safe for settings
            source_key = db_source.name.lower().replace(' ', '_').replace('-', '_').replace('.', '_')
            sources[source_key] = True  # All DB sources are enabled by default

        llm_provider = await get_setting("llm.provider", db, "deepseek")

        llm_models = {
            "analysis": await get_setting("llm.analysis.model", db, "deepseek-chat"),
            "draft_generation": await get_setting("llm.draft_generation.model", db, "deepseek-chat"),
            "ranking": await get_setting("llm.ranking.model", db, "deepseek-chat"),
        }

        dalle = {
            "enabled": await get_setting("dalle.enabled", db, False),
            "model": await get_setting("dalle.model", db, "dall-e-3"),
            "quality": await get_setting("dalle.quality", db, "standard"),
            "size": await get_setting("dalle.size", db, "1024x1024"),
            "auto_generate": await get_setting("dalle.auto_generate", db, False),
            "ask_on_review": await get_setting("dalle.ask_on_review", db, True),
        }

        auto_publish = {
            "enabled": await get_setting("auto_publish.enabled", db, False),
            "mode": await get_setting("auto_publish.mode", db, "best_time"),
            "max_per_day": await get_setting("auto_publish.max_per_day", db, 3),
            "weekdays_only": await get_setting("auto_publish.weekdays_only", db, False),
            "skip_holidays": await get_setting("auto_publish.skip_holidays", db, False),
        }

        filtering = {
            "min_score": await get_setting("filtering.min_score", db, 0.6),
            "min_content_length": await get_setting("filtering.min_content_length", db, 300),
            "similarity_threshold": await get_setting("filtering.similarity_threshold", db, 0.85),
        }

        budget = {
            "fetcher": {
                "max_articles_per_source": await get_setting("fetcher.max_articles_per_source", db, 300),
            },
            "max_per_month": await get_setting("budget.max_per_month", db, 50),
            "warning_threshold": await get_setting("budget.warning_threshold", db, 40),
            "stop_on_exceed": await get_setting("budget.stop_on_exceed", db, False),
            "switch_to_cheap": await get_setting("budget.switch_to_cheap", db, True),
        }

        return {
            "sources": sources,
            "llm_provider": llm_provider,
            "llm_models": llm_models,
            "dalle": dalle,
            "auto_publish": auto_publish,
            "filtering": filtering,
            "budget": budget,
        }

    except Exception as e:
        logger.error("get_settings_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get settings")


@router.put("/settings")
async def update_settings(
    settings_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user: Dict = Depends(verify_telegram_user)
):
    """Update system settings."""
    try:
        updated = []

        # Update sources
        if "sources" in settings_data:
            for source_key, enabled in settings_data["sources"].items():
                setting_key = f"sources.{source_key}.enabled"
                await set_setting(setting_key, enabled, db)
                updated.append(setting_key)

        # Update other settings
        settings_mapping = {
            "llm_provider": "llm.provider",
            "llm_models.analysis": "llm.analysis.model",
            "llm_models.draft_generation": "llm.draft_generation.model",
            "llm_models.ranking": "llm.ranking.model",
            "dalle.enabled": "dalle.enabled",
            "dalle.model": "dalle.model",
            "dalle.quality": "dalle.quality",
            "dalle.size": "dalle.size",
            "dalle.auto_generate": "dalle.auto_generate",
            "dalle.ask_on_review": "dalle.ask_on_review",
            "auto_publish.enabled": "auto_publish.enabled",
            "auto_publish.mode": "auto_publish.mode",
            "auto_publish.max_per_day": "auto_publish.max_per_day",
            "auto_publish.weekdays_only": "auto_publish.weekdays_only",
            "auto_publish.skip_holidays": "auto_publish.skip_holidays",
            "filtering.min_score": "filtering.min_score",
            "filtering.min_content_length": "filtering.min_content_length",
            "filtering.similarity_threshold": "filtering.similarity_threshold",
            "budget.fetcher.max_articles_per_source": "fetcher.max_articles_per_source",
            "budget.max_per_month": "budget.max_per_month",
            "budget.warning_threshold": "budget.warning_threshold",
            "budget.stop_on_exceed": "budget.stop_on_exceed",
            "budget.switch_to_cheap": "budget.switch_to_cheap",
        }

        async def update_nested_settings(data, prefix=""):
            for key, value in data.items():
                if isinstance(value, dict):
                    await update_nested_settings(value, f"{prefix}{key}.")
                else:
                    setting_key = settings_mapping.get(f"{prefix}{key}")
                    if setting_key:
                        await set_setting(setting_key, value, db)
                        updated.append(setting_key)

        await update_nested_settings(settings_data)

        logger.info("settings_updated", updated_count=len(updated), user_id=user.get('id'))

        return {"message": f"Updated {len(updated)} settings", "updated": updated}

    except Exception as e:
        logger.error("update_settings_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update settings")
