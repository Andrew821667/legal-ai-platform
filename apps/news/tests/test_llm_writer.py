from __future__ import annotations

from datetime import UTC, datetime

from news.llm_writer import LLMNewsWriter, compose_manual_post_html
from news.pipeline import ArticleCandidate
from prompts.news import build_news_writer_system_prompt


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    def create(self, **_: object) -> object:
        message = type("Message", (), {"content": self._content})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


class _SequenceFakeCompletions:
    def __init__(self, contents: list[str]) -> None:
        self._contents = list(contents)

    def create(self, **_: object) -> object:
        if not self._contents:
            raise AssertionError("no more fake completions")
        message = type("Message", (), {"content": self._contents.pop(0)})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


class _SequenceFakeChat:
    def __init__(self, contents: list[str]) -> None:
        self.completions = _SequenceFakeCompletions(contents)


class _SequenceFakeClient:
    def __init__(self, contents: list[str]) -> None:
        self.chat = _SequenceFakeChat(contents)


def test_looks_complete_prose_accepts_finished_text() -> None:
    text = "<b>Что произошло</b>\nТекст завершен.\n\n<b>Источник</b>: ссылка\n#AIVerdict"
    assert LLMNewsWriter._looks_complete_prose(text)


def test_looks_complete_prose_rejects_incomplete_tail() -> None:
    text = "<b>Что произошло</b>\nТекст оборван потому\n\n<b>Источник</b>: ссылка\n#AIVerdict"
    assert not LLMNewsWriter._looks_complete_prose(text)


def test_specificity_signal_allows_legal_markers_without_digits() -> None:
    text = "<b>Юридические риски</b>\nНужно проверить персональные данные, договорную ответственность и AI Act."
    assert LLMNewsWriter._has_specificity_signal(text)


def test_blocks_look_complete_rejects_truncated_internal_paragraph() -> None:
    text = (
        "<b>Что произошло</b>\nAnthropic попала в политический конфликт вокруг оборонных поставок и Пента\n\n"
        "<b>Почему это важно</b>\nЭто влияет на выбор поставщиков и корпоративные AI-стратегии.\n\n"
        "<b>Что это значит для рынка</b>\nРынок начнет жестче смотреть на политические риски AI-вендоров.\n\n"
        "<b>Источник</b>: ссылка\n#AIVerdict"
    )
    assert not LLMNewsWriter._blocks_look_complete(text)


def test_blocks_look_complete_ignores_title_line_without_period() -> None:
    text = (
        "<b>Theorem выпустил гид по Legal AI-платформам для юристов</b>\n\n"
        "<b>Что произошло</b>\nTheorem собрал обзор платформ, которые помогают юристам выбирать рабочий стек Legal AI.\n\n"
        "<b>Почему это важно</b>\nДля юрфункции это полезно как карта рынка и ориентир для vendor due diligence.\n\n"
        "<b>Что это значит для рынка</b>\nКомпании начнут сравнивать платформы не только по точности, но и по governance, SLA и режиму данных.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict #AI #LegalTech"
    )
    assert LLMNewsWriter._blocks_look_complete(text)


def test_quality_gate_rejects_title_cut_after_preposition() -> None:
    text = (
        "<b>Legora переходит от лицензии на рабочее место к лицензии на</b>\n\n"
        "Рынок юридического AI меняет модель оплаты корпоративных продуктов. Это влияет на бюджетирование и договорные условия внедрения.\n\n"
        "<b>Что произошло</b>\nLegora предложила клиентам перейти от оплаты за рабочее место к оплате по объему использования. Новая модель связывает цену с потреблением токенов, поэтому расходы зависят от сценариев работы и активности пользователей.\n\n"
        "<b>Почему это важно</b>\nЮридическим командам придется оценивать не только число лицензий, но и стоимость отдельных операций. В договоре важно зафиксировать правила тарификации, контроль лимитов, уведомления о перерасходе и доступ к статистике потребления.\n\n"
        "<b>Что это значит для рынка</b>\nПеред пилотом стоит посчитать стоимость типовых задач, установить месячный лимит и назначить владельца бюджета. Это позволит сравнивать поставщиков по стоимости полезной операции, а не по цене одного рабочего места.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict #AI #LegalTech"
    )

    assert LLMNewsWriter._quality_gate_failure_reason(text, "daily") == "incomplete_title"


