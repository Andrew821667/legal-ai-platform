"""RAG по знаниям компании — вторая половина пункта 3 плана «умный ассистент».

Источник — тот же контент, что публикует сайт (apps/web/lib/*Data.ts,
эндпоинт GET /api/knowledge/snapshot): услуги, FAQ, типовые сценарии
внедрения, методология. Не заводим отдельную базу вручную — один источник
правды, тот же текст, что видит посетитель сайта.

Снимок кешируется в памяти с TTL (config.WEB_KNOWLEDGE_CACHE_TTL_SECONDS,
по умолчанию час) — сайт не меняется каждую минуту, а лишний HTTP на
каждое сообщение клиента не нужен. Эмбеддинги элементов базы знаний тоже
считаются один раз за обновление кеша, а не на каждое сообщение: иначе,
в отличие от knowledge_engine.find_similar_conversations (там кеша нет —
диалоги короткие и их немного), на статичный контент уходили бы лишние
запросы эмбеддинга при каждой реплике клиента.
"""
from __future__ import annotations

import json as json_module
import logging
import time
import urllib.error
import urllib.request

from config import get_config
import knowledge_engine

config = get_config()
logger = logging.getLogger(__name__)

_MAX_ITEM_TEXT_LEN = 600
_MIN_QUERY_LEN = 10

_cache_items: list[dict] = []
_cache_embeddings: list[list[float]] = []
_cache_loaded_at: float = 0.0


def _fetch_snapshot() -> list[dict]:
    request = urllib.request.Request(
        url=config.WEB_KNOWLEDGE_URL,
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=config.WEB_KNOWLEDGE_TIMEOUT_SECONDS) as response:
        payload = json_module.loads(response.read().decode("utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else None
    return items if isinstance(items, list) else []


def _refresh_cache_if_stale() -> None:
    global _cache_items, _cache_embeddings, _cache_loaded_at
    now = time.monotonic()
    if (
        _cache_items
        and _cache_loaded_at > 0
        and (now - _cache_loaded_at) < config.WEB_KNOWLEDGE_CACHE_TTL_SECONDS
    ):
        return

    try:
        items = _fetch_snapshot()
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        logger.warning("Failed to refresh company knowledge snapshot: %s", error)
        if _cache_items:
            # Сайт временно недоступен — отдаём протухший кеш ещё час, чем
            # спамить недоступный эндпоинт на каждое сообщение клиента.
            _cache_loaded_at = now
        return

    if not items:
        return

    embeddings = [
        knowledge_engine.knowledge_engine.get_embedding(
            f"{item.get('title', '')}. {item.get('text', '')}"[:_MAX_ITEM_TEXT_LEN]
        )
        for item in items
    ]
    _cache_items = items
    _cache_embeddings = embeddings
    _cache_loaded_at = now
    logger.info("Company knowledge snapshot refreshed: %s items", len(items))


def find_relevant(query: str, *, top_k: int = 2, min_similarity: float = 0.6) -> list[tuple[dict, float]]:
    """Материалы компании, похожие на запрос. Пусто — не ошибка (см. build_context)."""
    _refresh_cache_if_stale()
    if not _cache_items or not _cache_embeddings:
        return []

    query_embedding = knowledge_engine.knowledge_engine.get_embedding(query)
    if not query_embedding:
        return []

    scored: list[tuple[dict, float]] = []
    for item, embedding in zip(_cache_items, _cache_embeddings):
        if not embedding:
            continue
        similarity = knowledge_engine.knowledge_engine.cosine_similarity(query_embedding, embedding)
        if similarity >= min_similarity:
            scored.append((item, similarity))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]


def format_for_prompt(matches: list[tuple[dict, float]]) -> str:
    if not matches:
        return ""
    lines = [
        "# База знаний компании",
        "Проверенные материалы AI Verdict по теме вопроса — используй как факты и, если "
        "уместно по смыслу разговора, дай ссылку:",
    ]
    for item, _ in matches:
        title = (item.get("title") or "").strip()
        text = (item.get("text") or "").strip()
        href = (item.get("href") or "").strip()
        line = f"- {title}: {text}" if title else f"- {text}"
        if href:
            line += f" ({href})"
        lines.append(line)
    return "\n".join(lines)


def build_context(query: str | None) -> str:
    """Точка входа — синхронная (сетевой запрос и эмбеддинги), как и
    ai_brain._rag_context_for; асинхронные вызыватели заворачивают в
    asyncio.to_thread. Любой сбой съедается — контекст необязателен."""
    try:
        if not query or len(query) <= _MIN_QUERY_LEN:
            return ""
        return format_for_prompt(find_relevant(query))
    except Exception as error:  # noqa: BLE001 — база знаний необязательна, ответ важнее
        logger.warning("Company knowledge search failed (non-critical): %s", error)
        return ""
