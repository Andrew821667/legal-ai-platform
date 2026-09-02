"""Защита проверки API-ключа от перебора.

Проверка ключа намеренно дорогая: неизвестный ключ сверяется bcrypt со всеми
активными записями. Эндпоинты доступны из интернета, поэтому поток мусорных
ключей насыщает процессор без всякого взлома — это можно сделать одним
скриптом.
"""

from __future__ import annotations

from core_api.auth_guard import AuthGuard, client_fingerprint


def test_rejected_key_is_not_checked_twice() -> None:
    """Повторный мусорный ключ отвергается без нового сравнения."""
    g = AuthGuard()

    assert g.is_known_bad("ak_garbage") is False
    g.remember_bad("ak_garbage")
    assert g.is_known_bad("ak_garbage") is True


def test_rejected_key_is_forgotten_after_ttl() -> None:
    """Запись не хранится вечно: ключ мог быть выпущен заново."""
    g = AuthGuard(rejected_ttl_seconds=60)
    g.remember_bad("ak_garbage", now=1000.0)

    assert g.is_known_bad("ak_garbage", now=1030.0) is True
    assert g.is_known_bad("ak_garbage", now=1100.0) is False


def test_failure_limit_triggers_for_one_client() -> None:
    """После лимита неудач адрес отсекается до дорогой проверки."""
    g = AuthGuard(max_failures_per_window=3, window_seconds=60)

    for _ in range(3):
        assert g.too_many_failures("203.0.113.7") is False
        g.register_failure("203.0.113.7")

    assert g.too_many_failures("203.0.113.7") is True


def test_limit_does_not_affect_other_clients() -> None:
    """Перебор с одного адреса не должен блокировать остальных."""
    g = AuthGuard(max_failures_per_window=2, window_seconds=60)
    for _ in range(5):
        g.register_failure("203.0.113.7")

    assert g.too_many_failures("203.0.113.7") is True
    assert g.too_many_failures("198.51.100.9") is False


def test_failures_expire_with_window() -> None:
    """Старые неудачи не копятся: честный клиент не блокируется навсегда."""
    g = AuthGuard(max_failures_per_window=2, window_seconds=60)
    g.register_failure("203.0.113.7", now=1000.0)
    g.register_failure("203.0.113.7", now=1001.0)

    assert g.too_many_failures("203.0.113.7", now=1002.0) is True
    assert g.too_many_failures("203.0.113.7", now=1200.0) is False


def test_rejected_cache_does_not_grow_without_bound() -> None:
    """Атакующий шлёт бесконечно разные ключи — словарь должен быть ограничен."""
    g = AuthGuard(rejected_cache_size=128)
    for i in range(500):
        g.remember_bad(f"ak_{i}")

    assert len(g._rejected) <= 128


def test_client_is_taken_from_proxy_not_from_sender() -> None:
    """Адрес берётся из части, добавленной прокси.

    Всё, что левее последнего элемента, присылает сам клиент: если брать
    первый, лимит обходится подменой заголовка на каждом запросе.
    """
    spoofed = {"x-forwarded-for": "1.2.3.4, 198.51.100.9"}
    other = {"x-forwarded-for": "9.9.9.9, 198.51.100.9"}

    assert client_fingerprint(spoofed) == client_fingerprint(other) == "198.51.100.9"


def test_client_falls_back_to_real_ip() -> None:
    assert client_fingerprint({"x-real-ip": "198.51.100.9"}) == "198.51.100.9"
    assert client_fingerprint({}) == "unknown"


def test_fingerprint_is_not_a_plain_fast_hash() -> None:
    """Отпечаток не должен совпадать с голым SHA256 от того же значения.

    Быстрый хеш позволяет сопоставить отпечаток с исходным ключом перебором,
    если содержимое памяти утечёт. Отпечаток берётся на ключе процесса, поэтому
    воспроизвести его снаружи нельзя.
    """
    from hashlib import sha256

    from core_api.key_fingerprint import fingerprint

    secret = "ak_example_secret_value"

    assert fingerprint(secret) != sha256(secret.encode()).hexdigest()
    assert secret not in fingerprint(secret)


def test_fingerprint_is_stable_within_process() -> None:
    """Внутри процесса отпечаток постоянен — иначе кэш не работал бы."""
    from core_api.key_fingerprint import fingerprint

    assert fingerprint("ak_same") == fingerprint("ak_same")
    assert fingerprint("ak_one") != fingerprint("ak_two")
