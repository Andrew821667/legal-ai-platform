"""Base SQLite runtime facade for the legacy lead-bot database layer."""
from __future__ import annotations

import copy
import json
import logging
import os
import sqlite3
import time
import urllib.parse
import urllib.request
import database_facade
import database_schema
from config import get_config
from lead_perf import log_span_timing, perf_start

config = get_config()
logger = logging.getLogger(__name__)


class Database(database_facade.DatabaseFacadeMixin):
    """Base runtime/database facade with connection handling and core-api sync."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        self._core_get_cache: dict[str, tuple[float, object]] = {}
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.init_database()

    @staticmethod
    def _core_cache_key(path: str, params: dict | None = None) -> str:
        cleaned = {key: value for key, value in (params or {}).items() if value is not None}
        return json.dumps(
            {
                "path": path,
                "params": cleaned,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

    def _core_cache_lookup(self, cache_key: str, ttl_seconds: float) -> object | None:
        if ttl_seconds <= 0:
            return None
        cached = self._core_get_cache.get(cache_key)
        if not cached:
            return None
        cached_at, payload = cached
        if (time.monotonic() - cached_at) > ttl_seconds:
            return None
        return copy.deepcopy(payload)

    def _core_cache_store(self, cache_key: str, payload: object) -> None:
        if config.CORE_API_STALE_CACHE_TTL_SECONDS <= 0:
            return
        self._core_get_cache[cache_key] = (time.monotonic(), copy.deepcopy(payload))
        if len(self._core_get_cache) > 256:
            oldest_key = min(self._core_get_cache.items(), key=lambda item: item[1][0])[0]
            self._core_get_cache.pop(oldest_key, None)

    def get_connection(self) -> sqlite3.Connection:
        """Получение подключения к БД."""
        conn = sqlite3.connect(self.db_path, timeout=20.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        except Exception as pragma_error:
            logger.debug("SQLite PRAGMA setup skipped: %s", pragma_error)
        return conn

    def _core_get_json(self, path: str, params: dict | None = None):
        if not (config.CORE_API_SYNC_ENABLED and config.CORE_API_URL and config.API_KEY_BOT):
            return None
        started_at = perf_start()
        cache_key = self._core_cache_key(path, params)
        cached = self._core_cache_lookup(cache_key, config.CORE_API_CACHE_TTL_SECONDS)
        if cached is not None:
            log_span_timing("lead_db_core_get", started_at, ok=True, path=path, cache="hot")
            return cached

        query = ""
        if params:
            cleaned = {key: value for key, value in params.items() if value is not None}
            if cleaned:
                query = "?" + urllib.parse.urlencode(cleaned)

        request = urllib.request.Request(
            url=f"{config.CORE_API_URL.rstrip('/')}{path}{query}",
            headers={"X-API-Key": config.API_KEY_BOT, "Content-Type": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=config.CORE_API_TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8")
                payload = json.loads(raw) if raw else None
                self._core_cache_store(cache_key, payload)
                log_span_timing("lead_db_core_get", started_at, ok=True, path=path)
                return payload
        except Exception as error:
            stale = self._core_cache_lookup(cache_key, config.CORE_API_STALE_CACHE_TTL_SECONDS)
            if stale is not None:
                log_span_timing(
                    "lead_db_core_get",
                    started_at,
                    ok=True,
                    path=path,
                    cache="stale",
                )
                logger.debug("Core API getter using stale cache for %s after error: %s", path, error)
                return stale
            log_span_timing(
                "lead_db_core_get",
                started_at,
                ok=False,
                error=type(error).__name__,
                force=True,
                path=path,
            )
            logger.debug("Core API getter fallback to SQLite for %s: %s", path, error)
            return None

    @staticmethod
    def _map_core_user(row: dict) -> dict:
        return {
            "telegram_id": row.get("telegram_id"),
            "username": row.get("username"),
            "first_name": row.get("first_name"),
            "last_name": row.get("last_name"),
            "email": row.get("email"),
            "name": row.get("name"),
            "consent_given": bool(row.get("consent_given")),
            "consent_date": row.get("consent_date"),
            "consent_revoked": bool(row.get("consent_revoked")),
            "consent_revoked_at": row.get("consent_revoked_at"),
            "transborder_consent": bool(row.get("transborder_consent")),
            "transborder_consent_date": row.get("transborder_consent_date"),
            "marketing_consent": bool(row.get("marketing_consent")),
            "marketing_consent_date": row.get("marketing_consent_date"),
            "conversation_stage": row.get("conversation_stage"),
            "cta_variant": row.get("cta_variant"),
            "cta_shown": bool(row.get("cta_shown")),
            "cta_shown_at": row.get("cta_shown_at"),
            "offer_profile_override": row.get("offer_profile_override"),
            "created_at": row.get("created_at"),
            "last_interaction": row.get("last_interaction"),
        }

    def _merge_user_row_with_core(self, local_user: dict | None) -> dict | None:
        if not local_user:
            return None
        telegram_id = local_user.get("telegram_id")
        if telegram_id is None:
            return local_user
        core_rows = self._core_get_json("/api/v1/users", {"telegram_id": telegram_id, "limit": 1})
        if isinstance(core_rows, list) and core_rows:
            merged = dict(local_user)
            merged.update({k: v for k, v in self._map_core_user(core_rows[0]).items() if v is not None})
            return merged
        return local_user

    def _sync_user_to_core(self, user_id: int) -> None:
        """Зеркалирует профиль и согласия пользователя в core-api."""
        try:
            from core_api_bridge import core_api_bridge

            if not core_api_bridge.enabled:
                return

            user = self.get_user_by_id(user_id)
            if not user:
                return

            core_api_bridge.sync_user(user)
        except Exception as mirror_error:
            logger.warning("Failed to sync user %s to core-api: %s", user_id, mirror_error)

    def init_database(self):
        """Инициализация базы данных и создание таблиц."""
        database_schema.init_database(self.get_connection, logger)


# Создание глобального экземпляра базы данных
db = Database()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    print("Initializing database...")
    Database()
    print("Database initialized successfully!")
