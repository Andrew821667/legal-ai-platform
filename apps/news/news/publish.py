from __future__ import annotations

import html
import json
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests

from news.active_queue import parse_post_datetime, rebalance_active_publish_queue
from news.control_plane import (
    intelligent_footer_enabled,
    publish_claim_limit,
    publish_idle_fallback_enabled,
)
from news.core_client import CoreClient
from news.llm_writer import LLMNewsWriter
from news.logging_config import setup_logging
from news.pipeline import normalize_rubric_to_pillar
from news.settings import settings
from news.strategy import build_schedule_window

setup_logging()
logger = logging.getLogger(__name__)
_REVIEW_AUTOFILL_MIN_LIMIT = 3
_REVIEW_AUTOFILL_SCAN_LIMIT = 10
_REVIEW_AUTOFILL_LOOKAHEAD_HOURS = 36
_REVIEW_AUTOFILL_MAX_STALENESS_HOURS = 24
_EDITORIAL_FALLBACK_STATUSES = ("ready", "review")
_WEAK_PRACTICAL_CONCLUSION_PATTERNS = (
    "практический смысл здесь не в самой новости",
    "не в самой новости, а в том",
    "какие процессы и роли можно пересобрать",
    "кейс показывает, как сократить ручную работу",
    "важно заранее подумать",
    "стоит обратить внимание",
    "рынок движется",
)
_PRACTICAL_ACTION_MARKERS = (
    "аудит",
    "договор",
    "данн",
    "закуп",
    "зафикс",
    "измер",
    "контрол",
    "логирован",
    "метрик",
    "назнач",
    "ответствен",
    "пилот",
    "провер",
    "процесс",
    "соглас",
    "sla",
    "стоимост",
)


class TelegramRequestError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, ambiguous_delivery: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.ambiguous_delivery = ambiguous_delivery


class PublishQualityError(RuntimeError):
    """Raised when a post is technically sendable but not fit for the public channel."""


def _post_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _post_exceeds_freshness_limit(row: dict[str, Any], *, now_utc: datetime) -> bool:
    created_at = _post_datetime(row.get("created_at"))
    if created_at is None:
        return False
    max_age = timedelta(days=max(1, settings.news_max_source_age_days))
    publish_at = _post_datetime(row.get("publish_at"))
    return created_at < now_utc - max_age or (publish_at is not None and publish_at > created_at + max_age)


def _expire_stale_publication_queue(client: CoreClient, *, scan_limit: int = 100) -> int:
    now_utc = datetime.now(UTC)
    expired = 0
    for status in ("review", "ready", "scheduled", "publishing"):
        response = client.list_posts(limit=max(scan_limit, 1), status=status, newest_first=False)
        response.raise_for_status()
        for row in list(response.json() or []):
            if not _post_exceeds_freshness_limit(row, now_utc=now_utc):
                continue
            post_id = str(row.get("id") or "").strip()
            if not post_id:
                continue
            client.patch_post(
                post_id,
                {
                    "status": "failed",
                    "last_error": f"expired_freshness_{max(1, settings.news_max_source_age_days)}d",
                },
            ).raise_for_status()
            expired += 1
    if expired:
        logger.info(
            "stale_publication_queue_expired",
            extra={"count": expired, "max_age_days": settings.news_max_source_age_days},
        )
    return expired


def _demote_stale_scheduled_posts(client: CoreClient, *, scan_limit: int = 100) -> int:
    scheduled_response = client.list_posts(limit=max(scan_limit, 1), status="scheduled", newest_first=False)
    scheduled_response.raise_for_status()
    scheduled_rows = list(scheduled_response.json() or [])
    if not scheduled_rows:
        return 0

    now_utc = datetime.now(UTC)
    stale_cutoff = now_utc - timedelta(minutes=max(settings.news_publish_max_overdue_minutes, 1))
    demoted = 0

    for row in scheduled_rows:
        publish_at = parse_post_datetime(row.get("publish_at"))
        if publish_at is None or publish_at >= stale_cutoff:
            continue
        post_id = str(row.get("id") or "").strip()
        if not post_id:
            continue
        client.patch_post(post_id, {"status": "ready"}).raise_for_status()
        demoted += 1

    if demoted:
        logger.info(
            "stale_scheduled_posts_demoted_to_ready",
            extra={
                "count": demoted,
                "max_overdue_minutes": settings.news_publish_max_overdue_minutes,
            },
        )
    return demoted


