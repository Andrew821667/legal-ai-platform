from __future__ import annotations

import logging

from news.core_client import CoreClient
from news.pipeline import RAGExample, select_rag_examples

logger = logging.getLogger(__name__)


class PostedContentRAG:
    def __init__(self, client: CoreClient) -> None:
        self.client = client

    def find_context(self, query_text: str, history_limit: int = 50, top_k: int = 3) -> list[RAGExample]:
        try:
            response = self.client.list_posts(limit=history_limit, status="posted", newest_first=True)
            response.raise_for_status()
            rows = response.json()
        except Exception as exc:
            logger.warning("rag_history_fetch_failed", extra={"error": str(exc)})
            return []

        candidates: list[RAGExample] = []
        for row in rows:
            text = (row.get("text") or "").strip()
            if not text:
                continue
            candidates.append(
                RAGExample(
                    title=(row.get("title") or "").strip(),
                    text=text,
                    rubric=row.get("rubric"),
                )
            )

        selected = select_rag_examples(query_text, candidates, top_k=top_k)
        logger.info(
            "rag_context_selected",
            extra={"history_candidates": len(candidates), "selected": len(selected)},
        )
        return selected