def test_quality_gate_rejects_title_cut_inside_last_word() -> None:
    text = (
        "<b>Международный ИИ-инструмент для арбитражной практики по корпоративн</b>\n\n"
        "Исследовательская команда описала LegalTech-сервис для анализа судебной практики по корпоративным спорам. Решение работает с массивом арбитражных актов и показывает первоисточники.\n\n"
        "<b>Что произошло</b>\nСервис использует ИИ-поиск по пяти миллионам решений арбитражных судов. Каждый ответ сопровождается ссылками на полные тексты судебных актов, чтобы юрист мог проверить вывод и контекст конкретного спора.\n\n"
        "<b>Почему это важно</b>\nТакой инструмент может сократить первичный поиск практики, но не заменяет проверку позиции по первоисточнику. Команде нужно оценить полноту базы, обновление данных и воспроизводимость результата на собственных делах.\n\n"
        "<b>Что проверить юристу</b>\nПеред использованием стоит провести тест на выборке завершенных дел, сверить найденные акты и зафиксировать правило обязательной проверки человеком. В договоре с поставщиком нужны условия о данных, SLA и ответственности за недоступность сервиса.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict #AI #LegalTech"
    )

    assert LLMNewsWriter._quality_gate_failure_reason(text, "daily") == "incomplete_title_word"


def test_quality_gate_rejects_unclosed_parenthesis() -> None:
    text = (
        "<b>Итоги недели в Legal AI</b>\n\n"
        "<b>Ключевые сигналы недели</b>\n"
        "1. OpenAI обновила корпоративные инструменты и добавила контроль доступа.\n"
        "2. LegalTech-платформа изменила модель лицензирования для юридических команд.\n"
        "3. Компании усиливают аудит договоров с поставщиками AI-сервисов.\n"
        "4. Регуляторы уточняют требования к обработке персональных данных.\n"
        "5. Юридические департаменты измеряют стоимость автоматизированных операций.\n"
        "6. Это обзор материалов с начала недели (2026-07-13.\n"
        "7. Команды вводят human-in-the-loop для проверки результата моделей.\n"
        "8. Поставщики расширяют журналирование действий и управление доступом.\n\n"
        "<b>Что это значит для юрфункции</b>\nКонтроль стоимости и данных становится частью договорной архитектуры Legal AI.\n\n"
        "<b>На что смотреть юристам</b>\nНужно проверить SLA, ответственность, права на данные и порядок аудита.\n\n"
        "<b>Что проверить у себя</b>\nЗафиксируйте владельца процесса, лимиты расходов и контроль качества результата.\n\n"
        "<b>Источник</b>: редакционный обзор\n"
        "#AIVerdict #AI #LegalTech"
    )

    assert LLMNewsWriter._quality_gate_failure_reason(text, "weekly_review") == "unbalanced_parentheses"


def test_quality_gate_rejects_daily_with_single_action_item() -> None:
    text = (
        "<b>Law Insider: как юристы используют ИИ в договорной работе</b>\n\n"
        "Опрос 534 трансакционных юристов из 75 стран показывает, какие инструменты участники используют в договорной работе. Выборка собрана внутри сообщества поставщика.\n\n"
        "<b>Что произошло</b>\nLaw Insider опросил участников своего сообщества об использовании ИИ. В числе популярных инструментов оказались фундаментальные модели и специализированные решения для договоров, однако состав выборки ограничивает перенос выводов на весь рынок.\n\n"
        "<b>Почему это важно</b>\nЮридическим командам полезно учитывать знакомство сотрудников с базовыми моделями, но опрос поставщика сам по себе не доказывает преимущество одного класса продуктов. Решение о закупке требует сравнения на собственных документах.\n\n"
        "<b>Где это можно применить</b>\n"
        "• Сразу заключить прямой контракт с поставщиком фундаментальной модели и установить жесткий SLA для всех договорных задач.\n\n"
        "<b>Источник</b>: ссылка\n"
        "#AIVerdict #AI #LegalTech"
    )

    assert LLMNewsWriter._quality_gate_failure_reason(text, "daily") == "weak_daily_list_items:1"


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
        "#AIVerdict #AI #LegalTech"
    )
    assert LLMNewsWriter._passes_quality_gate(text, "daily")


def test_structured_formats_disable_low_quality_fallback() -> None:
    assert not LLMNewsWriter._allow_quality_fallback("daily")
    assert not LLMNewsWriter._allow_quality_fallback("weekly_review")
    assert not LLMNewsWriter._allow_quality_fallback("longread")
    assert LLMNewsWriter._allow_quality_fallback("standard")


def test_build_news_writer_system_prompt_toggles_optional_module() -> None:
    enabled = build_news_writer_system_prompt(adoption_module_enabled=True)
    disabled = build_news_writer_system_prompt(adoption_module_enabled=False)

    assert "Модуль [adoption_pattern]" in enabled
    assert "включен" in enabled
    assert "adoption_fit" in enabled
    assert "выключен" in disabled


def test_build_news_writer_system_prompt_prefers_russian_terms() -> None:
    prompt = build_news_writer_system_prompt(adoption_module_enabled=True)

    assert "по умолчанию пиши «ИИ»" in prompt
    assert "а не AI, vendor, workflow" in prompt
    assert "выбор поставщика" in prompt


