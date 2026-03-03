from __future__ import annotations

from news.llm_writer import LLMNewsWriter


def test_looks_complete_prose_accepts_finished_text() -> None:
    text = "<b>Что произошло</b>\nТекст завершен.\n\n<b>Источник</b>: ссылка\n#LegalAI"
    assert LLMNewsWriter._looks_complete_prose(text)


def test_looks_complete_prose_rejects_incomplete_tail() -> None:
    text = "<b>Что произошло</b>\nТекст оборван потому\n\n<b>Источник</b>: ссылка\n#LegalAI"
    assert not LLMNewsWriter._looks_complete_prose(text)
