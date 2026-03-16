from __future__ import annotations

import asyncio

from news.admin_bot import (
    NewsAdminBot,
    _STATE_DRAFT_BATCH_PUBLISH,
    _STATE_DRAFT_PUBLISH,
    _STATE_PENDING_DELETE_REASON,
    _STATE_PENDING_EDIT,
    _STATE_PENDING_BATCH_PUBLISH_REASON,
    _STATE_PENDING_PUBLISH_REASON,
)


class _DummyMessage:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class _DummyQuery:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = _DummyMessage()
        self.answer_calls: list[tuple[str | None, bool]] = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answer_calls.append((text, show_alert))


class _DummyUpdate:
    def __init__(self, query: _DummyQuery) -> None:
        self.callback_query = query


class _DummyContext:
    def __init__(self) -> None:
        self.user_data: dict[str, object] = {}


class _DummyTextMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.replies: list[tuple[str, object]] = []

    async def reply_text(self, text: str, reply_markup=None) -> None:  # noqa: ANN001
        self.replies.append((text, reply_markup))


class _DummyTextUpdate:
    def __init__(self, text: str) -> None:
        self.effective_message = _DummyTextMessage(text)


def test_cb_posts_batch_prepare_sets_pending_state(monkeypatch) -> None:
    bot = NewsAdminBot()
    query = _DummyQuery("mbp:due:8:top3")
    update = _DummyUpdate(query)
    context = _DummyContext()
    context.user_data[_STATE_DRAFT_BATCH_PUBLISH] = {"old": True}
    edited: dict[str, object] = {}
    expected_markup = object()

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    async def _safe_edit(_query, text, reply_markup=None):  # noqa: ANN001
        edited["text"] = text
        edited["reply_markup"] = reply_markup

    def _load_manual_queue(*, queue_filter: str, offset: int):  # noqa: ANN001
        assert queue_filter == "due"
        assert offset == 8
        return (
            5,
            [{"id": "1"}, {"id": "2"}, {"id": "3"}, {"id": "4"}],
            2,
            3,
        )

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_sync_ui_hints_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "_safe_edit_message_text", _safe_edit)
    monkeypatch.setattr(bot, "_load_manual_queue", _load_manual_queue)
    monkeypatch.setattr(bot, "_batch_publish_reason_keyboard", lambda queue_filter, offset, mode: expected_markup)

    asyncio.run(bot.cb_posts(update, context))

    assert context.user_data[_STATE_PENDING_BATCH_PUBLISH_REASON] == {
        "queue_filter": "due",
        "offset": 8,
        "mode": "top3",
        "post_ids": ["1", "2", "3"],
    }
    assert _STATE_DRAFT_BATCH_PUBLISH not in context.user_data
    assert edited["reply_markup"] is expected_markup
    assert "Пакетная публикация: шаг 1 из 2" in str(edited["text"])
    assert query.answer_calls == [(None, False)]


