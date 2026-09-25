"""Этап дела — одна лестница на ядро и сайт (сайт больше не держит копию)."""

from __future__ import annotations

import pytest
from core_api import case_stage


@pytest.mark.parametrize(
    ("nda", "status", "without", "key", "title", "step"),
    [
        (False, None, False, "first_contact", "Первичное обращение", 1),
        (True, None, False, "preparing_terms", "Готовим условия", 2),
        (True, "draft", False, "not_sent", "Договор не отправлен", 3),
        (True, "sent", False, "with_client", "Договор у клиента", 3),
        (True, "viewed", False, "with_client", "Договор у клиента", 3),
        (True, "signed", False, "signed", "Договор подписан", 4),
        (True, "declined", False, "declined", "Клиент отказался", 1),
        (True, None, True, "without_agreement", "В работе без договора", None),
        # Передумали и составили договор — этап снова по нему.
        (True, "sent", True, "with_client", "Договор у клиента", 3),
    ],
)
def test_ladder(nda, status, without, key, title, step) -> None:
    stage = case_stage.stage_for(nda_signed=nda, agreement_status=status, without_agreement=without)
    assert case_stage.fields(stage) == {"stage": title, "stage_key": key, "stage_step": step}


def test_keys_are_unique() -> None:
    keys = [stage.key for stage in case_stage.ALL]
    assert len(keys) == len(set(keys))
