"""Уточняющий диалог с клиентом по юридическому обращению.

Сценарий: после первого обращения ассистент задаёт несколько фактических
вопросов, называет область права и нужные документы, предлагает подписать
соглашение о конфиденциальности и принимает материалы. Затем передаёт всё
юристу.

Состояние диалога живёт в context.user_data — оно короткое и не жаль потерять.
А всё содержательное (ответы, документы, подпись) уходит в core-api сразу же:
это материалы обращения, и перезапуск бота не должен стоить клиенту
повторного разговора.
"""

from __future__ import annotations

import asyncio
import logging
import time

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from telegram_ui import inline_button as InlineKeyboardButton

import database
import human_pace
import intake_dialog
import utils
from core_api_bridge import core_api_bridge

logger = logging.getLogger(__name__)

# Ключи состояния.
STAGE_KEY = "intake_dialog_stage"
INTAKE_ID_KEY = "intake_dialog_intake_id"
LEAD_ID_KEY = "intake_dialog_lead_id"
AREA_KEY = "intake_dialog_area"
ANSWERED_KEY = "intake_dialog_answered"
# Сами ответы, а не только ключи вопросов: по ним ориентация выбирает
# ветку внутри составных областей вроде «семья и наследство».
# Отдельным ключом, а не заменой ANSWERED_KEY: в продакшене уже есть
# сохранённые диалоги, и менять их формат на ходу нельзя.
ANSWERS_KEY = "intake_dialog_answers"
# Ход разговора для помощника: он отвечает на сказанное, а не идёт по анкете.
HISTORY_KEY = "intake_dialog_history"
# Что именно спросили последним и под каким ключом это записывать.
PENDING_TEXT_KEY = "intake_dialog_pending_text"
PENDING_KEY = "intake_dialog_pending_question"
DOCS_COUNT_KEY = "intake_dialog_documents"
NDA_SIGNED_KEY = "intake_dialog_nda_signed"
NDA_HASH_KEY = "intake_dialog_nda_hash"
# Отметка «в базу уже заглядывали»: живёт только в памяти и не сохраняется.
RESTORE_CHECKED_KEY = "intake_dialog_restore_checked"

STAGE_ASKING = "asking"
STAGE_NDA = "nda"
STAGE_DOCUMENTS = "documents"

_DONE_WORDS = ("готово", "всё", "все", "закончил", "закончила", "это всё", "больше нет")

_SUPPORTED_DOC_HINT = "PDF, Word, изображения"


def start_dialog(
    user_data: dict,
    *,
    intake_id: str,
    lead_id: str | None,
    legal_area: str | None,
    telegram_user_id: int | None = None,
) -> None:
    """Готовит состояние диалога.

    Принимает словарь, а не context: диалог заводит фоновая задача сразу после
    первого сообщения клиенту, а у неё нет контекста конкретного пользователя —
    только application.user_data[user_id].
    """
    user_data[STAGE_KEY] = STAGE_ASKING
    user_data[INTAKE_ID_KEY] = intake_id
    user_data[LEAD_ID_KEY] = lead_id
    user_data[AREA_KEY] = intake_dialog.normalize_area(legal_area)
    user_data[ANSWERED_KEY] = []
    user_data[ANSWERS_KEY] = {}
    user_data[HISTORY_KEY] = []
    user_data[DOCS_COUNT_KEY] = 0
    for key in (PENDING_KEY, NDA_SIGNED_KEY, NDA_HASH_KEY):
        user_data.pop(key, None)

    # Сразу в базу: между первым сообщением клиенту и его ответом может пройти
    # достаточно времени, чтобы бот успел перезапуститься.
    if telegram_user_id is not None:
        database.db.save_intake_dialog_state(int(telegram_user_id), dict(user_data))


def _persist(context: ContextTypes.DEFAULT_TYPE, user_id: int | None) -> None:
    """Записывает ход диалога, чтобы он пережил перезапуск бота."""
    if user_id is None:
        return
    database.db.save_intake_dialog_state(int(user_id), dict(context.user_data))


