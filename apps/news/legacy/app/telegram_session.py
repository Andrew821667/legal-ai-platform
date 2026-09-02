"""Создание Bot с учётом прокси до Telegram.

Прямой доступ к api.telegram.org с production-хоста закрыт, весь трафик идёт
через локальный прокси. Без него aiogram падает с ClientConnectorError на
каждом обращении, из-за чего reader-бот не отвечал вовсе.
"""

from __future__ import annotations


def resolve_proxy_url(raw: str | None) -> str | None:
    """Приводит значение из настроек к адресу прокси или None.

    Пустая строка и пробелы приходят из окружения, когда переменная объявлена,
    но не заполнена, — такое значение нельзя передавать в сессию как адрес.
    """
    value = (raw or "").strip()
    return value or None


def build_bot(token: str):
    """Возвращает Bot, настроенный на прокси, если он задан."""
    from aiogram import Bot
    from aiogram.client.session.aiohttp import AiohttpSession

    from app.config import settings

    proxy_url = resolve_proxy_url(settings.telegram_api_proxy_url)
    if proxy_url is None:
        return Bot(token=token)
    return Bot(token=token, session=AiohttpSession(proxy=proxy_url))