def test_build_news_writer_system_prompt_blocks_competitor_promotion() -> None:
    prompt = build_news_writer_system_prompt(adoption_module_enabled=True)

    assert "Не продвигай сторонних российских Legal AI-вендоров" in prompt
    assert "competitor_marketing = true" in prompt
    assert '"competitor_marketing": false' in prompt


def test_quality_gate_rejects_competitor_brand_leak() -> None:
    text = "<b>LawGPT выпустил новую функцию</b>\n\nРекламный материал конкурента."
    assert LLMNewsWriter._quality_gate_failure_reason(text, "daily") == "competitor_brand_mention"


def test_daily_format_prefers_adoption_block_when_present() -> None:
    writer = LLMNewsWriter.__new__(LLMNewsWriter)
    title, text, rubric = writer._format_post(
        {
            "title": "Новый AI-инструмент для договорной работы",
            "rubric": "legal_ops",
            "lead": "На рынке появился новый инструмент для команд, которые хотят ускорить проверку договоров.",
            "what_happened": "Вендор выпустил AI-функцию для сравнения версий, выявления red flags и подготовки summary по договору.",
            "business_effect": "Это сокращает время первичной проверки и помогает командам быстрее разбирать типовые документы.",
            "legal_risks": "Юристам все равно нужно проверить режим данных, ограничения на output и договорную ответственность поставщика.",
            "conclusion": "Практический интерес здесь связан с автоматизацией повторяющихся шагов в договорной работе.",
            "adoption_fit": "strong",
            "adoption_patterns": [
                "Первичная AI-проверка типовых договоров и выделение red flags до ручной ревизии юриста",
                "Подготовка короткого summary для внутреннего заказчика перед согласованием документа",
            ],
        },
        "https://example.com/article",
        "Новый AI-инструмент для договорной работы",
        format_type="daily",
        cta_type="soft",
        pillar="tools",
    )
    assert title == "Новый AI-инструмент для договорной работы"
    assert rubric == "legal_ops"
    assert "Где это можно применить" in text
    assert "Первичная ИИ-проверка типовых договоров" in text
    assert "рисковые признаки" in text
    assert "Что это значит для команд" not in text


def test_format_post_skips_intelligent_footer_when_disabled() -> None:
    writer = LLMNewsWriter.__new__(LLMNewsWriter)
    _, text, _ = writer._format_post(
        {
            "title": "Новый ИИ-инструмент для договорной работы",
            "rubric": "legal_ops",
            "lead": "На рынке появился новый инструмент для ускорения проверки договоров.",
            "what_happened": "Поставщик выпустил ИИ-функцию для сравнения версий и поиска рисков.",
            "business_effect": "Это сокращает время первичной проверки и помогает быстрее разбирать типовые документы.",
            "legal_risks": "Юристам нужно проверить режим данных, договорную ответственность поставщика и качество результата.",
            "conclusion": "Практический интерес связан с автоматизацией повторяющихся шагов.",
            "adoption_fit": "strong",
            "adoption_patterns": ["Первичная ИИ-проверка типовых договоров до ручной ревизии юриста"],
        },
        "https://example.com/article",
        "Новый ИИ-инструмент для договорной работы",
        format_type="daily",
        cta_type="soft",
        pillar="tools",
        intelligent_footer_enabled=False,
    )

    assert "Следующий шаг" not in text


def test_standard_format_skips_footer_without_adoption_patterns() -> None:
    writer = LLMNewsWriter.__new__(LLMNewsWriter)
    _, text, _ = writer._format_post(
        {
            "title": "Регулятор опубликовал новый обзор по AI",
            "rubric": "regulation",
            "lead": "Появился новый обзор регулятора по AI и данным.",
            "what_happened": "Регулятор выпустил обзор подходов к надзору за AI-системами и связанными данными.",
            "business_effect": "Для рынка это сигнал об усилении внимания к governance и контролю поставщиков.",
            "legal_risks": "Юристам важно проверить режим данных, внутренний контроль и договорный контур с вендорами.",
            "conclusion": "Новость важна как регуляторный сигнал, но без прямого прикладного сценария.",
            "adoption_fit": "none",
            "adoption_patterns": [],
        },
        "https://example.com/article",
        "Регулятор опубликовал новый обзор по AI",
        format_type="standard",
        cta_type="soft",
        pillar="market",
    )
    assert "Следующий шаг" not in text


def test_quality_gate_rejects_prompt_leak_markers() -> None:
    text = (
        "<b>Обзор недели</b>\n\n"
        "<b>Ключевые сигналы недели</b>\n1. Пункт один.\n2. Пункт два.\n3. Пункт три.\n4. Пункт четыре.\n"
        "5. Пункт пять.\n6. Пункт шесть.\n7. Пункт семь.\n8. Пункт восемь.\n\n"
        "<b>Что это значит для юрфункции</b>\nСтилистика канала: деловой тон и плотный анализ.\n\n"
        "<b>На что смотреть юристам</b>\nПроверить контур ответственности поставщика.\n\n"
        "<b>Что проверить у себя</b>\n• Обновить KPI.\n\n"
        "<b>Источник</b>: ссылка\n#AIVerdict"
    )
    assert LLMNewsWriter._quality_gate_failure_reason(text, "weekly_review") == "prompt_leak:стилистика канала"


