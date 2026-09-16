"""Явная подсказка о связи в собственных словах клиента — кейс Рябовой:
«Обращался Рябов АА. Уже есть информация по нашему случаю» в её же
обращении должно подсветить владельцу лид Александра Рябова."""
import name_hints


def test_extracts_surname_like_tokens_and_skips_stopwords():
    text = "Обращался Рябов АА\nУже есть информация по нашему случаю"
    candidates = name_hints.extract_name_candidates(text)
    assert "Рябов" in candidates
    for noise in ("Обращался", "Уже", "Есть", "Информация", "По", "Нашему", "Случаю"):
        assert noise not in candidates


def test_real_ryabova_case_matches_ryabov_lead():
    other_leads = [
        {"id": 24, "name": "Александр Рябов", "created_at": "2026-09-07T16:56:37"},
    ]
    match = name_hints.find_related_lead(
        text="Обращался Рябов АА\nУже есть информация по нашему случаю",
        own_lead_id=25,
        own_name="Alena Riabova",
        other_leads=other_leads,
    )
    assert match is not None
    assert match["lead"]["id"] == 24
    flag = name_hints.build_relation_flag(match)
    assert "Рябов" in flag and "№24" in flag and "2026-09-07" in flag
    assert "конфликт" in flag.lower()


def test_no_match_returns_none():
    other_leads = [{"id": 1, "name": "Иван Петров", "created_at": "2026-09-01T00:00:00"}]
    match = name_hints.find_related_lead(
        text="Нужна консультация по трудовому спору, ничего особенного",
        own_lead_id=2,
        own_name="Кто-то",
        other_leads=other_leads,
    )
    assert match is None


def test_own_lead_is_excluded_from_matches():
    other_leads = [{"id": 25, "name": "Alena Riabova", "created_at": "2026-09-08T00:00:00"}]
    match = name_hints.find_related_lead(
        text="Обращалась Рябова ранее",
        own_lead_id=25,
        own_name="Alena Riabova",
        other_leads=other_leads,
    )
    assert match is None


def test_own_surname_mentioned_about_self_is_not_flagged():
    # Человек упоминает свою же фамилию (например, представляется) — это не намёк на чужое дело.
    other_leads = [{"id": 9, "name": "Другой Клиент", "created_at": "2026-09-01T00:00:00"}]
    match = name_hints.find_related_lead(
        text="Здравствуйте, меня зовут Петров Иван, вопрос по договору",
        own_lead_id=5,
        own_name="Петров Иван",
        other_leads=other_leads,
    )
    assert match is None


def test_empty_text_returns_no_candidates():
    assert name_hints.extract_name_candidates("") == []
    assert name_hints.extract_name_candidates(None) == []
