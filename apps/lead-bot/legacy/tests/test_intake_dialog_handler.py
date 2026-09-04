"""Проверки поведения диалога в боте.

Отдельно от формулировок: здесь проверяется, что состояние переключается
правильно, ответы уходят в core-api и сбои не оставляют клиента в неведении.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import intake_dialog as handler


@pytest.fixture(autouse=True)
def dialog_store(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Подменяет хранилище состояния на словарь в памяти.

    Без этого тесты пишут в настоящую базу бота и видят состояние друг друга:
    один тест оставляет незавершённый диалог, а следующий получает его вместо
    чистого листа.
    """
    stored: dict = {}
    monkeypatch.setattr(
        handler.database.db,
        "save_intake_dialog_state",
        lambda user_id, user_data: stored.update({user_id: dict(user_data)}),
    )
    monkeypatch.setattr(
        handler.database.db,
        "load_intake_dialog_state",
        lambda user_id: dict(stored.get(user_id, {})),
    )
    monkeypatch.setattr(
        handler.database.db,
        "clear_intake_dialog_state",
        lambda user_id: stored.pop(user_id, None),
    )
    return stored


@pytest.fixture
def context() -> SimpleNamespace:
    ctx = SimpleNamespace(user_data={})
    handler.start_dialog(
        ctx.user_data,
        intake_id="11111111-1111-1111-1111-111111111111",
        lead_id="22222222-2222-2222-2222-222222222222",
        legal_area="employment",
    )
    return ctx


@pytest.fixture
def update() -> SimpleNamespace:
    message = SimpleNamespace(document=None, photo=None)
    return SimpleNamespace(
        effective_message=message,
        effective_user=SimpleNamespace(id=42, username="client", full_name="Иван Петров"),
        callback_query=None,
    )


