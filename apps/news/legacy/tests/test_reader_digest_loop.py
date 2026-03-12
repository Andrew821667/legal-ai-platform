from app.services.reader_text import normalize_reader_text


def test_normalize_digest_text_removes_html_entities_and_tags() -> None:
    cleaned = normalize_reader_text(
        '<b>Как юрфирма &amp; команда</b><br><ul><li>Пункт…</li></ul>\n> quote',
        multiline=True,
    )

    assert cleaned == "Как юрфирма & команда\n- Пункт...\nquote"