def _autofill_publish_at(row: dict[str, Any], *, queue_index: int, now_utc: datetime) -> str:
    publish_at = parse_post_datetime(row.get("publish_at"))
    if publish_at is not None and publish_at > now_utc:
        return publish_at.isoformat()
    fallback = now_utc + timedelta(hours=max(1, queue_index + 1))
    return fallback.isoformat()


def _promote_ready_posts_for_idle_queue(client: CoreClient, *, limit: int) -> int:
    ready_limit = max(limit, _REVIEW_AUTOFILL_MIN_LIMIT, _REVIEW_AUTOFILL_SCAN_LIMIT, 1)
    ready_response = client.list_posts(limit=ready_limit, status="ready", newest_first=False)
    ready_response.raise_for_status()
    ready_rows = list(ready_response.json() or [])
    if not ready_rows:
        return 0

    now_utc = datetime.now(UTC)
    lookahead = now_utc + timedelta(hours=_REVIEW_AUTOFILL_LOOKAHEAD_HOURS)
    stale_cutoff = now_utc - timedelta(hours=_REVIEW_AUTOFILL_MAX_STALENESS_HOURS)
    candidate_rows = []
    for row in ready_rows:
        publish_at = parse_post_datetime(row.get("publish_at"))
        if publish_at is None:
            continue
        if publish_at < stale_cutoff:
            continue
        if publish_at > lookahead:
            continue
        candidate_rows.append(row)

    if not candidate_rows:
        return 0

    promoted = 0
    for index, row in enumerate(candidate_rows):
        post_id = str(row.get("id") or "").strip()
        if not post_id:
            continue
        patch = client.patch_post(
            post_id,
            {
                "status": "scheduled",
                "publish_at": _autofill_publish_at(row, queue_index=index, now_utc=now_utc),
            },
        )
        patch.raise_for_status()
        promoted += 1

    if promoted:
        logger.info("ready_posts_promoted_to_scheduled", extra={"count": promoted})
    return promoted


def _promote_due_editorial_posts_for_idle_publisher(
    client: CoreClient,
    *,
    limit: int,
    now_utc: datetime | None = None,
    control_rows: list[dict[str, Any]] | None = None,
) -> int:
    now_utc = now_utc or datetime.now(UTC)
    promote_limit = max(limit, 1)
    scan_limit = max(promote_limit * 5, 10)
    local_tz = ZoneInfo(settings.tz_name)
    eligible_slot_keys = _eligible_editorial_fallback_slot_keys(now_utc, local_tz, control_rows=control_rows)
    if not eligible_slot_keys:
        return 0
    posted_slot_keys = _posted_slot_keys(client, local_tz)

    for source_status in _EDITORIAL_FALLBACK_STATUSES:
        response = client.list_posts(limit=scan_limit, status=source_status, newest_first=False)
        response.raise_for_status()
        rows = list(response.json() or [])
        due_rows: list[tuple[dict[str, Any], str]] = []
        for row in rows:
            publish_at = parse_post_datetime(row.get("publish_at"))
            slot_key = _publish_slot_key(publish_at, local_tz)
            if publish_at is None or publish_at > now_utc:
                continue
            if slot_key is None or slot_key not in eligible_slot_keys or slot_key in posted_slot_keys:
                continue
            post_id = str(row.get("id") or "").strip()
            if not post_id:
                continue
            try:
                normalized_text = _normalize_text_before_publish(
                    str(row.get("text") or ""),
                    row,
                    intelligent_footer=intelligent_footer_enabled(control_rows or []),
                    strict_quality=True,
                )
            except PublishQualityError as exc:
                quality_patch = _publish_quality_review_patch(row, exc)
                if quality_patch is not None:
                    client.patch_post(post_id, quality_patch).raise_for_status()
                logger.warning(
                    "due_editorial_fallback_quality_gate_review",
                    extra={"source_status": source_status, "post_id": post_id, "reason": str(exc)},
                )
                continue
            due_rows.append((row, normalized_text))
            posted_slot_keys.add(slot_key)
            if len(due_rows) >= promote_limit:
                break
        if not due_rows:
            continue

        promoted = 0
        for row, normalized_text in due_rows:
            post_id = str(row.get("id") or "").strip()
            if not post_id:
                continue
            original_text = str(row.get("text") or "").strip()
            patch_payload: dict[str, Any] = {
                "status": "scheduled",
                "last_error": None,
            }
            if normalized_text != original_text:
                patch_payload["text"] = normalized_text
            client.patch_post(
                post_id,
                patch_payload,
            ).raise_for_status()
            promoted += 1

        if promoted:
            logger.info(
                "due_editorial_fallback_promoted",
                extra={"source_status": source_status, "count": promoted},
            )
            return promoted

    return 0


