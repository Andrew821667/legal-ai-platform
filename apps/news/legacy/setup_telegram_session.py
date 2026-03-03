#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import os
from getpass import getpass
from pathlib import Path

from dotenv import dotenv_values
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent.parent


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BASE_DIR / ".env", PROJECT_ROOT / ".env"):
        if not path.exists():
            continue
        for key, value in dotenv_values(path).items():
            if value is None:
                continue
            merged[key] = value
    merged.update({key: value for key, value in os.environ.items() if value})
    return merged


def _resolve_session_name(raw: str) -> str:
    value = (raw or "apps/news/legacy/telegram_bot").strip()
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def _print_header(api_id: int, session_name: str) -> None:
    print("=" * 60)
    print("Telegram Client API - авторизация")
    print("=" * 60)
    print()
    print(f"API ID: {api_id}")
    print(f"Session name: {Path(session_name).name}")
    print()
    print("Выберите метод авторизации:")
    print("  1. QR-код")
    print("  2. Номер телефона")
    print()


async def _authorize_by_qr(client: TelegramClient) -> None:
    print("Открываю QR-логин...")
    qr_login = await client.qr_login()
    print()
    print("Откройте Telegram на телефоне:")
    print("  Настройки -> Устройства -> Подключить устройство")
    print("И отсканируйте этот URL/QR:")
    print(qr_login.url)
    print()
    try:
        import qrcode

        qr = qrcode.QRCode(border=1)
        qr.add_data(qr_login.url)
        qr.print_ascii(invert=True)
        print()
    except Exception:
        print("Пакет qrcode не установлен, поэтому показан только URL.")
        print()

    try:
        await qr_login.wait(timeout=180)
    except SessionPasswordNeededError:
        print()
        print("Для этого аккаунта включена двухфакторная защита Telegram.")
        password = getpass("Введите пароль 2FA: ")
        await client.sign_in(password=password)

    me = await client.get_me()
    print(f"Авторизация успешна: {me.first_name or me.username or me.id}")


async def _authorize_by_phone(client: TelegramClient) -> None:
    phone = input("Введите номер телефона в формате +7...: ").strip()
    if not phone:
        raise ValueError("Номер телефона не введен")

    sent = await client.send_code_request(phone)
    print()
    print("Код должен прийти в сам Telegram, обычно в сервисный чат Telegram.")
    print("Если кода нет сразу, проверьте все активные устройства и архив.")
    print()
    code = input("Введите код из Telegram: ").strip().replace(" ", "")
    if not code:
        raise ValueError("Код не введен")

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=sent.phone_code_hash)
    except SessionPasswordNeededError:
        password = getpass("У аккаунта включена 2FA. Введите пароль: ")
        await client.sign_in(password=password)

    me = await client.get_me()
    print(f"Авторизация успешна: {me.first_name or me.username or me.id}")


async def main() -> int:
    env = _load_env()
    api_id = int(str(env.get("TELEGRAM_API_ID", "0")).strip() or "0")
    api_hash = str(env.get("TELEGRAM_API_HASH", "")).strip()
    session_name = _resolve_session_name(str(env.get("TELEGRAM_SESSION_NAME", "apps/news/legacy/telegram_bot")))

    if not api_id or not api_hash:
        print("Ошибка: TELEGRAM_API_ID / TELEGRAM_API_HASH не настроены.")
        return 1

    _print_header(api_id, session_name)
    choice = input("Выбор (1 или 2): ").strip()
    if choice not in {"1", "2"}:
        print("Неверный выбор.")
        return 1

    client = TelegramClient(session_name, api_id, api_hash)
    await client.connect()

    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"Сессия уже авторизована: {me.first_name or me.username or me.id}")
            return 0

        if choice == "1":
            await _authorize_by_qr(client)
        else:
            await _authorize_by_phone(client)

        await client.disconnect()
        print()
        print(f"Файл сессии сохранен: {session_name}.session")
        return 0
    finally:
        if client.is_connected():
            await client.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
