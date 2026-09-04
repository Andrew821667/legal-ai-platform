"""Никита — помощник юриста, который ведёт первичный разговор с клиентом.

Зачем персонаж. Обращение приходит в тяжёлый момент: развод, долги, увольнение.
Человек, которому отвечает безымянная система, чувствует себя в очереди.
Человек, которому отвечает конкретный помощник, — что за его делом кто-то
следит. Разница не косметическая: от неё зависит, расскажет ли он
обстоятельства или ограничится парой строк.

Что Никита говорит о себе. Он представляется ИИ-помощником юриста. Это не
формальность: клиент раскрывает ему обстоятельства своей жизни, и он должен
понимать, кому. Скрыть это — значит выиграть немного доверия сейчас и потерять
всё, когда человек узнает. Роль при этом настоящая: он действительно собирает
информацию для юриста, и именно так себя и называет.

Где проходит граница. Никита спрашивает и ориентирует, но не оценивает
ситуацию по существу и не советует, что делать. Раньше эту границу держала
структура кода — вопросы были жёстко заданы, и отступить от них было
невозможно. Теперь говорит модель, поэтому граница держится трижды: правилами
в промпте, ограничением на роль реплики и проверкой готового текста перед
отправкой.

Базовые вопросы остаются заданными в коде: они выверены и одинаковы для всех.
Модель решает только, нужны ли уточнения сверх них — от трёх до семи вопросов
всего, в зависимости от того, насколько понятной вышла картина.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from core_api.model_client import DEFAULT_MODEL, ChatResult, chat

logger = logging.getLogger(__name__)

DEFAULT_ASSISTANT_NAME = "Никита"

# Сколько вопросов всего можно задать. Нижняя граница — базовый набор, он
# задан в коде. Верхняя — предел, за которым разговор превращается в допрос:
# человек пришёл за помощью, а не заполнять анкету.
MIN_QUESTIONS = 3
MAX_QUESTIONS = 7

# Обороты, которых в реплике клиенту быть не должно.
#
# Это не защита от злого умысла, а страховка от дрейфа: модель, которую просят
# быть полезной, естественно сползает к совету. Проверка грубая и намеренно
# такая — она ловит явные формы, а тонкие случаи закрывает промпт.
_FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bя\s+рекоменду", "совет"),
    (r"\bсоветую\b", "совет"),
    (r"\bвам\s+(?:следует|нужно|стоит)\s+(?:подать|обратиться\s+в\s+суд|взыскать|оспорить)", "совет"),
    (r"\bу\s+вас\s+(?:хорошие|высокие|неплохие)\s+шансы", "прогноз"),
    (r"\bсуд\s+(?:встанет|примет\s+вашу\s+сторону)", "прогноз"),
    (r"\bвы\s+(?:правы|в\s+своём\s+праве)\b", "оценка"),
    (r"\b(?:это|действия?)\s+(?:незаконн|неправомерн)", "оценка"),
    (r"\bнарушени[ея]\s+ваших\s+прав", "оценка"),
    (r"\bдело\s+(?:выигрышн|проигрышн)", "прогноз"),
    (r"\bсогласно\s+стать[ье]", "правовая норма"),
    (r"\bст\.\s*\d+", "правовая норма"),
)


@dataclass(frozen=True)
class AssistantTurn:
    """Реплика помощника и решение, продолжать ли расспросы."""

    text: str
    finished: bool
    cost_usd: float = 0.0
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: str | None = None
    blocked_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text)


def check_reply(text: str) -> str | None:
    """Возвращает причину, по которой реплику нельзя отправлять клиенту."""
    lowered = (text or "").lower()
    for pattern, reason in _FORBIDDEN_PATTERNS:
        if re.search(pattern, lowered):
            return reason
    return None


def build_system_prompt(
    *,
    assistant_name: str,
    area_label: str,
    base_questions: list[str],
    asked_count: int,
) -> str:
    """Системный промпт: кто такой помощник и чего он не делает."""
    remaining = max(0, MAX_QUESTIONS - asked_count)
    questions_block = "\n".join(f"— {item}" for item in base_questions) or "— (нет)"

    return (
        f"Тебя зовут {assistant_name}. Ты ИИ-помощник юриста в практике AI Verdict.\n"
        "Твоя работа — собрать у клиента предварительные сведения по его обращению, "
        "чтобы юрист начал разговор подготовленным.\n\n"
        f"Обращение относится к области: {area_label}.\n\n"
        "Базовые вопросы, которые нужно закрыть:\n"
        f"{questions_block}\n\n"
        "Как вести разговор:\n"
        "— задавай ровно один вопрос за реплику;\n"
        "— сначала коротко откликнись на то, что человек сказал, потом спрашивай;\n"
        "— спрашивай об обстоятельствах: что произошло, когда, есть ли документ;\n"
        "— если ответ понятен и полон, не переспрашивай ради вежливости;\n"
        f"— всего вопросов не больше {MAX_QUESTIONS}; сейчас задано {asked_count}, "
        f"осталось не больше {remaining};\n"
        "— уточняй сверх базовых вопросов только когда без этого картина неполная.\n\n"
        "Чего не делай никогда:\n"
        "— не оценивай ситуацию по существу и не говори, кто прав;\n"
        "— не предсказывай исход дела и не оценивай шансы;\n"
        "— не советуй, что делать, и не предлагай подать иск или обратиться куда-либо;\n"
        "— не ссылайся на статьи законов и не называй нормы;\n"
        "— не обещай сроки, стоимость и результат.\n"
        "Правовую оценку даёт юрист. Твоя задача — расспросить и передать.\n\n"
        "Как писать:\n"
        "— по-русски, простыми словами, тепло и уважительно;\n"
        "— как пишет живой человек: короткими абзацами, без канцелярита;\n"
        "— без восклицательных знаков и без бодрости — люди приходят с бедой;\n"
        "— две-четыре строки, не длиннее.\n\n"
        "Если тебя спрашивают, человек ли ты, — отвечай прямо, что ИИ-помощник, "
        "и что юрист посмотрит материалы сам.\n\n"
        "Ответ верни строгим JSON без пояснений:\n"
        '{"reply": "текст для клиента", "done": false}\n'
        'Поле done ставь true, когда сведений достаточно и пора переходить к документам.'
    )


def _history_block(history: list[dict[str, str]]) -> str:
    lines = []
    for item in history:
        role = "Клиент" if item.get("role") == "client" else "Ты"
        lines.append(f"{role}: {item.get('text', '')}")
    return "\n".join(lines) or "(разговор только начинается)"


def next_turn(
    *,
    intake: dict[str, object],
    history: list[dict[str, str]],
    base_questions: list[str],
    area_label: str,
    asked_count: int,
    api_key: str,
    assistant_name: str = DEFAULT_ASSISTANT_NAME,
    base_url: str = "https://api.openai.com/v1",
    model: str = DEFAULT_MODEL,
    proxy_url: str | None = None,
    timeout: float = 45.0,
) -> AssistantTurn:
    """Следующая реплика помощника.

    Сбой модели не должен обрывать разговор: вызывающая сторона в этом случае
    возвращается к заданным в коде вопросам. Поэтому ошибки не выбрасываются, а
    возвращаются полем error.
    """
    result: ChatResult = chat(
        [
            {
                "role": "system",
                "content": build_system_prompt(
                    assistant_name=assistant_name,
                    area_label=area_label,
                    base_questions=base_questions,
                    asked_count=asked_count,
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Обращение клиента: {intake.get('description') or 'не указано'}\n\n"
                    f"Разговор:\n{_history_block(history)}"
                ),
            },
        ],
        api_key=api_key,
        base_url=base_url,
        model=model,
        proxy_url=proxy_url,
        timeout=timeout,
        max_output_tokens=400,
        response_format={"type": "json_object"},
    )

    if not result.ok:
        return AssistantTurn(
            text="",
            finished=False,
            cost_usd=result.cost_usd,
            model=result.model,
            error=result.error or "empty_reply",
        )

    try:
        parsed = json.loads(result.text)
        reply = str(parsed.get("reply") or "").strip()
        finished = bool(parsed.get("done"))
    except (ValueError, AttributeError):
        # Модель ответила не JSON. Текст мог быть осмысленным, но разбирать
        # его догадками — значит отправить клиенту неизвестно что.
        return AssistantTurn(
            text="",
            finished=False,
            cost_usd=result.cost_usd,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            error="bad_json",
        )

    if not reply:
        return AssistantTurn(
            text="",
            finished=False,
            cost_usd=result.cost_usd,
            model=result.model,
            error="empty_reply",
        )

    blocked = check_reply(reply)
    if blocked:
        # Реплика перешла границу. Отправлять нельзя, и переспрашивать модель
        # тоже: она уже показала, куда её ведёт. Возвращаемся к заданным
        # вопросам — разговор станет суше, но останется в рамках.
        logger.warning("assistant_reply_blocked", extra={"reason": blocked})
        return AssistantTurn(
            text="",
            finished=False,
            cost_usd=result.cost_usd,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            error="blocked",
            blocked_reason=blocked,
        )

    return AssistantTurn(
        text=reply,
        finished=finished or asked_count >= MAX_QUESTIONS,
        cost_usd=result.cost_usd,
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
