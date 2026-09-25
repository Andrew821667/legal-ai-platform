"""Платёжный QR для акта — по ГОСТ Р 56042-2014 («ST00012»).

Клиент переводил оплату по номеру телефона и вручную набирал сумму: ошибка в
сумме или назначении — и юрист сверяет поступление вслепую. Этот QR сканирует
приложение любого крупного банка (Сбер, Т-Банк, ВТБ и другие): получатель,
счёт, сумма и назначение «Оплата по акту № …» заполняются сами.

Почему не QR СБП: его выпускает банк по торговому договору с ИП или
организацией, самозанятому без такого договора он недоступен. ST00012 —
открытый стандарт перевода по реквизитам счёта, для него договор не нужен.
Подтверждать оплату по-прежнему юристу: банковского API, который видел бы
поступления, у самозанятого нет.
"""

from __future__ import annotations

import io
import re

import qrcode

from core_api.config import get_settings

_DIGITS = re.compile(r"\D")


def _clean(value: str | None) -> str:
    # «|» — разделитель полей в ST00012: внутри значения он сломал бы разбор.
    return " ".join(str(value or "").replace("|", " ").split())


def requisites() -> dict | None:
    """Реквизиты получателя или None, если счёт не задан полностью."""
    settings = get_settings()
    account = _DIGITS.sub("", settings.lawyer_payment_account or "")
    bic = _DIGITS.sub("", settings.lawyer_payment_bic or "")
    corr = _DIGITS.sub("", settings.lawyer_payment_corr_account or "")
    name = _clean(
        settings.lawyer_payment_account_holder or settings.lawyer_payment_recipient or settings.operator_name
    )
    bank = _clean(settings.lawyer_payment_bank)
    if len(account) != 20 or len(bic) != 9 or len(corr) != 20 or not name or not bank:
        return None
    inn = _DIGITS.sub("", settings.lawyer_payment_inn or settings.operator_inn or "")
    prefix = _clean(settings.lawyer_payment_purpose_prefix)
    return {"name": name, "account": account, "bank": bank, "bic": bic, "corr": corr, "inn": inn, "prefix": prefix}


def payload(amount_minor: int, purpose: str) -> str | None:
    """Строка ST00012: «2» после ST0001 — кодировка UTF-8, сумма — в копейках."""
    req = requisites()
    if req is None:
        return None
    fields = [
        "ST00012",
        f"Name={req['name']}",
        f"PersonalAcc={req['account']}",
        f"BankName={req['bank']}",
        f"BIC={req['bic']}",
        f"CorrespAcc={req['corr']}",
    ]
    if len(req["inn"]) in (10, 12):
        fields.append(f"PayeeINN={req['inn']}")
    full_purpose = f"{req['prefix']} {purpose}" if req["prefix"] else purpose
    fields += [f"Sum={int(amount_minor)}", f"Purpose={_clean(full_purpose)[:210]}"]
    return "|".join(fields)


def png(data: str) -> bytes:
    image = qrcode.make(data, border=2, box_size=8, error_correction=qrcode.constants.ERROR_CORRECT_M)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