def _publish_slot_key(value: datetime | None, local_tz: ZoneInfo) -> str | None:
    if value is None:
        return None
    return value.astimezone(local_tz).replace(second=0, microsecond=0).isoformat()


def _eligible_editorial_fallback_slot_keys(
    now_utc: datetime,
    local_tz: ZoneInfo,
    *,
    control_rows: list[dict[str, Any]] | None = None,
) -> set[str]:
    now_local = now_utc.astimezone(local_tz)
    grace = timedelta(minutes=max(settings.news_publish_editorial_fallback_grace_minutes, 1))
    result: set[str] = set()
    for slot in build_schedule_window(now_local, days=1, control_rows=control_rows, future_only=False):
        slot_utc = slot.publish_at_local.astimezone(UTC)
        if slot_utc <= now_utc <= slot_utc + grace:
            result.add(_publish_slot_key(slot_utc, local_tz) or "")
    result.discard("")
    return result


def _posted_slot_keys(client: CoreClient, local_tz: ZoneInfo, *, scan_limit: int = 100) -> set[str]:
    response = client.list_posts(limit=scan_limit, status="posted", newest_first=True)
    response.raise_for_status()
    rows = list(response.json() or [])
    result: set[str] = set()
    for row in rows:
        publish_at = parse_post_datetime(row.get("publish_at"))
        slot_key = _publish_slot_key(publish_at, local_tz)
        if slot_key:
            result.add(slot_key)
    return result


def _split_text_for_telegram(text: str, limit: int = 4000) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []
    if len(normalized) <= limit:
        return [normalized]

    parts: list[str] = []
    rest = normalized
    while rest:
        if len(rest) <= limit:
            parts.append(rest)
            break
        cut = rest.rfind("\n", 0, limit)
        if cut < int(limit * 0.5):
            cut = rest.rfind(" ", 0, limit)
        if cut < int(limit * 0.5):
            cut = limit
        parts.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    return [part for part in parts if part]