def restore_if_needed(context: ContextTypes.DEFAULT_TYPE, user_id: int | None) -> None:
    """Поднимает диалог из базы, если процесс перезапускался.

    user_data живёт в памяти процесса: после деплоя он пуст, и без этого шага
    клиент отвечал бы на заданный вопрос в пустоту.

    В базу заглядываем один раз на пользователя за жизнь процесса. Дальше
    состояние есть в памяти: и фоновая задача, и сам диалог пишут туда же.
    Без этой отметки чтение происходило бы на каждое сообщение любого
    пользователя — ради случая, который наступает только после перезапуска.
    """
    if user_id is None or context.user_data.get(STAGE_KEY):
        return
    if context.user_data.get(RESTORE_CHECKED_KEY):
        return
    context.user_data[RESTORE_CHECKED_KEY] = True
    stored = database.db.load_intake_dialog_state(int(user_id))
    if stored:
        context.user_data.update(stored)


def _finish(context: ContextTypes.DEFAULT_TYPE, user_id: int | None = None) -> None:
    for key in (
        STAGE_KEY,
        PENDING_KEY,
        AREA_KEY,
        ANSWERED_KEY,
        ANSWERS_KEY,
        HISTORY_KEY,
        PENDING_TEXT_KEY,
        NDA_HASH_KEY,
    ):
        context.user_data.pop(key, None)
    context.user_data.pop(RESTORE_CHECKED_KEY, None)
    if user_id is not None:
        database.db.clear_intake_dialog_state(int(user_id))


def nda_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Подписать соглашение", callback_data="intake_nda:sign")],
            [InlineKeyboardButton("Показать текст", callback_data="intake_nda:text")],
            [InlineKeyboardButton("Без соглашения", callback_data="intake_nda:skip")],
        ]
    )


async def _say(
    message,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    *,
    action: str,
    already_waited: float = 0.0,
) -> None:
    """Отправляет реплику так, как её отправил бы человек.

    Индикатор «печатает» и пауза по длине текста. Мгновенный ответ выдаёт
    машину вернее любой формулировки и читается как отписка.

    Время, которое ушло на обращение к модели, засчитывается в паузу, а не
    добавляется к ней: клиент ждёт ответа целиком, и ему всё равно, что
    происходило внутри. Иначе к паузе на «печатает» прибавлялись бы секунды
    работы модели, и разговор становился бы вязким.
    """
    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    remaining = max(0.0, human_pace.typing_delay(text) - max(0.0, already_waited))
    for chunk in human_pace.typing_chunks(remaining):
        if chat_id is not None:
            try:
                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            except Exception:  # noqa: BLE001 — индикатор не стоит разговора
                pass
        await asyncio.sleep(chunk)
    await utils.safe_reply_text(message, text, action=action)


async def _assistant_question(
    context: ContextTypes.DEFAULT_TYPE,
) -> tuple[str, bool] | None:
    """Просит помощника сформулировать следующую реплику.

    Возвращает None при любом сбое: разговор в этом случае продолжается
    заданными в коде вопросами. Суше, но в рамках и без паузы для клиента.
    """
    intake_id = context.user_data.get(INTAKE_ID_KEY)
    if not intake_id:
        return None

    area = intake_dialog.normalize_area(context.user_data.get(AREA_KEY))
    history = list(context.user_data.get(HISTORY_KEY) or [])
    asked = len([item for item in history if item.get("role") == "assistant"])

    try:
        result = await asyncio.to_thread(
            core_api_bridge.assistant_turn,
            str(intake_id),
            history=history,
            base_questions=[q.text for q in intake_dialog.questions_for(area)],
            area_label=intake_dialog.AREA_LABEL[area],
            asked_count=asked,
        )
    except Exception as error:
        logger.warning("Помощник недоступен по обращению %s: %s", intake_id, error)
        return None

    if not isinstance(result, dict) or not result.get("ok") or not result.get("reply"):
        if isinstance(result, dict) and result.get("error"):
            logger.info(
                "Помощник не дал реплику по обращению %s: %s %s",
                intake_id,
                result.get("error"),
                result.get("blocked_reason") or "",
            )
        return None

    return str(result["reply"]), bool(result.get("done"))


