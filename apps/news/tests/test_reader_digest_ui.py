from __future__ import annotations

from news.reader_digest_ui import build_reader_digest_text, reader_digest_toggle_meta


def _screen_guide_stub(what: str, actions: list[str]) -> str:
    _ = actions
    return f"ℹ️ Что это: {what}"


def test_build_reader_digest_text_with_run_token() -> None:
    text = build_reader_digest_text(
        enabled=True,
        slot="12:15",
        max_users=15,
        run_token="2026-03-09T18:00:00+03:00",
        screen_guide=_screen_guide_stub,
    )
    assert "Reader digest-воркер" in text
    assert "Статус: 🟢 включен" in text
    assert "Слот авторассылки: 12:15" in text
    assert "Последний запрос теста: 2026-03-09T18:00:00+03:00" in text


def test_build_reader_digest_text_without_run_token() -> None:
    text = build_reader_digest_text(
        enabled=False,
        slot="09:30",
        max_users=10,
        run_token="",
        screen_guide=_screen_guide_stub,
    )
    assert "Статус: 🔴 выключен" in text
    assert "Последний запрос теста:" not in text


def test_reader_digest_toggle_meta() -> None:
    assert reader_digest_toggle_meta(True) == ("⛔ Выключить воркер", "0")
    assert reader_digest_toggle_meta(False) == ("🟢 Включить воркер", "1")
