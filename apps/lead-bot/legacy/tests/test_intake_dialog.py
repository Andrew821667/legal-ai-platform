"""Проверки уточняющего диалога.

Основное, что здесь закрепляется, — граница второго уровня самостоятельности:
ассистент собирает обстоятельства и ориентирует, но не оценивает ситуацию и не
советует. Эту границу легко размыть случайной правкой формулировки, поэтому
она под тестом.
"""

from __future__ import annotations

import pytest

import intake_dialog
import intake_outreach


def test_area_keys_match_core_api_enum() -> None:
    """Ключи областей права совпадают с перечислением в core-api.

    Ровно на этом уже спотыкались: в первом обращении были свои названия
    («labor», «court»), и шесть областей из десяти молча теряли уточнение.
    Список ниже переписан с LegalArea в core_api/models.py.
    """
    expected = {
        "contracts",
        "disputes",
        "corporate",
        "employment",
        "tax_compliance",
        "real_estate",
        "it_ip_data",
        "family_inheritance",
        "debt_bankruptcy",
        "other",
    }
    assert set(intake_dialog.AREA_GENITIVE) == expected
    assert set(intake_dialog.AREA_LABEL) == expected
    assert set(intake_dialog.QUESTIONS) == expected
    assert set(intake_dialog.DOCUMENTS) == expected
    assert set(intake_dialog.DEADLINE_NOTE) == expected


def test_outreach_names_the_area_for_every_case() -> None:
    """Первое сообщение называет тему обращения, а не отделывается общей фразой."""
    for area in intake_dialog.AREA_GENITIVE:
        if area == "other":
            continue
        message = intake_outreach.build_outreach_message({"legal_area": area, "name": "Иван"})
        assert intake_dialog.AREA_GENITIVE[area] in message


def test_unknown_area_does_not_break_dialog() -> None:
    assert intake_dialog.normalize_area("нет такой области") == "other"
    assert intake_dialog.normalize_area(None) == "other"
    assert intake_dialog.next_question("нет такой области", []) is not None


def test_questions_are_factual_not_evaluative() -> None:
    """Вопросы спрашивают об обстоятельствах, а не о правовой оценке.

    Второй уровень самостоятельности: ассистент выясняет, что произошло, но не
    подводит человека к юридическому выводу и не спрашивает его мнение о том,
    кто прав.
    """
    forbidden = ("кто прав", "как вы считаете", "правомерно", "законно ли", "имеете ли право")
    for area, questions in intake_dialog.QUESTIONS.items():
        for question in questions:
            lowered = question.text.lower()
            for phrase in forbidden:
                assert phrase not in lowered, f"{area}/{question.key}: {question.text}"


def test_question_keys_are_unique_within_area() -> None:
    for area, questions in intake_dialog.QUESTIONS.items():
        keys = [item.key for item in questions]
        assert len(keys) == len(set(keys)), area


def test_next_question_walks_through_and_stops() -> None:
    area = "employment"
    answered: list[str] = []
    seen = []
    while (question := intake_dialog.next_question(area, answered)) is not None:
        seen.append(question.key)
        answered.append(question.key)
        assert len(seen) <= 10, "обход не завершается"
    assert seen == [q.key for q in intake_dialog.QUESTIONS[area]]


def test_orientation_gives_no_legal_assessment() -> None:
    """Ориентация не превращается в совет или прогноз.

    Это главная граница второго уровня: назвать область права и нужные
    документы можно, сказать «вы правы» или «нужно подавать иск» — нет.
    """
    forbidden = (
        "вы правы",
        "у вас хорошие шансы",
        "суд встанет",
        "рекомендую подать",
        "советую",
        "вам следует",
        "нарушение ваших прав",
    )
    for area in intake_dialog.QUESTIONS:
        text = intake_dialog.build_orientation(area).lower()
        for phrase in forbidden:
            assert phrase not in text, f"{area}: {phrase}"


def test_orientation_names_area_and_documents() -> None:
    text = intake_dialog.build_orientation("employment")
    assert intake_dialog.AREA_LABEL["employment"].lower() in text.lower()
    for item in intake_dialog.DOCUMENTS["employment"]:
        assert item in text


def test_deadline_orientation_always_defers_to_lawyer() -> None:
    """Срок назван — но расчёт по конкретному делу оставлен юристу.

    Сроки полезно знать заранее, однако начало их течения зависит от
    обстоятельств. Справка без этой оговорки читалась бы как расчёт.
    """
    for area, note in intake_dialog.DEADLINE_NOTE.items():
        text = intake_dialog.build_orientation(area)
        if area in intake_dialog._AREA_BRANCHES:
            # У составных областей своя справка на каждую ветку — она
            # проверяется отдельно. Здесь важно только, что оговорка на месте.
            assert "определит юрист" in text, area
            continue
        if note:
            assert note in text
            assert "определит юрист" in text, area


def test_every_branch_keeps_the_lawyer_caveat() -> None:
    """Оговорка про расчёт срока обязательна и в ветках составных областей."""
    for area, branches in intake_dialog._AREA_BRANCHES.items():
        for branch in branches:
            answers = {"matter": branch.markers[0]} if branch.markers else None
            text = intake_dialog.build_orientation(area, answers)
            assert branch.deadline in text, f"{area}/{branch.label}"
            assert "определит юрист" in text, f"{area}/{branch.label}"


