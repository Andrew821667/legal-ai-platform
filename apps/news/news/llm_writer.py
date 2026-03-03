from __future__ import annotations

import html
import json
import logging
import re
from typing import Any

from news.pipeline import ArticleCandidate, RAGExample, normalize_post_text
from news.settings import settings

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """
Ты шеф-редактор Telegram-канала по Legal AI.

Задача: по новости подготовить полезный пост для руководителей и юристов-практиков.

Правила качества:
1) Только факты из исходной статьи. Нельзя додумывать цифры, законы, кейсы.
2) Никакой воды, клише и общих фраз.
3) Пиши конкретно: что случилось, почему важно для бизнеса, какие юридические риски, что делать завтра.
4) В каждом смысловом блоке минимум 1 конкретная деталь из статьи.
5) Язык: русский, деловой, без канцелярита.

Верни СТРОГО JSON-объект (без markdown и пояснений) с полями:
{
  "is_relevant": true,
  "reject_reason": "",
  "title": "краткий заголовок до 110 символов",
  "rubric": "ai_law|compliance|privacy|contracts|litigation|legal_ops|regulation|market",
  "what_happened": "2-4 предложения с фактами",
  "business_effect": "2-4 предложения про impact/ROI/операционные эффекты",
  "legal_risks": "2-4 предложения про риски и контур регулирования",
  "next_steps": "3-5 коротких практических шагов через ';'",
  "hashtags": ["#LegalAI", "#AI", "#LegalTech"]
}

Ставь "is_relevant": false, если статья не относится напрямую к одному из сценариев:
1) AI в юридической функции, legal ops, договорной работе, комплаенсе, privacy, спорах;
2) регулирование AI/данных, которое важно юристам и комплаенсу;
3) legal tech / AI-инструменты, реально применимые юристами;
4) кейсы внедрения AI, где явно затронута юридическая или комплаенс-функция.

Если это просто общая AI-новость, общий рынок труда в IT, бытовая автоматизация, M&A без AI-контекста, общая корпоративная новость или исторический/научпоп материал без юридической функции - ставь "is_relevant": false и кратко объясняй почему в "reject_reason".
""".strip()
_FORMAT_HINTS = {
    "signal": "Формат signal: 450-700 символов, только ключевые факты и 2-3 действия.",
    "standard": "Формат standard: 900-1400 символов, полный разбор по структуре.",
    "deep": "Формат deep: 1600-2200 символов, глубже анализ рисков и сценариев внедрения.",
    "digest": "Формат digest: 1200-1900 символов, структурируй как недельный обзор с 5-7 пунктами внутри блока 'Что произошло'.",
}
_FORMAT_MIN_CHARS = {
    "signal": 420,
    "standard": 750,
    "deep": 1100,
    "digest": 950,
}
_CTA_LIBRARY = {
    "soft": "Если хотите понять, как этот сценарий применить в вашей юридической функции, напишите в {bot_link}.",
    "mid": "Если хотите разобрать ваш процесс и подобрать рабочий сценарий внедрения, напишите в {bot_link}.",
    "hard": "Если нужен разбор задачи и формат внедрения под ваш юротдел или практику, напишите в {bot_link}.",
}
_DEFAULT_HASHTAGS = ["#LegalAI", "#LegalTech", "#AI"]
_DEFAULT_RUBRIC_BY_PILLAR = {
    "regulation": "regulation",
    "case": "legal_ops",
    "implementation": "legal_ops",
    "tools": "market",
    "market": "market",
}


