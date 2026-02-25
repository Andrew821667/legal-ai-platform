"""
Middleware для Telegram бота.
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from app.models.database import AsyncSessionLocal


class DbSessionMiddleware(BaseMiddleware):
    """Middleware для добавления сессии БД в контекст."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Добавляет сессию БД в data для обработчиков."""
        async with AsyncSessionLocal() as session:
            data['db'] = session
            return await handler(event, data)
