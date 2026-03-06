from __future__ import annotations

import utils


def test_mask_telegram_id_handles_empty_values() -> None:
    assert utils.mask_telegram_id(None) == ""
    assert utils.mask_telegram_id("") == ""


def test_mask_telegram_id_masks_short_values() -> None:
    assert utils.mask_telegram_id("1234") == "****"
    assert utils.mask_telegram_id("12345") == "1**45"


def test_mask_telegram_id_masks_long_values() -> None:
    assert utils.mask_telegram_id("321681061") == "32*****61"
    assert utils.mask_telegram_id(321681061) == "32*****61"
