from __future__ import annotations

import json
import logging
import re


_TELEGRAM_BOT_TOKEN_RE = re.compile(r"\b(?:bot)?\d{6,}:[A-Za-z0-9_-]{20,}\b")


def _redact_secrets(value: object) -> object:
    if isinstance(value, str):
        return _TELEGRAM_BOT_TOKEN_RE.sub("<telegram-bot-token>", value)
    if isinstance(value, dict):
        return {key: _redact_secrets(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_secrets(item) for item in value]
    return value


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": _redact_secrets(record.getMessage()),
            "module": record.module,
        }
        if record.exc_info:
            payload["exc"] = _redact_secrets(self.formatException(record.exc_info))

        # Preserve structured context passed through logger.*(..., extra={...}).
        skip = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
        }
        for key, value in record.__dict__.items():
            if key not in skip and key not in payload:
                payload[key] = _redact_secrets(value)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.root.handlers = [handler]
    logging.root.setLevel(logging.INFO)
    for logger_name in ("httpx", "httpcore"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