def test_cb_posts_publish_now_clears_publish_states(monkeypatch) -> None:
    bot = NewsAdminBot()
    query = _DummyQuery("ppc:42:scheduled:0")
    update = _DummyUpdate(query)
    context = _DummyContext()
    context.user_data[_STATE_DRAFT_PUBLISH] = {"x": 1}
    context.user_data[_STATE_PENDING_PUBLISH_REASON] = {"x": 1}
    context.user_data[_STATE_PENDING_BATCH_PUBLISH_REASON] = {"x": 1}
    context.user_data[_STATE_DRAFT_BATCH_PUBLISH] = {"x": 1}
    edits: list[tuple[str, object]] = []
    expected_markup = object()
    publish_calls: list[str] = []
    invalidation_calls: list[bool] = []

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    async def _safe_edit(_query, text, reply_markup=None):  # noqa: ANN001
        edits.append((text, reply_markup))

    async def _publish_now(_context, post_id: str) -> None:  # noqa: ANN001
        publish_calls.append(post_id)

    def _load_posts(*, status: str, offset: int):  # noqa: ANN001
        assert status == "scheduled"
        assert offset == 0
        return 1, [{"id": "42", "title": "Item"}]

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_sync_ui_hints_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "_safe_edit_message_text", _safe_edit)
    monkeypatch.setattr(bot, "_publish_now", _publish_now)
    monkeypatch.setattr(bot, "_invalidate_post_caches", lambda *args, **kwargs: invalidation_calls.append(True))
    monkeypatch.setattr(bot, "_load_posts", _load_posts)
    monkeypatch.setattr(bot, "_posts_text", lambda total, rows, offset, status: "POSTS_VIEW")
    monkeypatch.setattr(bot, "_posts_keyboard", lambda total, rows, offset, status: expected_markup)

    asyncio.run(bot.cb_posts(update, context))

    assert publish_calls == ["42"]
    assert invalidation_calls == [True]
    assert _STATE_DRAFT_PUBLISH not in context.user_data
    assert _STATE_PENDING_PUBLISH_REASON not in context.user_data
    assert _STATE_PENDING_BATCH_PUBLISH_REASON not in context.user_data
    assert _STATE_DRAFT_BATCH_PUBLISH not in context.user_data
    assert edits[0] == ("Публикуем пост...", None)
    assert "Пост успешно опубликован вручную." in edits[1][0]
    assert "POSTS_VIEW" in edits[1][0]
    assert edits[1][1] is expected_markup
    assert query.answer_calls == [(None, False)]


def test_cb_posts_batch_cancel_clears_states(monkeypatch) -> None:
    bot = NewsAdminBot()
    query = _DummyQuery("mbn:due:8:top3")
    update = _DummyUpdate(query)
    context = _DummyContext()
    context.user_data[_STATE_PENDING_BATCH_PUBLISH_REASON] = {"x": 1}
    context.user_data[_STATE_DRAFT_BATCH_PUBLISH] = {"x": 1}
    edited: dict[str, object] = {}
    expected_markup = object()

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    async def _safe_edit(_query, text, reply_markup=None):  # noqa: ANN001
        edited["text"] = text
        edited["reply_markup"] = reply_markup

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_sync_ui_hints_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "_safe_edit_message_text", _safe_edit)
    monkeypatch.setattr(
        bot,
        "_load_manual_queue",
        lambda *, queue_filter, offset: (3, [{"id": "1"}], 1, 2),
    )
    monkeypatch.setattr(bot, "_manual_queue_text", lambda *args, **kwargs: "MANUAL_QUEUE_VIEW")
    monkeypatch.setattr(bot, "_manual_queue_keyboard", lambda *args, **kwargs: expected_markup)

    asyncio.run(bot.cb_posts(update, context))

    assert _STATE_PENDING_BATCH_PUBLISH_REASON not in context.user_data
    assert _STATE_DRAFT_BATCH_PUBLISH not in context.user_data
    assert "Пакетная публикация отменена." in str(edited["text"])
    assert "MANUAL_QUEUE_VIEW" in str(edited["text"])
    assert edited["reply_markup"] is expected_markup


def test_cb_posts_delete_confirm_requires_reason(monkeypatch) -> None:
    bot = NewsAdminBot()
    query = _DummyQuery("pdy:42:scheduled:0")
    update = _DummyUpdate(query)
    context = _DummyContext()
    edited: dict[str, object] = {}
    expected_markup = object()

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    async def _safe_edit(_query, text, reply_markup=None):  # noqa: ANN001
        edited["text"] = text
        edited["reply_markup"] = reply_markup

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_sync_ui_hints_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "_safe_edit_message_text", _safe_edit)
    monkeypatch.setattr(bot, "_delete_reason_keyboard", lambda post_id, status, offset: expected_markup)

    asyncio.run(bot.cb_posts(update, context))

    assert edited["text"] == "Сначала укажите причину удаления."
    assert edited["reply_markup"] is expected_markup


