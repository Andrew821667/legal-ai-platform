from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


ScreenGuide = Callable[[str, list[str]], str]
VariantLabel = Callable[[str], str]


def build_reader_cta_ab_text(
    *,
    state: Mapping[str, Any],
    ordered_variants: list[str],
    enabled_variants: list[str],
    split: Mapping[str, int],
    variant_stats_lines: list[str],
    variant_label: VariantLabel,
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")

    split_line = ", ".join(
        f"{variant_label(variant)} {int(split.get(variant, 0))}%"
        for variant in ordered_variants
        if variant in enabled_variants
    ) or "н/д"

    lines = [
        "A/B CTA reader/mini-app",
        "",
        guide(
            "Управление CTA-вариантами reader/mini-app и их весами в распределении.",
            [
                "Меняйте split только для активных вариантов.",
                "После смены seed распределение пользователей пересчитается детерминированно.",
                "Ориентируйтесь на CR в intent и консультации через Reader-воронку.",
            ],
        ),
        "",
        f"Статус A/B: {'🟢 включен' if state.get('enabled', True) else '🔴 выключен'}",
        f"Seed: {state.get('seed')}",
        "Активные варианты: " + ", ".join(variant_label(variant) for variant in enabled_variants),
        f"Split: {split_line}",
    ]
    if variant_stats_lines:
        lines.extend(["", "Факт за 7 дней:", *variant_stats_lines[:6]])
    else:
        lines.extend(["", "Факт за 7 дней: нет данных или статистика временно недоступна."])
    return "\n".join(lines)
