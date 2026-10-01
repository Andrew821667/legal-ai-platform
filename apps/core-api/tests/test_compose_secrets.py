"""Секреты в прод-compose: сервису гасятся только те, которые его код не читает.

Все контейнеры получают общий .env, а x-secrets-off-* поверх него обнуляют
ненужные секреты. Если код сервиса начнёт читать погашенный секрет, на проде
он молча получит пустую строку — этот тест ловит такое до слияния.
"""

from __future__ import annotations

import ast
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

# Сервисы с общим образом, но своей точкой входа: проверяем только код,
# достижимый из неё по импортам. Иначе секрет, который нужен соседу по образу
# (ключ admin — news-admin-bot, секрет входа юриста — самому боту), нельзя было
# бы погасить там, где он не нужен (ассистент сайта, циклы новостей).
NEWS_ROOTS = ["apps/news", "packages/prompts", "packages/shared"]
ENTRYPOINTS = {
    "assistant-api": ("web_assistant_api", ["apps/lead-bot/legacy"]),
    "news-generate": ("news.generate_loop", NEWS_ROOTS),
    "news-telegram-ingest": ("news.telegram_ingest_loop", NEWS_ROOTS),
    "news-publish": ("news.publish_loop", NEWS_ROOTS),
}
# Модули настроек объявляют разом все переменные .env; читает ли секрет код
# на самом деле, видно по обращению к атрибуту в остальных модулях.
SETTINGS_MODULES = {"apps/lead-bot/legacy/config.py", "apps/news/news/settings.py"}


def _import_closure(entry: str, roots: list[str]) -> list[Path]:
    bases = [ROOT / root for root in roots]

    def resolve(module: str) -> Path | None:
        for base in bases:
            path = base.joinpath(*module.split("."))
            if path.with_suffix(".py").is_file():
                return path.with_suffix(".py")
            if (path / "__init__.py").is_file():
                return path / "__init__.py"
        return None

    def package_of(file: Path) -> list[str]:
        for base in bases:
            if file.is_relative_to(base):
                return list(file.relative_to(base).parent.parts)
        return []

    start = resolve(entry)
    assert start is not None, f"точка входа {entry} не найдена"
    seen: set[Path] = set()
    stack = [start]
    while stack:
        file = stack.pop()
        if file in seen:
            continue
        seen.add(file)
        package = package_of(file)
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = package[: len(package) - (node.level - 1)] if node.level > 1 else package
                    module = ".".join(base + ([node.module] if node.module else []))
                else:
                    module = node.module or ""
                names = [module] + [f"{module}.{alias.name}" for alias in node.names]
            for name in filter(None, names):
                parts = name.split(".")
                for size in range(1, len(parts) + 1):
                    found = resolve(".".join(parts[:size]))
                    if found is not None and found not in seen:
                        stack.append(found)
    return sorted(seen)


def _service_code(name: str) -> str:
    if name not in ENTRYPOINTS:
        return _sources(CODE[name])
    entry, roots = ENTRYPOINTS[name]
    files = [
        file for file in _import_closure(entry, roots)
        if str(file.relative_to(ROOT)) not in SETTINGS_MODULES
    ]
    return "\n".join(file.read_text(encoding="utf-8", errors="ignore") for file in files)


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
        code = _service_code(name)
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


def test_text_handling_services_get_no_admin_or_lawyer_secrets() -> None:
    """Ассистент сайта и циклы новостей разбирают чужой текст (посетители,
    RSS, Telegram) — утечка их окружения не должна давать ключ admin (весь
    /api/v1, выпуск ключей) и секрет входа юриста (подделка его сессии)."""
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    for name in ("assistant-api", "news-generate", "news-telegram-ingest", "news-publish"):
        env = services[name].get("environment") or {}
        assert env.get("API_KEY_ADMIN") == "", name
        assert env.get("LAWYER_SESSION_SECRET") == "", name
    assistant = services["assistant-api"]["environment"]
    # Config бота требует непустой токен — у ассистента только заглушка.
    assert assistant["LEAD_BOT_TOKEN"].startswith("0:"), assistant["LEAD_BOT_TOKEN"]
    assert assistant.get("TELEGRAM_BOT_TOKEN") == ""