def _telegram_request(method: str, payload: dict[str, Any], retries: int = 3) -> dict[str, Any]:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    last_error: Exception | None = None
    last_error_retryable = False
    last_error_ambiguous_delivery = False

    for attempt in range(1, retries + 1):
        try:
            proxy_url = str(getattr(settings, "telegram_api_proxy_url", "") or "").strip()
            proxies = {"https": proxy_url} if proxy_url else None
            response = requests.post(url, data=payload, timeout=20, proxies=proxies)
            if response.status_code == 429:
                retry_after = 3
                try:
                    body = response.json()
                    retry_after = int(body.get("parameters", {}).get("retry_after", retry_after))
                except Exception:
                    pass
                logger.warning("telegram_rate_limited", extra={"method": method, "retry_after": retry_after})
                time.sleep(retry_after)
                continue

            if response.status_code >= 500:
                raise TelegramRequestError(
                    f"Telegram HTTP {response.status_code}",
                    retryable=True,
                )
            response.raise_for_status()
            body = response.json()
            if not body.get("ok", False):
                description = body.get("description") or "unknown telegram error"
                raise TelegramRequestError(f"Telegram API error: {description}", retryable=False)
            return body
        except TelegramRequestError as exc:
            last_error = exc
            last_error_retryable = exc.retryable
            last_error_ambiguous_delivery = exc.ambiguous_delivery
            if attempt < retries and exc.retryable:
                time.sleep(attempt)
                continue
            break
        except requests.exceptions.ReadTimeout as exc:
            last_error = exc
            last_error_retryable = False
            last_error_ambiguous_delivery = True
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_error = exc
            last_error_retryable = True
            if attempt < retries:
                time.sleep(attempt)
                continue
            break
        except Exception as exc:
            last_error = exc
            last_error_retryable = False
            if attempt < retries:
                time.sleep(attempt)
                continue
            break

    raise TelegramRequestError(
        f"Telegram request failed: {last_error}",
        retryable=last_error_retryable,
        ambiguous_delivery=last_error_ambiguous_delivery,
    )


def _ambiguous_delivery_review_patch(post: dict[str, Any], exc: Exception) -> dict[str, Any] | None:
    if not isinstance(exc, TelegramRequestError) or not exc.ambiguous_delivery:
        return None
    attempts = int(post.get("attempts") or 0)
    return {
        "status": "review",
        "attempts": attempts + 1,
        "last_error": f"ambiguous_telegram_delivery: {str(exc)[:450]}",
    }


def _publish_quality_review_patch(post: dict[str, Any], exc: Exception) -> dict[str, Any] | None:
    if not isinstance(exc, PublishQualityError):
        return None
    attempts = int(post.get("attempts") or 0)
    return {
        "status": "review",
        "attempts": attempts + 1,
        "last_error": f"publish_quality_gate: {str(exc)[:450]}",
    }


def _retryable_publish_patch(post: dict[str, Any], exc: Exception, *, now_utc: datetime) -> dict[str, Any] | None:
    attempts = int(post.get("attempts") or 0)
    max_attempts = max(int(post.get("max_attempts") or 0), 1)
    next_attempt = attempts + 1

    retryable = isinstance(exc, TelegramRequestError) and exc.retryable
    if not retryable:
        return None
    if next_attempt >= max_attempts:
        return None

    retry_at = now_utc + timedelta(minutes=max(settings.news_retry_failed_after_minutes, 1))
    return {
        "status": "scheduled",
        "publish_at": retry_at.isoformat(),
        "attempts": next_attempt,
        "last_error": str(exc)[:500],
    }


