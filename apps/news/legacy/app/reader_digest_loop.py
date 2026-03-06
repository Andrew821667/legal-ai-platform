"""
Reader digest worker.

Runs on a schedule, selects users with enabled digest preferences,
builds a compact personalized digest, and sends it via reader bot.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

import requests
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import reader_models as _reader_models  # noqa: F401
from app.models import reader_publications as _reader_publications  # noqa: F401
from app.models.database import AsyncSessionLocal, engine
from app.models.reader_models import LeadProfile, SavedArticle, UserFeedback, UserInteraction, UserProfile
from app.modules.llm_provider import get_llm_provider
from app.services.core_feedback import reader_post_deeplink
from app.services.reader_service import get_weekly_digest_candidates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

_WORKER_ID = "news-reader-digest"
_CONTROL_KEY = "news.reader_digest.enabled"
_DEFAULT_SLOT_TIME = "12:15"
_DEFAULT_SLOT_GRACE_MINUTES = 30
_DEFAULT_MAX_USERS_PER_CYCLE = 30
_BLOCKED_BY_WORKERS = ("news-generate", "news-telegram-ingest")
_DIGEST_INTERVALS = {
    "daily": timedelta(hours=20),
    "twice_week": timedelta(hours=84),
    "weekly": timedelta(hours=156),
}
_TICK_HEARTBEAT_SECONDS = 600


def _core_api_enabled() -> bool:
    return bool((settings.core_api_url or "").strip() and (settings.api_key_news or "").strip())


def _trim_text(value: str, limit: int) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip(" ,.;:") + "..."


def _normalize_slot_time(value: str) -> str:
    raw = (value or "").strip()
    try:
        datetime.strptime(raw, "%H:%M")
    except ValueError:
        return _DEFAULT_SLOT_TIME
    return raw


def _slot_is_due(slot: str, now_local: datetime, *, grace_minutes: int) -> bool:
    try:
        hour_str, minute_str = slot.split(":", 1)
        hour = int(hour_str)
        minute = int(minute_str)
    except (ValueError, AttributeError):
        return False
    slot_dt = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now_local < slot_dt:
        return False
    return now_local <= slot_dt + timedelta(minutes=max(5, grace_minutes))


def _digest_due(frequency: str, last_sent_at: datetime | None, now_utc: datetime) -> bool:
    interval = _DIGEST_INTERVALS.get((frequency or "").strip())
    if interval is None:
        return False
    if last_sent_at is None:
        return True
    return now_utc - last_sent_at >= interval


def _heartbeat_headers() -> dict[str, str]:
    return {
        "X-API-Key": settings.api_key_news,
        "Content-Type": "application/json",
    }


def _send_worker_heartbeat_sync(info: dict[str, object]) -> None:
    if not _core_api_enabled():
        return
    response = requests.post(
        f"{settings.core_api_url.rstrip('/')}/api/v1/workers/heartbeat",
        headers=_heartbeat_headers(),
        json={"worker_id": _WORKER_ID, "info": info},
        timeout=8,
    )
    response.raise_for_status()


async def _send_worker_heartbeat(info: dict[str, object]) -> None:
    if not _core_api_enabled():
        return
    try:
        await asyncio.to_thread(_send_worker_heartbeat_sync, info)
    except Exception as exc:
        logger.warning("worker_heartbeat_failed", extra={"worker_id": _WORKER_ID, "error": str(exc)})


def _blocking_workers_busy_sync(worker_ids: tuple[str, ...]) -> list[str]:
    if not _core_api_enabled():
        return []

    response = requests.get(
        f"{settings.core_api_url.rstrip('/')}/api/v1/workers/status",
        headers={"X-API-Key": settings.api_key_news},
        timeout=8,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("workers") or []

    blocked: list[str] = []
    for row in rows:
        worker_id = str(row.get("worker_id") or "")
        if worker_id not in worker_ids:
            continue
        if not bool(row.get("active")):
            continue
        info = row.get("info") or {}
        if bool(info.get("busy")):
            blocked.append(worker_id)
    return blocked


async def _blocking_workers_busy(worker_ids: tuple[str, ...]) -> list[str]:
    try:
        return await asyncio.to_thread(_blocking_workers_busy_sync, worker_ids)
    except Exception as exc:
        logger.warning("workers_status_unavailable", extra={"error": str(exc)})
        return []


def _load_control_sync() -> dict[str, object]:
    default: dict[str, object] = {
        "enabled": True,
        "slot_time": _DEFAULT_SLOT_TIME,
        "slot_grace_minutes": _DEFAULT_SLOT_GRACE_MINUTES,
        "max_users_per_cycle": _DEFAULT_MAX_USERS_PER_CYCLE,
        "run_once_token": "",
    }
    if not _core_api_enabled():
        return default

    response = requests.get(
        f"{settings.core_api_url.rstrip('/')}/api/v1/automation-controls",
        params={"scope": "news"},
        headers={"X-API-Key": settings.api_key_news},
        timeout=8,
    )
    response.raise_for_status()
    rows = response.json()
    row = next((item for item in rows if str(item.get("key") or "") == _CONTROL_KEY), None)
    if not row:
        return default

    config = row.get("config") or {}
    max_users = config.get("max_users_per_cycle")
    if not isinstance(max_users, int) or max_users <= 0:
        max_users = _DEFAULT_MAX_USERS_PER_CYCLE

    return {
        "enabled": bool(row.get("enabled", True)),
        "slot_time": _normalize_slot_time(str(config.get("slot_time") or _DEFAULT_SLOT_TIME)),
        "slot_grace_minutes": max(
            5,
            min(int(config.get("slot_grace_minutes") or _DEFAULT_SLOT_GRACE_MINUTES), 120),
        ),
        "max_users_per_cycle": max(1, min(int(max_users), 500)),
        "run_once_token": str(config.get("run_once_token") or "").strip(),
    }


async def _load_control() -> dict[str, object]:
    try:
        return await asyncio.to_thread(_load_control_sync)
    except Exception as exc:
        logger.warning("reader_digest_control_fetch_failed", extra={"error": str(exc)})
        return {
            "enabled": True,
            "slot_time": _DEFAULT_SLOT_TIME,
            "slot_grace_minutes": _DEFAULT_SLOT_GRACE_MINUTES,
            "max_users_per_cycle": _DEFAULT_MAX_USERS_PER_CYCLE,
            "run_once_token": "",
        }


def _llm_available() -> bool:
    provider = (settings.default_llm_provider or "deepseek").strip().lower()
    if provider == "deepseek":
        return bool((settings.deepseek_api_key or "").strip())
    if provider == "openai":
        return bool((settings.openai_api_key or "").strip())
    if provider == "perplexity":
        return bool((settings.perplexity_api_key or "").strip())
    return False


async def _build_digest_summary(
    *,
    topics: list[str],
    articles_blob: str,
    db: AsyncSession,
) -> str:
    if not _llm_available():
        return ""

    topic_hint = ", ".join(topics) if topics else "общая legal AI-повестка"
    prompt = (
        "Ты редактор персонального дайджеста для читателя канала про AI в юридической функции. "
        "На основе списка материалов собери короткий digest.\n"
        "Требования:\n"
        "1) 2-3 предложения: что было главным трендом.\n"
        "2) 3 пункта: что важно проверить в юридической работе.\n"
        "3) 1 предложение: какой следующий шаг стоит сделать команде.\n"
        "Пиши по-русски, деловым языком, без воды и без markdown-таблиц."
    )
    try:
        llm = get_llm_provider(settings.default_llm_provider)
        result = await llm.generate_completion(
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"Интересы пользователя: {topic_hint}\n\n"
                        f"Материалы:\n{articles_blob}"
                    ),
                },
            ],
            max_tokens=520,
            temperature=0.35,
            operation="reader_digest_worker",
            db=db,
        )
        cleaned = " ".join((result or "").split()).strip()
        if cleaned:
            return escape(_trim_text(cleaned, 1800))
    except Exception:
        logger.exception("reader_digest_llm_failed")
    return ""


async def _render_digest_text(
    *,
    profile: UserProfile,
    db: AsyncSession,
) -> tuple[str | None, int]:
    articles = await get_weekly_digest_candidates(profile.user_id, limit=6, days=7, db=db)
    if not articles:
        return None, 0

    article_blocks: list[str] = []
    fallback_lines: list[str] = []
    links: list[str] = []
    for idx, article in enumerate(articles[:6], 1):
        title = _trim_text(article.draft.title, 120)
        body = _trim_text(article.draft.content, 250)
        article_blocks.append(f"{idx}) {title}\n{body}")
        fallback_lines.append(
            f"{idx}. <b>{escape(_trim_text(title, 92))}</b>\n"
            f"{escape(_trim_text(body, 160))}"
        )
        link = reader_post_deeplink(article.id)
        if link:
            links.append(
                f"• <a href=\"{escape(link, quote=True)}\">{escape(_trim_text(title, 80))}</a>"
            )

    summary = await _build_digest_summary(
        topics=list(profile.topics or []),
        articles_blob="\n\n".join(article_blocks),
        db=db,
    )
    if not summary:
        summary = "Ключевые материалы под ваши темы за последние дни:"

    text_parts = [
        "📬 <b>Персональный digest по AI в юридической функции</b>",
        "",
        summary,
        "",
        "\n\n".join(fallback_lines[:4]),
    ]
    if links:
        text_parts.extend(
            [
                "",
                "<b>Открыть материалы в reader-боте</b>",
                "\n".join(links[:3]),
            ]
        )
    text_parts.extend(
        [
            "",
            "⚙️ Частоту рассылки можно изменить в /settings",
        ]
    )
    text = "\n".join(part for part in text_parts if part is not None).strip()
    return text, len(articles)


async def _collect_due_users(
    db: AsyncSession,
    *,
    now_utc: datetime,
    max_users: int,
) -> list[UserProfile]:
    result = await db.execute(
        select(UserProfile)
        .where(UserProfile.is_active.is_(True))
        .where(UserProfile.digest_frequency.in_(tuple(_DIGEST_INTERVALS.keys())))
        .order_by(UserProfile.last_active.desc().nullslast(), UserProfile.created_at.asc())
    )
    profiles = list(result.scalars().all())
    if not profiles:
        return []

    user_ids = [int(profile.user_id) for profile in profiles]
    sent_rows = await db.execute(
        select(UserInteraction.user_id, func.max(UserInteraction.created_at))
        .where(UserInteraction.user_id.in_(user_ids))
        .where(UserInteraction.action == "digest_auto_sent")
        .group_by(UserInteraction.user_id)
    )
    sent_map = {int(user_id): sent_at for user_id, sent_at in sent_rows.all()}

    due: list[UserProfile] = []
    for profile in profiles:
        if _digest_due(str(profile.digest_frequency or ""), sent_map.get(int(profile.user_id)), now_utc):
            due.append(profile)
        if len(due) >= max_users:
            break
    return due


async def _run_digest_cycle(bot: Bot, *, max_users: int) -> dict[str, int]:
    now_utc = datetime.utcnow()
    sent = 0
    due_count = 0
    skipped_no_articles = 0
    failed = 0
    disabled_users = 0

    async with AsyncSessionLocal() as db:
        due_profiles = await _collect_due_users(db, now_utc=now_utc, max_users=max_users)
        due_count = len(due_profiles)

        for profile in due_profiles:
            try:
                digest_text, article_count = await _render_digest_text(profile=profile, db=db)
                if not digest_text or article_count == 0:
                    skipped_no_articles += 1
                    continue

                await bot.send_message(
                    chat_id=int(profile.user_id),
                    text=digest_text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                db.add(
                    UserInteraction(
                        user_id=int(profile.user_id),
                        publication_id=None,
                        action="digest_auto_sent",
                        source="digest_worker",
                    )
                )
                await db.commit()
                sent += 1
            except TelegramForbiddenError:
                await db.rollback()
                profile.is_active = False
                db.add(profile)
                await db.commit()
                disabled_users += 1
                logger.info("reader_digest_user_disabled", extra={"user_id": int(profile.user_id)})
            except TelegramBadRequest as exc:
                await db.rollback()
                failed += 1
                logger.warning(
                    "reader_digest_send_bad_request",
                    extra={"user_id": int(profile.user_id), "error": str(exc)},
                )
            except Exception:
                await db.rollback()
                failed += 1
                logger.exception("reader_digest_send_failed", extra={"user_id": int(profile.user_id)})

    return {
        "due": due_count,
        "sent": sent,
        "skipped_no_articles": skipped_no_articles,
        "failed": failed,
        "disabled_users": disabled_users,
    }


async def _init_reader_tables() -> None:
    tables = [
        UserProfile.__table__,
        LeadProfile.__table__,
        UserFeedback.__table__,
        UserInteraction.__table__,
        SavedArticle.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: _reader_models.Base.metadata.create_all(sync_conn, tables=tables))


async def main() -> int:
    token = (settings.reader_bot_token or "").strip()
    if not token or ":" not in token:
        logger.error("READER_BOT_TOKEN is required and must look like a Telegram token")
        return 1

    await _init_reader_tables()
    bot = Bot(token=token)
    logger.info("reader_digest_worker_started")
    await _send_worker_heartbeat(
        {
            "action": "startup",
            "component": "reader_digest_loop",
            "tz": settings.tz,
            "busy": False,
        }
    )

    last_slot_key = ""
    last_blocked_slot_key = ""
    last_manual_run_token: str | None = None
    last_tick_heartbeat_at = 0.0
    timezone = ZoneInfo(settings.tz)

    try:
        while True:
            sleep_for = 30
            try:
                control = await _load_control()
                enabled = bool(control.get("enabled", True))
                slot_time = _normalize_slot_time(str(control.get("slot_time") or _DEFAULT_SLOT_TIME))
                slot_grace_minutes = max(5, min(int(control.get("slot_grace_minutes") or _DEFAULT_SLOT_GRACE_MINUTES), 120))
                max_users = int(control.get("max_users_per_cycle") or _DEFAULT_MAX_USERS_PER_CYCLE)
                manual_run_token = str(control.get("run_once_token") or "").strip()
                now_local = datetime.now(timezone)
                today_key = now_local.date().isoformat()

                if last_manual_run_token is None:
                    last_manual_run_token = manual_run_token

                if enabled and _slot_is_due(slot_time, now_local, grace_minutes=slot_grace_minutes):
                    slot_key = f"{today_key}:{slot_time}"
                    if slot_key != last_slot_key:
                        blockers = await _blocking_workers_busy(_BLOCKED_BY_WORKERS)
                        if blockers:
                            if last_blocked_slot_key != slot_key:
                                await _send_worker_heartbeat(
                                    {
                                        "action": "digest_slot_wait_busy",
                                        "slot": slot_time,
                                        "date": today_key,
                                        "max_users": max_users,
                                        "blockers": blockers,
                                        "grace_minutes": slot_grace_minutes,
                                        "busy": False,
                                    }
                                )
                                last_blocked_slot_key = slot_key
                            continue
                        await _send_worker_heartbeat(
                            {
                                "action": "digest_slot_start",
                                "slot": slot_time,
                                "date": today_key,
                                "max_users": max_users,
                                "busy": True,
                            }
                        )
                        stats = await _run_digest_cycle(bot, max_users=max_users)
                        await _send_worker_heartbeat(
                            {
                                "action": "digest_slot_done",
                                "slot": slot_time,
                                "date": today_key,
                                "max_users": max_users,
                                "busy": False,
                                **stats,
                            }
                        )
                        last_slot_key = slot_key
                        last_blocked_slot_key = ""

                if manual_run_token and manual_run_token != last_manual_run_token:
                    await _send_worker_heartbeat(
                        {
                            "action": "digest_manual_run_start",
                            "token": manual_run_token,
                            "enabled": enabled,
                            "max_users": max_users,
                            "busy": True,
                        }
                    )
                    stats = await _run_digest_cycle(bot, max_users=max_users)
                    await _send_worker_heartbeat(
                        {
                            "action": "digest_manual_run_done",
                            "token": manual_run_token,
                            "enabled": enabled,
                            "max_users": max_users,
                            "busy": False,
                            **stats,
                        }
                    )
                    last_manual_run_token = manual_run_token

                now_ts = time.time()
                heartbeat_info: dict[str, object] = {
                    "mode": "poll",
                    "enabled": enabled,
                    "slot_time": slot_time,
                    "slot_grace_minutes": slot_grace_minutes,
                    "max_users": max_users,
                    "manual_run_token": manual_run_token[-32:] if manual_run_token else "",
                    "busy": False,
                }
                if now_ts - last_tick_heartbeat_at >= _TICK_HEARTBEAT_SECONDS:
                    heartbeat_info["action"] = "tick"
                    last_tick_heartbeat_at = now_ts
                await _send_worker_heartbeat(heartbeat_info)
            except Exception as exc:
                logger.exception("reader_digest_worker_iteration_failed", extra={"error": str(exc)})
                await _send_worker_heartbeat(
                    {
                        "action": "iteration_error",
                        "error": str(exc)[:400],
                        "busy": False,
                    }
                )
                sleep_for = 60
            await asyncio.sleep(max(15, sleep_for))
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
