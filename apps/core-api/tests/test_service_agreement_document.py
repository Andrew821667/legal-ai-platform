from __future__ import annotations

from core_api.service_agreement import AGREEMENT_VERSION, document_hash, render_agreement_text


def _render(**changes: str) -> str:
    data = {
        "number": "AV-20260907-ABC123",
        "revision": 1,
        "created_date": "07.09.2026",
        "expires_date": "14.09.2026",
        "operator_name": "Иванов Иван Иванович",
        "operator_status": "самозанятый",
        "operator_inn": "123456789012",
        "operator_details": "Москва, example@example.ru",
        "client_name": "Петров Пётр Петрович",
        "client_org": None,
        "client_details": "паспорт 00 00 000000; адрес: г. Москва",
        "subject": "Правовой анализ договора поставки",
        "scope": "Изучить договор и подготовить письменные замечания",
        "exclusions": "Судебное представительство",
        "schedule": "Три рабочих дня после получения документов",
        "price": "15 000 рублей",
        "payment_terms": "100% до начала работы",
    }
    data.update(changes)
    return render_agreement_text(**data)


def test_document_contains_material_terms_and_pep_rules() -> None:
    text = _render()
    for value in (
        "ДОГОВОР ВОЗМЕЗДНОГО ОКАЗАНИЯ ЮРИДИЧЕСКИХ УСЛУГ",
        "Правовой анализ договора поставки",
        "15 000 рублей",
        "сохранять конфиденциальность средств доступа",
        "уникальным идентификатором",
        "подписанный указанным способом обеими сторонами",
        "административной версии Telegram-бота",
        "паспорт 00 00 000000",
        AGREEMENT_VERSION,
    ):
        assert value in text


def test_exact_terms_change_document_hash() -> None:
    assert document_hash(_render()) != document_hash(_render(price="20 000 рублей"))


def test_company_is_named_as_client() -> None:
    assert "Заказчик: ООО «Пример», в лице Петров Пётр Петрович" in _render(
        client_org="ООО «Пример»"
    )
