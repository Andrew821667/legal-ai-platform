from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping


ScreenGuide = Callable[[str, list[str]], str]


def build_system_text(
    counts: Mapping[str, int],
    next_publish: str,
    *,
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    return (
        "Система и сервисные функции\n\n"
        "Этот раздел собран для операций, которые раньше были доступны только через slash-команды.\n\n"
        + guide(
            "Сервисные функции и диагностика редакторского контура.",
            [
                "Проверяйте статус API и Reader-разделы.",
                "При зависаниях используйте «Сброс stale», затем проверьте воркеры.",
            ],
        )
        + "\n\n"
        f"📝 Черновики: {counts.get('draft', -1)}\n"
        f"🟡 На проверке: {counts.get('review', -1)}\n"
        f"✅ На публикацию: {counts.get('scheduled', -1)}\n"
        f"📤 Опубликованные: {counts.get('posted', -1)}\n"
        f"❌ Ошибки: {counts.get('failed', -1)}\n"
        f"⏳ В публикации: {counts.get('publishing', -1)}\n\n"
        f"Следующая публикация: {next_publish}\n\n"
        "Отсюда доступны: статус API, Reader-раздел, принудительный reset stale и справка.\n"
        "Глобальная автоматизация и список воркеров вынесены на рабочий стол."
    )


def build_ops_health_mark(
    *,
    issues: Iterable[str],
    overdue: int,
    stale_publishing: int,
) -> str:
    issue_list = list(issues)
    mark = "🟢"
    if issue_list:
        mark = "🟠"
    if overdue > 0 or stale_publishing > 0 or any(item.startswith("worker_inactive") for item in issue_list):
        mark = "🔴"
    return mark


def build_ops_summary_text(
    *,
    next_publish: str,
    snapshot_at: str,
    heartbeat_max_age_minutes: int | None,
    overdue: int,
    stale_publishing: int,
    failed_posts: int,
    review_count: int,
    miniapp_line: str,
    worker_lines: list[str],
    issues: list[str],
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    health_mark = build_ops_health_mark(
        issues=issues,
        overdue=overdue,
        stale_publishing=stale_publishing,
    )

    lines = [
        "Операционный контроль контент-контура",
        "",
        guide(
            "Быстрая диагностика проблем генерации и публикации.",
            [
                "При красных индикаторах сначала проверьте «Воркеры», затем используйте «Сброс stale».",
                "После восстановления откройте экран повторно и проверьте, что все индикаторы зеленые.",
            ],
        ),
        "",
        f"Состояние контура: {health_mark}",
        f"Следующая публикация: {next_publish}",
        f"Снимок сформирован: {snapshot_at}",
        (
            f"Макс. давность heartbeat: {heartbeat_max_age_minutes} мин"
            if heartbeat_max_age_minutes is not None
            else "Макс. давность heartbeat: n/a"
        ),
        "",
        "Ключевые индикаторы:",
        f"• Просроченные scheduled: {overdue}",
        f"• Зависшие publishing (>30м): {stale_publishing}",
        f"• Ошибки в ленте (посл.100): {failed_posts}",
        f"• На проверке: {review_count}",
        miniapp_line,
        "",
        "Критичные воркеры:",
    ]
    lines.extend(worker_lines or ["• нет данных"])
    lines.append("")
    if issues:
        lines.append(f"Найдены риски: {len(issues)}")
        lines.append("Рекомендуется: проверить воркеры -> сбросить stale -> повторно открыть экран.")
    else:
        lines.append("Критичных рисков не обнаружено.")
    return "\n".join(lines)
