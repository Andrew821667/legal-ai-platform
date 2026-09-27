"""Персональные данные не уходят к вендору модели.

Перед вызовом имена, контакты, номера документов, счетов и карт, адреса и
даты рождения заменяются метками; ответ модели получает исходные значения.
"""

from __future__ import annotations

import json

from core_api.config import get_settings
from core_api.intake_analysis import analyze_intake
from shared.pii import Masker, StreamRestorer, mask_messages

from test_intake_analysis import _answer, _Opener

CLIENT_TEXT = (
    "Меня зовут Иван Петров, телефон +7 (999) 123-45-67, почта ivan.petrov@mail.ru. "
    "Арендодатель Смирнова Ольга Викторовна не возвращает залог по договору от 01.03.2026, "
    "квартира по адресу ул. Ленина, д. 5, кв. 12. Паспорт 45 07 123456, ИНН 771234567890, "
    "карта 4276 1600 1234 5678, счёт 40817810099910004312. Дата рождения: 12.05.1985."
)
SECRETS = (
    "Иван", "Петров", "123-45-67", "ivan.petrov", "Смирнова", "Ольга", "Ленина", "кв. 12",
    "123456", "771234567890", "4276", "40817810099910004312", "12.05.1985",
)


def test_masker_hides_personal_data_and_keeps_the_legal_substance() -> None:
    masker = Masker()
    masked = masker.mask(CLIENT_TEXT)
    for secret in SECRETS:
        assert secret not in masked, secret
    # Суть для юриста остаётся: предмет спора, дата договора, город.
    assert "не возвращает залог" in masked and "01.03.2026" in masked
    assert masker.restore(masked) == CLIENT_TEXT


def test_courts_cities_and_common_words_are_not_names() -> None:
    text = "Магазин отказался вернуть деньги. Московский городской суд, Ростов-на-Дону, Саратовской области."
    assert Masker().mask(text) == text


def test_known_client_name_is_masked_in_any_case() -> None:
    masker = Masker(known_names=("Лейла", "ООО Ромашка"))
    masked = masker.mask("Лейле пришла претензия, Лейла её оспаривает; поставщик — ООО Ромашка.")
    assert "Лейл" not in masked and "Ромашка" not in masked


def test_same_value_gets_the_same_placeholder_and_stream_restores_split_marks() -> None:
    masker = Masker()
    masked = masker.mask("Звонил +79991234567. Перезвоните на +79991234567.")
    assert masked.count("[ТЕЛЕФОН_1]") == 2
    stream = StreamRestorer(masker)
    out = "".join(stream.feed(chunk) for chunk in ["Ваш номер [ТЕЛ", "ЕФОН_1] записан"]) + stream.flush()
    assert out == "Ваш номер +79991234567 записан"


def test_system_prompt_is_left_as_is_and_note_is_added() -> None:
    masker = Masker()
    masked = mask_messages(
        [{"role": "system", "content": "Тебя зовут Никита."}, {"role": "user", "content": "Я Иван Петров."}],
        masker,
    )
    assert masked[0]["content"] == "Тебя зовут Никита."
    assert "метками" in masked[1]["content"]
    assert "Иван" not in masked[2]["content"]


def test_vendor_receives_placeholders_and_lawyer_gets_real_values(monkeypatch) -> None:
    opener = _Opener(_answer("Клиент [ИМЯ_1] просит вернуть залог; перезвонить на [ТЕЛЕФОН_1]."))
    monkeypatch.setattr("urllib.request.build_opener", lambda *a, **k: opener)

    result = analyze_intake(
        {"description": "Меня зовут Иван Петров, телефон +79991234567, залог не вернули.", "known_names": ["Иван Петров"]},
        api_key="sk-test",
    )

    sent = json.dumps(json.loads(opener.request.data.decode("utf-8")), ensure_ascii=False)
    assert "Иван" not in sent and "79991234567" not in sent
    assert "[ИМЯ_1]" in sent
    assert result.text == "Клиент Иван Петров просит вернуть залог; перезвонить на +79991234567."


def test_masking_can_be_switched_off(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PII_MASKING_ENABLED", "false")
    get_settings.cache_clear()
    try:
        opener = _Opener(_answer("ok"))
        monkeypatch.setattr("urllib.request.build_opener", lambda *a, **k: opener)
        analyze_intake({"description": "Меня зовут Иван Петров."}, api_key="sk-test")
        sent = json.dumps(json.loads(opener.request.data.decode("utf-8")), ensure_ascii=False)
        assert "Иван Петров" in sent
    finally:
        monkeypatch.delenv("LLM_PII_MASKING_ENABLED")
        get_settings.cache_clear()
