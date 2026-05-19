from __future__ import annotations

import re


EXTERNAL_LINK_VPN_NOTICE_TEXT = (
    "Важно: при переходе на сайт или внешний сервис отключите VPN, "
    "если страница не открывается."
)
EXTERNAL_LINK_VPN_NOTICE_HTML = f"<b>Важно</b>: {EXTERNAL_LINK_VPN_NOTICE_TEXT.removeprefix('Важно: ')}"

_EXTERNAL_NON_TELEGRAM_URL_RE = re.compile(
    r"https?://(?!(?:t\.me|telegram\.me|telegram\.dog|api\.telegram\.org)(?:/|\b))",
    re.IGNORECASE,
)
_VPN_NOTICE_MARKER = "отключите vpn"


def has_external_non_telegram_link(text: str) -> bool:
    return bool(_EXTERNAL_NON_TELEGRAM_URL_RE.search(text or ""))


def append_external_link_vpn_notice(text: str, *, notice: str = EXTERNAL_LINK_VPN_NOTICE_HTML) -> str:
    normalized = (text or "").rstrip()
    if not normalized:
        return normalized
    if _VPN_NOTICE_MARKER in normalized.lower():
        return normalized
    if not has_external_non_telegram_link(normalized):
        return normalized

    lines = normalized.splitlines()
    trailing_tags: list[str] = []
    while lines and lines[-1].strip().startswith("#"):
        trailing_tags.insert(0, lines.pop())

    body = "\n".join(lines).rstrip()
    tags = "\n".join(trailing_tags).strip()
    if tags:
        return f"{body}\n\n{notice}\n{tags}"
    return f"{body}\n\n{notice}"
