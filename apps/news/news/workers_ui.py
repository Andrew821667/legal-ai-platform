from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import quote, unquote


WORKER_LABELS = {
    "news-generate": "🧠 Генератор драфтов",
    "news-telegram-ingest": "📡 Telegram-парсер",
    "news-publish": "📤 Публикатор канала",
    "news-reader-digest": "📬 Reader-дайджест",
}


def format_workers_status(
    payload: dict[str, Any],
    *,
    worker_labels: Mapping[str, str] | None = None,
) -> str:
    labels = worker_labels or WORKER_LABELS
    any_active = bool(payload.get("any_active"))
    workers = payload.get("workers") or []

    lines = [
        "Статус воркеров",
        "",
        f"Активные воркеры: {'да' if any_active else 'нет'}",
    ]

    if not workers:
        lines.append("Список пуст.")
        lines.append("")
        lines.append("Это нормально, если сервисы-воркеры не запущены в текущем compose-профиле.")
        lines.append(
            "Воркеры нужны для фоновых задач (например, contract-worker), но для контент-бота могут быть не обязательны."
        )
        return "\n".join(lines)

    lines.append("")
    for row in workers[:20]:
        worker_id = str(row.get("worker_id") or "unknown")
        active = bool(row.get("active"))
        info = row.get("info") or {}
        mark = "🟢" if active else "⚪"
        display_name = labels.get(worker_id, worker_id)
        last_seen = str(row.get("last_seen_at") or "n/a")
        lines.append(f"{mark} {display_name}")
        if display_name != worker_id:
            lines.append(f"   id: {worker_id}")
        slot_times = info.get("slot_times")
        if isinstance(slot_times, list):
            slots = ", ".join(str(item) for item in slot_times if str(item).strip())
            if slots:
                lines.append(f"   слоты: {slots}")
        lines.append(f"   last_seen: {last_seen}")

    return "\n".join(lines)


def worker_callback_token(worker_id: str) -> str:
    return quote(worker_id, safe="")


def worker_id_from_callback_token(token: str) -> str:
    return unquote(token or "").strip()


def worker_list_text(
    payload: dict[str, Any],
    *,
    screen_guide: Callable[[str, list[str]], str] | None = None,
    worker_labels: Mapping[str, str] | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    workers = payload.get("workers") or []
    lines = [
        format_workers_status(payload, worker_labels=worker_labels),
        "",
        guide(
            "Сводный список фоновых воркеров и их доступности.",
            [
                "Нажмите на конкретного воркера, чтобы открыть карточку активности за 24 часа.",
                "Если список пуст, проверьте, что сервисы подняты и шлют heartbeat.",
            ],
        ),
        "",
    ]
    if not workers:
        lines.append("Когда сервисы начнут слать heartbeat, список и карточки заполнятся автоматически.")
    return "\n".join(lines).strip()


def format_worker_activity(
    payload: dict[str, Any],
    *,
    screen_guide: Callable[[str, list[str]], str] | None = None,
    worker_labels: Mapping[str, str] | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    labels = worker_labels or WORKER_LABELS

    worker_id = str(payload.get("worker_id") or "unknown")
    display_name = labels.get(worker_id, worker_id)
    active = bool(payload.get("active"))
    last_seen = str(payload.get("last_seen_at") or "n/a")
    hours = int(payload.get("window_hours") or 24)
    startup_events = payload.get("startup_events") or []
    action_counts = payload.get("action_counts") or []
    entries = payload.get("entries") or []

    lines = [
        f"Воркер: {display_name}",
        f"ID: {worker_id}",
        f"Статус: {'🟢 активен' if active else '⚪ неактивен'}",
        f"Последний heartbeat: {last_seen}",
        "",
        guide(
            "Детальная карточка конкретного воркера.",
            [
                "Смотрите блок «Запуски» и «Что делал за период», чтобы проверить фактическую работу.",
                "Если heartbeat старый или действий нет, откройте логи сервиса и перезапустите контейнер.",
            ],
        ),
        "",
        f"Запуски за {hours} ч: {len(startup_events)}",
    ]

    schedule_lines: list[str] = []
    for row in entries:
        details = row.get("details") or {}
        slot_times = details.get("slot_times")
        if not isinstance(slot_times, list):
            continue
        normalized = ", ".join(str(item) for item in slot_times if str(item).strip())
        if normalized:
            schedule_lines.append(normalized)
    if schedule_lines:
        lines.append(f"Слоты: {schedule_lines[0]}")
        lines.append("")

    if startup_events:
        for row in startup_events[:10]:
            lines.append(f"• {row}")
    else:
        lines.append("• запусков не зафиксировано")

    lines.append("")
    lines.append("Что делал за период:")
    if action_counts:
        for row in action_counts[:10]:
            action = str(row.get("action") or "action")
            count = int(row.get("count") or 0)
            lines.append(f"• {action}: {count}")
    else:
        lines.append("• действий не зафиксировано")

    lines.append("")
    lines.append("Последние события:")
    if entries:
        for row in entries[:12]:
            occurred_at = str(row.get("occurred_at") or "")
            action = str(row.get("action") or "action")
            details = row.get("details") or {}
            detail_line = ""
            if isinstance(details, dict):
                chunks: list[str] = []
                for key in (
                    "slot",
                    "job_id",
                    "result_code",
                    "error",
                    "publish_interval",
                    "limit",
                    "channels",
                    "fetch_limit",
                    "count",
                    "slot_times",
                ):
                    value = details.get(key)
                    if value in (None, "", []):
                        continue
                    chunks.append(f"{key}={value}")
                if chunks:
                    detail_line = " (" + ", ".join(chunks) + ")"
            lines.append(f"• {occurred_at} — {action}{detail_line}")
    else:
        lines.append("• событий пока нет")

    return "\n".join(lines)
