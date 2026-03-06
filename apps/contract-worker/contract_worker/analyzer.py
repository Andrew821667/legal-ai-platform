from __future__ import annotations

from collections import Counter
import re


RISK_KEYWORDS = [
    "penalty",
    "termination",
    "liability",
    "indemnity",
    "exclusive",
    "штраф",
    "расторжение",
    "ответственность",
]


def analyze_contract(document_text: str) -> dict:
    raw_text = document_text or ""
    normalized = re.sub(r"\s+", " ", raw_text).strip()
    lower = normalized.lower()
    words = re.findall(r"[0-9A-Za-zА-Яа-яЁё_]+", lower)

    risk_counts: dict[str, int] = {}
    risk_snippets: list[dict[str, str]] = []
    for keyword in RISK_KEYWORDS:
        count = lower.count(keyword)
        if count <= 0:
            continue
        risk_counts[keyword] = count

        for match in re.finditer(re.escape(keyword), lower):
            start = max(0, match.start() - 60)
            end = min(len(normalized), match.end() + 60)
            snippet = normalized[start:end].strip()
            risk_snippets.append({"keyword": keyword, "snippet": snippet})
            if len(risk_snippets) >= 15:
                break
        if len(risk_snippets) >= 15:
            break

    top_words = [
        {"word": word, "count": count}
        for word, count in Counter(words).most_common(10)
    ]
    risk_hits_total = sum(risk_counts.values())
    risk_density_per_1000_words = int((risk_hits_total / max(len(words), 1)) * 1000)
    risk_score = min(100, risk_hits_total * 12 + min(40, risk_density_per_1000_words))
    if risk_score >= 60:
        risk_level = "high"
    elif risk_score >= 30:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "summary": (
            f"Текст содержит {len(words)} слов. "
            f"Найдено риск-маркеров: {risk_hits_total} ({len(risk_counts)} уникальных). "
            f"Оценка риска: {risk_level} ({risk_score}/100)."
        ),
        "risk_level": risk_level,
        "risk_score": risk_score,
        "word_count": len(words),
        "risk_hits_total": risk_hits_total,
        "risk_counts": risk_counts,
        "risks": sorted(risk_counts.keys()),
        "risk_snippets": risk_snippets,
        "top_words": top_words,
    }
