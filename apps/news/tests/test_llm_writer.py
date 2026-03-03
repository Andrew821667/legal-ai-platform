from __future__ import annotations

from datetime import datetime, timezone

from news.llm_writer import LLMNewsWriter
from news.pipeline import ArticleCandidate


def test_looks_complete_prose_accepts_finished_text() -> None:
    text = "<b>Что произошло</b>\nТекст завершен.\n\n<b>Источник</b>: ссылка\n#LegalAI"
    assert LLMNewsWriter._looks_complete_prose(text)


def test_looks_complete_prose_rejects_incomplete_tail() -> None:
    text = "<b>Что произошло</b>\nТекст оборван потому\n\n<b>Источник</b>: ссылка\n#LegalAI"
    assert not LLMNewsWriter._looks_complete_prose(text)


def test_specificity_signal_allows_legal_markers_without_digits() -> None:
    text = "<b>Юридические риски</b>\nНужно проверить персональные данные, договорную ответственность и AI Act."
    assert LLMNewsWriter._has_specificity_signal(text)


def test_blocks_look_complete_rejects_truncated_internal_paragraph() -> None:
    text = (
        "<b>Что произошло</b>\nAnthropic попала в политический конфликт вокруг оборонных поставок и Пента\n\n"
        "<b>Почему это важно</b>\nЭто влияет на выбор поставщиков и корпоративные AI-стратегии.\n\n"
        "<b>Что это значит для рынка</b>\nРынок начнет жестче смотреть на политические риски AI-вендоров.\n\n"
        "<b>Источник</b>: ссылка\n#LegalAI"
    )
    assert not LLMNewsWriter._blocks_look_complete(text)


def test_format_daily_uses_contextual_market_block() -> None:
    writer = LLMNewsWriter.__new__(LLMNewsWriter)
    title, text, rubric = writer._format_post(
        {
            "title": "Anthropic и Пентагон",
            "rubric": "market",
            "lead": "Крупный AI-вендор оказался в центре оборонного и политического сюжета.",
            "what_happened": "Администрация США усилила давление на Anthropic в контексте оборонных цепочек поставок.",
            "business_effect": "Для рынка это сигнал, что выбор AI-вендора становится не только техническим, но и политическим вопросом.",
            "legal_risks": "Юристам нужно оценить санкционные ограничения, контур госзакупок и договорные риски поставщика.",
            "conclusion": "Дальше стоит смотреть, как это повлияет на закупки и стратегию корпоративных клиентов.",
        },
        "https://example.com/article",
        "Anthropic и Пентагон",
        format_type="daily",
        cta_type="soft",
        pillar="market",
    )
    assert title == "Anthropic и Пентагон"
    assert rubric == "market"
    assert "Что это значит для рынка" in text
    assert "Что проверить юристу" not in text


def test_passes_quality_gate_accepts_daily_with_contextual_third_block() -> None:
    text = (
        "<b>Anthropic и Пентагон</b>\n\n"
        "Крупный AI-вендор оказался в центре оборонного и политического сюжета, который быстро вышел за пределы обычной корпоративной новости и стал сигналом для всего рынка enterprise AI.\n\n"
        "<b>Что произошло</b>\nАдминистрация США усилила давление на Anthropic в контексте оборонных цепочек поставок. История быстро вышла из рамки технологической дискуссии и превратилась в вопрос о доверии к поставщику, его роли в чувствительных проектах и готовности государства влиять на выбор подрядчиков.\n\n"
        "<b>Почему это важно</b>\nДля рынка это сигнал, что выбор AI-вендора становится не только техническим, но и политическим вопросом. Корпоративные клиенты и их юридические команды будут смотреть не только на качество модели, но и на устойчивость поставщика, его регуляторный контур, режим доступа к данным и риск ограничений в стратегических секторах.\n\n"
        "<b>Что это значит для рынка</b>\nДальше стоит смотреть, как это повлияет на закупки, комплаенс-проверки и стратегию корпоративных клиентов. Если конфликт продолжится, крупные компании начнут жестче проверять contractual safeguards, governance-модель вендора, распределение ответственности и способность поставщика обслуживать критически важные сценарии без политических сбоев.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#LegalAI #AI #LegalTech"
    )
    assert LLMNewsWriter._passes_quality_gate(text, "daily")


def test_daily_disables_low_quality_fallback() -> None:
    assert not LLMNewsWriter._allow_quality_fallback("daily")
    assert LLMNewsWriter._allow_quality_fallback("weekly_review")


def test_shorten_with_prefer_sentence_never_cuts_mid_sentence() -> None:
    text = "Это очень длинное предложение без точки в пределах лимита и оно не должно обрезаться просто по слову где попало"
    assert LLMNewsWriter._shorten(text, 60, prefer_sentence=True) == ""


def test_shorten_with_prefer_sentence_keeps_last_full_sentence() -> None:
    text = "Первое предложение завершено. Второе предложение тоже завершено. Третье предложение уже не должно влезть целиком."
    shortened = LLMNewsWriter._shorten(text, 70, prefer_sentence=True)
    assert shortened == "Первое предложение завершено. Второе предложение тоже завершено."


def test_infer_legal_focus_hint_for_privacy_article() -> None:
    article = ArticleCandidate(
        source_url="https://example.com/rss",
        article_url="https://example.com/privacy-ai",
        title="AI privacy and cross-border data transfers",
        summary="The article discusses AI privacy, GDPR obligations and cross-border data transfers.",
        published_at=datetime.now(timezone.utc),
    )
    hint = LLMNewsWriter._infer_legal_focus_hint(article, "regulation")
    assert "трансгранич" in hint.lower()
    assert "локализац" in hint.lower()


def test_fallback_legal_commentary_for_contract_tooling_is_specific() -> None:
    article = ArticleCandidate(
        source_url="https://example.com/rss",
        article_url="https://example.com/contract-ai-platform",
        title="AI contract review platform adds new SLA terms",
        summary="A vendor expanded its AI contract review platform and updated SLA commitments for enterprise clients.",
        published_at=datetime.now(timezone.utc),
    )
    text = LLMNewsWriter._fallback_legal_commentary(article, "tools", "contracts")
    lowered = text.lower()
    assert "sla" in lowered
    assert "output" in lowered
    assert "vendor lock-in" in lowered or "lock-in" in lowered


def test_generic_legal_commentary_detection() -> None:
    assert LLMNewsWriter._looks_generic_legal_commentary("Есть риски, которые нужно учитывать.")
    assert not LLMNewsWriter._looks_generic_legal_commentary(
        "Юристу стоит проверить SLA, vendor lock-in, privacy-контур и распределение ответственности."
    )
