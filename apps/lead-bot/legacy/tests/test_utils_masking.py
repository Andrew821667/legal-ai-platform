from __future__ import annotations

import asyncio

import utils
from telegram.error import BadRequest


def test_mask_telegram_id_handles_empty_values() -> None:
    assert utils.mask_telegram_id(None) == ""
    assert utils.mask_telegram_id("") == ""


def test_mask_telegram_id_masks_short_values() -> None:
    assert utils.mask_telegram_id("1234") == "****"
    assert utils.mask_telegram_id("12345") == "1**45"


def test_mask_telegram_id_masks_long_values() -> None:
    assert utils.mask_telegram_id("321681061") == "32*****61"
    assert utils.mask_telegram_id(321681061) == "32*****61"


def test_expired_callback_does_not_block_action() -> None:
    class Query:
        calls = 0

        async def answer(self) -> None:
            self.calls += 1
            raise BadRequest("Query is too old and response timeout expired or query id is invalid")

    query = Query()

    assert asyncio.run(utils.safe_answer_callback(query, action="test_callback")) is None
    assert query.calls == 1
