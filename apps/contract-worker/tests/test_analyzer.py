from __future__ import annotations

from contract_worker.analyzer import analyze_contract


def test_analyze_contract_empty_text() -> None:
    result = analyze_contract("")
    assert result["word_count"] == 0
    assert result["risk_hits_total"] == 0
    assert result["risk_level"] == "low"
    assert result["risk_score"] == 0
    assert result["risks"] == []


def test_analyze_contract_detects_risks_and_counts() -> None:
    text = (
        "В договоре указаны штраф за просрочку, ответственность сторон и расторжение. "
        "Также есть liability clause и penalty terms."
    )
    result = analyze_contract(text)

    assert result["word_count"] > 0
    assert result["risk_hits_total"] >= 4
    assert "penalty" in result["risk_counts"]
    assert "liability" in result["risk_counts"]
    assert "штраф" in result["risk_counts"]
    assert "ответственность" in result["risk_counts"]
    assert len(result["risk_snippets"]) >= 1
    assert len(result["top_words"]) >= 1
    assert result["risk_level"] in {"medium", "high"}
