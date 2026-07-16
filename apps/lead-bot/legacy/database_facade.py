"""
Facade mixin that preserves the legacy Database API while delegating real work
to narrower database domain modules.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import database_chat_state
import database_consent
import database_conversations
import database_knowledge
import database_leads
import database_reporting
import database_security
import database_user_state
import database_users
from config import get_config

config = get_config()

_USERS_COLUMNS = frozenset({
    "telegram_id", "username", "first_name", "last_name",
    "consent_given", "consent_date", "consent_revoked", "consent_revoked_at",
    "transborder_consent", "transborder_consent_date",
    "marketing_consent", "marketing_consent_date",
    "conversation_stage", "cta_variant", "cta_shown", "cta_shown_at",
    "offer_profile_override",
    "created_at", "last_interaction",
})

_LEADS_COLUMNS = frozenset({
    "user_id", "name", "email", "phone", "company",
    "team_size", "contracts_per_month", "pain_point", "budget",
    "urgency", "industry", "service_category", "specific_need",
    "temperature", "status", "notes",
    "core_lead_id",
    "conversation_stage", "cta_variant", "cta_shown",
    "lead_magnet_type", "lead_magnet_delivered",
    "notification_sent", "last_message_at",
    "created_at", "updated_at",
})


def _validate_columns(columns, allowed: frozenset, context: str) -> None:
    bad = set(columns) - allowed
    if bad:
        raise ValueError(f"Disallowed column(s) in {context}: {bad}")


class DatabaseFacadeMixin:

    # === SECURITY ===

    def record_security_message_event(self, telegram_user_id: int, ts_epoch: int) -> None:
        """Сохраняет событие входящего сообщения для персистентного rate-limit."""
        database_security.record_security_message_event(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            ts_epoch=ts_epoch,
        )

    def prune_security_message_events(self, older_than_epoch: int, telegram_user_id: int | None = None) -> int:
        """Удаляет устаревшие события rate-limit, возвращает число удаленных строк."""
        return database_security.prune_security_message_events(
            self.get_connection,
            older_than_epoch=older_than_epoch,
            telegram_user_id=telegram_user_id,
        )

    def count_security_message_events_since(self, telegram_user_id: int, since_epoch: int) -> int:
        """Считает число событий сообщений пользователя после указанного unix-time."""
        return database_security.count_security_message_events_since(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            since_epoch=since_epoch,
        )

    def add_security_tokens_used(self, telegram_user_id: int, date_key: str, tokens: int) -> None:
        """Инкрементирует дневной расход токенов пользователя."""
        database_security.add_security_tokens_used(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            date_key=date_key,
            tokens=tokens,
        )

    def get_security_user_tokens(self, telegram_user_id: int, date_key: str) -> int:
        """Возвращает число токенов пользователя за конкретный день."""
        return database_security.get_security_user_tokens(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            date_key=date_key,
        )

    def get_security_user_tokens_since(self, telegram_user_id: int, start_date_key: str) -> int:
        """Возвращает суммарные токены пользователя с указанной даты (включительно)."""
        return database_security.get_security_user_tokens_since(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            start_date_key=start_date_key,
        )

    def get_security_total_tokens(self, date_key: str) -> int:
        """Возвращает общий расход токенов по всем пользователям за день."""
        return database_security.get_security_total_tokens(
            self.get_connection,
            date_key=date_key,
        )

    def add_security_blacklist(self, telegram_user_id: int, reason: str = "") -> None:
        """Добавляет/обновляет пользователя в персистентном blacklist."""
        database_security.add_security_blacklist(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            reason=reason,
        )

    def remove_security_blacklist(self, telegram_user_id: int) -> int:
        """Удаляет пользователя из blacklist. Возвращает число удаленных строк."""
        return database_security.remove_security_blacklist(
            self.get_connection,
            telegram_user_id=telegram_user_id,
        )

    def get_security_blacklist_entry(self, telegram_user_id: int) -> Optional[Dict]:
        """Возвращает запись blacklist по пользователю."""
        return database_security.get_security_blacklist_entry(
            self.get_connection,
            telegram_user_id=telegram_user_id,
        )

    def list_security_blacklist(self, limit: int = 200) -> List[Dict]:
        """Список blacklist в порядке свежих изменений."""
        return database_security.list_security_blacklist(
            self.get_connection,
            limit=limit,
        )

    def count_security_blacklist(self) -> int:
        """Количество пользователей в blacklist."""
        return database_security.count_security_blacklist(self.get_connection)

    def set_security_cooldown(self, telegram_user_id: int, last_message_ts: float) -> None:
        """Сохраняет отметку последнего сообщения пользователя для cooldown."""
        database_security.set_security_cooldown(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            last_message_ts=last_message_ts,
        )

    def get_security_cooldown(self, telegram_user_id: int) -> Optional[float]:
        """Возвращает ts последнего сообщения пользователя для cooldown."""
        return database_security.get_security_cooldown(
            self.get_connection,
            telegram_user_id=telegram_user_id,
        )

    def clear_security_cooldowns(self) -> int:
        """Очищает все cooldown-записи."""
        return database_security.clear_security_cooldowns(self.get_connection)

    def increment_security_suspicious(self, telegram_user_id: int) -> int:
        """Увеличивает счетчик suspicious strike и возвращает новое значение."""
        return database_security.increment_security_suspicious(
            self.get_connection,
            telegram_user_id=telegram_user_id,
        )

    def record_security_action_event(self, telegram_user_id: int, action_key: str, ts_epoch: int) -> None:
        """Сохраняет action-событие для callback/non-text антиабуза."""
        database_security.record_security_action_event(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            action_key=action_key,
            ts_epoch=ts_epoch,
        )

    def prune_security_action_events(
        self,
        older_than_epoch: int,
        telegram_user_id: int | None = None,
        action_key: str | None = None,
    ) -> int:
        """Удаляет устаревшие action-события."""
        return database_security.prune_security_action_events(
            self.get_connection,
            older_than_epoch=older_than_epoch,
            telegram_user_id=telegram_user_id,
            action_key=action_key,
        )

    def count_security_action_events_since(self, telegram_user_id: int, action_key: str, since_epoch: int) -> int:
        """Считает action-события пользователя по ключу за окно."""
        return database_security.count_security_action_events_since(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            action_key=action_key,
            since_epoch=since_epoch,
        )

    def record_security_incident(
        self,
        *,
        telegram_user_id: int | None = None,
        chat_id: int | None = None,
        update_id: int | None = None,
        update_type: str = "",
        action: str,
        reason_code: str,
        severity: str = "warning",
        payload: dict | None = None,
        ts_epoch: int | None = None,
    ) -> int:
        """Сохраняет security-инцидент для аудита."""
        return database_security.record_security_incident(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            update_id=update_id,
            update_type=update_type,
            action=action,
            reason_code=reason_code,
            severity=severity,
            payload=payload,
            ts_epoch=ts_epoch,
        )

    def list_security_incidents(self, limit: int = 100, telegram_user_id: int | None = None) -> List[Dict]:
        """Возвращает свежие security-инциденты."""
        return database_security.list_security_incidents(
            self.get_connection,
            limit=limit,
            telegram_user_id=telegram_user_id,
        )

    def upsert_security_quarantine(
        self,
        telegram_user_id: int,
        *,
        status: str,
        reason_code: str,
        strikes: int,
        quarantined_until_epoch: int | None,
    ) -> None:
        """Создает или обновляет карантин пользователя."""
        database_security.upsert_security_quarantine(
            self.get_connection,
            telegram_user_id=telegram_user_id,
            status=status,
            reason_code=reason_code,
            strikes=strikes,
            quarantined_until_epoch=quarantined_until_epoch,
        )

    def get_security_quarantine_entry(self, telegram_user_id: int) -> Optional[Dict]:
        """Возвращает запись карантина пользователя."""
        return database_security.get_security_quarantine_entry(
            self.get_connection,
            telegram_user_id=telegram_user_id,
        )

    def clear_security_quarantine(self, telegram_user_id: int) -> int:
        """Снимает карантин с пользователя."""
        return database_security.clear_security_quarantine(
            self.get_connection,
            telegram_user_id=telegram_user_id,
        )

    def count_security_quarantine(self) -> int:
        """Количество пользователей в активном карантине."""
        return database_security.count_security_quarantine(self.get_connection)

    def reset_security_suspicious(self) -> int:
        """Очищает счетчик suspicious пользователей."""
        return database_security.reset_security_suspicious(self.get_connection)

    def count_security_suspicious_users(self) -> int:
        """Количество пользователей с хотя бы одним suspicious strike."""
        return database_security.count_security_suspicious_users(self.get_connection)

    def reset_security_counters(self, clear_blacklist: bool = False) -> None:
        """Сбрасывает персистентные security-счетчики."""
        database_security.reset_security_counters(
            self.get_connection,
            clear_blacklist=clear_blacklist,
        )

    # === BUSINESS / CHAT STATES ===

    def is_chat_enabled(self, chat_id: int) -> bool:
        """Проверка, включен ли чат для автоответов."""
        return database_chat_state.is_chat_enabled(
            self.get_connection,
            chat_id=chat_id,
        )

    def set_chat_enabled(self, chat_id: int, enabled: bool):
        """Включение/отключение автоответов в конкретном чате."""
        database_chat_state.set_chat_enabled(
            self.get_connection,
            chat_id=chat_id,
            enabled=enabled,
        )

    def get_chat_mode(self, chat_id: int) -> str:
        """Режим чата: bot | personal."""
        return database_chat_state.get_chat_mode(
            self.get_connection,
            chat_id=chat_id,
        )

    def set_chat_mode(self, chat_id: int, mode: str) -> None:
        """Устанавливает режим чата."""
        database_chat_state.set_chat_mode(
            self.get_connection,
            chat_id=chat_id,
            mode=mode,
        )

    def get_disabled_chats(self) -> list:
        """Получение списка отключенных чатов."""
        return database_chat_state.get_disabled_chats(self.get_connection)

    def set_business_connection_state(self, connection_id: str, user_chat_id: Optional[int], is_enabled: bool):
        """Сохраняет состояние business connection (вкл/выкл)."""
        database_chat_state.set_business_connection_state(
            self.get_connection,
            connection_id=connection_id,
            user_chat_id=user_chat_id,
            is_enabled=is_enabled,
        )

    def is_business_connection_enabled(self, connection_id: Optional[str]) -> bool:
        """
        Проверяет включена ли business connection.
        Если состояние неизвестно, не блокируем (True по умолчанию).
        """
        return database_chat_state.is_business_connection_enabled(
            self.get_connection,
            connection_id=connection_id,
        )

    # === USERS ===

    def create_or_update_user(self, telegram_id: int, username: str = None,
                              first_name: str = None, last_name: str = None) -> int:
        """Создание или обновление пользователя"""
        return database_users.create_or_update_user(
            self.get_connection,
            self._sync_user_to_core,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

    def get_local_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Возвращает локальную запись пользователя без merge с core-api."""
        return database_users.get_local_user_by_telegram_id(
            self.get_connection,
            telegram_id=telegram_id,
        )

    def get_local_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Возвращает локальную запись пользователя без merge с core-api."""
        return database_users.get_local_user_by_id(
            self.get_connection,
            user_id=user_id,
        )

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Получение пользователя по telegram_id"""
        user = self.get_local_user_by_telegram_id(telegram_id)
        if user:
            return self._merge_user_row_with_core(user)
        return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Получение пользователя по user_id"""
        user = self.get_local_user_by_id(user_id)
        if user:
            return self._merge_user_row_with_core(user)
        return None

    def get_user_offer_profile(self, user_id: int) -> Optional[str]:
        """Возвращает ручной override профиля предложений пользователя."""
        return database_users.get_user_offer_profile(
            self.get_local_user_by_id,
            user_id=user_id,
        )

    def set_user_offer_profile(self, user_id: int, profile_key: Optional[str]) -> None:
        """Сохраняет ручной override профиля предложений (или сбрасывает в авто-режим)."""
        database_users.set_user_offer_profile(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
            profile_key=profile_key,
        )

    def get_recent_users(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """Получение последних активных пользователей."""
        return database_users.get_recent_users(
            self.get_connection,
            limit=limit,
            offset=offset,
        )

    def count_users(self) -> int:
        """Возвращает общее число пользователей в локальной БД."""
        return database_users.count_users(self.get_connection)

    def get_users_without_consent(self, limit: int = 20) -> List[Dict]:
        """Пользователи без активного согласия на обработку ПД."""
        return database_users.get_users_without_consent(
            self.get_connection,
            limit=limit,
        )

    def get_users_with_revoked_consent(self, limit: int = 20) -> List[Dict]:
        """Пользователи, которые отозвали согласие."""
        return database_users.get_users_with_revoked_consent(
            self.get_connection,
            limit=limit,
        )

    def get_user_consent_state(self, user_id: int) -> Dict:
        """Получение статуса согласий пользователя."""
        return database_consent.get_user_consent_state(
            self.get_local_user_by_id,
            user_id=user_id,
        )

    def grant_user_consent(self, user_id: int) -> None:
        """Выдать согласие на обработку ПД."""
        database_consent.grant_user_consent(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
        )

    def set_user_transborder_consent(self, user_id: int, granted: bool) -> None:
        """Обновить согласие на трансграничную передачу."""
        database_consent.set_user_transborder_consent(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
            granted=granted,
        )

    def set_user_marketing_consent(self, user_id: int, granted: bool) -> None:
        """Обновить согласие на рассылки."""
        database_consent.set_user_marketing_consent(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
            granted=granted,
        )

    def revoke_user_consent_and_delete_data(self, user_id: int) -> Dict:
        """
        Отзыв согласий + анонимизация ПД в анкете + удаление истории диалога.
        Возвращает сводку по измененным записям.
        """
        return database_consent.revoke_user_consent_and_delete_data(
            self.get_connection,
            self._sync_user_to_core,
            self._sync_lead_to_core,
            user_id=user_id,
        )

    def reset_user_to_new_state(self, user_id: int) -> Dict:
        """
        Сброс пользователя в состояние "как новый":
        - удаляются диалоги, лиды и аналитика;
        - обнуляются согласия и состояние воронки;
        - профиль пользователя (telegram_id/username/имя) сохраняется.
        """
        return database_user_state.reset_user_to_new_state(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
        )

    def delete_user_completely(self, user_id: int) -> Dict:
        """
        Полное удаление пользователя и всех связанных данных.
        """
        return database_user_state.delete_user_completely(
            self.get_connection,
            user_id=user_id,
        )

    def export_user_data(self, user_id: int) -> Dict:
        """Экспорт данных пользователя и связанной анкеты."""
        return database_consent.export_user_data(
            self.get_user_by_id,
            self.get_lead_by_user_id,
            user_id=user_id,
        )

    def update_user_fields(self, user_id: int, fields: Dict[str, str]) -> bool:
        """Обновление полей профиля пользователя."""
        return database_user_state.update_user_fields(
            self.get_connection,
            self._sync_user_to_core,
            _validate_columns,
            _USERS_COLUMNS,
            user_id=user_id,
            fields=fields,
        )

    def get_user_funnel_state(self, user_id: int) -> Dict:
        """
        Получение состояния воронки пользователя.

        Returns:
            dict: conversation_stage, cta_variant, cta_shown, cta_shown_at
        """
        return database_user_state.get_user_funnel_state(
            self.get_connection,
            user_id=user_id,
        )

    def update_user_funnel_state(
        self,
        user_id: int,
        conversation_stage: str = None,
        cta_variant: str = None,
        cta_shown: Optional[bool] = None,
    ) -> None:
        """Обновление состояния воронки пользователя."""
        database_user_state.update_user_funnel_state(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
            conversation_stage=conversation_stage,
            cta_variant=cta_variant,
            cta_shown=cta_shown,
        )

    def reset_user_funnel_state(self, user_id: int) -> None:
        """Сброс воронки при /reset."""
        database_user_state.reset_user_funnel_state(
            self.get_connection,
            self._sync_user_to_core,
            user_id=user_id,
        )

    # === CONVERSATIONS ===

    def add_message(self, user_id: int, role: str, message: str):
        """Добавление сообщения в историю диалога"""
        database_conversations.add_message(
            self.get_connection,
            user_id=user_id,
            role=role,
            message=message,
        )

    def get_conversation_history(self, user_id: int, limit: int = None) -> List[Dict]:
        """Получение истории диалога"""
        effective_limit = limit or config.MAX_HISTORY_MESSAGES
        return database_conversations.get_conversation_history(
            self.get_connection,
            user_id=user_id,
            limit=effective_limit,
        )

    def clear_conversation_history(self, user_id: int):
        """Очистка истории диалога"""
        database_conversations.clear_conversation_history(
            self.get_connection,
            user_id=user_id,
        )

    def cleanup_conversations_by_retention(self, retention_days: int | None = None) -> int:
        """Удаляет сообщения диалогов старше заданного retention-порога."""
        days = max(1, int(retention_days or config.CONVERSATION_RETENTION_DAYS))
        return database_conversations.cleanup_conversations_by_retention(
            self.get_connection,
            retention_days=days,
        )

    # === LEADS ===

    def create_or_update_lead(self, user_id: int, lead_data: Dict) -> int:
        """Создание или обновление лида"""
        return database_leads.create_or_update_lead(
            self.get_connection,
            self._sync_lead_to_core,
            _LEADS_COLUMNS,
            user_id=user_id,
            lead_data=lead_data,
        )

    def create_new_lead(self, user_id: int, lead_data: Dict) -> int:
        """Принудительное создание нового лида, без merge с предыдущим."""
        return database_leads.create_new_lead(
            self.get_connection,
            self._sync_lead_to_core,
            _LEADS_COLUMNS,
            user_id=user_id,
            lead_data=lead_data,
        )

    def create_new_local_lead(self, user_id: int, lead_data: Dict) -> int:
        """Create a fallback lead without mirroring it as a generic core lead."""
        return database_leads.create_new_lead(
            self.get_connection,
            lambda _lead_id: None,
            _LEADS_COLUMNS,
            user_id=user_id,
            lead_data=lead_data,
        )

    def get_lead_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Получение последнего лида по user_id"""
        return database_leads.get_lead_by_user_id(
            self.get_connection,
            self.get_local_user_by_id,
            self._merge_lead_row_with_core,
            user_id=user_id,
        )

    def get_local_lead_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Получение последнего лида по user_id без merge с core-api."""
        return database_leads.get_local_lead_by_user_id(
            self.get_connection,
            user_id=user_id,
        )

    def mark_lead_notification_sent(self, lead_id: int):
        """Помечаем что уведомление о лиде отправлено"""
        database_leads.mark_lead_notification_sent(
            self.get_connection,
            lead_id=lead_id,
        )

    def get_lead_by_id(self, lead_id: int) -> Optional[Dict]:
        """Получение лида по lead_id"""
        return database_leads.get_lead_by_id(
            self.get_connection,
            self.get_user_by_id,
            self._merge_lead_row_with_core,
            lead_id=lead_id,
        )

    def set_core_lead_id(self, lead_id: int, core_lead_id: str) -> None:
        """Сохраняет UUID лида из core-api для legacy лида."""
        database_leads.set_core_lead_id(
            self.get_connection,
            lead_id=lead_id,
            core_lead_id=core_lead_id,
        )

    def get_all_leads(
        self,
        temperature: str = None,
        status: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """Получение всех лидов с фильтрами"""
        return database_leads.get_all_leads(
            self.get_connection,
            temperature=temperature,
            status=status,
            limit=limit,
            offset=offset,
        )

    def get_leads_ready_for_notification(self, idle_minutes: int = 5) -> List[Dict]:
        """
        Получение лидов готовых к уведомлению:
        - Прошло idle_minutes минут с последнего сообщения
        - Уведомление еще не отправлено
        - Лид теплый или горячий (или есть ключевые данные)
        """
        return database_leads.get_leads_ready_for_notification(
            self.get_connection,
            idle_minutes=idle_minutes,
        )

    def update_lead_last_message_time(self, user_id: int):
        """Обновление времени последнего сообщения лида"""
        database_leads.update_lead_last_message_time(
            self.get_connection,
            user_id=user_id,
        )

    def update_lead_funnel_state(
        self,
        user_id: int,
        conversation_stage: str = None,
        cta_variant: str = None,
        cta_shown: Optional[bool] = None,
    ) -> None:
        """Синхронизация состояния воронки в таблице leads для последнего лида пользователя."""
        database_leads.update_lead_funnel_state(
            self.get_connection,
            user_id=user_id,
            conversation_stage=conversation_stage,
            cta_variant=cta_variant,
            cta_shown=cta_shown,
        )

    def update_lead_funnel_state_by_id(
        self,
        lead_id: int,
        conversation_stage: str = None,
        cta_variant: str = None,
        cta_shown: Optional[bool] = None,
    ) -> None:
        """Синхронизация состояния воронки для конкретного лида."""
        database_leads.update_lead_funnel_state_by_id(
            self.get_connection,
            lead_id=lead_id,
            conversation_stage=conversation_stage,
            cta_variant=cta_variant,
            cta_shown=cta_shown,
        )

    def create_notification(self, lead_id: int, notification_type: str,
                            message: str) -> int:
        """Создание уведомления для админа"""
        return database_leads.create_notification(
            self.get_connection,
            lead_id=lead_id,
            notification_type=notification_type,
            message=message,
        )

    # === REPORTING / FUNNEL ===

    def track_event(
        self,
        user_id: int,
        event_type: str,
        payload: Optional[Dict] = None,
        lead_id: Optional[int] = None,
    ) -> int:
        """Запись события аналитики."""
        return database_reporting.track_event(
            self.get_connection,
            self.get_lead_by_id,
            user_id=user_id,
            event_type=event_type,
            payload=payload,
            lead_id=lead_id,
        )

    def get_statistics(self, days: int = 30) -> Dict:
        """Получение статистики"""
        return database_reporting.get_statistics(
            self.get_connection,
            days=days,
        )

    def get_funnel_report(self, days: int = 30) -> Dict:
        """
        SQL-отчет по этапам воронки за период.
        Основан на событиях analytics_events и активности в conversations.
        """
        return database_reporting.get_funnel_report(
            self.get_connection,
            days=days,
        )

    def get_ab_cta_report(self, days: int = 30) -> Dict:
        """
        SQL-отчет по A/B вариантам CTA за период.
        """
        return database_reporting.get_ab_cta_report(
            self.get_connection,
            days=days,
        )

    # === KNOWLEDGE BASE / RAG ===

    def get_successful_conversations(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """
        Получение успешных диалогов (warm/hot лиды) для RAG

        Returns:
            Список словарей с полными диалогами и метаданными лидов
        """
        return database_knowledge.get_successful_conversations(
            self.get_connection,
            limit=limit,
            offset=offset,
        )

    def get_conversations_by_category(
        self,
        service_category: str,
        temperature: str = None,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Получение диалогов по категории услуги

        Args:
            service_category: Категория услуги
            temperature: Фильтр по температуре (опционально)
            limit: Максимальное количество результатов

        Returns:
            Список диалогов с метаданными
        """
        return database_knowledge.get_conversations_by_category(
            self.get_connection,
            service_category=service_category,
            temperature=temperature,
            limit=limit,
        )
