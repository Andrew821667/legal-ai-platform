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
