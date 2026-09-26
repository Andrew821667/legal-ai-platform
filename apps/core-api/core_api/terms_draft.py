"""Черновик условий договора по обращению — одной кнопкой в рабочем месте.

Юрист по каждому обращению набирал предмет, объём работ, исключения и сроки
руками, хотя всё нужное уже лежит в описании клиента и в его же заготовках.
Здесь модель раскладывает обращение по полям формы договора, а юрист правит
и составляет договор как обычно: в документ без его правки ничего не уходит.

Деньги модель не предлагает. Стоимость, сумма и порядок оплаты берутся
дословно из заготовки, на которую модель сослалась, — или остаются пустыми.
Придуманная цена в договоре хуже пустого поля: пустое юрист заметит.

Граница та же, что у разбора обращения: ни правовых оценок, ни обещаний
результата, ни фактов, которых нет в обращении. Промпт это запрещает, а
готовый текст проверяется на обещания исхода — найденное юрист видит
предупреждением, а не узнаёт от клиента.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from core_api.lead_notifications import (
    _LEGAL_AREA_LABELS,
    _LEGAL_CLIENT_LABELS,
    _LEGAL_URGENCY_LABELS,
)
from core_api.model_client import DEFAULT_MODEL, chat
from core_api.models import AgreementTemplate, LegalIntake, Practice

logger = logging.getLogger(__name__)

# Поля, которые модель пишет сама, и их пределы — те же, что у AgreementCreate:
# длиннее ядро договор не примет.
TEXT_FIELDS: dict[str, int] = {
    "subject": 4000,
    "scope_text": 6000,
    "exclusions_text": 2000,
    "schedule_text": 2000,
}
# Поля только из заготовки: деньги и порядок оплаты.
MONEY_FIELDS = ("price_text", "payment_terms")

# Сколько заготовок показать модели как образцы: больше — дороже и не точнее.
MAX_TEMPLATES = 3
MAX_NOTES = 5

_PRACTICE_LABELS = {
    Practice.legal: "Юридическая практика",
    Practice.engineering: "Разработка",
    Practice.hybrid: "Автоматизация юридической функции",
}

SYSTEM_PROMPT = (
    "Ты помогаешь юристу практики AI Verdict составить условия договора об оказании "
    "услуг по обращению клиента. Юрист прочитает и поправит всё, что ты предложишь.\n\n"
    "Верни JSON-объект с ключами:\n"
    "subject — предмет: какую услугу и по какому вопросу оказывает исполнитель, "
    "одно-два предложения;\n"
    "scope_text — что входит: нумерованный список конкретных действий исполнителя, "
    "три-семь пунктов, только то, что нужно по этому обращению;\n"
    "exclusions_text — что не входит без отдельного согласования, коротко;\n"
    "schedule_text — сроки выполнения в рабочих днях; если клиент назвал свой срок, "
    "учти его;\n"
    "template — номер заготовки, условия которой ближе всего к обращению, "
    "или null, если ни одна не подходит;\n"
    "notes — список из одной-четырёх коротких строк: что юристу проверить или "
    "уточнить у клиента до отправки договора.\n\n"
    "Если подходящая заготовка есть, бери её формулировки за основу и меняй только "
    "то, что отличается в этом обращении.\n\n"
    "Строгие ограничения:\n"
    "— не давай правовых оценок ситуации и не предсказывай исход дела;\n"
    "— не обещай результат: ни выигрыша, ни возврата денег, ни гарантий;\n"
    "— не называй стоимость и порядок оплаты — их юрист берёт из заготовки или "
    "указывает сам;\n"
    "— не называй статьи законов, суммы, даты, имена и организации, которых нет в "
    "обращении;\n"
    "— если данных мало, пиши условия в общем виде и отметь это в notes, а не "
    "достраивай ситуацию догадками.\n\n"
    "Пиши по-русски, деловым языком договора, без канцелярита и без воды."
)

# Обещания исхода: модель их не должна писать, но если написала — юрист должен
# увидеть это до того, как текст уйдёт клиенту.
# «Гарантирует конфиденциальность» — обычное условие, поэтому ловим гарантию
# именно исхода.
_PROMISES = re.compile(
    r"гарант\w*\s+(\w+\s+)?(положительн|успе|результат|выигрыш|возврат|победу)|"
    r"выиграем|выиграть дело|добь[её]мся|обязательно\s+(получ|верн|взыщ)|"
    r"100\s*%\s*(результат|успех)",
    re.IGNORECASE,
)


@dataclass
class TermsDraft:
    """Предложенные поля формы договора и то, что юристу стоит проверить."""

    fields: dict[str, str] = field(default_factory=dict)
    amount_minor: int | None = None
    template: AgreementTemplate | None = None
    notes: list[str] = field(default_factory=list)
    model: str = DEFAULT_MODEL
    cost_usd: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _intake_block(intake: LegalIntake) -> str:
    parts = [f"Описание: {intake.description or 'не указано'}"]
    practice = intake.practice
    if practice is not None:
        parts.append(f"Направление практики: {_PRACTICE_LABELS.get(practice, practice.value)}")
    if practice in (None, Practice.legal) and intake.legal_area is not None:
        parts.append(f"Область права: {_LEGAL_AREA_LABELS.get(intake.legal_area.value, intake.legal_area.value)}")
    elif intake.category:
        parts.append(f"Категория: {intake.category}")
    if intake.client_type is not None:
        parts.append(f"Клиент: {_LEGAL_CLIENT_LABELS.get(intake.client_type.value, intake.client_type.value)}")
    if intake.urgency is not None:
        parts.append(f"Срочность: {_LEGAL_URGENCY_LABELS.get(intake.urgency.value, intake.urgency.value)}")
    if intake.deadline:
        parts.append(f"Срок, названный клиентом: {intake.deadline}")
    if intake.region:
        parts.append(f"Регион: {intake.region}")
    return "\n".join(parts)


def _templates_block(templates: list[AgreementTemplate]) -> str:
    if not templates:
        return "Заготовок нет — template всегда null."
    blocks = []
    for number, template in enumerate(templates, start=1):
        # Цену и оплату модели не показываем: предлагать их она не должна, а
        # увиденное легко «подправить».
        blocks.append(
            "\n".join(
                [
                    f"Заготовка {number} «{template.name}»",
                    f"Предмет: {template.subject}",
                    f"Что входит: {template.scope_text}",
                    f"Не входит: {template.exclusions_text}",
                    f"Сроки: {template.schedule_text}",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_messages(intake: LegalIntake, templates: list[AgreementTemplate]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Обращение клиента\n{_intake_block(intake)}\n\nЗаготовки юриста\n{_templates_block(templates)}",
        },
    ]


def _text(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def parse_reply(raw: str, templates: list[AgreementTemplate]) -> TermsDraft:
    """Ответ модели → поля формы. Не JSON — черновика нет, догадками не разбираем."""
    try:
        data = json.loads(raw)
    except ValueError:
        return TermsDraft(error="bad_json")
    if not isinstance(data, dict):
        return TermsDraft(error="bad_json")

    fields = {key: _text(data.get(key), limit) for key, limit in TEXT_FIELDS.items()}
    if not fields["subject"] and not fields["scope_text"]:
        return TermsDraft(error="empty_reply")

    template: AgreementTemplate | None = None
    number = data.get("template")
    if isinstance(number, int) and not isinstance(number, bool) and 1 <= number <= len(templates):
        template = templates[number - 1]

    for key in MONEY_FIELDS:
        fields[key] = (getattr(template, key) or "").strip() if template is not None else ""

    raw_notes = data.get("notes")
    notes = [
        note.strip()[:300]
        for note in (raw_notes if isinstance(raw_notes, list) else [])
        if isinstance(note, str) and note.strip()
    ][:MAX_NOTES]
    if any(_PROMISES.search(fields[key]) for key in TEXT_FIELDS):
        notes.insert(0, "В тексте есть обещание результата — уберите его перед отправкой клиенту.")

    return TermsDraft(
        fields=fields,
        amount_minor=template.amount_minor if template is not None else None,
        template=template,
        notes=notes,
    )


def draft_terms(
    intake: LegalIntake,
    templates: list[AgreementTemplate],
    *,
    api_key: str,
    base_url: str = "https://api.openai.com/v1",
    model: str = DEFAULT_MODEL,
    proxy_url: str | None = None,
    timeout: float = 90.0,
) -> TermsDraft:
    """Черновик условий. Сбой модели — поле error, исключений наружу нет."""
    templates = templates[:MAX_TEMPLATES]
    result = chat(
        build_messages(intake, templates),
        api_key=api_key,
        base_url=base_url,
        model=model,
        proxy_url=proxy_url,
        timeout=timeout,
        # Рассуждающая модель тратит часть лимита на рассуждение, а русский
        # текст договора дорог в токенах: с меньшим лимитом ответ обрывается.
        max_output_tokens=3000,
        response_format={"type": "json_object"},
    )
    if not result.ok:
        return TermsDraft(model=result.model, cost_usd=result.cost_usd, error=result.error or "empty_reply")
    draft = parse_reply(result.text, templates)
    draft.model = result.model
    draft.cost_usd = result.cost_usd
    if draft.error:
        logger.warning("terms_draft_rejected", extra={"error": draft.error})
    return draft
