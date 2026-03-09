from __future__ import annotations

from news.reader_cta_ui import build_reader_cta_ab_text


def _screen_guide_stub(what: str, actions: list[str]) -> str:
    _ = actions
    return f"ℹ️ Что это: {what}"


def _label_stub(variant: str) -> str:
    return {"v1_direct": "Прямой", "v2_diagnostic": "Диагностический"}.get(variant, variant)


def test_build_reader_cta_ab_text_with_stats() -> None:
    text = build_reader_cta_ab_text(
        state={"enabled": True, "seed": "seed-1"},
        ordered_variants=["v1_direct", "v2_diagnostic"],
        enabled_variants=["v1_direct", "v2_diagnostic"],
        split={"v1_direct": 70, "v2_diagnostic": 30},
        variant_stats_lines=["• Прямой: CTA 10, intent 5, CR 50.0%"],
        variant_label=_label_stub,
        screen_guide=_screen_guide_stub,
    )
    assert "Статус A/B: 🟢 включен" in text
    assert "Split: Прямой 70%, Диагностический 30%" in text
    assert "Факт за 7 дней:" in text


def test_build_reader_cta_ab_text_without_stats() -> None:
    text = build_reader_cta_ab_text(
        state={"enabled": False, "seed": "seed-2"},
        ordered_variants=["v1_direct", "v2_diagnostic"],
        enabled_variants=["v1_direct"],
        split={"v1_direct": 100},
        variant_stats_lines=[],
        variant_label=_label_stub,
        screen_guide=_screen_guide_stub,
    )
    assert "Статус A/B: 🔴 выключен" in text
    assert "Активные варианты: Прямой" in text
    assert "Факт за 7 дней: нет данных или статистика временно недоступна." in text