def test_quality_gate_rejects_format_instruction_leak() -> None:
    text = (
        "<b>Обзор недели</b>\n\n"
        "<b>Ключевые сигналы недели</b>\n"
        "1. Первый сигнал.\n2. Второй сигнал.\n3. Третий сигнал.\n4. Четвертый сигнал.\n"
        "5. Пятый сигнал.\n6. Шестой сигнал.\n7. Седьмой сигнал.\n8. Восьмой сигнал.\n\n"
        "<b>Что это значит для юрфункции</b>\nФормат weekly_review: 8-10 пунктов и плотная аналитика.\n\n"
        "<b>На что смотреть юристам</b>\nПроверить контур ответственности поставщика.\n\n"
        "<b>Что проверить у себя</b>\n• Обновить KPI.\n\n"
        "<b>Источник</b>: ссылка\n#AIVerdict"
    )
    assert LLMNewsWriter._quality_gate_failure_reason(text, "weekly_review") == "prompt_leak:формат weekly_review"


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
        "<b>Источник</b>: ссылка\n#AIVerdict #AI #LegalTech"
    )
    assert LLMNewsWriter._quality_gate_failure_reason(text, "weekly_review") == "weak_weekly_points:4"


def test_quality_gate_rejects_weekly_with_escaped_markup() -> None:
    text = (
        "<b>Обзор недели</b>\n\n"
        "<b>Ключевые сигналы недели</b>\n"
        "1. Первый сигнал — &lt;b&gt;дублированный фрагмент&lt;/b&gt;.\n"
        "2. Второй сигнал.\n"
        "3. Третий сигнал.\n"
        "4. Четвертый сигнал.\n"
        "5. Пятый сигнал.\n"
        "6. Шестой сигнал.\n"
        "7. Седьмой сигнал.\n"
        "8. Восьмой сигнал.\n\n"
        "<b>Что это значит для юрфункции</b>\nДлинный аналитический блок про governance, SLA, vendor due diligence и контроль качества output для стабильного внедрения Legal AI.\n\n"
        "<b>На что смотреть юристам</b>\nДлинный аналитический блок про права на данные, трансграничную передачу, audit trails и распределение ответственности в договорной конструкции.\n\n"
        "<b>Что проверить у себя</b>\n"
        "• Проверить критерии качества.\n"
        "• Обновить contractual safeguards.\n"
        "• Назначить owner за контроль output.\n"
        "• Проверить privacy и security-контур.\n\n"
        "<b>Источник</b>: ссылка\n#AIVerdict #AI #LegalTech"
    )
    assert LLMNewsWriter._quality_gate_failure_reason(text, "weekly_review") == "escaped_markup"


def test_derive_weekly_points_sanitizes_duplicates_and_markup() -> None:
    data = {
        "weekly_points": [
            "1. Юрист как оператор кнопки — &lt;b&gt;Юрист как оператор кнопки&lt;/b&gt; Вопрос роли юриста.",
            "2. Юрист как оператор кнопки — Вопрос роли юриста.",
            "3. LIGA360 запустила Contractum для автоматизации договорной работы.",
            "Сигналы недели для итогового обзора: 10. 2.",
        ],
        "what_happened": "",
        "business_effect": "",
        "legal_risks": "",
    }
    points = LLMNewsWriter._derive_weekly_points(data)
    assert len(points) == 2
    assert "Юрист как оператор кнопки." in points[0]
    assert all("&lt;" not in point and "<b>" not in point for point in points)


def test_sanitize_weekly_point_rejects_truncated_tail() -> None:
    assert (
        LLMNewsWriter._sanitize_weekly_point(
            "LIGA360 запустила систему Contractum для автоматизации договорной работы. В системе появился новый модуль для."
        )
        == ""
    )


def test_fallback_weekly_post_passes_quality_gate_for_dirty_summary() -> None:
    writer = LLMNewsWriter.__new__(LLMNewsWriter)
    article = ArticleCandidate(
        source_url="internal://weekly-review",
        article_url="internal://weekly-review/2026-W10",
        title="Обзор недели по Legal AI и автоматизации юрфункции (W10)",
        summary=(
            "Сигналы недели для итогового обзора:\n"
            "1. Юрист как оператор кнопки — &lt;b&gt;Юрист как оператор кнопки&lt;/b&gt; Обсуждение роли юриста.\n"
            "2. LIGA360 запустила Contractum для автоматизации договорной работы.\n"
            "3. 10. 2.\n"
        ),
        published_at=datetime.now(UTC),
    )
    result = writer._fallback_post(article, format_type="weekly_review", cta_type="soft", pillar="implementation")
    assert len(result["text"]) >= 2800
    assert "&lt;" not in result["text"]
    assert LLMNewsWriter._quality_gate_failure_reason(result["text"], "weekly_review") is None