def test_cb_posts_delete_confirm_success_shows_scope(monkeypatch) -> None:
    class _Response:
        def __init__(self, status_code: int = 200) -> None:
            self.status_code = status_code

        def raise_for_status(self) -> None:
            return None

    class _ClientStub:
        def __init__(self) -> None:
            self.feedback_calls: list[tuple[str, dict[str, object]]] = []
            self.delete_calls: list[str] = []

        def create_post_feedback(self, post_id: str, payload: dict[str, object]) -> _Response:
            self.feedback_calls.append((post_id, payload))
            return _Response(201)

        def delete_post(self, post_id: str) -> _Response:
            self.delete_calls.append(post_id)
            return _Response(204)

    bot = NewsAdminBot()
    bot.client = _ClientStub()
    query = _DummyQuery("pdy:42:scheduled:0")
    update = _DummyUpdate(query)
    context = _DummyContext()
    context.user_data[_STATE_PENDING_DELETE_REASON] = {"post_id": "42", "status": "scheduled", "offset": 0, "reason": "noise"}
    invalidation_calls: list[bool] = []
    scope_calls: list[tuple[str, int, str]] = []

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    async def _show_scope(_query, *, status: str, offset: int, message_prefix: str) -> None:  # noqa: ANN001
        scope_calls.append((status, offset, message_prefix))

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_sync_ui_hints_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "_invalidate_post_caches", lambda *args, **kwargs: invalidation_calls.append(True))
    monkeypatch.setattr(bot, "_show_status_scope_message", _show_scope)

    asyncio.run(bot.cb_posts(update, context))

    assert bot.client.delete_calls == ["42"]
    assert bot.client.feedback_calls and bot.client.feedback_calls[0][0] == "42"
    assert _STATE_PENDING_DELETE_REASON not in context.user_data
    assert invalidation_calls == [True]
    assert scope_calls == [("scheduled", 0, "Пост удален, негативный feedback сохранен.\n\n")]


def test_cb_posts_publish_back_clears_states_and_shows_card(monkeypatch) -> None:
    bot = NewsAdminBot()
    query = _DummyQuery("ppn:42:scheduled:0")
    update = _DummyUpdate(query)
    context = _DummyContext()
    context.user_data[_STATE_PENDING_PUBLISH_REASON] = {"x": 1}
    context.user_data[_STATE_DRAFT_PUBLISH] = {"x": 1}
    context.user_data[_STATE_PENDING_BATCH_PUBLISH_REASON] = {"x": 1}
    context.user_data[_STATE_DRAFT_BATCH_PUBLISH] = {"x": 1}
    edited: dict[str, object] = {}
    expected_markup = object()

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    async def _safe_edit(_query, text, reply_markup=None):  # noqa: ANN001
        edited["text"] = text
        edited["reply_markup"] = reply_markup

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_sync_ui_hints_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "_safe_edit_message_text", _safe_edit)
    monkeypatch.setattr(bot, "_get_post", lambda post_id: {"id": post_id, "title": "Item"})
    monkeypatch.setattr(bot, "_post_card_text", lambda post: "POST_CARD")
    monkeypatch.setattr(bot, "_post_card_keyboard", lambda post_id, status, offset: expected_markup)

    asyncio.run(bot.cb_posts(update, context))

    assert _STATE_PENDING_PUBLISH_REASON not in context.user_data
    assert _STATE_DRAFT_PUBLISH not in context.user_data
    assert _STATE_PENDING_BATCH_PUBLISH_REASON not in context.user_data
    assert _STATE_DRAFT_BATCH_PUBLISH not in context.user_data
    assert edited == {"text": "POST_CARD", "reply_markup": expected_markup}


def test_cb_posts_publish_yes_uses_shared_publish_helper(monkeypatch) -> None:
    bot = NewsAdminBot()
    query = _DummyQuery("ppy:42:scheduled:0")
    update = _DummyUpdate(query)
    context = _DummyContext()
    calls: list[tuple[str, tuple[str, ...], bool]] = []

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    async def _publish_helper(  # noqa: ANN001
        _query,
        _context,
        *,
        post_id: str,
        status: str,
        offset: int,
        clear_state_keys: tuple[str, ...],
        force_invalidate: bool = False,
    ) -> None:
        calls.append((f"{post_id}:{status}:{offset}", clear_state_keys, force_invalidate))

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_sync_ui_hints_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "_publish_and_show_status_scope", _publish_helper)

    asyncio.run(bot.cb_posts(update, context))

    assert calls == [("42:scheduled:0", (_STATE_PENDING_PUBLISH_REASON, _STATE_DRAFT_PUBLISH), False)]


