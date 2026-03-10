"""
Модуль безопасности и защиты от атак.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, Dict, Optional

from config import Config
import database

logger = logging.getLogger(__name__)
config = Config()


@dataclass(frozen=True)
class SecurityDecision:
    """Результат проверки безопасности для конкретного апдейта."""

    allowed: bool
    action: str = "allow"
    reason_code: str = ""
    user_message: str | None = None
    alert_admin: bool = False
    details: dict[str, Any] | None = None


class SecurityManager:
    """Управление безопасностью и защита от атак."""

    _ALLOWED_NON_TEXT_TYPES = frozenset({"contact", "document", "photo"})
    _DIRECT_QUARANTINE_REASONS = frozenset(
        {
            "from_user_is_bot",
            "via_bot_message",
            "sender_business_bot",
            "private_sender_chat_mismatch",
            "invalid_sender_chat_ids",
            "callback_duplicate_burst",
        }
    )

    def __init__(self):
        self.message_timestamps = defaultdict(deque)
        self.action_timestamps = defaultdict(deque)
        self.token_usage = defaultdict(int)
        self.blacklist = set()
        self.cooldowns = {}
        self.quarantine = {}
        self.suspicious_users = defaultdict(int)
        self._last_suspicious_decision: dict[int, SecurityDecision] = {}
        self.stats_start_time = datetime.now()
        self.total_tokens_today = 0
        self._rate_limit_checks = 0

        self.RATE_LIMITS = {
            "messages_per_minute": 10,
            "messages_per_hour": 50,
            "messages_per_day": 200,
        }
        self.TOKEN_LIMITS = {
            "per_day": 50000,
            "per_week": 200000,
        }

        self.COOLDOWN_SECONDS = 1
        self.MAX_MESSAGE_LENGTH = 4000
        self.TOTAL_DAILY_BUDGET = 100000

        self.HUMAN_ONLY_ENABLED = config.SECURITY_HUMAN_ONLY_ENABLED
        self.CALLBACKS_PER_MINUTE = config.SECURITY_CALLBACKS_PER_MINUTE
        self.CALLBACK_DUPLICATE_WINDOW_SECONDS = config.SECURITY_CALLBACK_DUPLICATE_WINDOW_SECONDS
        self.CALLBACK_DUPLICATE_BURST = config.SECURITY_CALLBACK_DUPLICATE_BURST
        self.NON_TEXT_PER_HOUR = config.SECURITY_NON_TEXT_PER_HOUR
        self.QUARANTINE_MINUTES = config.SECURITY_QUARANTINE_MINUTES
        self.QUARANTINE_STRIKES = config.SECURITY_QUARANTINE_STRIKES
        self.BLACKLIST_STRIKES = config.SECURITY_BLACKLIST_STRIKES
        self.ALERT_BURST_THRESHOLD = config.SECURITY_ALERT_BURST_THRESHOLD

        logger.info("Security Manager initialized")

    @staticmethod
    def _today_key(now: datetime | None = None) -> str:
        moment = now or datetime.now()
        return moment.strftime("%Y-%m-%d")

    @staticmethod
    def _week_start_key(now: datetime | None = None) -> str:
        moment = now or datetime.now()
        week_start = moment - timedelta(days=moment.weekday())
        return week_start.strftime("%Y-%m-%d")

    @staticmethod
    def _hash_value(raw: str) -> str:
        return sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
        if not payload:
            return {}
        safe: dict[str, Any] = {}
        for key, value in payload.items():
            if value is None:
                continue
            if isinstance(value, (bool, int, float)):
                safe[key] = value
                continue
            if isinstance(value, str):
                safe[key] = value[:180]
                continue
            if isinstance(value, (list, tuple)):
                safe[key] = [str(item)[:80] for item in value[:10]]
                continue
            safe[key] = str(value)[:180]
        return safe

    def _quarantine_user_message(self, until_epoch: int | None) -> str:
        if until_epoch is None:
            return "Зафиксирована подозрительная активность. Попробуйте позже или свяжитесь с нашей командой."
        seconds_left = max(0, int(until_epoch - time.time()))
        minutes_left = max(1, (seconds_left + 59) // 60)
        return (
            "Зафиксирована подозрительная активность. "
            f"Попробуйте позже, ориентировочно через {minutes_left} мин., "
            "или свяжитесь с нашей командой."
        )

    def _record_incident(
        self,
        *,
        telegram_user_id: int | None = None,
        chat_id: int | None = None,
        update_id: int | None = None,
        update_type: str = "",
        action: str,
        reason_code: str,
        severity: str = "warning",
        payload: dict[str, Any] | None = None,
    ) -> None:
        safe_payload = self._sanitize_payload(payload)
        try:
            database.db.record_security_incident(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                update_id=update_id,
                update_type=update_type,
                action=action,
                reason_code=reason_code,
                severity=severity,
                payload=safe_payload,
            )
        except Exception as db_error:
            logger.warning("Failed to persist security incident %s for user %s: %s", reason_code, telegram_user_id, db_error)
        logger.warning(
            "Security incident action=%s reason=%s user=%s payload=%s",
            action,
            reason_code,
            telegram_user_id,
            safe_payload,
        )

    def _record_action_event(self, user_id: int, action_key: str, now_epoch: int) -> None:
        try:
            database.db.record_security_action_event(user_id, action_key, now_epoch)
        except Exception as db_error:
            logger.warning("Action-event DB fallback for user %s key %s: %s", user_id, action_key, db_error)
            self.action_timestamps[(int(user_id), str(action_key))].append(now_epoch)

    def _count_action_events_since(self, user_id: int, action_key: str, since_epoch: int) -> int:
        try:
            database.db.prune_security_action_events(
                older_than_epoch=since_epoch,
                telegram_user_id=user_id,
                action_key=action_key,
            )
            return database.db.count_security_action_events_since(user_id, action_key, since_epoch)
        except Exception as db_error:
            logger.warning("Action-event count DB fallback for user %s key %s: %s", user_id, action_key, db_error)
            queue = self.action_timestamps[(int(user_id), str(action_key))]
            while queue and queue[0] <= since_epoch:
                queue.popleft()
            return len(queue)

    def _set_quarantine(self, user_id: int, reason_code: str, strikes: int) -> int:
        until_epoch = int(time.time()) + self.QUARANTINE_MINUTES * 60
        try:
            database.db.upsert_security_quarantine(
                user_id,
                status="active",
                reason_code=reason_code,
                strikes=strikes,
                quarantined_until_epoch=until_epoch,
            )
        except Exception as db_error:
            logger.warning("Quarantine DB fallback for user %s: %s", user_id, db_error)
            self.quarantine[int(user_id)] = {
                "status": "active",
                "reason_code": reason_code,
                "strikes": strikes,
                "quarantined_until_epoch": until_epoch,
            }
        return until_epoch

    def clear_quarantine(self, user_id: int) -> None:
        try:
            database.db.clear_security_quarantine(user_id)
        except Exception as db_error:
            logger.warning("Failed to clear quarantine for user %s: %s", user_id, db_error)
        self.quarantine.pop(int(user_id), None)

    def is_quarantined(self, user_id: int) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
        entry: dict[str, Any] | None = None
        try:
            entry = database.db.get_security_quarantine_entry(user_id)
        except Exception as db_error:
            logger.warning("Quarantine DB fallback for user %s: %s", user_id, db_error)
            entry = self.quarantine.get(int(user_id))

        if not entry:
            return False, None, None

        until_epoch = entry.get("quarantined_until_epoch")
        if until_epoch is not None and int(until_epoch) <= int(time.time()):
            self.clear_quarantine(user_id)
            return False, None, None

        return True, self._quarantine_user_message(int(until_epoch) if until_epoch else None), entry

    def _check_existing_block(self, user_id: int) -> SecurityDecision | None:
        blacklisted, reason = self.is_blacklisted(user_id)
        if blacklisted:
            return SecurityDecision(
                allowed=False,
                action="blacklist",
                reason_code="blacklisted_access",
                user_message=reason,
            )

        quarantined, reason, entry = self.is_quarantined(user_id)
        if quarantined:
            return SecurityDecision(
                allowed=False,
                action="quarantine",
                reason_code=str((entry or {}).get("reason_code") or "quarantine_active"),
                user_message=reason,
                details=entry or None,
            )

        return None

    def _decision_from_strike(
        self,
        *,
        user_id: int,
        reason_code: str,
        payload: dict[str, Any] | None = None,
        chat_id: int | None = None,
        update_id: int | None = None,
        update_type: str = "",
        direct_quarantine: bool = False,
    ) -> SecurityDecision:
        count = 0
        try:
            count = database.db.increment_security_suspicious(user_id)
        except Exception as db_error:
            logger.warning("Suspicious counter DB fallback for user %s: %s", user_id, db_error)
            self.suspicious_users[int(user_id)] += 1
            count = self.suspicious_users[int(user_id)]

        if direct_quarantine or reason_code in self._DIRECT_QUARANTINE_REASONS:
            count = max(count, self.QUARANTINE_STRIKES)

        if count >= self.BLACKLIST_STRIKES:
            self.clear_quarantine(user_id)
            self.add_to_blacklist(user_id, reason_code)
            self._record_incident(
                telegram_user_id=user_id,
                chat_id=chat_id,
                update_id=update_id,
                update_type=update_type,
                action="blacklist",
                reason_code=reason_code,
                severity="critical",
                payload={**(payload or {}), "strikes": count},
            )
            return SecurityDecision(
                allowed=False,
                action="blacklist",
                reason_code=reason_code,
                user_message="Доступ заблокирован. Свяжитесь с нашей командой для разблокировки.",
                alert_admin=True,
                details={"strikes": count},
            )

        if count >= self.QUARANTINE_STRIKES:
            until_epoch = self._set_quarantine(user_id, reason_code, count)
            self._record_incident(
                telegram_user_id=user_id,
                chat_id=chat_id,
                update_id=update_id,
                update_type=update_type,
                action="quarantine",
                reason_code=reason_code,
                severity="warning",
                payload={**(payload or {}), "strikes": count, "quarantined_until_epoch": until_epoch},
            )
            return SecurityDecision(
                allowed=False,
                action="quarantine",
                reason_code=reason_code,
                user_message=self._quarantine_user_message(until_epoch),
                alert_admin=True,
                details={"strikes": count, "quarantined_until_epoch": until_epoch},
            )

        self._record_incident(
            telegram_user_id=user_id,
            chat_id=chat_id,
            update_id=update_id,
            update_type=update_type,
            action="blocked_soft",
            reason_code=reason_code,
            severity="warning",
            payload={**(payload or {}), "strikes": count},
        )
        return SecurityDecision(
            allowed=False,
            action="blocked_soft",
            reason_code=reason_code,
            user_message="Обнаружена подозрительная активность. Попробуйте позже.",
            details={"strikes": count},
        )

    def register_actor_violation(
        self,
        *,
        user_id: int | None,
        reason_code: str,
        payload: dict[str, Any] | None = None,
        chat_id: int | None = None,
        update_id: int | None = None,
        update_type: str = "",
    ) -> SecurityDecision:
        if user_id is None:
            self._record_incident(
                chat_id=chat_id,
                update_id=update_id,
                update_type=update_type,
                action="blocked_soft",
                reason_code=reason_code,
                severity="warning",
                payload=payload,
            )
            return SecurityDecision(
                allowed=False,
                action="blocked_soft",
                reason_code=reason_code,
                user_message="Некорректный тип входящего события.",
            )

        return self._decision_from_strike(
            user_id=user_id,
            reason_code=reason_code,
            payload=payload,
            chat_id=chat_id,
            update_id=update_id,
            update_type=update_type,
            direct_quarantine=reason_code in self._DIRECT_QUARANTINE_REASONS,
        )

    def evaluate_human_actor(
        self,
        *,
        user_id: int | None,
        chat_id: int | None,
        chat_type: str = "",
        is_bot: bool = False,
        via_bot: bool = False,
        sender_business_bot: bool = False,
        update_type: str = "",
        update_id: int | None = None,
    ) -> SecurityDecision:
        if user_id is None:
            return self.register_actor_violation(
                user_id=None,
                reason_code="missing_user_identity",
                payload={"chat_id": chat_id, "chat_type": chat_type},
                chat_id=chat_id,
                update_id=update_id,
                update_type=update_type,
            )

        existing = self._check_existing_block(user_id)
        if existing is not None:
            return existing

        if not self.HUMAN_ONLY_ENABLED:
            return SecurityDecision(allowed=True)

        if is_bot:
            return self.register_actor_violation(
                user_id=user_id,
                reason_code="from_user_is_bot",
                payload={"chat_id": chat_id, "chat_type": chat_type},
                chat_id=chat_id,
                update_id=update_id,
                update_type=update_type,
            )

        if via_bot:
            return self.register_actor_violation(
                user_id=user_id,
                reason_code="via_bot_message",
                payload={"chat_id": chat_id, "chat_type": chat_type},
                chat_id=chat_id,
                update_id=update_id,
                update_type=update_type,
            )

        if sender_business_bot:
            return self.register_actor_violation(
                user_id=user_id,
                reason_code="sender_business_bot",
                payload={"chat_id": chat_id, "chat_type": chat_type},
                chat_id=chat_id,
                update_id=update_id,
                update_type=update_type,
            )

        if chat_id is not None and str(chat_type).lower() == "private":
            try:
                if int(chat_id) != int(user_id):
                    return self.register_actor_violation(
                        user_id=user_id,
                        reason_code="private_sender_chat_mismatch",
                        payload={"chat_id": chat_id, "chat_type": chat_type},
                        chat_id=chat_id,
                        update_id=update_id,
                        update_type=update_type,
                    )
            except (TypeError, ValueError):
                return self.register_actor_violation(
                    user_id=user_id,
                    reason_code="invalid_sender_chat_ids",
                    payload={"chat_id": chat_id, "chat_type": chat_type},
                    chat_id=chat_id,
                    update_id=update_id,
                    update_type=update_type,
                )

        return SecurityDecision(allowed=True)

    def check_callback_gate(
        self,
        *,
        user_id: int | None,
        chat_id: int | None,
        callback_data: str,
        update_id: int | None = None,
    ) -> SecurityDecision:
        if user_id is None:
            return self.register_actor_violation(
                user_id=None,
                reason_code="callback_missing_user",
                payload={"callback_hash": self._hash_value(callback_data or "")},
                chat_id=chat_id,
                update_id=update_id,
                update_type="callback_query",
            )

        existing = self._check_existing_block(user_id)
        if existing is not None:
            return existing

        if not callback_data:
            self._record_incident(
                telegram_user_id=user_id,
                chat_id=chat_id,
                update_id=update_id,
                update_type="callback_query",
                action="blocked_soft",
                reason_code="empty_callback_data",
                severity="warning",
            )
            return SecurityDecision(
                allowed=False,
                action="blocked_soft",
                reason_code="empty_callback_data",
                user_message="Действие кнопки некорректно. Обновите меню и попробуйте снова.",
            )

        now_epoch = int(time.time())
        callback_count = self._count_action_events_since(user_id, "callback:any", now_epoch - 60)
        if callback_count >= self.CALLBACKS_PER_MINUTE:
            self._record_incident(
                telegram_user_id=user_id,
                chat_id=chat_id,
                update_id=update_id,
                update_type="callback_query",
                action="blocked_soft",
                reason_code="callback_rate_limited",
                severity="warning",
                payload={"callback_count": callback_count},
            )
            return SecurityDecision(
                allowed=False,
                action="blocked_soft",
                reason_code="callback_rate_limited",
                user_message="Слишком много быстрых нажатий. Подождите немного и повторите.",
            )

        callback_hash = self._hash_value(callback_data)
        duplicate_key = f"callback:data:{callback_hash}"
        duplicate_count = self._count_action_events_since(
            user_id,
            duplicate_key,
            now_epoch - self.CALLBACK_DUPLICATE_WINDOW_SECONDS,
        )
        if duplicate_count >= self.CALLBACK_DUPLICATE_BURST:
            return self.register_actor_violation(
                user_id=user_id,
                reason_code="callback_duplicate_burst",
                payload={
                    "callback_hash": callback_hash,
                    "duplicate_count": duplicate_count,
                },
                chat_id=chat_id,
                update_id=update_id,
                update_type="callback_query",
            )

        self._record_action_event(user_id, "callback:any", now_epoch)
        self._record_action_event(user_id, duplicate_key, now_epoch)
        return SecurityDecision(allowed=True)

    def check_non_text_gate(
        self,
        *,
        user_id: int | None,
        chat_id: int | None,
        message_kind: str,
        update_id: int | None = None,
    ) -> SecurityDecision:
        if user_id is None:
            return self.register_actor_violation(
                user_id=None,
                reason_code="non_text_missing_user",
                payload={"message_kind": message_kind},
                chat_id=chat_id,
                update_id=update_id,
                update_type="message",
            )

        existing = self._check_existing_block(user_id)
        if existing is not None:
            return existing

        now_epoch = int(time.time())
        total_count = self._count_action_events_since(user_id, "non_text:any", now_epoch - 3600)
        if total_count >= self.NON_TEXT_PER_HOUR:
            self._record_incident(
                telegram_user_id=user_id,
                chat_id=chat_id,
                update_id=update_id,
                update_type="message",
                action="blocked_soft",
                reason_code="non_text_rate_limited",
                severity="warning",
                payload={"message_kind": message_kind, "count": total_count},
            )
            return SecurityDecision(
                allowed=False,
                action="blocked_soft",
                reason_code="non_text_rate_limited",
                user_message="Слишком много вложений за короткий период. Попробуйте позже.",
            )

        kind_key = f"non_text:{message_kind}"
        kind_count = self._count_action_events_since(user_id, kind_key, now_epoch - 3600)
        self._record_action_event(user_id, "non_text:any", now_epoch)
        self._record_action_event(user_id, kind_key, now_epoch)

        if message_kind not in self._ALLOWED_NON_TEXT_TYPES:
            if kind_count >= 2:
                return self.register_actor_violation(
                    user_id=user_id,
                    reason_code=f"unsupported_non_text_{message_kind}",
                    payload={"message_kind": message_kind, "count": kind_count + 1},
                    chat_id=chat_id,
                    update_id=update_id,
                    update_type="message",
                )

            self._record_incident(
                telegram_user_id=user_id,
                chat_id=chat_id,
                update_id=update_id,
                update_type="message",
                action="blocked_soft",
                reason_code="unsupported_non_text",
                severity="warning",
                payload={"message_kind": message_kind},
            )
            return SecurityDecision(
                allowed=False,
                action="blocked_soft",
                reason_code="unsupported_non_text",
                user_message="Этот тип вложения сейчас не поддерживается. Отправьте текст, контакт или документ для демо.",
            )

        return SecurityDecision(allowed=True)

    def check_rate_limit(self, user_id: int) -> tuple[bool, Optional[str]]:
        """
        Проверка rate limiting.

        Returns:
            (allowed, reason) - True если разрешено, False + причина если заблокировано
        """
        now = int(time.time())
        day_ago = now - 86400

        try:
            self._rate_limit_checks += 1
            if self._rate_limit_checks % 200 == 0:
                database.db.prune_security_message_events(day_ago)
            else:
                database.db.prune_security_message_events(day_ago, telegram_user_id=user_id)

            minute_ago = now - 60
            hour_ago = now - 3600
            messages_last_minute = database.db.count_security_message_events_since(user_id, minute_ago)
            messages_last_hour = database.db.count_security_message_events_since(user_id, hour_ago)
            messages_last_day = database.db.count_security_message_events_since(user_id, day_ago)
        except Exception as db_error:
            logger.warning("Rate-limit DB fallback to memory for user %s: %s", user_id, db_error)
            user_messages = self.message_timestamps[user_id]
            while user_messages and user_messages[0] < day_ago:
                user_messages.popleft()
            minute_ago = now - 60
            hour_ago = now - 3600
            messages_last_minute = sum(1 for ts in user_messages if ts > minute_ago)
            messages_last_hour = sum(1 for ts in user_messages if ts > hour_ago)
            messages_last_day = len(user_messages)

        if messages_last_minute >= self.RATE_LIMITS["messages_per_minute"]:
            logger.warning("Rate limit exceeded for user %s: %s msgs/min", user_id, messages_last_minute)
            return (
                False,
                f"Слишком много сообщений! Пожалуйста, подождите минуту. "
                f"(Лимит: {self.RATE_LIMITS['messages_per_minute']} сообщений в минуту)",
            )

        if messages_last_hour >= self.RATE_LIMITS["messages_per_hour"]:
            logger.warning("Rate limit exceeded for user %s: %s msgs/hour", user_id, messages_last_hour)
            return (
                False,
                f"Превышен лимит сообщений в час. Пожалуйста, подождите. "
                f"(Лимит: {self.RATE_LIMITS['messages_per_hour']} сообщений в час)",
            )

        if messages_last_day >= self.RATE_LIMITS["messages_per_day"]:
            logger.warning("Rate limit exceeded for user %s: %s msgs/day", user_id, messages_last_day)
            return (
                False,
                f"Превышен дневной лимит сообщений. Попробуйте завтра. "
                f"(Лимит: {self.RATE_LIMITS['messages_per_day']} сообщений в день)",
            )

        try:
            database.db.record_security_message_event(user_id, now)
        except Exception as db_error:
            logger.warning("Failed to persist rate-limit event for user %s: %s", user_id, db_error)
            self.message_timestamps[user_id].append(now)
        return True, None

    def check_cooldown(self, user_id: int) -> tuple[bool, Optional[str]]:
        """
        Проверка cooldown между сообщениями.

        Returns:
            (allowed, reason)
        """
        now = time.time()

        last_message_time: float | None = None
        try:
            last_message_time = database.db.get_security_cooldown(user_id)
        except Exception as db_error:
            logger.warning("Cooldown DB fallback for user %s: %s", user_id, db_error)
            last_message_time = self.cooldowns.get(user_id)

        if last_message_time is not None:
            time_since_last = now - float(last_message_time)
            if time_since_last < self.COOLDOWN_SECONDS:
                wait_time = self.COOLDOWN_SECONDS - time_since_last
                return False, f"Подождите {wait_time:.1f} секунд перед следующим сообщением."

        try:
            database.db.set_security_cooldown(user_id, now)
        except Exception as db_error:
            logger.warning("Failed to persist cooldown for user %s: %s", user_id, db_error)
            self.cooldowns[user_id] = now
        return True, None

    def check_message_length(self, message: str) -> tuple[bool, Optional[str]]:
        """Проверка длины сообщения."""
        if len(message) > self.MAX_MESSAGE_LENGTH:
            return (
                False,
                f"Сообщение слишком длинное! Максимум {self.MAX_MESSAGE_LENGTH} символов. "
                f"(У вас: {len(message)})",
            )
        return True, None

    def check_token_limit(self, user_id: int, estimated_tokens: int = 1000) -> tuple[bool, Optional[str]]:
        """Проверка дневного/недельного лимита токенов для пользователя."""
        now = datetime.now()
        day_key = self._today_key(now)
        week_key = self._week_start_key(now)

        try:
            used_today = database.db.get_security_user_tokens(user_id, day_key)
            used_week = database.db.get_security_user_tokens_since(user_id, week_key)
        except Exception as db_error:
            logger.warning("Token-limit DB fallback for user %s: %s", user_id, db_error)
            used_today = self.token_usage[user_id]
            used_week = self.token_usage[user_id]

        if used_today + estimated_tokens > self.TOKEN_LIMITS["per_day"]:
            return (
                False,
                f"Превышен дневной лимит токенов. Попробуйте позже. "
                f"(Лимит: {self.TOKEN_LIMITS['per_day']})",
            )

        if used_week + estimated_tokens > self.TOKEN_LIMITS["per_week"]:
            return (
                False,
                f"Превышен недельный лимит токенов. Попробуйте на следующей неделе. "
                f"(Лимит: {self.TOKEN_LIMITS['per_week']})",
            )

        return True, None

    def check_total_budget(self, estimated_tokens: int = 1000) -> tuple[bool, Optional[str]]:
        """Проверка общего дневного бюджета."""
        day_key = self._today_key()
        try:
            used_today = database.db.get_security_total_tokens(day_key)
            self.total_tokens_today = used_today
        except Exception as db_error:
            logger.warning("Total budget DB fallback: %s", db_error)
            used_today = self.total_tokens_today

        if used_today + estimated_tokens > self.TOTAL_DAILY_BUDGET:
            logger.error("Daily budget exceeded! Used: %s, Budget: %s", used_today, self.TOTAL_DAILY_BUDGET)
            return (
                False,
                "Извините, дневной лимит запросов исчерпан. "
                "Попробуйте завтра или свяжитесь с нашей командой напрямую.",
            )

        return True, None

    def estimate_tokens(self, text: str) -> int:
        """
        Оценка количества токенов в тексте.

        Приблизительная оценка: 1 токен ≈ 4 символа для русского текста.
        """
        return len(text) // 4

    def add_tokens_used(self, tokens: int, user_id: int | None = None):
        """Добавить использованные токены к счетчикам (персистентно)."""
        if tokens <= 0:
            return

        day_key = self._today_key()
        target_user_id = int(user_id) if user_id is not None else 0

        try:
            database.db.add_security_tokens_used(target_user_id, day_key, int(tokens))
            self.total_tokens_today = database.db.get_security_total_tokens(day_key)
            if user_id is not None:
                self.token_usage[int(user_id)] += int(tokens)
        except Exception as db_error:
            logger.warning("Failed to persist token usage, fallback to memory: %s", db_error)
            self.total_tokens_today += int(tokens)
            if user_id is not None:
                self.token_usage[int(user_id)] += int(tokens)

        logger.debug("Tokens used today: %s/%s", self.total_tokens_today, self.TOTAL_DAILY_BUDGET)

    def is_blacklisted(self, user_id: int) -> tuple[bool, Optional[str]]:
        """Проверка черного списка."""
        try:
            entry = database.db.get_security_blacklist_entry(user_id)
            if entry:
                reason = (entry.get("reason") or "").strip()
                logger.warning("Blacklisted user attempted access: %s", user_id)
                suffix = f" Причина: {reason}." if reason else ""
                return True, f"Доступ заблокирован. Свяжитесь с нашей командой для разблокировки.{suffix}"
        except Exception as db_error:
            logger.warning("Blacklist DB fallback for user %s: %s", user_id, db_error)
            if user_id in self.blacklist:
                return True, "Доступ заблокирован. Свяжитесь с нашей командой для разблокировки."
        return False, None

    def add_to_blacklist(self, user_id: int, reason: str = "Suspicious activity"):
        """Добавить пользователя в черный список."""
        try:
            database.db.add_security_blacklist(user_id, reason)
        except Exception as db_error:
            logger.warning("Failed to persist blacklist for user %s: %s", user_id, db_error)
            self.blacklist.add(user_id)
        logger.warning("User %s added to blacklist. Reason: %s", user_id, reason)

    def remove_from_blacklist(self, user_id: int):
        """Убрать пользователя из черного списка."""
        removed = 0
        try:
            removed = database.db.remove_security_blacklist(user_id)
        except Exception as db_error:
            logger.warning("Failed to remove persisted blacklist for user %s: %s", user_id, db_error)

        if user_id in self.blacklist:
            self.blacklist.remove(user_id)
            removed = max(removed, 1)

        if removed:
            logger.info("User %s removed from blacklist", user_id)

    def list_blacklist(self, limit: int = 200) -> list[dict]:
        """Возвращает blacklist для админ-панели."""
        try:
            return database.db.list_security_blacklist(limit=limit)
        except Exception as db_error:
            logger.warning("Blacklist list fallback: %s", db_error)
            rows: list[dict] = []
            for item in sorted(int(uid) for uid in self.blacklist):
                rows.append({"telegram_user_id": item, "reason": "", "updated_at": None, "created_at": None})
            return rows[: max(1, int(limit))]

    def detect_suspicious_activity(self, user_id: int, message: str) -> bool:
        """
        Обнаружение подозрительной активности.

        Признаки:
        - Очень длинные сообщения
        - Повторяющиеся сообщения
        - Только цифры / бессмысленный паттерн
        """
        reasons: list[str] = []

        if len(message) > self.MAX_MESSAGE_LENGTH * 0.9:
            reasons.append("near_max_length")
        if len(set(message)) < 10 and len(message) > 50:
            reasons.append("low_symbol_diversity")
        if message.replace(" ", "").isdigit() and len(message) > 100:
            reasons.append("long_numeric_payload")

        if not reasons:
            self._last_suspicious_decision.pop(user_id, None)
            return False

        decision = self._decision_from_strike(
            user_id=user_id,
            reason_code=f"text_suspicious_{reasons[0]}",
            payload={"signals": reasons, "message_length": len(message)},
            update_type="message",
        )
        logger.warning("Suspicious activity detected from user %s. Decision: %s", user_id, decision.action)
        self._last_suspicious_decision[user_id] = decision
        return True

    def check_all_security(self, user_id: int, message: str) -> tuple[bool, Optional[str]]:
        """
        Комплексная проверка всех систем безопасности.

        Returns:
            (allowed, reason) - True если все проверки пройдены
        """
        is_blocked, reason = self.is_blacklisted(user_id)
        if is_blocked:
            return False, reason

        quarantined, reason, _entry = self.is_quarantined(user_id)
        if quarantined:
            return False, reason

        is_valid, reason = self.check_message_length(message)
        if not is_valid:
            self._record_incident(
                telegram_user_id=user_id,
                update_type="message",
                action="blocked_soft",
                reason_code="message_too_long",
                severity="warning",
                payload={"message_length": len(message)},
            )
            return False, reason

        if self.detect_suspicious_activity(user_id, message):
            decision = self._last_suspicious_decision.get(user_id)
            return False, (decision.user_message if decision else "Обнаружена подозрительная активность.")

        estimated_tokens = max(250, self.estimate_tokens(message) * 3)

        is_allowed, reason = self.check_rate_limit(user_id)
        if not is_allowed:
            self._record_incident(
                telegram_user_id=user_id,
                update_type="message",
                action="blocked_soft",
                reason_code="message_rate_limited",
                severity="warning",
            )
            return False, reason

        is_allowed, reason = self.check_cooldown(user_id)
        if not is_allowed:
            self._record_incident(
                telegram_user_id=user_id,
                update_type="message",
                action="blocked_soft",
                reason_code="message_cooldown",
                severity="info",
            )
            return False, reason

        is_allowed, reason = self.check_token_limit(user_id, estimated_tokens=estimated_tokens)
        if not is_allowed:
            self._record_incident(
                telegram_user_id=user_id,
                update_type="message",
                action="blocked_soft",
                reason_code="token_limit_exceeded",
                severity="warning",
                payload={"estimated_tokens": estimated_tokens},
            )
            return False, reason

        is_allowed, reason = self.check_total_budget(estimated_tokens=estimated_tokens)
        if not is_allowed:
            self._record_incident(
                update_type="message",
                action="blocked_soft",
                reason_code="global_budget_exceeded",
                severity="warning",
                payload={"estimated_tokens": estimated_tokens},
            )
            return False, reason

        return True, None

    def reset_stats_time(self):
        """Сброс времени начала сбора статистики."""
        self.stats_start_time = datetime.now()
        logger.info("Stats start time reset to %s", self.stats_start_time)

    def reset_runtime_state(self, clear_blacklist: bool = False):
        """Сброс in-memory + персистентных security-счетчиков."""
        self.message_timestamps.clear()
        self.action_timestamps.clear()
        self.token_usage.clear()
        self.cooldowns.clear()
        self.quarantine.clear()
        self.suspicious_users.clear()
        self._last_suspicious_decision.clear()
        if clear_blacklist:
            self.blacklist.clear()
        self.total_tokens_today = 0
        self.reset_stats_time()
        try:
            database.db.reset_security_counters(clear_blacklist=clear_blacklist)
        except Exception as db_error:
            logger.warning("Failed to reset persisted security counters: %s", db_error)

    def get_stats(self) -> Dict:
        """Получить статистику безопасности."""
        total_tokens_today = self.total_tokens_today
        blacklisted_users = len(self.blacklist)
        suspicious_users_count = len(self.suspicious_users)
        quarantine_users = len(self.quarantine)
        try:
            total_tokens_today = database.db.get_security_total_tokens(self._today_key())
            self.total_tokens_today = total_tokens_today
            blacklisted_users = database.db.count_security_blacklist()
            suspicious_users_count = database.db.count_security_suspicious_users()
            if hasattr(database.db, "count_security_quarantine"):
                quarantine_users = database.db.count_security_quarantine()
        except Exception as db_error:
            logger.debug("Security stats DB fallback: %s", db_error)
        return {
            "blacklisted_users": blacklisted_users,
            "quarantine_users": quarantine_users,
            "suspicious_users": suspicious_users_count,
            "total_tokens_today": total_tokens_today,
            "daily_budget": self.TOTAL_DAILY_BUDGET,
            "budget_remaining": self.TOTAL_DAILY_BUDGET - total_tokens_today,
            "budget_percentage": (total_tokens_today / self.TOTAL_DAILY_BUDGET * 100),
            "stats_start_time": self.stats_start_time,
        }


security_manager = SecurityManager()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== Testing Security Manager ===\n")

    print("Test 1: Rate limiting")
    test_user = 999999999

    for i in range(12):
        allowed, reason = security_manager.check_rate_limit(test_user)
        print(f"  Message {i+1}: {'✅ Allowed' if allowed else f'❌ Blocked - {reason}'}")

    print("\nTest 2: Cooldown")
    for i in range(3):
        allowed, reason = security_manager.check_cooldown(test_user)
        print(f"  Attempt {i+1}: {'✅ Allowed' if allowed else f'❌ Blocked - {reason}'}")
        time.sleep(1)

    print("\nTest 3: Suspicious activity detection")
    spam_messages = [
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "111111111111111111111111111111111111111111111111111111111111",
        "sssssssssssssssssssssssssssssssssssssssssssssssssssss",
    ]

    for msg in spam_messages:
        is_suspicious = security_manager.detect_suspicious_activity(test_user, msg)
        print(f"  Message '{msg[:20]}...': {'🚨 Suspicious' if is_suspicious else '✅ OK'}")

    print("\nTest 4: Statistics")
    stats = security_manager.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