def test_quality_gate_failure_reason_for_short_daily() -> None:
    text = "<b>Короткий пост</b>\n\n<b>Что произошло</b>\nМало текста.\n\n<b>Почему это важно</b>\nМало.\n\n<b>Юридический контур</b>\nЕще мало.\n\n<b>Источник</b>: ссылка"
    reason = LLMNewsWriter._quality_gate_failure_reason(text, "daily")
    assert reason is not None
    assert reason.startswith("too_short:")


def test_relevance_bias_hint_for_enterprise_ai_signal() -> None:
    article = ArticleCandidate(
        source_url="https://habr.com/ru/rss/news/?fl=ru",
        article_url="https://habr.com/ru/news/enterprise-ai-copilot",
        title="Enterprise AI-платформа выпустила reasoning copilot для корпоративных команд",
        summary=(
            "Вендор представил enterprise AI assistant с agentic workflow и multimodal reasoning. "
            "Релиз влияет на vendor selection, governance и автоматизацию корпоративных процессов."
        ),
        published_at=datetime.now(UTC),
    )
    hint = LLMNewsWriter._relevance_bias_hint(article, "tools")
    assert "пограничный, но приоритетный ИИ-сигнал" in hint


def test_relevance_bias_hint_empty_for_noise() -> None:
    article = ArticleCandidate(
        source_url="https://habr.com/ru/rss/news/?fl=ru",
        article_url="https://habr.com/ru/news/misc-tech",
        title="Новый USB-хаб для домашних рабочих мест",
        summary="Материал про периферию для домашнего офиса без AI-контекста и бизнес-сигнала.",
        published_at=datetime.now(UTC),
    )
    assert LLMNewsWriter._relevance_bias_hint(article, "tools") == ""


def test_temporal_guard_rejects_near_term_forecast_same_day() -> None:
    text = (
        "<b>Что произошло</b>\n"
        "Ожидается снижение ключевой ставки ЦБ на 0,5 п.п.\n\n"
        "<b>Почему это важно</b>\n"
        "Это повлияет на рынок.\n\n"
        "<b>Что это значит для рынка</b>\n"
        "Нужно следить за реакцией.\n\n"
        "<b>Источник</b>: ссылка\n#AIVerdict"
    )
    reason = LLMNewsWriter._temporal_guard_failure_reason(
        text,
        target_publish_at=datetime(2026, 3, 24, 18, 0, tzinfo=UTC),
        source_published_at=datetime(2026, 3, 24, 8, 0, tzinfo=UTC),
        format_type="daily",
    )
    assert reason == "needs_temporal_recheck:near_term_forecast"


def test_temporal_guard_rejects_elapsed_weekly_calendar_window() -> None:
    text = (
        "<b>Обзор недели</b>\n\n"
        "<b>Ключевые сигналы недели</b>\n"
        "1. Регулятор может принять следующий шаг во второй половине марта.\n"
        "2. Пункт два.\n3. Пункт три.\n4. Пункт четыре.\n5. Пункт пять.\n6. Пункт шесть.\n7. Пункт семь.\n8. Пункт восемь.\n\n"
        "<b>Что это значит для юрфункции</b>\n"
        "Длинный блок про governance, качество и сроки.\n\n"
        "<b>На что смотреть юристам</b>\n"
        "Длинный блок про контроль качества и дедлайны.\n\n"
        "<b>Что проверить у себя</b>\n"
        "• Проверить процесс.\n• Обновить контур.\n• Назначить owner.\n• Проверить контроль.\n\n"
        "<b>Источник</b>: ссылка\n#AIVerdict #AI #LegalTech"
    )
    reason = LLMNewsWriter._temporal_guard_failure_reason(
        text,
        target_publish_at=datetime(2026, 3, 29, 12, 0, tzinfo=UTC),
        source_published_at=datetime(2026, 3, 24, 8, 0, tzinfo=UTC),
        format_type="weekly_review",
    )
    assert reason == "needs_temporal_recheck:elapsed_calendar_window"


def test_completion_kwargs_disable_deepseek_reasoning_for_routine_generation() -> None:
    writer = LLMNewsWriter.__new__(LLMNewsWriter)
    writer._use_max_tokens_param = True
    writer._thinking_enabled = False
    writer._reasoning_token_reserve = 0

    assert writer._completion_kwargs("daily") == {
        "max_tokens": 1800,
        "extra_body": {"thinking": {"type": "disabled"}},
    }
    assert writer._completion_kwargs("weekly_review") == {
        "max_tokens": 3400,
        "extra_body": {"thinking": {"type": "disabled"}},
    }