def test_cb_posts_edit_cancel_uses_scope_helper(monkeypatch) -> None:
    bot = NewsAdminBot()
    query = _DummyQuery("px:scheduled:3")
    update = _DummyUpdate(query)
    context = _DummyContext()
    context.user_data[_STATE_DRAFT_PUBLISH] = {"x": 1}
    context.user_data[_STATE_PENDING_EDIT] = {"x": 1}
    calls: list[tuple[str, int, str]] = []

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    async def _show_scope(_query, *, status: str, offset: int, message_prefix: str) -> None:  # noqa: ANN001
        calls.append((status, offset, message_prefix))

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_sync_ui_hints_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "_show_status_scope_message", _show_scope)

    asyncio.run(bot.cb_posts(update, context))

    assert _STATE_PENDING_EDIT not in context.user_data
    assert calls == [("scheduled", 3, "Редактирование отменено.\n\n")]


def test_cb_posts_ready_transition_uses_helper(monkeypatch) -> None:
    class _Response:
        def raise_for_status(self) -> None:
            return None

    class _ClientStub:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def patch_post(self, post_id: str, payload: dict[str, object]) -> _Response:
            self.calls.append((post_id, payload))
            return _Response()

    bot = NewsAdminBot()
    bot.client = _ClientStub()
    query = _DummyQuery("pr:42:review:0")
    update = _DummyUpdate(query)
    context = _DummyContext()
    helper_calls: list[tuple[str, int, str, str]] = []
    invalidation_calls: list[bool] = []

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    async def _show_after(  # noqa: ANN001
        _query,
        *,
        source_status: str,
        offset: int,
        target_status: str,
        message_prefix: str,
    ) -> None:
        helper_calls.append((source_status, offset, target_status, message_prefix))

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_sync_ui_hints_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "_get_post", lambda post_id: {"id": post_id, "status": "review"})
    monkeypatch.setattr(bot, "_ready_status_payload", lambda post: {"status": "ready"})
    monkeypatch.setattr(bot, "_invalidate_post_caches", lambda *args, **kwargs: invalidation_calls.append(True))
    monkeypatch.setattr(bot, "_show_after_transition", _show_after)

    asyncio.run(bot.cb_posts(update, context))

    assert bot.client.calls == [("42", {"status": "ready"})]
    assert invalidation_calls == [True]
    assert helper_calls == [("review", 0, "ready", "Пост переведён в папку «Готовые» (ready).\n\n")]


def test_cb_posts_schedule_transition_uses_helper(monkeypatch) -> None:
    class _Response:
        def raise_for_status(self) -> None:
            return None

    class _ClientStub:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def patch_post(self, post_id: str, payload: dict[str, object]) -> _Response:
            self.calls.append((post_id, payload))
            return _Response()

    bot = NewsAdminBot()
    bot.client = _ClientStub()
    query = _DummyQuery("pg:42:ready:0")
    update = _DummyUpdate(query)
    context = _DummyContext()
    helper_calls: list[tuple[str, int, str, str]] = []
    invalidation_calls: list[bool] = []

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    async def _show_after(  # noqa: ANN001
        _query,
        *,
        source_status: str,
        offset: int,
        target_status: str,
        message_prefix: str,
    ) -> None:
        helper_calls.append((source_status, offset, target_status, message_prefix))

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_sync_ui_hints_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "_get_post", lambda post_id: {"id": post_id, "status": "ready"})
    monkeypatch.setattr(bot, "_scheduled_status_payload", lambda post: {"status": "scheduled"})
    monkeypatch.setattr(bot, "_invalidate_post_caches", lambda *args, **kwargs: invalidation_calls.append(True))
    monkeypatch.setattr(bot, "_show_after_transition", _show_after)

    asyncio.run(bot.cb_posts(update, context))

    assert bot.client.calls == [("42", {"status": "scheduled"})]
    assert invalidation_calls == [True]
    assert helper_calls == [("ready", 0, "scheduled", "Пост переведён в папку «На публикацию» (scheduled).\n\n")]


