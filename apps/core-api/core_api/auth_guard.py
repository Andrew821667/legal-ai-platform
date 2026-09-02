"""Защита проверки API-ключа от перебора.

Проверка ключа намеренно дорогая: пароли хранятся в bcrypt, и одно сравнение
занимает заметное время. При неизвестном ключе перебираются все активные
записи, поэтому один запрос с мусором стоит примерно столько же процессорного
времени, сколько несколько десятков обычных запросов.

Эндпоинты доступны из интернета, так что поток мусорных ключей насыщает
процессор без всякого взлома. Здесь два дешёвых барьера перед дорогой
проверкой:

* уже отклонённые ключи запоминаются и отвергаются без повторного сравнения;
* с одного адреса ограничивается число неудачных проверок в минуту.

Это не заменяет переход на схему с идентификатором ключа, но снимает
возможность положить сервис одним скриптом.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from hashlib import sha256


class AuthGuard:
    def __init__(
        self,
        *,
        max_failures_per_window: int = 20,
        window_seconds: int = 60,
        rejected_cache_size: int = 4096,
        rejected_ttl_seconds: int = 300,
    ) -> None:
        self._max_failures = max_failures_per_window
        self._window = window_seconds
        self._rejected_ttl = rejected_ttl_seconds
        self._rejected_cache_size = rejected_cache_size
        self._failures: dict[str, deque[float]] = {}
        self._rejected: dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _fingerprint(raw_key: str) -> str:
        return sha256(raw_key.encode("utf-8")).hexdigest()

    def is_known_bad(self, raw_key: str, *, now: float | None = None) -> bool:
        """Проверяет, отвергался ли этот ключ недавно."""
        now = time.time() if now is None else now
        key = self._fingerprint(raw_key)
        with self._lock:
            seen_at = self._rejected.get(key)
            if seen_at is None:
                return False
            if now - seen_at > self._rejected_ttl:
                self._rejected.pop(key, None)
                return False
            return True

    def remember_bad(self, raw_key: str, *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        key = self._fingerprint(raw_key)
        with self._lock:
            # Отсекаем самые старые записи, чтобы словарь не рос без предела:
            # атакующий может слать бесконечно разные ключи.
            if len(self._rejected) >= self._rejected_cache_size:
                for old_key, seen_at in sorted(self._rejected.items(), key=lambda kv: kv[1])[:64]:
                    _ = seen_at
                    self._rejected.pop(old_key, None)
            self._rejected[key] = now

    def too_many_failures(self, client: str, *, now: float | None = None) -> bool:
        """Исчерпан ли лимит неудачных проверок для адреса."""
        now = time.time() if now is None else now
        with self._lock:
            attempts = self._failures.get(client)
            if not attempts:
                return False
            while attempts and now - attempts[0] > self._window:
                attempts.popleft()
            if not attempts:
                self._failures.pop(client, None)
                return False
            return len(attempts) >= self._max_failures

    def register_failure(self, client: str, *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            attempts = self._failures.setdefault(client, deque())
            while attempts and now - attempts[0] > self._window:
                attempts.popleft()
            attempts.append(now)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()
            self._rejected.clear()


guard = AuthGuard()


def client_fingerprint(headers, fallback: str = "unknown") -> str:
    """Адрес клиента по заголовкам обратного прокси.

    Берётся последний элемент X-Forwarded-For: его добавляет прокси, тогда как
    всё, что левее, приходит от самого клиента и подделывается свободно.
    """
    forwarded = str(headers.get("x-forwarded-for") or "")
    parts = [part.strip() for part in forwarded.split(",") if part.strip()]
    if parts:
        return parts[-1][:120]
    real = str(headers.get("x-real-ip") or "").strip()
    return (real or fallback)[:120]
