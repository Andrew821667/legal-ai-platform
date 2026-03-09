from __future__ import annotations

from collections.abc import Callable


ScreenGuide = Callable[[str, list[str]], str]


def build_reader_digest_text(
    *,
    enabled: bool,
    slot: str,
    max_users: int,
    run_token: str,
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    return (
        "Reader digest-воркер\n\n"
        + guide(
            "Управление авторассылкой персональных дайджестов reader-бота.",
            [
                "Меняйте слот и лимит цикла кнопками ниже.",
                "«Тестовый прогон» запускает внеплановый единичный цикл.",
            ],
        )
        + "\n\n"
        f"Статус: {'🟢 включен' if enabled else '🔴 выключен'}\n"
        f"Слот авторассылки: {slot}\n"
        f"Лимит пользователей за цикл: {max_users}\n\n"
        "Тестовый прогон запускает одну внеплановую рассылку сразу после ближайшего цикла опроса воркера.\n"
        + (f"Последний запрос теста: {run_token}\n" if run_token else "")
    )


def reader_digest_toggle_meta(enabled: bool) -> tuple[str, str]:
    label = "⛔ Выключить воркер" if enabled else "🟢 Включить воркер"
    target_value = "0" if enabled else "1"
    return label, target_value
