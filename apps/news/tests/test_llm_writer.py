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


def test_blocks_look_complete_ignores_title_line_without_period() -> None:
    text = (
        "<b>Theorem выпустил гид по Legal AI-платформам для юристов</b>\n\n"
        "<b>Что произошло</b>\nTheorem собрал обзор платформ, которые помогают юристам выбирать рабочий стек Legal AI.\n\n"
        "<b>Почему это важно</b>\nДля юрфункции это полезно как карта рынка и ориентир для vendor due diligence.\n\n"
        "<b>Что это значит для рынка</b>\nКомпании начнут сравнивать платформы не только по точности, но и по governance, SLA и режиму данных.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#LegalAI #AI #LegalTech"
    )
    assert LLMNewsWriter._blocks_look_complete(text)


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


def test_structured_formats_disable_low_quality_fallback() -> None:
    assert not LLMNewsWriter._allow_quality_fallback("daily")
    assert not LLMNewsWriter._allow_quality_fallback("weekly_review")
    assert not LLMNewsWriter._allow_quality_fallback("longread")
    assert LLMNewsWriter._allow_quality_fallback("standard")


def test_quality_gate_rejects_prompt_leak_markers() -> None:
    text = (
        "<b>Обзор недели</b>\n\n"
        "<b>Ключевые сигналы недели</b>\n1. Пункт один.\n2. Пункт два.\n3. Пункт три.\n4. Пункт четыре.\n"
        "5. Пункт пять.\n6. Пункт шесть.\n7. Пункт семь.\n8. Пункт восемь.\n\n"
        "<b>Что это значит для юрфункции</b>\nСтилистика канала: деловой тон и плотный анализ.\n\n"
        "<b>На что смотреть юристам</b>\nПроверить контур ответственности поставщика.\n\n"
        "<b>Что проверить у себя</b>\n• Обновить KPI.\n\n"
        "<b>Источник</b>: ссылка\n#LegalAI"
    )
    assert LLMNewsWriter._quality_gate_failure_reason(text, "weekly_review") == "prompt_leak:стилистика канала"


def test_quality_gate_rejects_weekly_with_few_points() -> None:
    long_block = (
        "Юрфункция ускоряет цикл договорной проверки, пересматривает матрицу рисков, "
        "обновляет SLA и фиксирует роли контроля качества output в каждом процессе. "
        "Команда также пересобирает процедуры privacy и governance для стабильного внедрения."
    )
    text = (
        "<b>Обзор недели</b>\n\n"
        "<b>Ключевые сигналы недели</b>\n1. Пункт один.\n2. Пункт два.\n3. Пункт три.\n4. Пункт четыре.\n\n"
        f"<b>Что это значит для юрфункции</b>\n{long_block} {long_block} {long_block} {long_block} {long_block} {long_block}\n\n"
        f"<b>На что смотреть юристам</b>\n{long_block} {long_block} {long_block} {long_block} {long_block}\n\n"
        "<b>Что проверить у себя</b>\n"
        "• Зафиксировать контрольные точки quality gate.\n"
        "• Обновить контрактные safeguards для вендоров.\n"
        "• Проверить режим данных и права на output.\n"
        "• Назначить ответственных за human-in-the-loop.\n\n"
        "<b>Источник</b>: ссылка\n#LegalAI #AI #LegalTech"
    )
    assert LLMNewsWriter._quality_gate_failure_reason(text, "weekly_review") == "weak_weekly_points:4"


def test_quality_gate_failure_reason_for_short_daily() -> None:
    text = "<b>Короткий пост</b>\n\n<b>Что произошло</b>\nМало текста.\n\n<b>Почему это важно</b>\nМало.\n\n<b>Юридический контур</b>\nЕще мало.\n\n<b>Источник</b>: ссылка"
    reason = LLMNewsWriter._quality_gate_failure_reason(text, "daily")
    assert reason is not None
    assert reason.startswith("too_short:")