def test_wants_lawyer_recognises_request() -> None:
    assert intake_dialog.wants_lawyer("хочу к юристу")
    assert intake_dialog.wants_lawyer("Соедините с живым человеком")
    assert intake_dialog.wants_lawyer("юрист")
    assert intake_dialog.wants_lawyer("Адвокат, пожалуйста")
    assert intake_dialog.wants_lawyer("перезвоните мне")


def test_wants_lawyer_does_not_trigger_on_description() -> None:
    """Рассказ о ситуации не обрывает диалог.

    Ошибки здесь несимметричны: не расслышать просьбу — мелочь, человек
    повторит. А оборвать разговор на середине, приняв описание за просьбу, —
    грубо и необъяснимо со стороны клиента.
    """
    assert not intake_dialog.wants_lawyer(
        "Этот человек взял у меня телефон и не отдаёт, я звонил ему много раз"
    )
    assert not intake_dialog.wants_lawyer(
        "Мой бывший работодатель нанял юриста и теперь через него передаёт документы, "
        "а мне не отвечает уже второй месяц"
    )
    assert not intake_dialog.wants_lawyer("")
    assert not intake_dialog.wants_lawyer(None)


def test_nda_offer_is_an_offer_not_a_gate() -> None:
    """Соглашение предлагается, а не требуется.

    Клиент решил: документы принимаем и без подписи, с пометкой. Формулировка
    не должна выглядеть условием.
    """
    text = intake_dialog.build_nda_offer().lower()
    assert "не обязательно" in text
    assert "без соглашения" in text
    for phrase in ("обязаны подписать", "только после подписания", "без подписи не"):
        assert phrase not in text


def test_document_request_mentions_how_to_send() -> None:
    text = intake_dialog.build_document_request("contracts", nda_signed=False)
    assert "готово" in text.lower()
    signed = intake_dialog.build_document_request("contracts", nda_signed=True)
    assert "подписано" in signed.lower()


def test_document_accepted_notes_missing_agreement() -> None:
    without = intake_dialog.build_document_accepted(count=1, nda_signed=False)
    assert "не подписывалось" in without
    with_nda = intake_dialog.build_document_accepted(count=1, nda_signed=True)
    assert "не подписывалось" not in with_nda


@pytest.mark.parametrize(
    ("count", "word"),
    [(1, "документ"), (2, "документа"), (4, "документа"), (5, "документов"), (11, "документов")],
)
def test_document_count_agrees_grammatically(count: int, word: str) -> None:
    """Согласование числительного: «1 документ», «2 документа», «5 документов»."""
    assert f"{count} {word}" in intake_dialog.build_document_accepted(count=count, nda_signed=True)


def test_handoff_mentions_what_was_collected() -> None:
    text = intake_dialog.build_handoff(documents_count=3, answered_count=3)
    assert "документы (3)" in text
    assert "юрист" in text.lower()


def test_handoff_without_materials_stays_correct() -> None:
    """Диалог мог оборваться сразу — перечислять нечего, но текст остаётся связным."""
    text = intake_dialog.build_handoff(documents_count=0, answered_count=0)
    assert "передал юристу" in text.lower()
    assert "(0)" not in text


def test_family_case_is_not_told_about_inheritance() -> None:
    """Раздел имущества после развода — не наследственное дело.

    Перечисление склеивает «семью и наследство» в одно значение. Пока
    ориентация смотрела на название области, человеку с ипотечной квартирой
    после развода бот рассказывал про шестимесячный срок принятия наследства
    и просил свидетельство о смерти и завещание.
    """
    text = intake_dialog.build_orientation(
        "family_inheritance",
        {"matter": "раздел совместно нажитого имущества, квартира в ипотеке"},
    )

    for phrase in ("наслед", "завещан", "свидетельство о смерти", "шесть месяцев"):
        assert phrase not in text.lower(), phrase
    assert "расторжении брака" in text
    assert "ипотек" in text.lower()


def test_inheritance_case_still_gets_its_deadline() -> None:
    text = intake_dialog.build_orientation(
        "family_inheritance", {"matter": "вступление в наследство после смерти отца"}
    )

    assert "шесть месяцев" in text
    assert "свидетельство о смерти" in text


def test_plain_debt_is_not_told_about_bankruptcy() -> None:
    """Взыскание долга по расписке — не банкротство."""
    text = intake_dialog.build_orientation(
        "debt_bankruptcy", {"side": "кредитор", "amount": "300 тысяч по расписке"}
    )

    assert "банкрот" not in text.lower()
    assert "реестр" not in text.lower()
    assert "расписку" in text


def test_bankruptcy_case_gets_its_own_orientation() -> None:
    text = intake_dialog.build_orientation(
        "debt_bankruptcy", {"status": "должник подал заявление о банкротстве"}
    )

    assert "банкротстве" in text.lower()
    assert "реестр" in text.lower()


def test_composite_area_without_answers_uses_the_safer_branch() -> None:
    """Ответов ещё нет — берём вариант, который не додумывает за человека.

    Ошибиться в сторону наследства или банкротства хуже: это более узкие
    предметы, и попасть в них случайно значит говорить человеку заведомо не
    о том.
    """
    for area, forbidden in (
        ("family_inheritance", "шесть месяцев"),
        ("debt_bankruptcy", "реестр"),
    ):
        text = intake_dialog.build_orientation(area, None)
        assert forbidden not in text.lower(), area


def test_simple_areas_are_unaffected_by_answers() -> None:
    """Ветвление касается только составных областей."""
    for area in ("contracts", "employment", "real_estate", "disputes"):
        assert intake_dialog.build_orientation(area) == intake_dialog.build_orientation(
            area, {"whatever": "наследство банкротство"}
        )