def _send_to_telegram(text: str, media_urls: list[str] | None) -> int:
    chat_id = settings.telegram_channel_id or settings.telegram_channel_username
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHANNEL_ID or TELEGRAM_CHANNEL_USERNAME is required")

    normalized_text = (text or "").strip()
    if not normalized_text:
        raise RuntimeError("Post text is empty")

    if media_urls:
        caption = normalized_text[:1020]
        remainder = normalized_text[1020:].strip()

        def _payload_for_media(media: str) -> tuple[str, str, str]:
            if media.startswith("tgphoto://"):
                return "photo", media.replace("tgphoto://", "", 1), "sendPhoto"
            if media.startswith("tgvideo://"):
                return "video", media.replace("tgvideo://", "", 1), "sendVideo"
            if media.startswith("tgdocument://"):
                return "document", media.replace("tgdocument://", "", 1), "sendDocument"
            return "photo", media.replace("tg://", "", 1) if media.startswith("tg://") else media, "sendPhoto"

        resolved = [_payload_for_media(item) for item in media_urls if item]
        album_eligible = len(resolved) > 1 and all(kind in {"photo", "video"} for kind, _, _ in resolved)

        if album_eligible:
            media_payload: list[dict[str, Any]] = []
            for index, (kind, payload_value, _) in enumerate(resolved[:10]):
                item: dict[str, Any] = {"type": kind, "media": payload_value}
                if index == 0 and caption:
                    item["caption"] = caption
                    item["parse_mode"] = "HTML"
                media_payload.append(item)
            response = _telegram_request(
                "sendMediaGroup",
                {
                    "chat_id": chat_id,
                    "media": json.dumps(media_payload, ensure_ascii=False),
                },
            )
            result = response.get("result") or []
            first_message = result[0] if isinstance(result, list) and result else {}
            message_id = int(first_message.get("message_id") or 0)
        else:
            message_id = 0
            for index, (kind, payload_value, method) in enumerate(resolved):
                payload: dict[str, Any] = {
                    "chat_id": chat_id,
                    kind: payload_value,
                }
                if index == 0 and caption:
                    payload["caption"] = caption
                    payload["parse_mode"] = "HTML"
                response = _telegram_request(method, payload)
                if message_id == 0:
                    message_id = int(response.get("result", {}).get("message_id") or 0)

        if remainder:
            for part in _split_text_for_telegram(remainder):
                _telegram_request(
                    "sendMessage",
                    {
                        "chat_id": chat_id,
                        "text": part,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
        return message_id

    primary_message_id = 0
    for part in _split_text_for_telegram(normalized_text):
        response = _telegram_request(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": part,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
        if primary_message_id == 0:
            primary_message_id = int(response.get("result", {}).get("message_id") or 0)
    return primary_message_id


def _normalize_format_type(value: object) -> str:
    raw = str(value or "").strip().lower()
    for prefix in ("operator_ai_", "manual_"):
        if raw.startswith(prefix):
            return raw.removeprefix(prefix)
    return raw or "daily"


def _insert_footer_before_source(text: str, footer_html: str) -> str:
    footer = f"<b>Следующий шаг</b>\n{footer_html}"
    source_index = text.find("<b>Источник</b>")
    if source_index != -1:
        return f"{text[:source_index].rstrip()}\n\n{footer}\n\n{text[source_index:].lstrip()}"
    return f"{text.rstrip()}\n\n{footer}"


def _ensure_intelligent_footer_before_publish(text: str, post: dict[str, Any], *, enabled: bool = True) -> str:
    normalized = LLMNewsWriter.normalize_post_footer_blocks(text)
    if not enabled or "<b>Следующий шаг</b>" in normalized:
        return normalized

    format_type = _normalize_format_type(post.get("format_type"))
    if format_type == "weekly_review":
        return normalized

    title = str(post.get("title") or "")
    rubric = str(post.get("rubric") or "")
    pillar = normalize_rubric_to_pillar(rubric, f"{title}\n{normalized}")
    cta_type = str(post.get("cta_type") or "soft").strip().lower() or "soft"
    footer_text = LLMNewsWriter._auto_footer_text(format_type, cta_type, pillar)
    footer_html = LLMNewsWriter._finalize_footer_html(footer_text)
    if not footer_html:
        return normalized
    return LLMNewsWriter.normalize_post_footer_blocks(_insert_footer_before_source(normalized, footer_html))


def _plain_text(value: str) -> str:
    return " ".join(
        html.unescape(value)
        .replace("<br>", "\n")
        .replace("<br/>", "\n")
        .replace("<br />", "\n")
        .split()
    )


def _extract_html_block(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"<b>\s*{re.escape(heading)}\s*</b>\s*(.*?)(?=\n\n<b>|\n<b>|<b>Источник</b>|\n\n#|$)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text or "")
    return match.group(1).strip() if match else ""


def _practical_conclusion_failure_reason(text: str, post: dict[str, Any] | None) -> str | None:
    normalized = text or ""
    format_type = _normalize_format_type((post or {}).get("format_type"))
    conclusion = _extract_html_block(normalized, "Практический вывод") or _extract_html_block(normalized, "Вывод")
    if not conclusion:
        return None

    plain = re.sub(r"<[^>]+>", " ", conclusion)
    plain = _plain_text(plain).lower()
    if any(pattern in plain for pattern in _WEAK_PRACTICAL_CONCLUSION_PATTERNS):
        return "weak_generic_conclusion"
    if format_type in {"daily", "weekly_review"}:
        return None
    marker_count = sum(1 for marker in _PRACTICAL_ACTION_MARKERS if marker in plain)
    if len(plain) < 90 or marker_count < 2:
        return "conclusion_not_practical_enough"
    return None


def _ensure_practical_output_before_publish(text: str, post: dict[str, Any] | None) -> str:
    reason = _practical_conclusion_failure_reason(text, post)
    if reason is not None:
        raise PublishQualityError(reason)
    return text


def _ensure_writer_quality_before_publish(text: str, post: dict[str, Any] | None) -> str:
    if post is None:
        return text
    format_type = _normalize_format_type(post.get("format_type"))
    reason = LLMNewsWriter._quality_gate_failure_reason(text, format_type)
    if reason is not None:
        raise PublishQualityError(f"writer_quality_gate:{reason}")
    return text


def _normalize_text_before_publish(
    text: str,
    post: dict[str, Any] | None = None,
    *,
    intelligent_footer: bool = True,
    strict_quality: bool = False,
) -> str:
    if post is None:
        return LLMNewsWriter.normalize_post_footer_blocks(text)
    normalized = _ensure_intelligent_footer_before_publish(text, post, enabled=intelligent_footer)
    normalized = _ensure_practical_output_before_publish(normalized, post)
    if strict_quality:
        normalized = _ensure_writer_quality_before_publish(normalized, post)
    return normalized



def main(*, allow_idle_fallback: bool = True) -> int:
    if not settings.api_key_news:
        logger.error("API_KEY_NEWS is required")
        return 1

    client = CoreClient(settings.core_api_url, settings.api_key_news)
    claim_limit = max(settings.news_publish_claim_limit, 1)
    control_rows: list[dict[str, Any]] = []
    publish_intelligent_footer = True
    allow_configured_idle_fallback = settings.news_publish_idle_fallback_enabled
    try:
        controls_response = client.list_automation_controls(scope="news")
        controls_response.raise_for_status()
        control_rows = list(controls_response.json())
        controls = {row.get("key"): bool(row.get("enabled", True)) for row in control_rows}
        claim_limit = publish_claim_limit(control_rows)
        publish_intelligent_footer = intelligent_footer_enabled(control_rows)
        allow_configured_idle_fallback = publish_idle_fallback_enabled(control_rows)
        if controls.get("news.publish.enabled") is False:
            logger.info("publish_disabled_by_control_plane")
            return 0
    except Exception as exc:
        logger.warning("publish_controls_fetch_failed", extra={"error": str(exc)})

    try:
        expired_queue = _expire_stale_publication_queue(client)
        if expired_queue:
            logger.info("stale_publication_queue_processed", extra={"count": expired_queue})
    except Exception as exc:
        logger.warning("stale_publication_queue_expire_failed", extra={"error": str(exc)})

    try:
        stale_demoted = _demote_stale_scheduled_posts(client)
        if stale_demoted:
            logger.info("stale_scheduled_posts_processed", extra={"count": stale_demoted})
    except Exception as exc:
        logger.warning("stale_scheduled_posts_demote_failed", extra={"error": str(exc)})

    claim_response = client.claim_posts(limit=claim_limit)
    if claim_response.status_code == 204:
        due_fallback_promoted = 0
        try:
            due_fallback_promoted = _promote_due_editorial_posts_for_idle_publisher(
                client,
                limit=claim_limit,
                control_rows=control_rows,
            )
        except Exception as exc:
            logger.warning("due_editorial_fallback_failed", extra={"error": str(exc)})

        if due_fallback_promoted:
            claim_response = client.claim_posts(limit=claim_limit)

    if claim_response.status_code == 204:
        try:
            rebalance = rebalance_active_publish_queue(client, control_rows=control_rows)
            if any(rebalance.values()):
                logger.info("active_publish_queue_rebalanced", extra=rebalance)
        except Exception as exc:
            logger.warning("active_publish_queue_rebalance_failed", extra={"error": str(exc)})

        fallback_promoted = 0
        if allow_idle_fallback and allow_configured_idle_fallback:
            logger.warning("unsafe_idle_publisher_fallback_ignored")
        elif not allow_configured_idle_fallback:
            logger.info("idle_publisher_fallback_disabled")
        else:
            logger.info("idle_publisher_fallback_skipped_during_startup_grace")

        if fallback_promoted:
            claim_response = client.claim_posts(limit=claim_limit)
        else:
            logger.info("no_due_posts")
            return 0

    if claim_response.status_code == 204:
        logger.info("no_due_posts_after_fallback")
        return 0
    claim_response.raise_for_status()

    posts = claim_response.json()
    consecutive_errors = 0

    for post in posts:
        post_id = post["id"]
        try:
            if _post_exceeds_freshness_limit(post, now_utc=datetime.now(UTC)):
                client.patch_post(
                    post_id,
                    {
                        "status": "failed",
                        "last_error": f"expired_freshness_{max(1, settings.news_max_source_age_days)}d",
                    },
                ).raise_for_status()
                logger.warning("claimed_stale_post_expired", extra={"post_id": post_id})
                continue

            original_text = str(post.get("text") or "")
            normalized_text = _normalize_text_before_publish(
                original_text,
                post,
                intelligent_footer=publish_intelligent_footer,
                strict_quality=True,
            )
            message_id = _send_to_telegram(normalized_text, post.get("media_urls"))
            patch_payload: dict[str, Any] = {
                "status": "posted",
                "last_error": None,
                "telegram_message_id": message_id or None,
                "posted_at": datetime.now(UTC).isoformat(),
            }
            if normalized_text != original_text.strip():
                patch_payload["text"] = normalized_text
            patch = client.patch_post(
                post_id,
                patch_payload,
            )
            patch.raise_for_status()
            consecutive_errors = 0
            logger.info("post_published", extra={"post_id": post_id})
        except Exception as exc:
            consecutive_errors += 1
            logger.exception("post_publish_failed", extra={"post_id": post_id, "error": str(exc)})
            ambiguous_patch = _ambiguous_delivery_review_patch(post, exc)
            if ambiguous_patch is not None:
                ambiguous = client.patch_post(post_id, ambiguous_patch)
                if ambiguous.status_code >= 400:
                    logger.error("post_ambiguous_delivery_patch_error", extra={"post_id": post_id, "status": ambiguous.status_code})
                else:
                    logger.warning(
                        "post_publish_ambiguous_delivery_review",
                        extra={
                            "post_id": post_id,
                            "attempts": ambiguous_patch["attempts"],
                        },
                    )
                    continue

            quality_patch = _publish_quality_review_patch(post, exc)
            if quality_patch is not None:
                quality = client.patch_post(post_id, quality_patch)
                if quality.status_code >= 400:
                    logger.error("post_quality_gate_patch_error", extra={"post_id": post_id, "status": quality.status_code})
                else:
                    logger.warning(
                        "post_publish_quality_gate_review",
                        extra={
                            "post_id": post_id,
                            "reason": quality_patch["last_error"],
                        },
                    )
                    continue

            retry_patch = _retryable_publish_patch(post, exc, now_utc=datetime.now(UTC))
            if retry_patch is not None:
                retry = client.patch_post(post_id, retry_patch)
                if retry.status_code >= 400:
                    logger.error("post_retry_patch_error", extra={"post_id": post_id, "status": retry.status_code})
                else:
                    logger.warning(
                        "post_publish_retry_scheduled",
                        extra={
                            "post_id": post_id,
                            "retry_at": retry_patch["publish_at"],
                            "attempts": retry_patch["attempts"],
                            "max_attempts": post.get("max_attempts"),
                        },
                    )
                    continue

            fail = client.patch_post(post_id, {"status": "failed", "last_error": str(exc)[:500]})
            if fail.status_code >= 400:
                logger.error("post_failed_patch_error", extra={"post_id": post_id, "status": fail.status_code})

            if consecutive_errors >= 3:
                logger.error("publisher_circuit_breaker_activated")
                break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
