"""Страж: токены ботов не должны попадать в журналы.

Журналы читаются шире, чем секреты: их смотрят при отладке, пересылают,
сохраняют. Даже первые символы токена содержат идентификатор бота и начало
секрета, поэтому в логе не должно быть ни самого токена, ни его срезов.

Регрессия была в reader-боте: строка вида
    logger.info(f"Reader bot starting with token: {token[:10]}...")
писала часть секрета при каждом запуске.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

APP_DIRS = (
    Path(__file__).resolve().parents[1] / "legacy" / "app",
    Path(__file__).resolve().parents[1] / "news",
)

# Логирование, куда подставляется переменная с токеном: и целиком, и срезом.
TOKEN_IN_LOG = re.compile(
    r"(logger|logging|print)\s*[.(][^\n]*\{[a-z_]*token[a-z_]*(\[[^\]]*\])?\}",
    re.IGNORECASE,
)

# run_once_token — идентификатор ручного запуска из automation-controls,
# а не секрет доступа: он нужен в heartbeat для дедупликации запусков.
ALLOWED = ("manual_run_token", "run_once_token")


def _python_files() -> list[Path]:
    files: list[Path] = []
    for base in APP_DIRS:
        if base.exists():
            files.extend(sorted(base.rglob("*.py")))
    return files


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_token_is_never_logged(path: Path) -> None:
    offenders = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not TOKEN_IN_LOG.search(line):
            continue
        if any(name in line for name in ALLOWED):
            continue
        offenders.append(f"{path.name}:{number}: {line.strip()}")

    assert not offenders, "токен попадает в журнал:\n" + "\n".join(offenders)