class LLMNewsWriter:
    def __init__(self) -> None:
        client_kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        try:
            from openai import OpenAI
        except Exception as exc:
            raise RuntimeError("openai package is required for news generation") from exc
        self.client = OpenAI(**client_kwargs)
        self.model = settings.news_model
        self._use_max_tokens_param = "deepseek" in (settings.openai_base_url or "").lower()

    def _completion_kwargs(self) -> dict[str, Any]:
        if self._use_max_tokens_param:
            return {"max_tokens": 900}
        return {"max_completion_tokens": 900}

    @staticmethod
    def _shorten(text: str, limit: int) -> str:
        normalized = re.sub(r"\s+", " ", (text or "").strip())
        return normalized[:limit].strip()

    @staticmethod
    def _build_context(rag_examples: list[RAGExample]) -> str:
        if not rag_examples:
            return "Нет релевантных прошлых постов."

        lines: list[str] = ["Релевантные прошлые посты (используй только как стилистический ориентир, без копирования):"]
        for idx, example in enumerate(rag_examples, start=1):
            lines.append(
                f"{idx}. [{example.rubric or 'general'}] {example.title}\n"
                f"{example.text[:500]}"
            )
        return "\n\n".join(lines)

    @staticmethod
    def _extract_json(payload: str) -> dict[str, Any]:
        text = (payload or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            left = text.find("{")
            right = text.rfind("}")
            if left != -1 and right != -1 and right > left:
                return json.loads(text[left : right + 1])
            raise

    @staticmethod
    def _cta_text(cta_type: str) -> str:
        template = _CTA_LIBRARY.get(cta_type, _CTA_LIBRARY["soft"])
        if settings.lead_bot_url:
            bot_link = f'<a href="{html.escape(settings.lead_bot_url, quote=True)}">бот Legal AI PRO</a>'
        else:
            bot_link = "бот Legal AI PRO"
        return template.format(bot_link=bot_link)

    def _format_post(
        self,
        data: dict[str, Any],
        article_url: str,
        fallback_title: str,
        format_type: str,
        cta_type: str,
        pillar: str,
    ) -> tuple[str, str, str]:
        title = self._shorten(data.get("title") or fallback_title, 110)
        default_rubric = _DEFAULT_RUBRIC_BY_PILLAR.get(pillar, "legal_ai")
        rubric = self._shorten(data.get("rubric") or default_rubric, 100)
        what_happened = self._shorten(data.get("what_happened") or "", 900)
        business_effect = self._shorten(data.get("business_effect") or "", 900)
        legal_risks = self._shorten(data.get("legal_risks") or "", 900)
        next_steps_raw = data.get("next_steps") or ""
        hashtags_value = data.get("hashtags")

        steps: list[str] = []
        for part in str(next_steps_raw).split(";"):
            cleaned = self._shorten(part, 180)
            if cleaned:
                steps.append(cleaned)
        steps = steps[:5]

        hashtags: list[str] = []
        if isinstance(hashtags_value, list):
            for item in hashtags_value:
                tag = self._shorten(str(item), 40)
                if tag and tag.startswith("#"):
                    hashtags.append(tag)
        if not hashtags:
            hashtags = list(_DEFAULT_HASHTAGS)

        escaped_title = html.escape(title)
        escaped_what_happened = html.escape(
            what_happened or "В статье описан новый кейс внедрения AI с конкретными операционными деталями."
        )
        escaped_business_effect = html.escape(
            business_effect or "Сценарий влияет на скорость процессов, стоимость операций и управляемость качества сервиса."
        )
        escaped_legal_risks = html.escape(
            legal_risks or "Требуется проверить обработку данных, модель ответственности и регуляторные ограничения."
        )
        escaped_steps = [html.escape(item) for item in steps]
        steps_block = "\n".join(f"• {item}" for item in escaped_steps) if escaped_steps else "• Проверить применимость кейса к текущим процессам."
        cta_line = self._cta_text(cta_type)
        safe_article_url = html.escape(article_url, quote=True)
        hashtags_line = " ".join(html.escape(tag) for tag in hashtags[:4])

        text = normalize_post_text(
            f"<b>{escaped_title}</b>\n\n"
            f"<b>Что произошло</b>\n{escaped_what_happened}\n\n"
            f"<b>Бизнес-эффект</b>\n{escaped_business_effect}\n\n"
            f"<b>Юридические риски</b>\n{escaped_legal_risks}\n\n"
            f"<b>Что делать</b>\n{steps_block}\n\n"
            f"<b>Следующий шаг</b>\n{cta_line}\n\n"
            f"<b>Источник</b>: <a href=\"{safe_article_url}\">оригинал статьи</a>\n"
            f"{hashtags_line}"
        )
        return title, text, rubric

    @staticmethod
    def _passes_quality_gate(text: str, format_type: str) -> bool:
        normalized = (text or "").strip()
        required_markers = ("Что произошло", "Бизнес-эффект", "Юридические риски", "Что делать", "Следующий шаг", "Источник:")
        min_chars = _FORMAT_MIN_CHARS.get(format_type, _FORMAT_MIN_CHARS["standard"])
        if len(normalized) < min_chars:
            return False
        for marker in required_markers:
            if marker not in normalized:
                return False
        # Минимум один маркер конкретики (число/дата/процент)
        if not re.search(r"\d", normalized):
            return False
        return True

    def _fallback_post(self, article: ArticleCandidate, format_type: str, cta_type: str, pillar: str) -> dict[str, str]:
        title = self._shorten(article.title or "Обзор новости", 110)
        summary = self._shorten(article.summary, 1300)
        summary = summary or "Источник сообщил о новом кейсе внедрения AI в юридическом процессе."
        base = {
            "title": title,
            "rubric": _DEFAULT_RUBRIC_BY_PILLAR.get(pillar, "legal_ai"),
            "what_happened": summary[:450],
            "business_effect": "Кейс показывает, как сократить ручную работу и повысить скорость обработки типовых задач.",
            "legal_risks": "Нужно заранее определить границы автоматизации, требования к защите данных и юридическую ответственность.",
            "next_steps": "Описать текущий процесс в цифрах; выбрать 1-2 этапа для пилота; согласовать критерии качества и контроля",
            "hashtags": list(_DEFAULT_HASHTAGS),
        }
        _, text, rubric = self._format_post(
            base,
            article.article_url,
            title,
            format_type=format_type,
            cta_type=cta_type,
            pillar=pillar,
        )
        return {"title": title, "text": text, "rubric": rubric}

    def generate_post(
        self,
        article: ArticleCandidate,
        rag_examples: list[RAGExample],
        format_type: str = "standard",
        cta_type: str = "soft",
        pillar: str = "implementation",
        negative_feedback_context: str = "",
    ) -> dict[str, str] | None:
        format_hint = _FORMAT_HINTS.get(format_type, _FORMAT_HINTS["standard"])
        user_prompt = (
            f"Источник: {article.source_url}\n"
            f"URL статьи: {article.article_url}\n"
            f"Заголовок: {article.title}\n"
            f"Дата публикации: {article.published_at.isoformat() if article.published_at else 'не указана'}\n\n"
            f"Целевая смысловая корзина: {pillar}\n"
            f"{format_hint}\n"
            f"CTA-уровень: {cta_type}\n\n"
            f"Краткое содержание статьи:\n{article.summary[:3000]}\n\n"
            f"{self._build_context(rag_examples)}\n\n"
            f"{negative_feedback_context or 'Негативных сигналов по похожим постам не найдено.'}"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.35,
            **self._completion_kwargs(),
        )

        raw = response.choices[0].message.content or ""
        try:
            data = self._extract_json(raw)
            if data.get("is_relevant") is False:
                logger.info(
                    "llm_post_rejected_by_relevance_gate",
                    extra={
                        "article_url": article.article_url,
                        "reason": str(data.get("reject_reason") or "")[:180],
                        "format_type": format_type,
                    },
                )
                return None
            title, text, rubric = self._format_post(
                data,
                article.article_url,
                article.title[:110],
                format_type=format_type,
                cta_type=cta_type,
                pillar=pillar,
            )
            if not self._passes_quality_gate(text, format_type):
                logger.warning(
                    "llm_post_failed_quality_gate",
                    extra={"title": title[:80], "rubric": rubric, "format_type": format_type},
                )
                return self._fallback_post(article, format_type=format_type, cta_type=cta_type, pillar=pillar)
            logger.info("llm_post_generated", extra={"title": title[:80], "rubric": rubric, "format_type": format_type})
            return {"title": title[:160], "text": text, "rubric": rubric[:100]}
        except Exception as exc:
            logger.warning("llm_post_parse_failed", extra={"error": str(exc), "format_type": format_type})
            return self._fallback_post(article, format_type=format_type, cta_type=cta_type, pillar=pillar)
