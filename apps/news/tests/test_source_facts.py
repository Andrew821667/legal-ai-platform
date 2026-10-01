"""Сверка «жёстких» фактов поста с источником (news.source_facts)."""
from __future__ import annotations

from news import source_facts
from news.daily_report import fact_guard_lines

SOURCE = (
    "Госдума приняла закон № 243-ФЗ. Изменения в статью 10 Гражданского кодекса вступают в силу "
    "с 1 марта 2027 года. Выручка рынка превысила 20,7 млрд рублей, рост — 17%. Штраф до 50 000 рублей."
)


def test_post_with_facts_from_source_passes() -> None:
    post = (
        "<b>Что изменилось</b>\nЗакон 243-ФЗ меняет ст. 10 ГК РФ с 01.03.2027. "
        "Рынок — 20,7 млрд ₽, рост 17 %, штраф до 50 000 ₽."
    )
    assert source_facts.unsupported_facts("Закон № 243-ФЗ", post, SOURCE) == []


def test_invented_law_article_date_and_amount_are_caught() -> None:
    post = "Закон 245-ФЗ меняет ст. 12 с 1 апреля 2027, рынок — 21 млрд ₽, № А40-1234/2026."
    problems = source_facts.unsupported_facts("Новость", post, SOURCE)
    assert "245-ФЗ" in problems
    assert "ст. 12" in problems
    assert "01.04.2027" in problems
    assert any(item.startswith("21 ") for item in problems)
    assert "№ А40-1234/2026" in problems


def test_our_footer_and_source_block_are_not_checked() -> None:
    post = (
        "<b>Главное</b>\nЗакон 243-ФЗ вступает в силу 1 марта 2027.\n\n"
        "<b>Следующий шаг</b>\nКонсультация юриста — 4 900 ₽, проверка договора от 7 900 ₽.\n\n"
        '<b>Источник</b>\n<a href="https://example.ru/news/2026/09/30/123">example.ru</a>\n\n#право_РФ'
    )
    assert source_facts.unsupported_facts("Закон", post, SOURCE) == []


def test_numbers_do_not_glue_across_words() -> None:
    # «в 2025 17 компаний» — два числа, а не 202517.
    source = "В 2025 17 компаний увеличили выручку на 12%."
    assert source_facts.unsupported_facts("", "Выручка выросла на 12% у 17 компаний.", source) == []


def test_dates_can_be_skipped_for_weekly_reviews() -> None:
    post = "Обзор недели 22 сентября — 28 сентября."
    assert source_facts.unsupported_facts("", post, SOURCE)
    assert source_facts.unsupported_facts("", post, SOURCE, check_dates=False) == []


def test_journal_summary_and_report_lines() -> None:
    source_facts._journal.clear()
    source_facts.record("checked", "A")
    source_facts.record("repaired", "B")
    source_facts.record("rejected", "Придуманный закон")
    summary = source_facts.journal_summary()
    assert (summary["checked"], summary["repaired"], summary["rejected"]) == (1, 1, 1)
    text = fact_guard_lines(summary)
    assert "подтверждено 1, исправлено 1, не допущено 1" in text
    assert "Придуманный закон" in text
    assert "данных пока нет" in fact_guard_lines(None)
