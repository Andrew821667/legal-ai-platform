# -*- coding: utf-8 -*-
from types import SimpleNamespace

from src.services.risk_scorer import RiskScorer


def test_risk_scorer_detects_high_risk():
    scorer = RiskScorer()

    template_comparison = SimpleNamespace(
        critical_count=1,
        high_count=1,
        medium_count=0,
        low_count=0,
        missing_sections=["Ответственность"],
        total_deviations=2,
    )

    result = scorer.score(
        raw_text=(
            "Сторона несет неограниченную ответственность. "
            "Предоплата 70%. Срок оплаты 90 дней. "
            "Пеня 1.0% в день."
        ),
        extracted_data={"financials": {"prepayment_percent": 70}, "terms": {"payment_days": 90}},
        validation_result={"errors": ["amount missing"], "warnings": ["term unclear"]},
        template_comparison=template_comparison,
        section_analysis=None,
        accepted_recommendations=[],
    )

    assert result.overall_score >= 75
    assert result.risk_level in ("critical", "high")
    assert result.critical_factors >= 1


def test_risk_scorer_mitigation_reduces_score():
    scorer = RiskScorer()

    accepted_recommendations = [
        {"priority": "critical"},
        {"priority": "important"},
        {"priority": "optional"},
    ]

    result = scorer.score(
        raw_text="Неограниченная ответственность. Предоплата 80%.",
        extracted_data={"financials": {"prepayment_percent": 80}},
        validation_result={"errors": ["missing section"], "warnings": []},
        accepted_recommendations=accepted_recommendations,
    )

    assert result.mitigated_score <= result.overall_score
    assert result.overall_score - result.mitigated_score >= 1

