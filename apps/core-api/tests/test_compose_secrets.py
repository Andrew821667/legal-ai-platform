"""Секреты в прод-compose: сервису гасятся только те, которые его код не читает.

Все контейнеры получают общий .env, а x-secrets-off-* поверх него обнуляют
ненужные секреты. Если код сервиса начнёт читать погашенный секрет, на проде
он молча получит пустую строку — этот тест ловит такое до слияния.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "infra" / "compose" / "docker-compose.prod.yml"

# Где лежит код каждого сервиса (образ lead-bot общий у бота и assistant-api).
CODE = {
    "web": ["apps/web/app", "apps/web/lib", "apps/web/components", "apps/web/next.config.js"],
    "core-api": ["apps/core-api/core_api", "apps/core-api/alembic"],
    "lead-bot": ["apps/lead-bot/legacy", "apps/lead-bot/lead_bot"],
    "assistant-api": ["apps/lead-bot/legacy", "apps/lead-bot/lead_bot"],
    "news-generate": ["apps/news/news", "packages"],
    "news-telegram-ingest": ["apps/news/news", "packages"],
    "news-publish": ["apps/news/news", "packages"],
    "news-admin-bot": ["apps/news/news", "packages"],
    "news-reader-bot": ["apps/news/legacy/app"],
    "news-reader-digest": ["apps/news/legacy/app"],
}
SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs"}


def _sources(paths: list[str]) -> str:
    chunks: list[str] = []
    for rel in paths:
        path = ROOT / rel
        files = [path] if path.is_file() else [p for p in path.rglob("*") if p.suffix in SUFFIXES]
        for file in files:
            parts = set(file.parts)
            if "node_modules" in parts or "tests" in parts or ".test." in file.name:
                continue
            chunks.append(file.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


def test_blanked_secrets_are_not_read_by_the_service() -> None:
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    problems: list[str] = []
    for name, paths in CODE.items():
        env = services[name].get("environment") or {}
        blanked = sorted(key for key, value in env.items() if value == "" and key.isupper())
        assert blanked, f"{name}: нет блока x-secrets-off"
        code = _sources(paths)
        for secret in blanked:
            if re.search(rf"\b(?:{secret}|{secret.lower()})\b", code):
                problems.append(f"{name} читает {secret}, а в compose он погашен")
    assert not problems, "\n".join(problems)


def test_pii_key_reaches_only_the_core() -> None:
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    for name in CODE:
        env = services[name].get("environment") or {}
        if name == "core-api":
            assert "PII_ENCRYPTION_KEY" not in env
        else:
            assert env.get("PII_ENCRYPTION_KEY") == "", name