def test_quality_gate_rejects_weak_daily_third_block() -> None:
    text = (
        "<b>360 Business Law расширяет AI-сервис проверки договоров</b>\n\n"
        "Фирма расширяет доступ к своему AI-сервису проверки договоров для международной сети консультантов и использует это как часть новой операционной модели работы с контрактами.\n\n"
        "<b>Что произошло</b>\n"
        "Ранее инструмент был доступен только команде в Великобритании, а теперь его передают международным консультантам. Это означает расширение единого AI-контура проверки договоров на распределенную международную команду, которая работает с едиными шаблонами и стандартами проверки.\n\n"
        "<b>Почему это важно</b>\n"
        "Это ускоряет договорную работу и снижает рутинную нагрузку. Для фирм с распределенной моделью это еще и способ выровнять качество первичной проверки контрактов между разными юристами и юрисдикциями, не собирая весь поток только на внутреннюю команду.\n\n"
        "<b>Юридический контур</b>\n"
        "Нужно проработать договорной контур с вендором.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#LegalAI #AI #LegalTech"
    )
    assert LLMNewsWriter._quality_gate_failure_reason(text, "daily") == "weak_daily_third_block:47"


def test_shorten_with_prefer_sentence_never_cuts_mid_sentence() -> None:
    text = "Это очень длинное предложение без точки в пределах лимита и оно не должно обрезаться просто по слову где попало"
    assert LLMNewsWriter._shorten(text, 60, prefer_sentence=True) == ""


def test_shorten_with_prefer_sentence_keeps_last_full_sentence() -> None:
    text = "Первое предложение завершено. Второе предложение тоже завершено. Третье предложение уже не должно влезть целиком."
    shortened = LLMNewsWriter._shorten(text, 70, prefer_sentence=True)
    assert shortened == "Первое предложение завершено. Второе предложение тоже завершено."


def test_shorten_title_removes_cut_prepositional_tail() -> None:
    text = "Юрфирма 360 Business Law расширяет AI-сервис проверки договоров на международных сделках"
    shortened = LLMNewsWriter._shorten_title(text, 76)
    assert shortened == "Юрфирма 360 Business Law расширяет AI-сервис проверки договоров"


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


def test_infer_rubric_hint_for_litigation_article() -> None:
    article = ArticleCandidate(
        source_url="https://example.com/rss",
        article_url="https://example.com/legal-hold-ai",
        title="AI document review and legal hold in litigation",
        summary="The article discusses AI document review, legal hold and chain of custody requirements.",
        published_at=datetime.now(timezone.utc),
    )
    assert LLMNewsWriter._infer_rubric_hint(article, "case") == "litigation"


def test_fallback_legal_commentary_for_regulation_article_is_specific() -> None:
    article = ArticleCandidate(
        source_url="https://example.com/rss",
        article_url="https://example.com/ai-act-governance",
        title="AI Act governance and risk classification update",
        summary="The article covers AI Act obligations, governance and logging duties for enterprise deployments.",
        published_at=datetime.now(timezone.utc),
    )
    text = LLMNewsWriter._fallback_legal_commentary(article, "regulation", "regulation")
    lowered = text.lower()
    assert "ai act" in lowered
    assert "логирован" in lowered
    assert "санкцион" in lowered or "экспорт" in lowered or "классификац" in lowered


def test_fallback_legal_commentary_for_ai_law_article_is_specific() -> None:
    article = ArticleCandidate(
        source_url="https://example.com/rss",
        article_url="https://example.com/output-copyright",
        title="AI output copyright and automated decision making",
        summary="The article discusses copyright in AI output, training data and automated decision making.",
        published_at=datetime.now(timezone.utc),
    )
    text = LLMNewsWriter._fallback_legal_commentary(article, "tools", "ai_law")
    lowered = text.lower()
    assert "output" in lowered
    assert "training data" in lowered
    assert "automated decision" in lowered


def test_fallback_legal_commentary_for_litigation_article_is_specific() -> None:
    article = ArticleCandidate(
        source_url="https://example.com/rss",
        article_url="https://example.com/ediscovery-ai",
        title="AI in e-discovery and document review",
        summary="The article discusses e-discovery, document review and explainability in litigation workflows.",
        published_at=datetime.now(timezone.utc),
    )
    text = LLMNewsWriter._fallback_legal_commentary(article, "case", "litigation")
    lowered = text.lower()
    assert "chain of custody" in lowered
    assert "legal hold" in lowered
    assert "human-in-the-loop" in lowered


def test_generic_legal_commentary_detection() -> None:
    assert LLMNewsWriter._looks_generic_legal_commentary("Есть риски, которые нужно учитывать.")
    assert not LLMNewsWriter._looks_generic_legal_commentary(
        "Юристу стоит проверить SLA, vendor lock-in, privacy-контур и распределение ответственности."
    )