def test_completion_kwargs_reserve_space_when_deepseek_reasoning_is_enabled() -> None:
    writer = LLMNewsWriter.__new__(LLMNewsWriter)
    writer._use_max_tokens_param = True
    writer._thinking_enabled = True
    writer._reasoning_token_reserve = 3000

    assert writer._token_limit_kwargs(260) == {
        "max_tokens": 3260,
        "extra_body": {"thinking": {"type": "enabled"}},
    }


def test_completion_kwargs_keep_plain_provider_budget() -> None:
    writer = LLMNewsWriter.__new__(LLMNewsWriter)
    writer._use_max_tokens_param = False
    writer._reasoning_token_reserve = 0

    assert writer._completion_kwargs("daily") == {"max_completion_tokens": 1800}


def test_generate_post_applies_fact_check_correction_for_subject_mixup() -> None:
    writer = LLMNewsWriter.__new__(LLMNewsWriter)
    writer.client = _SequenceFakeClient(
        [
            """{"is_relevant": true, "reject_reason": "", "title": "Ипотечные квартиры и аренда", "rubric": "market", "lead": "Лид о рынке ипотеки и аренды.", "what_happened": "Доля сдаваемых ипотечных квартир достигла 40-45%. Многие заемщики арендуют жилье для покрытия кредитных платежей.", "business_effect": "Это влияет на рынок аренды и на поведение инвесторов в жилую недвижимость.", "legal_risks": "Нужно проверить договорный контур, раскрытие условий аренды и распределение рисков.", "next_steps": "Проверить продукт; сверить риски; обновить модель", "conclusion": "Вывод о том, что рынок меняет модель использования ипотечного жилья.", "hashtags": ["#AIVerdict"]}""",
            """{"approved": true, "reason": "", "title": "Ипотечные квартиры и аренда", "text": "<b>Ипотечные квартиры и аренда</b>\n\nЛид о рынке ипотеки и аренды, где поведение заемщиков уже влияет на структуру предложения и на логику инвестиционных решений.\n\n<b>Что произошло</b>\nДоля сдаваемых ипотечных квартир достигла 40-45%. Многие заемщики сдают жилье, чтобы покрывать кредитные платежи, а не сами снимают его. Это меняет картину предложения и поведение собственников на рынке.\n\n<b>Почему это важно</b>\nДля рынка это сигнал, что ипотечное жилье все чаще рассматривается как денежный поток, а не только как объект проживания. Это влияет на стратегию инвесторов, модель спроса и устойчивость арендных ставок.\n\n<b>Что это значит для рынка</b>\nЮристам и продуктовым командам важно смотреть на договорную модель аренды, режим раскрытия условий, риски по просрочке и то, как кредитные ограничения влияют на фактическое использование объекта. Ошибка в трактовке роли собственника здесь меняет весь смысл новости.\n\n<b>Источник</b>: ссылка\n#AIVerdict #AI #LegalTech"}""",
        ]
    )
    writer.model = "fake"
    writer._use_max_tokens_param = True
    article = ArticleCandidate(
        source_url="https://example.com/feed",
        article_url="https://example.com/article",
        title="Ипотечные квартиры и аренда",
        summary="Доля сдаваемых ипотечных квартир достигла 40-45%. Многие заемщики сдают жилье для покрытия кредитных платежей.",
        published_at=datetime(2026, 3, 24, 8, 0, tzinfo=UTC),
    )
    result = writer.generate_post(
        article,
        [],
        format_type="daily",
        cta_type="soft",
        pillar="market",
        target_publish_at=datetime(2026, 3, 24, 18, 0, tzinfo=UTC),
    )
    assert result is not None
    assert "сдают жилье" in result["text"]
    assert "арендуют жилье" not in result["text"]


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
        "#AIVerdict #AI #LegalTech"
    )
    assert LLMNewsWriter._quality_gate_failure_reason(text, "daily") == "weak_daily_third_block:47"


def test_language_gate_rejects_english_title_and_body() -> None:
    text = (
        "<b>New AI platform changes legal operations</b>\n\n"
        "<b>Что произошло</b>\nA new platform was launched for corporate legal teams. "
        "It automates contract review, intake and document analysis across multiple business systems.\n\n"
        "<b>Почему это важно</b>\nThe release changes how teams purchase and deploy legal technology. "
        "Buyers should review data access, audit logs, service levels and supplier accountability.\n\n"
        "<b>Что это значит для рынка</b>\nVendors will compete on workflow integration, measurable outcomes and governance. "
        "Legal departments should define a pilot, owner and quality metrics before scaling.\n\n"
        "<b>Источник</b>: https://example.com/news\n#AIVerdict #LegalTech"
    )

    reason = LLMNewsWriter._language_gate_failure_reason(text)

    assert reason == "language_title_not_russian"


