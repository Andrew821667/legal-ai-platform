"""Рабочее место юриста: задачи, клиенты, деньги, архив.

Собирает данные, разбросанные по обращениям, диалогам, соглашениям и
документам. Был одним файлом почти на две тысячи строк; разрезан по экранам,
пути и ответы не менялись. Роутер собирается здесь в прежнем порядке.
"""

from __future__ import annotations

from fastapi import APIRouter

from core_api.routers.lawyer_workspace import (
    archive,
    card,
    clients,
    deliveries,
    documents,
    links,
    money,
    reviews,
    today,
)

router = APIRouter()
for _module in (today, clients, card, documents, money, links, archive, deliveries, reviews):
    router.include_router(_module.router)
