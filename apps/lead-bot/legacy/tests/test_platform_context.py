"""Контекст ядра в промпте ассистента: собственные дела, NDA, договоры, акты
собеседника — то, чего ассистенту раньше не хватило в кейсе Рябовой (см.
Current.md, «Контекстный ассистент»)."""
import platform_context


def _bridge(monkeypatch, *, enabled=True, summary=None, raises=None):
    from core_api_bridge import core_api_bridge as bridge

    monkeypatch.setattr(bridge, "enabled", enabled)

    def _fake_summary(telegram_user_id):
        if raises:
            raise raises
        return summary

    monkeypatch.setattr(bridge, "client_portal_summary", _fake_summary)
    return bridge


def test_no_telegram_id_returns_empty(monkeypatch):
    _bridge(monkeypatch, summary={"cases": [{"id": "x"}]})
    assert platform_context.build_core_context_block(None) == ""


def test_bridge_disabled_returns_empty(monkeypatch):
    _bridge(monkeypatch, enabled=False, summary={"cases": [{"id": "x"}]})
    assert platform_context.build_core_context_block(123) == ""


def test_no_history_returns_empty(monkeypatch):
    _bridge(monkeypatch, summary={"client": {"has_cases": False}, "nda": {"signed": False}, "cases": [], "agreements": [], "acts": []})
    assert platform_context.build_core_context_block(123) == ""


def test_summary_none_returns_empty(monkeypatch):
    _bridge(monkeypatch, summary=None)
    assert platform_context.build_core_context_block(123) == ""


def test_bridge_error_is_swallowed(monkeypatch):
    _bridge(monkeypatch, raises=RuntimeError("core-api недоступен"))
    assert platform_context.build_core_context_block(123) == ""


def test_own_case_and_nda_render_into_block(monkeypatch):
    summary = {
        "client": {"has_cases": True},
        "nda": {"signed": True, "signed_at": "2026-09-08T15:23:00", "version": "2026-07-16"},
        "cases": [
            {
                "id": "case-1",
                "legal_area": "family",
                "status": "in_progress",
                "description": "Раздел совместно нажитого имущества",
                "created_at": "2026-09-08T09:00:00",
            }
        ],
        "agreements": [],
        "acts": [],
    }
    _bridge(monkeypatch, summary=summary)
    block = platform_context.build_core_context_block(275782221)

    assert "Собеседник уже известен платформе" in block
    assert "NDA подписан 2026-09-08" in block
    assert "семейное право" in block and "в работе" in block
    assert "Раздел совместно нажитого имущества" in block


def test_agreements_and_acts_are_listed(monkeypatch):
    summary = {
        "client": {"has_cases": True},
        "nda": {"signed": False},
        "cases": [],
        "agreements": [{"number": "AGR-1", "status": "signed", "subject": "Консультация по разделу имущества"}],
        "acts": [{"number": "ACT-1", "status": "paid"}],
    }
    _bridge(monkeypatch, summary=summary)
    block = platform_context.build_core_context_block(1)

    assert "Договор № AGR-1 (подписан)" in block
    assert "Консультация по разделу имущества" in block
    assert "Акт № ACT-1 (оплачен)" in block


def test_case_list_is_capped_with_a_counter(monkeypatch):
    cases = [
        {"id": f"c{i}", "legal_area": "civil", "status": "new", "description": "", "created_at": "2026-09-01T00:00:00"}
        for i in range(7)
    ]
    _bridge(monkeypatch, summary={"client": {"has_cases": True}, "nda": {"signed": False}, "cases": cases, "agreements": [], "acts": []})
    block = platform_context.build_core_context_block(1)

    assert block.count("- Обращение от") == platform_context._MAX_CASES
    assert "…и ещё 2 обращени(й) ранее." in block


def test_unknown_labels_fall_back_to_raw_value(monkeypatch):
    summary = {
        "client": {"has_cases": True},
        "nda": {"signed": False},
        "cases": [{"id": "c1", "legal_area": "space_law", "status": "new", "description": "", "created_at": "2026-09-01T00:00:00"}],
        "agreements": [],
        "acts": [],
    }
    _bridge(monkeypatch, summary=summary)
    block = platform_context.build_core_context_block(1)
    assert "space_law" in block


# ── build_full_case_details_block: инструмент get_full_case_details ────────
# В отличие от build_core_context_block — без ограничения в 5 штук, без
# обрезки текста, плюс документы/переписка/возражения, которых в кратком
# блоке нет вовсе.

def test_full_details_no_telegram_id_returns_message(monkeypatch):
    _bridge(monkeypatch, summary={"cases": [{"id": "x"}]})
    assert "нет" in platform_context.build_full_case_details_block(None)


def test_full_details_bridge_disabled_returns_message(monkeypatch):
    _bridge(monkeypatch, enabled=False, summary={"cases": [{"id": "x"}]})
    assert "нет" in platform_context.build_full_case_details_block(1)


def test_full_details_empty_summary_returns_message(monkeypatch):
    _bridge(monkeypatch, summary={"client": {}, "nda": {"signed": False}, "cases": [], "agreements": [], "acts": []})
    assert "нет" in platform_context.build_full_case_details_block(1)


def test_full_details_bridge_error_is_swallowed(monkeypatch):
    _bridge(monkeypatch, raises=RuntimeError("core-api недоступен"))
    result = platform_context.build_full_case_details_block(1)
    assert "не удалось" in result.lower() or "недоступн" in result.lower()