def test_language_gate_allows_russian_post_with_product_names() -> None:
    text = (
        "<b>OpenAI обновила платформу для корпоративных команд</b>\n\n"
        "<b>Что произошло</b>\nКомпания представила обновление API для автоматизации повторяющихся операций. "
        "В центре релиза находятся управляемые рабочие процессы, журналирование и интеграция с внутренними системами.\n\n"
        "<b>Почему это важно</b>\nЮридическим департаментам нужно оценивать не название модели, а качество результата, "
        "режим доступа к данным, договорную ответственность поставщика и стоимость одной операции.\n\n"
        "<b>Что это значит для рынка</b>\nПеред пилотом стоит зафиксировать владельца процесса, SLA, метрики и порядок проверки человеком. "
        "Так команда сможет измерить эффект и контролировать риски до масштабирования.\n\n"
        "<b>Источник</b>: https://example.com/news\n#AIVerdict #LegalTech"
    )

    assert LLMNewsWriter._language_gate_failure_reason(text) is None


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
        published_at=datetime.now(UTC),
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
        published_at=datetime.now(UTC),
    )
    text = LLMNewsWriter._fallback_legal_commentary(article, "tools", "contracts")
    lowered = text.lower()
    assert "sla" in lowered
    assert "результат" in lowered
    assert "зависимости от поставщика" in lowered


def test_infer_rubric_hint_for_litigation_article() -> None:
    article = ArticleCandidate(
        source_url="https://example.com/rss",
        article_url="https://example.com/legal-hold-ai",
        title="AI document review and legal hold in litigation",
        summary="The article discusses AI document review, legal hold and chain of custody requirements.",
        published_at=datetime.now(UTC),
    )
    assert LLMNewsWriter._infer_rubric_hint(article, "case") == "litigation"


def test_fallback_legal_commentary_for_regulation_article_is_specific() -> None:
    article = ArticleCandidate(
        source_url="https://example.com/rss",
        article_url="https://example.com/ai-act-governance",
        title="AI Act governance and risk classification update",
        summary="The article covers AI Act obligations, governance and logging duties for enterprise deployments.",
        published_at=datetime.now(UTC),
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
        published_at=datetime.now(UTC),
    )
    text = LLMNewsWriter._fallback_legal_commentary(article, "tools", "ai_law")
    lowered = text.lower()
    assert "результат" in lowered
    assert "обучающие данные" in lowered
    assert "автоматизированного принятия решений" in lowered


def test_fallback_legal_commentary_for_litigation_article_is_specific() -> None:
    article = ArticleCandidate(
        source_url="https://example.com/rss",
        article_url="https://example.com/ediscovery-ai",
        title="AI in e-discovery and document review",
        summary="The article discusses e-discovery, document review and explainability in litigation workflows.",
        published_at=datetime.now(UTC),
    )
    text = LLMNewsWriter._fallback_legal_commentary(article, "case", "litigation")
    lowered = text.lower()
    assert "цепочку хранения доказательств" in lowered
    assert "сохранение документов" in lowered
    assert "участие человека" in lowered


def test_generic_legal_commentary_detection() -> None:
    assert LLMNewsWriter._looks_generic_legal_commentary("Есть риски, которые нужно учитывать.")
    assert not LLMNewsWriter._looks_generic_legal_commentary(
        "Юристу стоит проверить SLA, vendor lock-in, privacy-контур и распределение ответственности."
    )


def test_semantic_footer_html_adds_clickable_assistant_link() -> None:
    writer = LLMNewsWriter.__new__(LLMNewsWriter)
    writer.client = _FakeClient(
        '{"include_footer": true, "footer_text": "Эту практику можно применить у вас в юрфункции. Напишите в Ассистент AI Verdict.", "fit_reason": "case fit"}'
    )
    writer.model = "deepseek-chat"
    writer._use_max_tokens_param = True

    footer_html = writer._semantic_footer_html(
        title="Кейс автоматизации intake",
        rubric="legal_ops",
        pillar="implementation",
        format_type="daily",
        cta_type="soft",
        lead="Короткий лид",
        what_happened="Описание фактов",
        business_effect="Описание эффекта",
        legal_risks="Описание ограничений",
        conclusion="Итог",
    )

    assert 'Ассистент' in footer_html
    assert 'https://t.me/legal_ai_helper_new_bot' in footer_html


def test_semantic_footer_html_dedupes_duplicate_assistant_cta() -> None:
    writer = LLMNewsWriter.__new__(LLMNewsWriter)
    writer.client = _FakeClient(
        '{"include_footer": true, "footer_text": "Если для вашей команды тоже актуальна автоматизация проверки договоров, обсудите возможные сценарии с Ассистентом AI Verdict. Напишите в Ассистент AI Verdict.", "fit_reason": "implementation fit"}'
    )
    writer.model = "deepseek-chat"
    writer._use_max_tokens_param = True

    footer_html = writer._semantic_footer_html(
        title="Проверка договоров с AI",
        rubric="legal_ops",
        pillar="implementation",
        format_type="daily",
        cta_type="soft",
        lead="Короткий лид",
        what_happened="Описание фактов",
        business_effect="Описание эффекта",
        legal_risks="Описание ограничений",
        conclusion="Итог",
    )

    assert footer_html.count("Ассистентом AI Verdict") == 1
    assert "Напишите" not in footer_html
    assert 'href="https://t.me/legal_ai_helper_new_bot"' in footer_html


