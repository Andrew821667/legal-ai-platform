"""Shared reader text normalization helpers."""

from __future__ import annotations

import re
from html import unescape as html_unescape

_READER_HTML_BREAK_RE = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
_READER_HTML_BLOCK_RE = re.compile(r"</?\s*(?:p|div|section|article|blockquote|pre|ul|ol)\b[^>]*>", re.IGNORECASE)
_READER_HTML_LI_OPEN_RE = re.compile(r"<\s*li\b[^>]*>", re.IGNORECASE)
_READER_HTML_LI_CLOSE_RE = re.compile(r"</\s*li\s*>", re.IGNORECASE)
_READER_HTML_TAG_RE = re.compile(r"<[^>]+>")
_READER_MARKDOWN_QUOTES_RE = re.compile(r"(?m)^\s*>\s?")
_SPECIAL_CHAR_REPLACEMENTS = {
    "\u00a0": " ",
    "\u200b": "",
    "\u200c": "",
    "\u200d": "",
    "\ufeff": "",
    "«": '"',
    "»": '"',
    "“": '"',
    "”": '"',
    "„": '"',
    "‟": '"',
    "’": "'",
    "‘": "'",
    "—": "-",
    "–": "-",
    "…": "...",
    "•": "- ",
    "◦": "- ",
    "▪": "- ",
    "●": "- ",
    "►": "- ",
    "→": "->",
    "←": "<-",
}


def normalize_reader_text(text: str | None, *, multiline: bool = True) -> str:
    value = html_unescape(str(text or ""))
    for source, target in _SPECIAL_CHAR_REPLACEMENTS.items():
        value = value.replace(source, target)
    value = _READER_HTML_BREAK_RE.sub("\n", value)
    value = _READER_HTML_BLOCK_RE.sub("\n", value)
    value = _READER_HTML_LI_OPEN_RE.sub("\n- ", value)
    value = _READER_HTML_LI_CLOSE_RE.sub("", value)
    value = _READER_HTML_TAG_RE.sub("", value)
    value = value.replace("**", "").replace("__", "").replace("`", "").replace("~~", "")
    value = _READER_MARKDOWN_QUOTES_RE.sub("", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    if multiline:
        lines = [" ".join(line.split()) for line in value.split("\n")]
        value = "\n".join(lines)
        value = re.sub(r"\n{2,}(?=- )", "\n", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
    else:
        value = " ".join(value.split())
    return value.strip()