def test_full_details_includes_untruncated_description_and_documents(monkeypatch):
    long_description = "Раздел совместно нажитого имущества. " * 20  # длиннее лимита краткого блока
    summary = {
        "nda": {"signed": True, "signed_at": "2026-09-07T17:08:00", "version": "2026-09-04.1"},
        "cases": [
            {
                "legal_area": "family",
                "status": "in_progress",
                "description": long_description,
                "created_at": "2026-09-07T16:56:00",
                "documents": [{"file_name": "паспорт.pdf", "created_at": "2026-09-07T17:00:00"}],
            }
        ],
        "agreements": [],
        "acts": [],
    }
    _bridge(monkeypatch, summary=summary)
    block = platform_context.build_full_case_details_block(1)

    assert long_description.strip() in block  # не обрезано
    assert "паспорт.pdf" in block


def test_full_details_includes_agreement_messages_and_price(monkeypatch):
    summary = {
        "nda": {"signed": False},
        "cases": [],
        "agreements": [
            {
                "number": "AV-201",
                "status": "signed",
                "subject": "Консультация по разделу имущества",
                "price_text": "10 000 руб.",
                "messages": [
                    {"role": "client", "text": "Когда будет готово?", "created_at": "2026-09-08T10:00:00"},
                    {"role": "lawyer", "text": "К пятнице.", "created_at": "2026-09-08T11:00:00"},
                ],
            }
        ],
        "acts": [],
    }
    _bridge(monkeypatch, summary=summary)
    block = platform_context.build_full_case_details_block(1)

    assert "AV-201" in block and "10 000 руб." in block
    assert "Когда будет готово?" in block and "К пятнице." in block


def test_full_details_includes_act_objection(monkeypatch):
    summary = {
        "nda": {"signed": False},
        "cases": [],
        "agreements": [],
        "acts": [{"number": "ACT-9", "status": "objected", "description": "Консультация", "objection_text": "Не согласен с объёмом работ"}],
    }
    _bridge(monkeypatch, summary=summary)
    block = platform_context.build_full_case_details_block(1)

    assert "ACT-9" in block
    assert "Не согласен с объёмом работ" in block


def test_full_details_shows_all_cases_without_cap(monkeypatch):
    cases = [
        {"legal_area": "civil", "status": "new", "description": f"дело {i}", "created_at": "2026-09-01T00:00:00", "documents": []}
        for i in range(8)
    ]
    _bridge(monkeypatch, summary={"nda": {"signed": False}, "cases": cases, "agreements": [], "acts": []})
    block = platform_context.build_full_case_details_block(1)

    for i in range(8):
        assert f"дело {i}" in block
    assert "…и ещё" not in block  # краткий блок так пишет, полный — нет


# ── build_topic_memory_block: пункт 4 «умного ассистента» ──────────────────
# В отличие от build_core_context_block — не зависит от ядра/формальных дел,
# работает по локальной памяти тем разговора (database.db.get_topic_memory).

def test_topic_memory_no_telegram_id_returns_empty(monkeypatch):
    assert platform_context.build_topic_memory_block(None) == ""


def test_topic_memory_unknown_user_returns_empty(monkeypatch):
    monkeypatch.setattr(platform_context.database.db, "get_user_by_telegram_id", lambda tg: None)
    assert platform_context.build_topic_memory_block(12345) == ""


def test_topic_memory_no_summary_yet_returns_empty(monkeypatch):
    monkeypatch.setattr(platform_context.database.db, "get_user_by_telegram_id", lambda tg: {"id": 7})
    monkeypatch.setattr(platform_context.database.db, "get_topic_memory", lambda user_id: None)
    assert platform_context.build_topic_memory_block(12345) == ""


def test_topic_memory_present_renders_block(monkeypatch):
    monkeypatch.setattr(platform_context.database.db, "get_user_by_telegram_id", lambda tg: {"id": 7})
    monkeypatch.setattr(
        platform_context.database.db,
        "get_topic_memory",
        lambda user_id: "Интересовался ценами на проверку договоров.",
    )

    block = platform_context.build_topic_memory_block(12345)

    assert "# Прошлые темы разговора" in block
    assert "Интересовался ценами на проверку договоров." in block


def test_topic_memory_lookup_error_is_swallowed(monkeypatch):
    def _boom(tg):
        raise RuntimeError("db locked")

    monkeypatch.setattr(platform_context.database.db, "get_user_by_telegram_id", _boom)

    assert platform_context.build_topic_memory_block(12345) == ""


def test_topic_memory_works_without_any_core_case_data(monkeypatch):
    """Ключевое отличие от build_core_context_block: применимо и без единого
    формального обращения в ядре — например, для тех, кто только спрашивал
    про платформу, но никогда не оставлял заявку."""
    monkeypatch.setattr(platform_context.database.db, "get_user_by_telegram_id", lambda tg: {"id": 42})
    monkeypatch.setattr(
        platform_context.database.db, "get_topic_memory", lambda user_id: "Спрашивал, что делает AI Verdict."
    )
    _bridge(monkeypatch, summary=None)  # в ядре про этого человека вообще ничего нет

    assert platform_context.build_core_context_block(12345) == ""  # ядро — пусто
    assert "AI Verdict" in platform_context.build_topic_memory_block(12345)  # память тем — есть