def test_semantic_footer_html_dedupes_typo_and_repeated_assistant_cta() -> None:
    writer = LLMNewsWriter.__new__(LLMNewsWriter)
    writer.client = _FakeClient(
        '{"include_footer": true, "footer_text": "Если это актуально, обсудите с Асистентом AI Verdict, обсудите детали с Ассистентом AI Verdict. Напишите в @legal_ai_helper_new_bot.", "fit_reason": "implementation fit"}'
    )
    writer.model = "deepseek-chat"
    writer._use_max_tokens_param = True

    footer_html = writer._semantic_footer_html(
        title="AI для договоров",
        rubric="legal_ops",
        pillar="implementation",
        format_type="daily",
        cta_type="soft",
        lead="Короткий лид",
        what_happened="Описание фактов",
        business_effect="Описание эффекта",
        legal_risks="Описание ограничений",
        conclusion="Итог",
    )

    assert footer_html.count("Ассистентом AI Verdict") == 1
    assert "Асистент" not in footer_html
    assert "Напишите" not in footer_html


def test_normalize_post_footer_blocks_keeps_single_footer_before_source() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "Текст поста.\n\n"
        "<b>Следующий шаг</b>\nОбсудите с Асистентом AI Verdict.\n\n"
        "<b>Следующий шаг</b>\nНапишите в @legal_ai_helper_new_bot.\n\n"
        "<b>Источник</b>: ссылка\n#AIVerdict"
    )

    normalized = LLMNewsWriter.normalize_post_footer_blocks(original)

    assert normalized.count("<b>Следующий шаг</b>") == 1
    assert normalized.count("https://t.me/legal_ai_helper_new_bot") == 1
    assert "Асистент" not in normalized
    assert normalized.index("<b>Следующий шаг</b>") < normalized.index("<b>Источник</b>")


def test_semantic_footer_html_skips_when_not_fit() -> None:
    writer = LLMNewsWriter.__new__(LLMNewsWriter)
    writer.client = _FakeClient('{"include_footer": false, "footer_text": "", "fit_reason": "no service match"}')
    writer.model = "deepseek-chat"
    writer._use_max_tokens_param = True

    footer_html = writer._semantic_footer_html(
        title="Нейтральная новость",
        rubric="market",
        pillar="market",
        format_type="daily",
        cta_type="soft",
        lead="Короткий лид",
        what_happened="Описание фактов",
        business_effect="Описание эффекта",
        legal_risks="Описание ограничений",
        conclusion="Итог",
    )

    assert footer_html == ""


def test_compose_manual_post_html_uses_explicit_footer_text() -> None:
    post_html = compose_manual_post_html(
        "Тест",
        "Тело поста",
        "promo_offer",
        footer_text="Ненавязчивый следующий шаг.",
    )
    assert "<b>Следующий шаг</b>" in post_html
    assert "Ассистент" in post_html


def test_compose_manual_post_html_skips_footer_when_explicitly_empty() -> None:
    post_html = compose_manual_post_html(
        "Тест",
        "Тело поста",
        "promo_offer",
        footer_text="",
    )
    assert "<b>Следующий шаг</b>" not in post_html


def test_normalize_title_for_longread_strips_prefix() -> None:
    normalized = LLMNewsWriter._normalize_title_for_format("Лонгрид: AI для intake", "longread", "Fallback")
    assert normalized == "AI для intake"


def test_human_style_gate_rejects_canned_phrase() -> None:
    reason = LLMNewsWriter._human_style_failure_reason(
        "Важно отметить: это не просто новая функция, а ключевой сдвиг для рынка."
    )

    assert reason == "robot_style_phrase:важно отметить"


def test_human_style_gate_rejects_marker_cluster() -> None:
    reason = LLMNewsWriter._human_style_failure_reason(
        "Ключевой фактор влияет на эффективность процесса. "
        "Это комплексная трансформация. Это решение меняет рынок. Это новый этап."
    )

    assert reason is not None
    assert reason.startswith("robot_style_cluster:")


def test_human_style_gate_allows_specific_editorial_prose() -> None:
    reason = LLMNewsWriter._human_style_failure_reason(
        "Поставщик изменил тариф: теперь цена зависит от числа обработанных документов. "
        "Перед пилотом юротделу стоит посчитать стоимость проверки одного договора и закрепить лимит в SLA."
    )

    assert reason is None