def test_cb_posts_review_transition_uses_helper(monkeypatch) -> None:
    class _Response:
        def raise_for_status(self) -> None:
            return None

    class _ClientStub:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def patch_post(self, post_id: str, payload: dict[str, object]) -> _Response:
            self.calls.append((post_id, payload))
            return _Response()

    bot = NewsAdminBot()
    bot.client = _ClientStub()
    query = _DummyQuery("rr:42:scheduled:3")
    update = _DummyUpdate(query)
    context = _DummyContext()
    helper_calls: list[tuple[str, int, str, str]] = []
    invalidation_calls: list[bool] = []

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    async def _show_after(  # noqa: ANN001
        _query,
        *,
        source_status: str,
        offset: int,
        target_status: str,
        message_prefix: str,
    ) -> None:
        helper_calls.append((source_status, offset, target_status, message_prefix))

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_sync_ui_hints_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "_invalidate_post_caches", lambda *args, **kwargs: invalidation_calls.append(True))
    monkeypatch.setattr(bot, "_show_after_transition", _show_after)

    asyncio.run(bot.cb_posts(update, context))

    assert bot.client.calls == [("42", {"status": "review"})]
    assert invalidation_calls == [True]
    assert helper_calls == [("scheduled", 3, "review", "Пост переведён в проверку (review).\n\n")]


def test_cb_posts_batch_action_uses_helper(monkeypatch) -> None:
    bot = NewsAdminBot()
    query = _DummyQuery("ba:ready:scheduled:8")
    update = _DummyUpdate(query)
    context = _DummyContext()
    helper_calls: list[tuple[str, str, int]] = []

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    async def _apply(_query, *, action: str, status: str, offset: int) -> None:  # noqa: ANN001
        helper_calls.append((action, status, offset))

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_sync_ui_hints_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "_apply_batch_status_action", _apply)

    asyncio.run(bot.cb_posts(update, context))

    assert helper_calls == [("ready", "scheduled", 8)]


def test_on_edit_text_pending_batch_reason_builds_draft(monkeypatch) -> None:
    bot = NewsAdminBot()
    update = _DummyTextUpdate("  срочно   в эфир ")
    context = _DummyContext()
    context.user_data[_STATE_PENDING_BATCH_PUBLISH_REASON] = {
        "queue_filter": "due",
        "offset": 8,
        "mode": "top3",
        "post_ids": ["1", "2"],
    }
    expected_markup = object()

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_batch_publish_confirm_keyboard", lambda queue_filter, offset, mode: expected_markup)

    asyncio.run(bot.on_edit_text(update, context))

    assert _STATE_PENDING_BATCH_PUBLISH_REASON not in context.user_data
    assert context.user_data[_STATE_DRAFT_BATCH_PUBLISH] == {
        "queue_filter": "due",
        "offset": 8,
        "mode": "top3",
        "post_ids": ["1", "2"],
        "reason": "срочно в эфир",
    }
    assert update.effective_message.replies
    text, markup = update.effective_message.replies[-1]
    assert "Пакетная публикация: шаг 2 из 2" in text
    assert markup is expected_markup


def test_on_edit_text_pending_publish_reason_builds_draft(monkeypatch) -> None:
    bot = NewsAdminBot()
    update = _DummyTextUpdate("  ручная публикация ")
    context = _DummyContext()
    context.user_data[_STATE_PENDING_PUBLISH_REASON] = {
        "post_id": "42",
        "status": "scheduled",
        "offset": 0,
    }
    expected_markup = object()

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_get_post", lambda post_id: {"id": post_id, "title": "Тест"})
    monkeypatch.setattr(bot, "_publish_confirm_keyboard", lambda post_id, status, offset: expected_markup)

    asyncio.run(bot.on_edit_text(update, context))

    assert _STATE_PENDING_PUBLISH_REASON not in context.user_data
    assert context.user_data[_STATE_DRAFT_PUBLISH] == {
        "post_id": "42",
        "status": "scheduled",
        "offset": 0,
        "reason": "ручная публикация",
    }
    assert update.effective_message.replies
    text, markup = update.effective_message.replies[-1]
    assert "Ручная публикация: шаг 2 из 2" in text
    assert markup is expected_markup
