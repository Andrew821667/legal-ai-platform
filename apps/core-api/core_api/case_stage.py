"""Этап дела одной фразой — единственное место, где он считается.

Лестница жила дважды: ядро считало этап на клиента, сайт — свою копию на
каждое обращение, и оба сравнивали этапы по русскому тексту («Договор
подписан»). Поменяй формулировку в одном месте — фильтры и шкала в другом
молча перестали бы совпадать. Теперь ядро отдаёт и текст, и ключ, и шаг
шкалы; сайт показывает текст и решает по ключу.
"""

from __future__ import annotations

from typing import NamedTuple


class Stage(NamedTuple):
    key: str
    title: str
    # Шаг шкалы «Обращение → NDA → Договор → Подписан»; None — шкалы нет:
    # дело ведут без договора, и лестница «договор → подписан» к нему неприменима.
    step: int | None


SIGNED = Stage("signed", "Договор подписан", 4)
WITH_CLIENT = Stage("with_client", "Договор у клиента", 3)
NOT_SENT = Stage("not_sent", "Договор не отправлен", 3)
DECLINED = Stage("declined", "Клиент отказался", 1)
WITHOUT_AGREEMENT = Stage("without_agreement", "В работе без договора", None)
PREPARING_TERMS = Stage("preparing_terms", "Готовим условия", 2)
FIRST_CONTACT = Stage("first_contact", "Первичное обращение", 1)

ALL = (SIGNED, WITH_CLIENT, NOT_SENT, DECLINED, WITHOUT_AGREEMENT, PREPARING_TERMS, FIRST_CONTACT)


def stage_for(*, nda_signed: bool, agreement_status: str | None, without_agreement: bool = False) -> Stage:
    """Этап по последнему договору, NDA и решению вести дело без договора.

    without_agreement — юрист сам решил вести дело без договора. Пока
    договора нет, «Готовим условия» тут было бы неправдой: условия никто не
    готовит, работа уже идёт. Появится договор — этап снова по нему.
    """
    if agreement_status == "signed":
        return SIGNED
    if agreement_status in {"sent", "viewed"}:
        return WITH_CLIENT
    if agreement_status == "draft":
        return NOT_SENT
    if agreement_status == "declined":
        return DECLINED
    if without_agreement:
        return WITHOUT_AGREEMENT
    if nda_signed:
        return PREPARING_TERMS
    return FIRST_CONTACT


def fields(stage: Stage) -> dict:
    """Поля ответа: текст для экрана, ключ для решений, шаг для шкалы."""
    return {"stage": stage.title, "stage_key": stage.key, "stage_step": stage.step}
