from datetime import UTC, datetime

from news.daily_report import (
    DailyReportSnapshot,
    build_daily_report_text,
    count_recent_posts,
    daily_report_due,
    persisted_report_date,
    summarize_sources,
)
from news.rss_fetcher import RSSSourceResult


def test_daily_report_runs_once_after_configured_time() -> None:
    before = datetime(2026, 9, 1, 5, 29, tzinfo=UTC)
    due = datetime(2026, 9, 1, 5, 30, tzinfo=UTC)

    assert not daily_report_due(
        before,
        last_report_date="",
        tz_name="Europe/Moscow",
        hour=8,
        minute=30,
    )
    assert daily_report_due(
        due,
        last_report_date="",
        tz_name="Europe/Moscow",
        hour=8,
        minute=30,
    )
    assert not daily_report_due(
        due,
        last_report_date="2026-09-01",
        tz_name="Europe/Moscow",
        hour=8,
        minute=30,
    )


def test_report_state_is_restored_from_monitor_heartbeat() -> None:
    workers = [
        {
            "worker_id": "news-publication-monitor",
            "info": {"last_daily_report_date": "2026-09-01"},
        }
    ]

    assert persisted_report_date(
        workers,
        worker_id="news-publication-monitor",
    ) == "2026-09-01"


def test_source_summary_separates_working_empty_and_failed() -> None:
    rows = [
        RSSSourceResult("https://ok", [], True, 4),
        RSSSourceResult("https://empty", [], True, 0),
        RSSSourceResult("https://failed", [], False, 0, "timeout"),
    ]

    summary = summarize_sources(
        rows,
        names_by_url={
            "https://ok": "Рабочий",
            "https://empty": "Пустой",
            "https://failed": "Недоступный",
        },
    )

    assert (summary.working, summary.empty, summary.failed, summary.total) == (1, 1, 1, 3)
    assert summary.problem_names == ("Недоступный", "Пустой")


def test_count_recent_posts_uses_available_timestamps() -> None:
    rows = [
        {"posted_at": "2026-09-01T04:00:00Z"},
        {"updated_at": "2026-08-30T04:00:00Z"},
        {"publish_at": "not-a-date"},
    ]

    assert count_recent_posts(
        rows,
        now_utc=datetime(2026, 9, 1, 6, 0, tzinfo=UTC),
    ) == 1


def test_daily_report_text_contains_source_queue_and_worker_counts() -> None:
    snapshot = DailyReportSnapshot(
        now_local=datetime.fromisoformat("2026-09-01T08:30:00+03:00"),
        source_health=summarize_sources(
            [RSSSourceResult("https://ok", [], True, 3)],
            names_by_url={"https://ok": "Рабочий"},
        ),
        telegram_channels=34,
        telegram_items=75,
        telegram_checked_at=datetime.fromisoformat("2026-09-01T04:35:00+00:00"),
        telegram_stale=False,
        worker_active=3,
        worker_total=3,
        inactive_workers=(),
        published_24h=2,
        failed_24h=0,
        review_count=1,
        ready_count=3,
        scheduled_count=2,
        publishing_count=0,
        next_publish="01.09 09:00",
        generation_state="успешно (01.09 08:12)",
    )

    text = build_daily_report_text(snapshot)

    assert "RSS: 1/1 работают" in text
    assert "Telegram: 34 каналов; последний сбор 75 материалов" in text
    assert "Запас: 5 (готовых 3, запланированных 2)" in text
    assert "Критические воркеры: 3/3 активны" in text
    assert "СИСТЕМА РАБОТАЕТ ШТАТНО" in text
