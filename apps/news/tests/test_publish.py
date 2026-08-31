from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import requests
from news.publish import (
    PublishQualityError,
    TelegramRequestError,
    _ambiguous_delivery_review_patch,
    _autofill_publish_at,
    _demote_stale_scheduled_posts,
    _normalize_text_before_publish,
    _promote_due_editorial_posts_for_idle_publisher,
    _promote_ready_posts_for_idle_queue,
    _publish_quality_review_patch,
    _retryable_publish_patch,
    _telegram_request,
)
from news.publish import (
    main as publish_main,
)
from news.settings import settings


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def __init__(self, *, ready_rows=None, review_rows=None, scheduled_rows=None, posted_rows=None) -> None:
        self._ready_rows = ready_rows or []
        self._review_rows = review_rows or []
        self._scheduled_rows = scheduled_rows
        self._posted_rows = posted_rows or []
        self.patched: list[tuple[str, dict[str, object]]] = []

    def list_posts(self, limit: int = 20, status: str | None = None, newest_first: bool = False, offset: int = 0):
        _ = (limit, newest_first, offset)
        if status == "ready":
            return _FakeResponse(self._ready_rows[:limit])
        if status == "review":
            return _FakeResponse(self._review_rows[:limit])
        if status == "scheduled":
            return _FakeResponse(self._scheduled_rows[:limit])
        if status == "posted":
            return _FakeResponse(self._posted_rows[:limit])
        raise AssertionError(f"unexpected status {status}")

    def patch_post(self, post_id: str, payload: dict[str, str]):
        self.patched.append((post_id, payload))
        return _FakeResponse({})


class _FakeMainClient(_FakeClient):
    def __init__(self) -> None:
        super().__init__(
            ready_rows=[{"id": "ready-1"}],
            review_rows=[{"id": "review-1"}],
            scheduled_rows=[],
        )
        self.claims = 0

    def list_automation_controls(self, scope: str | None = None):
        _ = scope
        return _FakeResponse([])

    def claim_posts(self, limit: int):
        _ = limit
        self.claims += 1
        return _FakeResponse([], status_code=204)


def _valid_daily_post(title: str = "Legal AI меняет работу юрфункции") -> dict[str, object]:
    text = (
        f"<b>{title}</b>\n\n"
        "<b>Что произошло</b>\n"
        "Свежий материал описывает, как Legal AI переходит из экспериментов в рабочие процессы юридических департаментов. "
        "Команды уже тестируют agentic AI, пересматривают бюджет на технологии и связывают внедрение с конкретными операциями: "
        "договорной проверкой, intake, поиском по базе знаний и подготовкой типовых правовых документов.\n\n"
        "<b>Почему это важно</b>\n"
        "Для юрфункции это означает, что эффект больше нельзя оценивать по числу купленных лицензий. "
        "Нужны процесс, владелец результата, контроль качества, логирование действий модели, понятный SLA и договорная ответственность поставщика. "
        "Иначе пилот быстро превращается в красивую демонстрацию без управляемой экономики.\n\n"
        "<b>Что это значит для рынка</b>\n"
        "Закупка Legal AI будет смещаться от выбора модели к выбору операционного контура. "
        "Победят поставщики, которые умеют встраиваться в реальные юридические процессы, считать стоимость одной операции, "
        "показывать аудит результата и поддерживать проверку человеком в спорных сценариях.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict #LegalTech #AI"
    )
    return {
        "title": title,
        "text": text,
        "format_type": "daily",
        "rubric": "market",
        "cta_type": "soft",
    }


def test_autofill_publish_at_keeps_future_publish_time() -> None:
    now_utc = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
    future = now_utc + timedelta(hours=5)
    row = {"publish_at": future.isoformat()}

    result = _autofill_publish_at(row, queue_index=0, now_utc=now_utc)

    assert result == future.isoformat()


def test_autofill_publish_at_shifts_past_review_post_forward() -> None:
    now_utc = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
    past = now_utc - timedelta(hours=2)
    row = {"publish_at": past.isoformat()}

    result = _autofill_publish_at(row, queue_index=1, now_utc=now_utc)

    assert datetime.fromisoformat(result) == now_utc + timedelta(hours=2)