@pytest.fixture
def replies(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    sent: list[str] = []

    async def _reply(message, text, **kwargs) -> None:
        sent.append(text)

    monkeypatch.setattr(handler.utils, "safe_reply_text", _reply)
    return sent


@pytest.fixture(autouse=True)
def instant_pace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Убирает человеческие паузы из тестов.

    В жизни пауза перед репликой обязательна, здесь она превращает набор в
    полминуты ожидания и ничего не проверяет — темп закреплён отдельно, в
    tests/test_human_pace.py.
    """

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(handler.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(handler.human_pace, "typing_delay", lambda text, **kwargs: 0.0)


def _silence_bridge(monkeypatch: pytest.MonkeyPatch, **overrides) -> dict:
    """Отключает сеть: по умолчанию всё сохраняется, NDA не подписан."""
    calls: dict = {"clarifications": [], "documents": []}

    def _clarify(intake_id, *, question_key, question_text, answer_text):
        calls["clarifications"].append((intake_id, question_key, answer_text))
        return True

    def _document(intake_id, **kwargs):
        calls["documents"].append((intake_id, kwargs))
        return overrides.get("document_result", True)

    monkeypatch.setattr(handler.core_api_bridge, "record_clarification", _clarify)
    # По умолчанию помощник недоступен: эти проверки о заданном в коде наборе.
    # Работа помощника закреплена отдельными тестами ниже.
    monkeypatch.setattr(
        handler.core_api_bridge,
        "assistant_turn",
        lambda *args, **kwargs: overrides.get("assistant"),
    )
    monkeypatch.setattr(handler.core_api_bridge, "record_intake_document", _document)
    monkeypatch.setattr(
        handler.core_api_bridge,
        "get_nda_status",
        lambda lead_id: overrides.get("nda_status", {"signed": False}),
    )
    monkeypatch.setattr(
        handler.core_api_bridge,
        "get_nda_document",
        lambda: overrides.get("nda_document", {"text": "текст", "hash": "abc", "version": "v1"}),
    )
    return calls


@pytest.mark.anyio
async def test_dialog_ignores_messages_when_not_started(update, replies) -> None:
    context = SimpleNamespace(user_data={})
    handled = await handler.handle_intake_dialog_message(update, context, "здравствуйте")
    assert handled is False
    assert replies == []


@pytest.mark.anyio
async def test_first_reply_starts_questions(context, update, replies, monkeypatch) -> None:
    """Первое сообщение — согласие продолжать, а не ответ на вопрос."""
    _silence_bridge(monkeypatch)
    handled = await handler.handle_intake_dialog_message(update, context, "давайте")

    assert handled is True
    assert replies == [handler.intake_dialog.QUESTIONS["employment"][0].text]
    assert context.user_data[handler.PENDING_KEY] == "side"


@pytest.mark.anyio
async def test_answers_are_saved_and_questions_advance(context, update, replies, monkeypatch) -> None:
    calls = _silence_bridge(monkeypatch)
    questions = handler.intake_dialog.QUESTIONS["employment"]

    await handler.handle_intake_dialog_message(update, context, "начнём")
    for question in questions:
        await handler.handle_intake_dialog_message(update, context, f"ответ про {question.key}")

    saved_keys = [item[1] for item in calls["clarifications"]]
    assert saved_keys == [question.key for question in questions]
    # Вопросы закончились — перешли к соглашению перед документами.
    assert context.user_data[handler.STAGE_KEY] == handler.STAGE_NDA


@pytest.mark.anyio
async def test_answer_survives_core_api_failure(context, update, replies, monkeypatch) -> None:
    """Сбой сохранения не обрывает разговор: человек этого видеть не должен."""

    def _boom(*args, **kwargs):
        raise RuntimeError("core-api недоступен")

    _silence_bridge(monkeypatch)
    monkeypatch.setattr(handler.core_api_bridge, "record_clarification", _boom)

    await handler.handle_intake_dialog_message(update, context, "начнём")
    handled = await handler.handle_intake_dialog_message(update, context, "работник")

    assert handled is True
    # Диалог идёт дальше: задан следующий вопрос.
    assert replies[-1] == handler.intake_dialog.QUESTIONS["employment"][1].text


@pytest.mark.anyio
async def test_request_for_lawyer_ends_dialog_immediately(context, update, replies, monkeypatch) -> None:
    _silence_bridge(monkeypatch)
    handled = await handler.handle_intake_dialog_message(update, context, "хочу к юристу")

    assert handled is True
    assert handler.STAGE_KEY not in context.user_data
    assert "передаю юристу" in replies[-1].lower()


@pytest.mark.anyio
async def test_already_signed_nda_is_not_offered_again(context, update, replies, monkeypatch) -> None:
    """Клиент подписал соглашение раньше — второе предложение выглядело бы недоверием."""
    _silence_bridge(monkeypatch, nda_status={"signed": True, "version": "v1"})

    await handler.handle_intake_dialog_message(update, context, "начнём")
    for _ in handler.intake_dialog.QUESTIONS["employment"]:
        await handler.handle_intake_dialog_message(update, context, "ответ")

    assert context.user_data[handler.STAGE_KEY] == handler.STAGE_DOCUMENTS
    assert context.user_data[handler.NDA_SIGNED_KEY] is True
    assert "подписано" in replies[-1].lower()


@pytest.mark.anyio
async def test_document_is_registered_with_nda_flag(context, update, replies, monkeypatch) -> None:
    calls = _silence_bridge(monkeypatch)
    context.user_data[handler.STAGE_KEY] = handler.STAGE_DOCUMENTS
    context.user_data[handler.NDA_SIGNED_KEY] = False
    update.effective_message.document = SimpleNamespace(
        file_id="FILE123", file_name="приказ.pdf", file_size=1024, mime_type="application/pdf"
    )

    handled = await handler.handle_intake_dialog_document(update, context)

    assert handled is True
    intake_id, kwargs = calls["documents"][0]
    assert kwargs["telegram_file_id"] == "FILE123"
    assert kwargs["nda_signed_at_upload"] is False
    assert "не подписывалось" in replies[-1]


@pytest.mark.anyio
async def test_photo_is_accepted_as_document(context, update, replies, monkeypatch) -> None:
    """Фотографию документа принимаем: требовать скан — лишний барьер."""
    calls = _silence_bridge(monkeypatch)
    context.user_data[handler.STAGE_KEY] = handler.STAGE_DOCUMENTS
    update.effective_message.photo = [
        SimpleNamespace(file_id="SMALL", file_size=100),
        SimpleNamespace(file_id="LARGE", file_size=9000),
    ]

    await handler.handle_intake_dialog_document(update, context)

    _, kwargs = calls["documents"][0]
    # Берём наибольший размер: мелкая копия нечитаема.
    assert kwargs["telegram_file_id"] == "LARGE"


@pytest.mark.anyio
async def test_failed_document_save_is_reported_to_client(context, update, replies, monkeypatch) -> None:
    """Молчать нельзя: человек считает, что документ у нас, и не пришлёт его снова."""
    _silence_bridge(monkeypatch, document_result=False)
    context.user_data[handler.STAGE_KEY] = handler.STAGE_DOCUMENTS
    update.effective_message.document = SimpleNamespace(
        file_id="FILE", file_name="d.pdf", file_size=10, mime_type="application/pdf"
    )

    handled = await handler.handle_intake_dialog_document(update, context)

    assert handled is True
    assert "не удалось" in replies[-1].lower()
    assert context.user_data[handler.DOCS_COUNT_KEY] == 0


@pytest.mark.anyio
async def test_done_word_hands_over_to_lawyer(context, update, replies, monkeypatch) -> None:
    _silence_bridge(monkeypatch)
    context.user_data[handler.STAGE_KEY] = handler.STAGE_DOCUMENTS
    context.user_data[handler.DOCS_COUNT_KEY] = 2

    await handler.handle_intake_dialog_message(update, context, "готово")

    assert handler.STAGE_KEY not in context.user_data
    assert "документы (2)" in replies[-1]


@pytest.mark.anyio
async def test_documents_ignored_outside_document_stage(context, update, replies, monkeypatch) -> None:
    """На стадии вопросов файл диалогу не принадлежит — пусть его разберут другие обработчики."""
    _silence_bridge(monkeypatch)
    update.effective_message.document = SimpleNamespace(
        file_id="F", file_name=None, file_size=None, mime_type=None
    )

    assert await handler.handle_intake_dialog_document(update, context) is False


@pytest.mark.anyio
async def test_nda_skip_moves_to_documents(context, update, replies, monkeypatch) -> None:
    _silence_bridge(monkeypatch)
    context.user_data[handler.STAGE_KEY] = handler.STAGE_NDA
    query = SimpleNamespace(data="intake_nda:skip", message=update.effective_message)
    update.callback_query = query

    async def _answer(q, **kwargs) -> None:
        return None

    monkeypatch.setattr(handler.utils, "safe_answer_callback", _answer)
    await handler.handle_intake_nda_callback(update, context)

    assert context.user_data[handler.STAGE_KEY] == handler.STAGE_DOCUMENTS
    assert context.user_data[handler.NDA_SIGNED_KEY] is False


@pytest.mark.anyio
async def test_nda_sign_records_hash_of_shown_text(context, update, replies, monkeypatch) -> None:
    """Подпись относится к той редакции, которую человек видел на экране."""
    _silence_bridge(monkeypatch)
    signed: dict = {}

    def _sign(**kwargs):
        signed.update(kwargs)
        return {"signed": True, "already_signed": False}

    async def _answer(q, **kwargs) -> None:
        return None

    monkeypatch.setattr(handler.utils, "safe_answer_callback", _answer)
    monkeypatch.setattr(handler.core_api_bridge, "sign_nda", _sign)

    context.user_data[handler.STAGE_KEY] = handler.STAGE_NDA
    update.callback_query = SimpleNamespace(
        data="intake_nda:sign", message=update.effective_message
    )

    await handler.handle_intake_nda_callback(update, context)

    assert signed["document_hash"] == "abc"
    assert signed["telegram_user_id"] == 42
    assert context.user_data[handler.NDA_SIGNED_KEY] is True
    assert context.user_data[handler.STAGE_KEY] == handler.STAGE_DOCUMENTS


@pytest.mark.anyio
async def test_failed_signing_does_not_block_documents(context, update, replies, monkeypatch) -> None:
    """Отказ подписания не должен стоить клиенту возможности прислать документы."""
    _silence_bridge(monkeypatch)

    async def _answer(q, **kwargs) -> None:
        return None

    monkeypatch.setattr(handler.utils, "safe_answer_callback", _answer)
    monkeypatch.setattr(handler.core_api_bridge, "sign_nda", lambda **kwargs: None)

    context.user_data[handler.STAGE_KEY] = handler.STAGE_NDA
    update.callback_query = SimpleNamespace(
        data="intake_nda:sign", message=update.effective_message
    )

    await handler.handle_intake_nda_callback(update, context)

    assert context.user_data[handler.STAGE_KEY] == handler.STAGE_DOCUMENTS
    assert context.user_data[handler.NDA_SIGNED_KEY] is False


@pytest.mark.anyio
async def test_dialog_survives_bot_restart(update, replies, monkeypatch) -> None:
    """Деплой посреди разговора не должен выглядеть так, будто клиента перестали слушать.

    user_data живёт в памяти процесса. Проверяем, что ход диалога поднимается
    из базы и человек получает следующий вопрос, а не ответ из общей воронки.
    """
    _silence_bridge(monkeypatch)

    before = SimpleNamespace(user_data={})
    handler.start_dialog(
        before.user_data,
        intake_id="11111111-1111-1111-1111-111111111111",
        lead_id="22222222-2222-2222-2222-222222222222",
        legal_area="employment",
        telegram_user_id=42,
    )
    await handler.handle_intake_dialog_message(update, before, "начнём")
    await handler.handle_intake_dialog_message(update, before, "как работник")

    # Процесс перезапустился: память пуста, база — нет.
    after = SimpleNamespace(user_data={})
    handled = await handler.handle_intake_dialog_message(update, after, "уволили 3 сентября")

    assert handled is True
    assert after.user_data[handler.INTAKE_ID_KEY] == "11111111-1111-1111-1111-111111111111"
    # Первый вопрос был отвечён до перезапуска — продолжаем со следующих.
    assert "side" in after.user_data[handler.ANSWERED_KEY]


@pytest.mark.anyio
async def test_completed_dialog_leaves_no_stale_state(update, replies, monkeypatch, dialog_store) -> None:
    """После передачи юристу состояние удаляется: иначе следующее обращение
    подхватит чужие ответы."""
    _silence_bridge(monkeypatch)
    dialog_store[42] = {"intake_dialog_stage": "documents"}

    context = SimpleNamespace(user_data={})
    await handler.handle_intake_dialog_message(update, context, "готово")

    assert 42 not in dialog_store


@pytest.mark.anyio
async def test_database_is_consulted_once_per_process(update, replies, monkeypatch, dialog_store) -> None:
    """Чтение состояния — не на каждое сообщение.

    Случай, ради которого оно нужно, наступает только после перезапуска. Без
    отметки бот ходил бы в базу на каждое сообщение любого пользователя.
    """
    _silence_bridge(monkeypatch)
    reads: list[int] = []

    def _load(user_id: int) -> dict:
        reads.append(user_id)
        return dict(dialog_store.get(user_id, {}))

    monkeypatch.setattr(handler.database.db, "load_intake_dialog_state", _load)

    context = SimpleNamespace(user_data={})
    for _ in range(3):
        await handler.handle_intake_dialog_message(update, context, "здравствуйте")

    assert reads == [42]


@pytest.mark.anyio
async def test_assistant_voices_the_questions(context, update, replies, monkeypatch) -> None:
    """Спрашивает помощник, а не заданный в коде набор."""
    _silence_bridge(
        monkeypatch,
        assistant={"ok": True, "reply": "Понял вас. Какого числа вручили приказ?", "done": False},
    )

    await handler.handle_intake_dialog_message(update, context, "начнём")

    assert replies[-1] == "Понял вас. Какого числа вручили приказ?"
    # Реплика попала в историю: следующий вопрос строится на разговоре.
    history = context.user_data[handler.HISTORY_KEY]
    assert history[-1] == {"role": "assistant", "text": "Понял вас. Какого числа вручили приказ?"}


@pytest.mark.anyio
async def test_client_answers_land_in_the_case_file(context, update, replies, monkeypatch) -> None:
    """Вопрос помощника сохраняется вместе с ответом.

    Формулировки нет в заданном наборе, поэтому в карточку уходит текст
    целиком — иначе через полгода по ключу не восстановить, на что человек
    отвечал.
    """
    calls = _silence_bridge(
        monkeypatch,
        assistant={"ok": True, "reply": "Какого числа вручили приказ?", "done": False},
    )

    await handler.handle_intake_dialog_message(update, context, "начнём")
    await handler.handle_intake_dialog_message(update, context, "третьего сентября")

    intake_id, key, answer = calls["clarifications"][0]
    assert answer == "третьего сентября"
    assert key.startswith("q")


@pytest.mark.anyio
async def test_falls_back_to_scripted_questions(context, update, replies, monkeypatch) -> None:
    """Помощник недоступен — разговор продолжается заданным набором.

    Суше, но не прерывается: для клиента ничего не ломается.
    """
    _silence_bridge(monkeypatch, assistant=None)

    await handler.handle_intake_dialog_message(update, context, "начнём")

    assert replies[-1] == handler.intake_dialog.QUESTIONS["employment"][0].text


@pytest.mark.anyio
async def test_blocked_reply_falls_back_too(context, update, replies, monkeypatch) -> None:
    """Реплика за границей не доходит до клиента.

    core-api вернул отказ — бот не пытается его обойти, а берёт свой вопрос.
    """
    _silence_bridge(
        monkeypatch,
        assistant={"ok": False, "error": "blocked", "blocked_reason": "прогноз", "reply": ""},
    )

    await handler.handle_intake_dialog_message(update, context, "начнём")

    assert replies[-1] == handler.intake_dialog.QUESTIONS["employment"][0].text
    for phrase in ("шанс", "выигр", "рекоменд"):
        assert phrase not in replies[-1].lower()


@pytest.mark.anyio
async def test_assistant_can_end_the_questions(context, update, replies, monkeypatch) -> None:
    """Помощник решил, что сведений достаточно — переходим к соглашению."""
    _silence_bridge(
        monkeypatch,
        assistant={"ok": True, "reply": "Спасибо, картина понятна.", "done": True},
    )

    await handler.handle_intake_dialog_message(update, context, "начнём")

    assert "Спасибо, картина понятна." in replies
    assert context.user_data[handler.STAGE_KEY] == handler.STAGE_NDA


@pytest.mark.anyio
async def test_typing_pause_precedes_every_reply(context, update, monkeypatch) -> None:
    """Мгновенный ответ выдаёт машину и читается как отписка."""
    _silence_bridge(
        monkeypatch, assistant={"ok": True, "reply": "Какого числа?", "done": False}
    )
    actions: list[str] = []
    slept: list[float] = []

    async def _action(chat_id, action):
        actions.append(action)

    async def _sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(handler.human_pace, "typing_delay", lambda text, **kwargs: 2.5)
    monkeypatch.setattr(handler.asyncio, "sleep", _sleep)
    monkeypatch.setattr(handler.utils, "safe_reply_text", lambda *a, **k: _noop())
    update.effective_message.chat = SimpleNamespace(id=42)
    context.bot = SimpleNamespace(send_chat_action=_action)

    async def _noop():
        return None

    await handler.handle_intake_dialog_message(update, context, "начнём")

    assert actions == ["typing"]
    assert slept and abs(sum(slept) - 2.5) < 0.01


@pytest.mark.anyio
async def test_model_latency_counts_toward_the_pause(context, update, monkeypatch) -> None:
    """Секунды работы модели не прибавляются к паузе, а входят в неё.

    Иначе клиент ждал бы ответ модели плюс имитацию набора, и разговор
    становился бы вязким.
    """
    slept: list[float] = []

    async def _sleep(seconds):
        slept.append(seconds)

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(handler.asyncio, "sleep", _sleep)
    monkeypatch.setattr(handler.utils, "safe_reply_text", _noop)
    monkeypatch.setattr(handler.human_pace, "typing_delay", lambda text, **kwargs: 3.0)

    await handler._say(
        SimpleNamespace(chat=None), SimpleNamespace(bot=None), "текст",
        action="test", already_waited=2.0,
    )

    assert abs(sum(slept) - 1.0) < 0.01


@pytest.mark.anyio
async def test_slow_model_leaves_no_extra_pause(context, update, monkeypatch) -> None:
    """Модель думала дольше, чем длилась бы пауза — отправляем сразу."""
    slept: list[float] = []

    async def _sleep(seconds):
        slept.append(seconds)

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(handler.asyncio, "sleep", _sleep)
    monkeypatch.setattr(handler.utils, "safe_reply_text", _noop)
    monkeypatch.setattr(handler.human_pace, "typing_delay", lambda text, **kwargs: 2.0)

    await handler._say(
        SimpleNamespace(chat=None), SimpleNamespace(bot=None), "текст",
        action="test", already_waited=9.0,
    )

    assert slept == []
