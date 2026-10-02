"""Сообщение юристу по конкретному делу — вход из клиентского кабинета.

Кнопка «Написать по делу» в кабинете открывает бота с `/start case_<id>`.
До этого бот такой payload не знал: обработчик /start молча пропускал его,
приветствие при payload не показывается, и человек, нажавший кнопку,
оказывался в пустом чате без единого слова.

Здесь бот подтверждает, какое дело открыто, и следующие сообщения клиента
уходят юристу с пометкой этого дела: в карточку обращения (раздел «Что
уточнили») и уведомлением в Telegram. Контекст дела живёт недолго: клиент
обычно пишет одно-три сообщения подряд, а через полчаса чат должен снова
вести себя как обычно, а не тянуть всё подряд в старое дело.
"""

from __future__ import annotations

import logging
import re
import time

import utils
from config import get_config
from core_api_bridge import core_api_bridge
from handlers.constants import lawyer_workspace_button
from intake_dialog import AREA_LABEL

logger = logging.getLogger(__name__)
config = get_config()

CASE_START_PAYLOAD_RE = re.compile(r"^case_(?P<intake_id>[0-9a-fA-F-]{36})$")
CASE_CONTEXT_KEY = "case_message_context"
CASE_CONTEXT_TTL_SECONDS = 30 * 60

_STATUS_LABEL = {
    "received": "получено",
    "needs_clarification": "уточняем детали",
    "conflict_check": "проверка конфликта интересов",
    "proposal_sent": "условия отправлены",
    "accepted": "в работе",
    "declined": "отклонено",
    "closed": "закрыто",
}


def case_title(case: dict) -> str:
    """Название дела так же, как в кабинете: категория — для инженерной и гибридной практики, область права — для юридической."""
    # Импорт здесь: engineering_help тянет user_commands, а тот — этот модуль.
    from handlers.engineering_help import CATEGORIES_BY_PRACTICE

    practice = str(case.get("practice") or "legal")
    if practice != "legal":
        categories = CATEGORIES_BY_PRACTICE.get(practice, {})
        return categories.get(str(case.get("category") or ""), "Задача для команды")
    return AREA_LABEL.get(str(case.get("legal_area") or ""), AREA_LABEL["other"])


def _find_case(telegram_user_id: int, intake_id: str) -> tuple[dict | None, str | None]:
    """Дело клиента по идентификатору — только среди его собственных обращений.

    Идентификатор приходит из ссылки, а ссылку можно подделать: чужое дело
    по ней открыться не должно, поэтому ищем через сводку по telegram_user_id,
    а не по самому идентификатору.
    """
    summary = core_api_bridge.client_portal_summary(telegram_user_id)
    if not isinstance(summary, dict):
        return None, None
    wanted = intake_id.lower()
    for case in summary.get("cases") or []:
        if str(case.get("id") or "").lower() == wanted:
            return case, (summary.get("client") or {}).get("lead_id")
    return None, None


def _created_label(case: dict) -> str:
    raw = str(case.get("created_at") or "")
    return f" от {raw[8:10]}.{raw[5:7]}.{raw[:4]}" if len(raw) >= 10 else ""


async def handle_case_start_payload(*, message, context, user, intake_id: str) -> bool:
    case, lead_id = _find_case(int(user.id), intake_id)
    if case is None:
        await utils.safe_reply_text(
            message,
            "Не нашёл это дело среди ваших обращений. Откройте кабинет заново "
            "или просто напишите здесь, что случилось, — разберёмся.",
            action="case_start_not_found",
        )
        return True

    title = case_title(case)
    context.user_data[CASE_CONTEXT_KEY] = {
        "intake_id": str(case.get("id")),
        "lead_id": lead_id,
        "title": title,
        "until": time.time() + CASE_CONTEXT_TTL_SECONDS,
    }
    status = _STATUS_LABEL.get(str(case.get("status") or ""), "")
    status_line = f" · {status}" if status else ""
    await utils.safe_reply_text(
        message,
        f"📁 Дело: {title}{_created_label(case)}{status_line}.\n\n"
        "Напишите, что хотите передать юристу по этому делу, — сообщение "
        "уйдёт ему с пометкой дела, и он ответит вам здесь.",
        action="case_start_opened",
    )
    return True


def _active_case(context) -> dict | None:
    state = (context.user_data or {}).get(CASE_CONTEXT_KEY)
    if not isinstance(state, dict) or not state.get("intake_id"):
        return None
    if float(state.get("until") or 0) < time.time():
        context.user_data.pop(CASE_CONTEXT_KEY, None)
        return None
    return state


def clear_case_context(context) -> None:
    (context.user_data or {}).pop(CASE_CONTEXT_KEY, None)


async def maybe_handle_case_message(*, update, context, original_message, message_text: str, user, user_data) -> bool:
    """Переправляет сообщение юристу, если клиент пришёл из кабинета по делу."""
    state = _active_case(context)
    if state is None:
        return False
    text = (message_text or "").strip()
    if not text:
        return False

    intake_id = str(state["intake_id"])
    title = str(state.get("title") or "дело")
    # В общую переписку по делу: юрист видит её в карточке клиента, клиент — в
    # кабинете. Уведомление юристу ставит ядро — без имени и текста клиента.
    recorded = core_api_bridge.post_case_message(intake_id, telegram_user_id=int(user.id), text=text)

    delivered = False
    if not recorded:
        # Ядро не ответило — текст не должен пропасть: юристу, но без имени,
        # а телефоны, почта и документы в тексте — метками (Telegram за рубежом).
        import pii

        names = tuple(n for n in (user_data.get("first_name"), user_data.get("last_name")) if n)
        masked = pii.Masker(known_names=names).mask(text[:3000])
        notice = (
            f"💬 Сообщение клиента по делу «{title}» не записалось в систему — ядро не ответило.\n\n"
            f"{masked}"
        )
        markup = lawyer_workspace_button(state.get("lead_id"), label="Открыть карточку")
        try:
            await utils.safe_send_message(
                context.bot,
                action="case_message_notify",
                chat_id=config.ADMIN_TELEGRAM_ID,
                text=notice,
                reply_markup=markup,
            )
            delivered = True
        except Exception as error:  # noqa: BLE001 — клиент не должен видеть падение доставки
            logger.warning("Case message notification failed: %s", type(error).__name__)

    # Окно продлевается: следующее сообщение того же разговора — тоже по делу.
    state["until"] = time.time() + CASE_CONTEXT_TTL_SECONDS
    if recorded or delivered:
        reply = f"Передал юристу по делу «{title}». Ответ придёт сюда же и в личный кабинет на сайте."
    else:
        reply = (
            "Не получилось передать сообщение прямо сейчас. Попробуйте ещё раз "
            "через минуту или напишите юристу через кабинет."
        )
    await utils.safe_reply_text(original_message, reply, action="case_message_forwarded")
    return True


async def handle_case_callback(update, context) -> None:
    """Кнопка «Ответить по делу» под ответом юриста: открыть дело в чате."""
    query = update.callback_query
    if query is None or query.from_user is None:
        return
    await utils.safe_answer_callback(query, action="case_reply_answer")
    intake_id = (query.data or "").removeprefix("case:")
    if not CASE_START_PAYLOAD_RE.match(f"case_{intake_id}"):
        return
    await handle_case_start_payload(message=query.message, context=context, user=query.from_user, intake_id=intake_id)