def test_promote_ready_posts_for_idle_queue() -> None:
    now_utc = datetime.now(UTC)
    client = _FakeClient(
        ready_rows=[
            {"id": "r1", "publish_at": (now_utc - timedelta(hours=1)).isoformat()},
            {"id": "r2", "publish_at": (now_utc + timedelta(hours=3)).isoformat()},
        ],
    )

    promoted = _promote_ready_posts_for_idle_queue(client, limit=1)

    assert promoted == 2
    assert [post_id for post_id, _ in client.patched] == ["r1", "r2"]
    assert client.patched[0][1]["status"] == "scheduled"
    assert client.patched[1][1]["status"] == "scheduled"


def test_due_editorial_fallback_promotes_due_ready_before_review(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tz_name", "UTC")
    monkeypatch.setattr(settings, "news_publish_editorial_fallback_grace_minutes", 45)
    now_utc = datetime(2026, 5, 14, 9, 15, tzinfo=UTC)
    due_ready = {
        **_valid_daily_post("Готовый пост"),
        "id": "due-ready",
        "publish_at": datetime(2026, 5, 14, 9, 0, tzinfo=UTC).isoformat(),
    }
    client = _FakeClient(
        ready_rows=[
            {"id": "future-ready", "publish_at": (now_utc + timedelta(hours=2)).isoformat()},
            due_ready,
        ],
        review_rows=[{"id": "due-review", "publish_at": datetime(2026, 5, 14, 9, 0, tzinfo=UTC).isoformat()}],
    )

    promoted = _promote_due_editorial_posts_for_idle_publisher(client, limit=1, now_utc=now_utc)

    assert promoted == 1
    assert client.patched[0][0] == "due-ready"
    assert client.patched[0][1]["status"] == "scheduled"
    assert client.patched[0][1]["last_error"] is None


def test_due_editorial_fallback_promotes_quality_checked_review_posts(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tz_name", "UTC")
    monkeypatch.setattr(settings, "news_publish_editorial_fallback_grace_minutes", 45)
    now_utc = datetime(2026, 5, 14, 9, 15, tzinfo=UTC)
    due_review = {
        **_valid_daily_post("Пост после проверки"),
        "id": "due-review",
        "publish_at": datetime(2026, 5, 14, 9, 0, tzinfo=UTC).isoformat(),
    }
    client = _FakeClient(
        ready_rows=[{"id": "future-ready", "publish_at": (now_utc + timedelta(hours=2)).isoformat()}],
        review_rows=[due_review],
    )

    promoted = _promote_due_editorial_posts_for_idle_publisher(client, limit=1, now_utc=now_utc)

    assert promoted == 1
    assert client.patched[0][0] == "due-review"
    assert client.patched[0][1]["status"] == "scheduled"
    assert client.patched[0][1]["last_error"] is None


def test_due_editorial_fallback_keeps_weak_review_post_in_review(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tz_name", "UTC")
    monkeypatch.setattr(settings, "news_publish_editorial_fallback_grace_minutes", 45)
    now_utc = datetime(2026, 5, 14, 9, 15, tzinfo=UTC)
    client = _FakeClient(
        ready_rows=[],
        review_rows=[
            {
                "id": "weak-review",
                "publish_at": datetime(2026, 5, 14, 9, 0, tzinfo=UTC).isoformat(),
                "format_type": "daily",
                "rubric": "market",
                "text": "<b>Заголовок</b>\n\n<b>Источник</b>: ссылка",
            }
        ],
    )

    promoted = _promote_due_editorial_posts_for_idle_publisher(client, limit=1, now_utc=now_utc)

    assert promoted == 0
    assert client.patched[0][0] == "weak-review"
    assert client.patched[0][1]["status"] == "review"
    assert str(client.patched[0][1]["last_error"]).startswith("publish_quality_gate: writer_quality_gate:")


def test_due_editorial_fallback_skips_future_review_posts(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tz_name", "UTC")
    monkeypatch.setattr(settings, "news_publish_editorial_fallback_grace_minutes", 45)
    now_utc = datetime(2026, 5, 14, 9, 15, tzinfo=UTC)
    client = _FakeClient(
        ready_rows=[],
        review_rows=[{"id": "future-review", "publish_at": (now_utc + timedelta(hours=2)).isoformat()}],
    )

    promoted = _promote_due_editorial_posts_for_idle_publisher(client, limit=1, now_utc=now_utc)

    assert promoted == 0
    assert client.patched == []


def test_due_editorial_fallback_skips_posts_outside_current_slot_window(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tz_name", "UTC")
    monkeypatch.setattr(settings, "news_publish_editorial_fallback_grace_minutes", 45)
    now_utc = datetime(2026, 5, 14, 9, 15, tzinfo=UTC)
    client = _FakeClient(
        ready_rows=[],
        review_rows=[
            {"id": "stale-review", "publish_at": datetime(2026, 5, 13, 9, 0, tzinfo=UTC).isoformat()},
            {
                **_valid_daily_post("Свежий пост"),
                "id": "fresh-review",
                "publish_at": datetime(2026, 5, 14, 9, 0, tzinfo=UTC).isoformat(),
            },
        ],
    )

    promoted = _promote_due_editorial_posts_for_idle_publisher(client, limit=1, now_utc=now_utc)

    assert promoted == 1
    assert client.patched[0][0] == "fresh-review"
    assert client.patched[0][1]["status"] == "scheduled"
    assert client.patched[0][1]["last_error"] is None


def test_due_editorial_fallback_skips_slot_that_was_already_posted(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tz_name", "UTC")
    monkeypatch.setattr(settings, "news_publish_editorial_fallback_grace_minutes", 45)
    now_utc = datetime(2026, 5, 14, 9, 15, tzinfo=UTC)
    slot_at = datetime(2026, 5, 14, 9, 0, tzinfo=UTC).isoformat()
    client = _FakeClient(
        ready_rows=[],
        review_rows=[{"id": "due-review", "publish_at": slot_at}],
        posted_rows=[{"id": "posted-review", "publish_at": slot_at}],
    )

    promoted = _promote_due_editorial_posts_for_idle_publisher(client, limit=1, now_utc=now_utc)

    assert promoted == 0
    assert client.patched == []


def test_main_skips_idle_fallback_when_startup_grace_is_active(monkeypatch) -> None:
    client = _FakeMainClient()

    monkeypatch.setattr("news.publish.CoreClient", lambda *_args, **_kwargs: client)
    monkeypatch.setattr("news.publish.rebalance_active_publish_queue", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(settings, "api_key_news", "test-key")

    result = publish_main(allow_idle_fallback=False)

    assert result == 0
    assert client.claims == 1
    assert client.patched == []


def test_main_ignores_unsafe_idle_fallback_after_startup_grace(monkeypatch) -> None:
    client = _FakeMainClient()

    monkeypatch.setattr("news.publish.CoreClient", lambda *_args, **_kwargs: client)
    monkeypatch.setattr("news.publish.rebalance_active_publish_queue", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(settings, "api_key_news", "test-key")
    monkeypatch.setattr(settings, "news_publish_idle_fallback_enabled", True)

    result = publish_main(allow_idle_fallback=True)

    assert result == 0
    assert client.claims == 1
    assert client.patched == []


def test_main_disables_idle_fallback_by_default(monkeypatch) -> None:
    client = _FakeMainClient()

    monkeypatch.setattr("news.publish.CoreClient", lambda *_args, **_kwargs: client)
    monkeypatch.setattr("news.publish.rebalance_active_publish_queue", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(settings, "api_key_news", "test-key")
    monkeypatch.setattr(settings, "news_publish_idle_fallback_enabled", False)

    result = publish_main(allow_idle_fallback=True)

    assert result == 0
    assert client.claims == 1
    assert client.patched == []


def test_do_not_promote_stale_or_distant_ready_posts_for_idle_queue() -> None:
    now_utc = datetime.now(UTC)
    client = _FakeClient(
        ready_rows=[
            {"id": "stale", "publish_at": (now_utc - timedelta(days=3)).isoformat()},
            {"id": "distant", "publish_at": (now_utc + timedelta(days=3)).isoformat()},
        ],
    )

    promoted = _promote_ready_posts_for_idle_queue(client, limit=3)

    assert promoted == 0
    assert client.patched == []


def test_demote_stale_scheduled_posts_to_ready() -> None:
    now_utc = datetime.now(UTC)
    client = _FakeClient(
        scheduled_rows=[
            {"id": "old", "publish_at": (now_utc - timedelta(hours=7)).isoformat()},
            {"id": "fresh", "publish_at": (now_utc - timedelta(hours=2)).isoformat()},
            {"id": "future", "publish_at": (now_utc + timedelta(hours=2)).isoformat()},
        ],
    )

    original = settings.news_publish_max_overdue_minutes
    settings.news_publish_max_overdue_minutes = 360
    try:
        demoted = _demote_stale_scheduled_posts(client)
    finally:
        settings.news_publish_max_overdue_minutes = original

    assert demoted == 1
    assert client.patched == [("old", {"status": "ready"})]


def test_retryable_publish_patch_requeues_transient_telegram_failure() -> None:
    original = settings.news_retry_failed_after_minutes
    settings.news_retry_failed_after_minutes = 15
    try:
        now_utc = datetime(2026, 4, 13, 6, 5, tzinfo=UTC)
        patch = _retryable_publish_patch(
            {"attempts": 0, "max_attempts": 3},
            TelegramRequestError("dns fail", retryable=True),
            now_utc=now_utc,
        )
    finally:
        settings.news_retry_failed_after_minutes = original

    assert patch is not None
    assert patch["status"] == "scheduled"
    assert patch["attempts"] == 1
    assert datetime.fromisoformat(patch["publish_at"]) == now_utc + timedelta(minutes=15)


def test_retryable_publish_patch_stops_after_max_attempts() -> None:
    patch = _retryable_publish_patch(
        {"attempts": 2, "max_attempts": 3},
        TelegramRequestError("dns fail", retryable=True),
        now_utc=datetime(2026, 4, 13, 6, 5, tzinfo=UTC),
    )

    assert patch is None


def test_retryable_publish_patch_ignores_non_retryable_error() -> None:
    patch = _retryable_publish_patch(
        {"attempts": 0, "max_attempts": 3},
        TelegramRequestError("bad request", retryable=False),
        now_utc=datetime(2026, 4, 13, 6, 5, tzinfo=UTC),
    )

    assert patch is None


def test_ambiguous_delivery_review_patch_moves_post_to_review() -> None:
    patch = _ambiguous_delivery_review_patch(
        {"attempts": 1, "max_attempts": 3},
        TelegramRequestError("read timeout", ambiguous_delivery=True),
    )

    assert patch is not None
    assert patch["status"] == "review"
    assert patch["attempts"] == 2
    assert str(patch["last_error"]).startswith("ambiguous_telegram_delivery:")


def test_publish_quality_review_patch_moves_post_to_review() -> None:
    patch = _publish_quality_review_patch(
        {"attempts": 0},
        PublishQualityError("weak_generic_conclusion"),
    )

    assert patch is not None
    assert patch["status"] == "review"
    assert patch["attempts"] == 1
    assert patch["last_error"] == "publish_quality_gate: weak_generic_conclusion"


def test_telegram_request_does_not_retry_read_timeout(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_post(url, **kwargs):
        _ = (url, kwargs)
        calls["count"] += 1
        raise requests.exceptions.ReadTimeout("read timed out")

    monkeypatch.setattr("news.publish.requests.post", fake_post)
    monkeypatch.setattr(
        "news.publish.settings",
        SimpleNamespace(telegram_bot_token="test-token", telegram_api_proxy_url=""),
    )

    try:
        _telegram_request("sendMessage", {"chat_id": "@channel", "text": "test"}, retries=3)
    except TelegramRequestError as exc:
        assert exc.retryable is False
        assert exc.ambiguous_delivery is True
    else:
        raise AssertionError("expected TelegramRequestError")

    assert calls["count"] == 1


def test_telegram_request_uses_configured_proxy(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _FakeResponse({"ok": True, "result": {"message_id": 1}})

    monkeypatch.setattr("news.publish.requests.post", fake_post)
    monkeypatch.setattr(
        "news.publish.settings",
        SimpleNamespace(
            telegram_bot_token="test-token",
            telegram_api_proxy_url="http://host.docker.internal:18080",
        ),
    )

    result = _telegram_request("sendMessage", {"chat_id": "@channel", "text": "test"}, retries=1)

    assert result["ok"] is True
    assert captured["proxies"] == {"https": "http://host.docker.internal:18080"}


def test_normalize_text_before_publish_collapses_duplicate_footer_blocks() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "Текст поста.\n\n"
        "Обсудите внедрение с Асистентом AI Verdict.\n\n"
        "<b>Следующий шаг</b>\nОбсудите с Асистентом AI Verdict.\n\n"
        "<b>Следующий шаг</b>\nНапишите в @legal_ai_helper_new_bot.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict"
    )

    normalized = _normalize_text_before_publish(original)

    assert normalized.count("<b>Следующий шаг</b>") == 1
    assert normalized.count("https://t.me/legal_ai_helper_new_bot") == 1
    assert "Асистент" not in normalized
    assert "Напишите в" not in normalized
    assert normalized.index("<b>Следующий шаг</b>") < normalized.index("<b>Источник</b>")


def test_normalize_text_before_publish_rejects_competitor_source() -> None:
    try:
        _normalize_text_before_publish(
            "<b>Нейтральный заголовок</b>\n\nТекст редакционного материала.",
            {
                "title": "Нейтральный заголовок",
                "source_url": "https://t.me/Law_GPT/144",
                "format_type": "daily",
            },
        )
    except PublishQualityError as exc:
        assert str(exc) == "competitor_source"
    else:
        raise AssertionError("expected PublishQualityError")


def test_normalize_text_before_publish_rejects_competitor_brand_leak() -> None:
    try:
        _normalize_text_before_publish(
            "<b>LawGPT выпустил новую функцию</b>\n\nТекст рекламного материала.",
            {
                "title": "LawGPT выпустил новую функцию",
                "source_url": "https://example.com/news",
                "format_type": "daily",
            },
        )
    except PublishQualityError as exc:
        assert str(exc) == "competitor_brand_mention"
    else:
        raise AssertionError("expected PublishQualityError")


def test_normalize_text_before_publish_rejects_unknown_russian_vendor_launch() -> None:
    try:
        _normalize_text_before_publish(
            "На российский рынок вышел сервис «ЮрБот». Новый продукт — ИИ-юрист для проверки договоров.",
            {
                "title": "На рынок вышел новый ИИ-юрист",
                "source_url": "https://example.com/news",
                "format_type": "daily",
            },
        )
    except PublishQualityError as exc:
        assert str(exc) == "competitor_marketing_pattern"
    else:
        raise AssertionError("expected PublishQualityError")


def test_normalize_text_before_publish_rejects_generic_practical_conclusion() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "<b>Что произошло</b>\nТекст поста про Legal AI.\n\n"
        "<b>Бизнес-эффект</b>\nКейс показывает, как сократить ручную работу.\n\n"
        "<b>Юридические риски</b>\nПроверить данные, SLA и ответственность.\n\n"
        "<b>Что делать</b>\n• Проверить процесс и данные.\n\n"
        "<b>Вывод</b>\n"
        "Практический смысл здесь не в самой новости, а в том, какие процессы и роли можно пересобрать внутри юрфункции.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict"
    )

    try:
        _normalize_text_before_publish(
            original,
            {"title": "Заголовок", "format_type": "standard", "cta_type": "soft", "rubric": "legal_ops"},
        )
    except PublishQualityError as exc:
        assert str(exc) == "weak_generic_conclusion"
    else:
        raise AssertionError("expected PublishQualityError")


def test_normalize_text_before_publish_allows_actionable_practical_conclusion() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "<b>Что произошло</b>\nТекст поста про Legal AI.\n\n"
        "<b>Бизнес-эффект</b>\nСценарий влияет на стоимость операций и контроль качества.\n\n"
        "<b>Юридические риски</b>\nПроверить данные, SLA и ответственность.\n\n"
        "<b>Что делать</b>\n• Проверить процесс и данные.\n\n"
        "<b>Вывод</b>\n"
        "Перед пилотом нужно зафиксировать владельца процесса, перечень данных, SLA, метрику стоимости операции и правило контроля результата юристом.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict"
    )

    normalized = _normalize_text_before_publish(
        original,
        {"title": "Заголовок", "format_type": "standard", "cta_type": "soft", "rubric": "legal_ops"},
    )

    assert "Перед пилотом нужно зафиксировать" in normalized


def test_manual_editorial_post_keeps_human_structure_under_strict_gate() -> None:
    original = (
        "<b>С 1 сентября начинает действовать закон об ИИ</b>\n\n"
        "1 сентября 2026 года вступает в силу основная часть закона. Она формирует общую "
        "рамку регулирования, но не вводит на этом этапе все специальные обязанности.\n\n"
        "<b>Первый этап регулирования</b>\n\n"
        "Бизнесу не нужно экстренно отключать иностранные модели или маркировать каждый текст. При этом "
        "стоит зафиксировать модели, поставщиков, виды данных и точки человеческого контроля.\n\n"
        "<b>Отложенные положения</b>\n\n"
        "Основные специальные требования отложены до 1 марта 2027 года. До этой даты нужно следить за подзаконными "
        "актами и обновлять внутреннюю дорожную карту по мере появления конкретных правил.\n\n"
        "Для подготовки компании стоит отдельно проверить договоры с поставщиками, места обработки данных, права на результаты и "
        "порядок проверки юридически значимых решений человеком. Эти действия нужны для контроля рисков уже сейчас.\n\n"
        "Источник: https://publication.pravo.gov.ru/document/example"
    )

    normalized = _normalize_text_before_publish(
        original,
        {"title": "Закон об ИИ", "format_type": "manual_daily", "source_url": "https://publication.pravo.gov.ru/document/example"},
        intelligent_footer=False,
        strict_quality=True,
    )

    assert "<b>Первый этап регулирования</b>" in normalized


def test_normalize_text_before_publish_adds_missing_footer_for_applicable_ready_post() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "Текст поста про рынок Legal AI и внедрение в юрфункции.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict"
    )

    normalized = _normalize_text_before_publish(
        original,
        {"title": "Заголовок", "format_type": "daily", "cta_type": "soft", "rubric": "contracts"},
    )

    assert "<b>Следующий шаг</b>" in normalized
    assert "https://t.me/legal_ai_helper_new_bot" in normalized
    assert normalized.index("<b>Следующий шаг</b>") < normalized.index("<b>Источник</b>")


def test_normalize_text_before_publish_does_not_force_footer_when_not_applicable() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "Текст поста про общий рыночный сигнал без явного сценария внедрения.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict"
    )

    normalized = _normalize_text_before_publish(
        original,
        {"title": "Заголовок", "format_type": "daily", "cta_type": "soft", "rubric": "market"},
    )

    assert "<b>Следующий шаг</b>" not in normalized


def test_normalize_text_before_publish_respects_disabled_footer_control() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "Текст поста.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict"
    )

    normalized = _normalize_text_before_publish(
        original,
        {"title": "Заголовок", "format_type": "daily", "cta_type": "soft", "rubric": "market"},
        intelligent_footer=False,
    )

    assert "<b>Следующий шаг</b>" not in normalized


def test_normalize_text_before_publish_keeps_weekly_review_footerless() -> None:
    original = (
        "<b>Обзор недели</b>\n\n"
        "1. Первый сигнал.\n"
        "2. Второй сигнал.\n\n"
        "<b>Источник</b>: внутренняя подборка\n"
        "#AIVerdict"
    )

    normalized = _normalize_text_before_publish(
        original,
        {"title": "Обзор недели", "format_type": "weekly_review", "cta_type": "soft", "rubric": "market"},
    )

    assert "<b>Следующий шаг</b>" not in normalized