async def _ask_next_question(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Задаёт следующий вопрос либо переходит к ориентации и документам.

    Спрашивает помощник: он откликается на сказанное и решает, нужны ли
    уточнения сверх базовых. Если он недоступен или вышел за границу, работает
    заданный в коде набор — разговор станет суше, но не прервётся.
    """
    area = context.user_data.get(AREA_KEY)

    started = time.monotonic()
    reply = await _assistant_question(context)
    spent = time.monotonic() - started
    if reply is not None:
        text, done = reply
        history = list(context.user_data.get(HISTORY_KEY) or [])
        history.append({"role": "assistant", "text": text})
        context.user_data[HISTORY_KEY] = history
        if not done:
            asked = len([item for item in history if item.get("role") == "assistant"])
            context.user_data[PENDING_KEY] = f"q{asked}"
            context.user_data[PENDING_TEXT_KEY] = text
            await _say(
                message, context, text, action="intake_dialog_question", already_waited=spent
            )
            return
        # Помощник считает, что сведений достаточно: реплику всё равно
        # показываем — она подводит итог разговора, — и переходим дальше.
        await _say(
            message,
            context,
            text,
            action="intake_dialog_question_last",
            already_waited=spent,
        )

    else:
        answered = context.user_data.get(ANSWERED_KEY) or []
        question = intake_dialog.next_question(area, answered)
        if question is not None:
            context.user_data[PENDING_KEY] = question.key
            context.user_data[PENDING_TEXT_KEY] = question.text
            await _say(message, context, question.text, action="intake_dialog_question")
            return

    # Вопросы закончились: называем область права и нужные документы, затем
    # предлагаем соглашение — до того, как человек начнёт присылать материалы.
    context.user_data.pop(PENDING_KEY, None)
    context.user_data.pop(PENDING_TEXT_KEY, None)
    await _say(
        message,
        context,
        intake_dialog.build_orientation(area, context.user_data.get(ANSWERS_KEY)),
        action="intake_dialog_orientation",
    )
    await _offer_nda(message, context)


async def _offer_nda(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Предлагает подписать соглашение перед передачей документов."""
    lead_id = context.user_data.get(LEAD_ID_KEY)

    # Клиент мог подписать соглашение раньше — по другому обращению. Второе
    # предложение подписать выглядело бы так, будто первое не в счёт.
    if lead_id:
        status = await asyncio.to_thread(core_api_bridge.get_nda_status, str(lead_id))
        if isinstance(status, dict) and status.get("signed"):
            context.user_data[NDA_SIGNED_KEY] = True
            context.user_data[STAGE_KEY] = STAGE_DOCUMENTS
            await utils.safe_reply_text(
                message,
                intake_dialog.build_document_request(
                    context.user_data.get(AREA_KEY), nda_signed=True
                ),
                action="intake_dialog_documents_nda_known",
            )
            return

    context.user_data[STAGE_KEY] = STAGE_NDA
    await utils.safe_reply_text(
        message,
        intake_dialog.build_nda_offer(),
        reply_markup=nda_markup(),
        action="intake_dialog_nda_offer",
    )


async def _go_to_documents(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[STAGE_KEY] = STAGE_DOCUMENTS
    await utils.safe_reply_text(
        message,
        intake_dialog.build_document_request(
            context.user_data.get(AREA_KEY),
            nda_signed=bool(context.user_data.get(NDA_SIGNED_KEY)),
        ),
        action="intake_dialog_documents",
    )


async def _handoff(
    message,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    early: bool,
    user_id: int | None,
) -> None:
    """Завершает диалог и передаёт материалы юристу."""
    if early:
        text = intake_dialog.build_early_handoff()
    else:
        text = intake_dialog.build_handoff(
            documents_count=int(context.user_data.get(DOCS_COUNT_KEY) or 0),
            answered_count=len(context.user_data.get(ANSWERED_KEY) or []),
        )
    _finish(context, user_id)
    await utils.safe_reply_text(message, text, action="intake_dialog_handoff")


async def handle_intake_dialog_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    message_text: str,
) -> bool:
    """Обрабатывает сообщение клиента в рамках диалога.

    Возвращает True, если сообщение принадлежит диалогу и обработано.
    """
    user_id = getattr(update.effective_user, "id", None)

    # Процесс мог перезапуститься на середине разговора — поднимаем ход
    # диалога из базы, прежде чем решать, наш ли это случай.
    restore_if_needed(context, user_id)

    stage = context.user_data.get(STAGE_KEY)
    if not stage:
        return False

    message = update.effective_message
    text = (message_text or "").strip()
    if not text:
        return False

    # Просьба позвать юриста прекращает расспросы на любом шаге. Продолжать
    # после неё — значит не слышать человека.
    if intake_dialog.wants_lawyer(text):
        await _handoff(message, context, early=True, user_id=user_id)
        return True

    if stage == STAGE_ASKING:
        pending = context.user_data.get(PENDING_KEY)
        if not pending:
            # Диалог только начался: первое сообщение — согласие продолжать,
            # а не ответ на вопрос.
            await _ask_next_question(message, context)
            _persist(context, user_id)
            return True

        # Текст вопроса берём из состояния: спрашивать мог помощник, и тогда
        # формулировки нет в заданном наборе. В карточку вопрос уходит
        # целиком — через полгода по одному ключу не восстановить, на что
        # человек отвечал.
        question_text = context.user_data.get(PENDING_TEXT_KEY) or _base_question_text(
            context, pending
        )
        if question_text:
            await _record_answer(
                context, question_key=pending, question_text=question_text, answer=text
            )
            answered = list(context.user_data.get(ANSWERED_KEY) or [])
            if pending not in answered:
                answered.append(pending)
            context.user_data[ANSWERED_KEY] = answered
            answers = dict(context.user_data.get(ANSWERS_KEY) or {})
            answers[pending] = text
            context.user_data[ANSWERS_KEY] = answers

        history = list(context.user_data.get(HISTORY_KEY) or [])
        history.append({"role": "client", "text": text})
        context.user_data[HISTORY_KEY] = history

        await _ask_next_question(message, context)
        _persist(context, user_id)
        return True

    if stage == STAGE_NDA:
        # Человек написал текстом вместо нажатия кнопки — это не ошибка,
        # просто продолжаем без соглашения.
        await _go_to_documents(message, context)
        _persist(context, user_id)
        return True

    if stage == STAGE_DOCUMENTS:
        if text.lower() in _DONE_WORDS:
            await _handoff(message, context, early=False, user_id=user_id)
            return True
        await utils.safe_reply_text(
            message,
            "Принял. Документы можно прислать файлами "
            f"({_SUPPORTED_DOC_HINT}), а когда закончите — напишите «готово».",
            action="intake_dialog_documents_hint",
        )
        return True

    return False


def _base_question_text(context: ContextTypes.DEFAULT_TYPE, key: str) -> str:
    """Формулировка заданного в коде вопроса по его ключу."""
    for item in intake_dialog.questions_for(context.user_data.get(AREA_KEY)):
        if item.key == key:
            return item.text
    return ""


async def _record_answer(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    question_key: str,
    question_text: str,
    answer: str,
) -> None:
    """Отправляет ответ в core-api. Сбой не прерывает разговор."""
    intake_id = context.user_data.get(INTAKE_ID_KEY)
    if not intake_id:
        return
    try:
        await asyncio.to_thread(
            core_api_bridge.record_clarification,
            str(intake_id),
            question_key=question_key,
            question_text=question_text,
            answer_text=answer[:4000],
        )
    except Exception as error:
        # Ответ потерян для карточки, но человек об этом знать не должен:
        # для него разговор идёт нормально, а юрист увидит описание обращения.
        logger.warning("Не удалось сохранить ответ по обращению %s: %s", intake_id, error)


async def handle_intake_dialog_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """Принимает документ или фотографию в рамках диалога."""
    restore_if_needed(context, getattr(update.effective_user, "id", None))
    if context.user_data.get(STAGE_KEY) != STAGE_DOCUMENTS:
        return False

    message = update.effective_message
    if not message:
        return False

    document = getattr(message, "document", None)
    photos = getattr(message, "photo", None)

    if document is not None:
        file_id = document.file_id
        file_name = document.file_name
        file_size = document.file_size
        mime_type = document.mime_type
    elif photos:
        # У фотографии несколько размеров; берём последний — он наибольший.
        largest = photos[-1]
        file_id = largest.file_id
        file_name = None
        file_size = largest.file_size
        mime_type = "image/jpeg"
    else:
        return False

    intake_id = context.user_data.get(INTAKE_ID_KEY)
    nda_signed = bool(context.user_data.get(NDA_SIGNED_KEY))

    saved = False
    if intake_id:
        try:
            saved = await asyncio.to_thread(
                core_api_bridge.record_intake_document,
                str(intake_id),
                telegram_file_id=file_id,
                file_name=file_name,
                file_size=file_size,
                mime_type=mime_type,
                nda_signed_at_upload=nda_signed,
            )
        except Exception as error:
            logger.warning("Не удалось сохранить документ по обращению %s: %s", intake_id, error)

    if not saved:
        # Здесь молчать нельзя: человек считает, что документ у нас, и может
        # не прислать его повторно.
        await utils.safe_reply_text(
            message,
            "Файл получен, но записать его в обращение не удалось. "
            "Юрист об этом узнает и попросит прислать ещё раз — приносим извинения.",
            action="intake_dialog_document_failed",
        )
        return True

    count = int(context.user_data.get(DOCS_COUNT_KEY) or 0) + 1
    context.user_data[DOCS_COUNT_KEY] = count
    _persist(context, getattr(update.effective_user, "id", None))
    await utils.safe_reply_text(
        message,
        intake_dialog.build_document_accepted(count=count, nda_signed=nda_signed),
        action="intake_dialog_document_accepted",
    )
    return True


async def handle_intake_nda_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Кнопки под предложением подписать соглашение."""
    query = update.callback_query
    if not query:
        return
    await utils.safe_answer_callback(query, action="intake_nda_callback")

    action = (query.data or "").partition(":")[2]
    message = query.message
    user = update.effective_user
    restore_if_needed(context, getattr(user, "id", None))

    if action == "text":
        document = await asyncio.to_thread(core_api_bridge.get_nda_document)
        if not isinstance(document, dict) or not document.get("text"):
            await utils.safe_reply_text(
                message,
                "Не удалось загрузить текст соглашения. Можно продолжить без него — "
                "документы примем и так.",
                reply_markup=nda_markup(),
                action="intake_nda_text_failed",
            )
            return
        # Запоминаем контрольную сумму показанного текста: подпись должна
        # относиться именно к той редакции, которую человек прочитал.
        context.user_data[NDA_HASH_KEY] = document.get("hash")
        await utils.safe_reply_text(
            message, str(document["text"])[:4000], action="intake_nda_text"
        )
        await utils.safe_reply_text(
            message,
            "Подписать?",
            reply_markup=nda_markup(),
            action="intake_nda_text_confirm",
        )
        return

    if action == "skip":
        context.user_data[NDA_SIGNED_KEY] = False
        await _go_to_documents(message, context)
        _persist(context, getattr(user, "id", None))
        return

    if action != "sign":
        return

    lead_id = context.user_data.get(LEAD_ID_KEY)
    if not lead_id:
        logger.warning("Подписание NDA без известного lead_id")
        context.user_data[NDA_SIGNED_KEY] = False
        await _go_to_documents(message, context)
        _persist(context, getattr(user, "id", None))
        return

    document_hash = context.user_data.get(NDA_HASH_KEY)
    if not document_hash:
        # Клиент подписывает, не открыв текст. Хеш всё равно нужен: подпись
        # должна относиться к конкретной редакции, а не к «документу вообще».
        document = await asyncio.to_thread(core_api_bridge.get_nda_document)
        if isinstance(document, dict):
            document_hash = document.get("hash")

    result = await asyncio.to_thread(
        core_api_bridge.sign_nda,
        lead_id=str(lead_id),
        telegram_user_id=getattr(user, "id", None),
        telegram_username=getattr(user, "username", None),
        signer_name=getattr(user, "full_name", None),
        document_hash=str(document_hash or ""),
    )

    if not isinstance(result, dict) or not result.get("signed"):
        await utils.safe_reply_text(
            message,
            "Не удалось зафиксировать подписание. Продолжим без соглашения — "
            "документы примем, а отметку об этом юрист увидит в карточке.",
            action="intake_nda_sign_failed",
        )
        context.user_data[NDA_SIGNED_KEY] = False
        await _go_to_documents(message, context)
        _persist(context, getattr(user, "id", None))
        return

    context.user_data[NDA_SIGNED_KEY] = True
    await _go_to_documents(message, context)
    _persist(context, getattr(user, "id", None))
