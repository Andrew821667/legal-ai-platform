from __future__ import annotations

import json
import logging

from news.logging_config import JSONFormatter, setup_logging


def test_json_formatter_redacts_telegram_bot_tokens_in_message_and_extra() -> None:
    token = "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ_1234567890"
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="HTTP Request: POST https://api.telegram.org/bot%s/getMe",
        args=(token,),
        exc_info=None,
    )
    record.url = f"https://api.telegram.org/bot{token}/setMyCommands"
    record.details = {"token": token, "items": [f"bot{token}"]}

    payload = json.loads(JSONFormatter().format(record))

    serialized = json.dumps(payload)
    assert token not in serialized
    assert "<telegram-bot-token>" in payload["msg"]
    assert payload["url"] == "https://api.telegram.org/<telegram-bot-token>/setMyCommands"
    assert payload["details"]["token"] == "<telegram-bot-token>"
    assert payload["details"]["items"] == ["<telegram-bot-token>"]


def test_setup_logging_quiets_http_client_info_logs() -> None:
    setup_logging()

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
