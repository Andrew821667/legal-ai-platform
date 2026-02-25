from __future__ import annotations

from collections import Counter


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
    text = document_text or ""
    lower = text.lower()
    hits = [kw for kw in RISK_KEYWORDS if kw in lower]
    words = [word for word in lower.replace("\n", " ").split(" ") if word]
    top_words = Counter(words).most_common(10)

    return {
        "summary": f"Текст содержит {len(words)} слов. Найдено риск-маркеров: {len(hits)}.",
        "risks": hits,
        "top_words": top_words,
    }
