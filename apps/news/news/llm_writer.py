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
6) Поле legal_risks должно содержать именно юридический комментарий, а не общие слова про "риски".
7) Если статья позволяет, в legal_risks укажи 2-4 конкретных правовых угла из этого списка:
   - персональные данные, трансграничная передача, локализация данных;
   - конфиденциальность, коммерческая тайна, доступ к документам;
   - договорные ограничения, SLA, ответственность поставщика, indemnity;
   - IP / лицензии / права на модель, датасет, output;
   - compliance / governance / аудит / логирование / human-in-the-loop;
   - AI Act, privacy law, отраслевые регуляторные требования;
   - судебная доказуемость, explainability, контроль качества output.
8) Если в статье нет явного правового угла, legal_risks должен честно объяснять, какой именно юридический вопрос должен проверить юрист перед внедрением.
9) Для daily-поста третий блок не должен автоматически становиться юридическим чек-листом. Выбирай его по контексту новости:
   - регулирование / privacy / compliance / contracts -> «Юридический контур»;
   - внедрение / legal ops / кейс -> «Что это значит для юрфункции»;
   - инструмент / продукт -> «Что это значит для команд»;
   - рынок / вендоры / сделки / геополитика -> «Что это значит для рынка» или «На что смотреть дальше».
10) Предпочитай русский юридический язык. Английские термины используй только там, где без них теряется точность (например AI Act, SLA, legal hold), и не перегружай ими текст.

Верни СТРОГО JSON-объект (без markdown и пояснений) с полями:
{
  "is_relevant": true,
  "reject_reason": "",
  "title": "краткий заголовок до 110 символов",
  "rubric": "ai_law|compliance|privacy|contracts|litigation|legal_ops|regulation|market",
  "lead": "1-2 предложения лид-абзаца",
  "what_happened": "2-4 предложения с фактами",
  "business_effect": "2-4 предложения про impact/ROI/операционные эффекты",
  "legal_risks": "2-4 предложения про риски и контур регулирования",
  "next_steps": "3-5 коротких практических шагов через ';'",
  "weekly_points": ["опционально: 8-10 коротких пунктов для weekly_review"],
  "conclusion": "1-2 предложения итогового вывода",
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
    "daily": "Формат daily: 1100-1700 символов, плотный ежедневный пост по новости для канала о Legal AI.",
    "weekly_review": "Формат weekly_review: 3200-3900 символов, 8-10 пунктов, без обрезки текста, это обзор недели по Legal AI и автоматизации юрфункции.",
    "longread": "Формат longread: 2600-3600 символов, это воскресный разбор темы с сильной практической частью и четкой логикой.",
    "humor": "Формат humor: 900-1500 символов, легкий субботний пост с профессиональным юмором про Legal AI и юрфункцию, без клоунады.",
}
_FORMAT_SHAPE_HINTS = {
    "daily": (
        "Структура daily: сильный заголовок -> короткий лид -> блок «Что произошло» -> блок «Почему это важно» "
        "-> третий блок по контексту новости (например: «Юридический контур», «Что это значит для юрфункции», "
        "«Что это значит для рынка», «На что смотреть дальше») -> источник. Абзацы короткие, по 2-3 предложения."
    ),
    "weekly_review": (
        "Структура weekly_review: короткий лид -> 8-10 коротких пунктов недели -> блок «Что это значит для юрфункции» "
        "-> блок «Что проверить у себя» -> источник. Поле weekly_points обязательно, если хватает материала."
    ),
    "longread": (
        "Структура longread: сильный лид -> «Контекст» -> «Практический смысл» -> «Риски и ограничения» "
        "-> «Что делать» -> «Вывод» -> источник. Нужна цельная логика без обрывов."
    ),
    "humor": (
        "Структура humor: короткий лид -> «Ситуация недели» -> «Почему это смешно» -> «Где здесь практический смысл» "
        "-> источник. Юмор профессиональный, без клоунады."
    ),
}
_FORMAT_MIN_CHARS = {
    "signal": 420,
    "standard": 750,
    "deep": 1100,
    "digest": 950,
    "daily": 900,
    "weekly_review": 2800,
    "longread": 2000,
    "humor": 700,
}
_FORMAT_MAX_OUTPUT_TOKENS = {
    "signal": 900,
    "standard": 1100,
    "deep": 1400,
    "digest": 1500,
    "daily": 1200,
    "weekly_review": 2200,
    "longread": 1800,
    "humor": 1000,
}
_FORMAT_FIELD_LIMITS: dict[str, dict[str, int]] = {
    "signal": {"what": 320, "effect": 240, "risks": 220, "step": 90, "steps": 3, "hashtags": 3},
    "standard": {"what": 500, "effect": 420, "risks": 380, "step": 110, "steps": 4, "hashtags": 3},
    "deep": {"what": 700, "effect": 540, "risks": 520, "step": 120, "steps": 4, "hashtags": 4},
    "digest": {"what": 900, "effect": 420, "risks": 360, "step": 95, "steps": 4, "hashtags": 4},
    "daily": {"what": 520, "effect": 360, "risks": 320, "step": 95, "steps": 3, "hashtags": 3},
    "weekly_review": {"what": 1500, "effect": 520, "risks": 420, "step": 100, "steps": 4, "hashtags": 4},
    "longread": {"what": 1000, "effect": 650, "risks": 540, "step": 110, "steps": 4, "hashtags": 4},
    "humor": {"what": 420, "effect": 280, "risks": 220, "step": 90, "steps": 3, "hashtags": 3},
}
_CTA_LIBRARY = {
    "soft": {
        "regulation": "Если хотите разобрать, как такой регуляторный риск влияет на вашу AI-, privacy- или compliance-функцию, напишите в {bot_link}.",
        "case": "Если хотите понять, как такой сценарий внедрения применим в вашей юрфункции, напишите в {bot_link}.",
        "implementation": "Если хотите примерить такой сценарий автоматизации на договорную работу, заявки или внутренние процессы, напишите в {bot_link}.",
        "tools": "Если хотите оценить, подходит ли такой инструмент для юротдела или практики, напишите в {bot_link}.",
        "market": "Если хотите перевести этот рыночный сигнал в план действий для вашей юрфункции или продукта, напишите в {bot_link}.",
    },
    "mid": {
        "regulation": "Если нужен прикладной разбор рисков, роли юристов и контура контроля для внедрения AI, напишите в {bot_link}.",
        "case": "Если хотите разобрать ваш процесс и собрать пилот внедрения по такому кейсу, напишите в {bot_link}.",
        "implementation": "Если хотите разобрать ваш контур автоматизации и выбрать реальный формат внедрения для юротдела, напишите в {bot_link}.",
        "tools": "Если нужен отбор инструмента, пилот и юридические ограничения по данным и ответственности, напишите в {bot_link}.",
        "market": "Если хотите понять, как этот тренд влияет на ваши процессы, продукт и архитектуру Legal AI, напишите в {bot_link}.",
    },
    "hard": {
        "regulation": "Если нужен проектный формат: аудит риска, регламенты, процесс и контроль качества AI в юрфункции, напишите в {bot_link}.",
        "case": "Если готовы переходить от идеи к проекту внедрения, соберем архитектуру и план запуска в {bot_link}.",
        "implementation": "Если нужен проект автоматизации заявок, договорной работы или типовых юридических процессов, напишите в {bot_link}.",
        "tools": "Если нужен подбор стека, интеграция и запуск пилота для юротдела, напишите в {bot_link}.",
        "market": "Если хотите из этого тренда собрать полезный продукт или сервис для юридической функции, напишите в {bot_link}.",
    },
}
_AUTO_FOOTER_MODE_BY_FORMAT = {
    "signal": "none",
    "standard": "soft",
    "deep": "soft",
    "digest": "soft",
    "daily": "none",
    "weekly_review": "none",
    "longread": "soft",
    "humor": "none",
}
_MANUAL_FOOTER_LIBRARY = {
    "promo_offer": "Если хотите обсудить внедрение Legal AI под ваш кейс, напишите в {bot_link}.",
    "product_review": "",
    "case_story": "Если хотите собрать похожий сценарий автоматизации под вашу команду, напишите в {bot_link}.",
    "opinion": "",
    "problem_breakdown": "Если хотите разобрать узкое место в заявках, договорах или внутренних процессах, напишите в {bot_link}.",
    "checklist": "Если хотите адаптировать этот чек-лист под ваш юридический процесс, напишите в {bot_link}.",
    "faq": "Если хотите разобрать ваши вопросы по AI и юридической функции на конкретном кейсе, напишите в {bot_link}.",
    "announcement": "Если тема для вас актуальна и нужен следующий шаг по внедрению, напишите в {bot_link}.",
    "digest": "",
    "service_page": "Если хотите обсудить услугу, формат проекта и следующий шаг, напишите в {bot_link}.",
}
_CHANNEL_STYLE_HINTS = {
    "daily": "Редакционный тон: коротко, плотно, без рекламного хвоста. Это информационный пост, а не продающий.",
    "weekly_review": "Редакционный тон: обзор недели. Никакого CTA, только редакционный вывод и ощущение собранного материала.",
    "longread": "Редакционный тон: экспертный воскресный разбор. Допустим мягкий следующий шаг, но без навязчивой продажи.",
    "humor": "Редакционный тон: профессиональная ирония без клоунады. CTA не нужен.",
}
_DEFAULT_HASHTAGS = ["#LegalAI", "#LegalTech", "#AI"]
_DEFAULT_RUBRIC_BY_PILLAR = {
    "regulation": "regulation",
    "case": "legal_ops",
    "implementation": "legal_ops",
    "tools": "market",
    "market": "market",
}
_INCOMPLETE_TRAILING_WORDS = (
    "и",
    "или",
    "но",
    "а",
    "что",
    "чтобы",
    "потому",
    "поэтому",
    "если",
    "когда",
    "для",
    "через",
)
_TRAILING_PREPOSITIONAL_PHRASE_RE = re.compile(
    r"(?:\b(?:на|по|для|в|во|о|об|при|под|над|с|со|к|из|от|до|без)\b)\s+\S+\s*$",
    re.IGNORECASE,
)
_QUALITY_SPECIFICITY_MARKERS = (
    "legal ai",
    "legaltech",
    "legal tech",
    "ai act",
    "gdpr",
    "openai",
    "deepseek",
    "anthropic",
    "персональн",
    "трансгранич",
    "локализац",
    "конфиденциаль",
    "договор",
    "ответствен",
    "лиценз",
    "privacy",
    "compliance",
    "governance",
    "логирован",
    "аудит",
    "человек",
    "human-in-the-loop",
    "vendor",
    "lock-in",
    "sla",
    "indemn",
    "санкц",
    "госзакуп",
    "закуп",
    "поставщик",
    "надежност",
    "надёжност",
    "критер",
    "due diligence",
    "procurement",
    "benchmark",
    "экспортн",
    "e-discovery",
    "legal hold",
    "chain of custody",
)
_SPELLED_NUMBER_MARKERS = (
    "один",
    "два",
    "три",
    "четыре",
    "пять",
    "шесть",
    "семь",
    "восемь",
    "девять",
    "десять",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
)
_DAILY_LEGAL_RUBRICS = {"ai_law", "compliance", "privacy", "contracts", "litigation", "regulation"}
_DAILY_THIRD_BLOCK_HEADINGS = (
    "Юридический контур",
    "Что это значит для юрфункции",
    "Что это значит для команд",
    "Что это значит для рынка",
    "На что смотреть дальше",
)
_DAILY_HEADING_MARKERS = ("Что произошло", "Почему это важно",) + _DAILY_THIRD_BLOCK_HEADINGS + ("Источник",)
_GENERIC_LEGAL_PATTERNS = (
    "есть юридические риски",
    "есть риски",
    "нужно учитывать риски",
    "стоит учитывать риски",
    "важно учитывать риски",
    "нужно проверить юридические аспекты",
)
_RUBRIC_LEGAL_TEMPLATE_HINTS = {
    "privacy": (
        "Если материал относится к privacy, юридический блок должен говорить про правовое основание обработки, "
        "трансграничную передачу, локализацию, DPA/поручение обработки, права доступа к данным и режим работы с output."
    ),
    "contracts": (
        "Если материал относится к contracts, юридический блок должен говорить про SLA, scope использования модели, "
        "ограничения на output, распределение ответственности, indemnity, audit rights и риск vendor lock-in."
    ),
    "litigation": (
        "Если материал относится к litigation, юридический блок должен говорить про explainability, admissibility, "
        "chain of custody, legal hold, document review, human-in-the-loop и контроль качества доказательственной базы."
    ),
    "regulation": (
        "Если материал относится к regulation, юридический блок должен говорить про применимость AI Act, privacy law, "
        "классификацию риска, governance, логирование, внутренний контроль, санкционные и экспортные ограничения."
    ),
    "ai_law": (
        "Если материал относится к ai_law, юридический блок должен говорить про права на output, обучение на данных, "
        "IP и лицензии, automated decision-making, роль человека в принятии решения, explainability и enforceability."
    ),
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

    def _completion_kwargs(self, format_type: str) -> dict[str, Any]:
        token_limit = _FORMAT_MAX_OUTPUT_TOKENS.get(format_type, _FORMAT_MAX_OUTPUT_TOKENS["standard"])
        if self._use_max_tokens_param:
            return {"max_tokens": token_limit}
        return {"max_completion_tokens": token_limit}

    @staticmethod
    def _allow_quality_fallback(format_type: str) -> bool:
        return format_type not in {"daily"}

    @staticmethod
    def _shorten(text: str, limit: int, *, prefer_sentence: bool = False) -> str:
        normalized = re.sub(r"\s+", " ", (text or "").strip())
        if len(normalized) <= limit:
            return normalized

        if prefer_sentence:
            punctuation_positions = [
                match.end()
                for match in re.finditer(r"[.!?…](?:[\"'»”)]*)", normalized[: limit + 1])
                if match.end() <= limit
            ]
            if punctuation_positions:
                return normalized[: punctuation_positions[-1]].strip()
            return ""

        word_cutoff = max(int(limit * 0.65), limit - 80)
        last_space = normalized.rfind(" ", 0, limit + 1)
        if last_space >= word_cutoff:
            return normalized[:last_space].rstrip(" ,;:-")

        return normalized[:limit].rstrip(" ,;:-")

    @classmethod
    def _shorten_title(cls, text: str, limit: int = 110) -> str:
        normalized = re.sub(r"\s+", " ", (text or "").strip())
        if len(normalized) <= limit:
            return normalized

        punctuation_positions = [
            match.end()
            for match in re.finditer(r"[:.!?…](?:[\"'»”)]*)", normalized[: limit + 1])
            if match.end() <= limit
        ]
        if punctuation_positions:
            candidate = normalized[: punctuation_positions[-1]].strip(" ,;:-")
        else:
            last_space = normalized.rfind(" ", 0, limit + 1)
            candidate = normalized[:last_space].rstrip(" ,;:-") if last_space > 0 else normalized[:limit].rstrip(" ,;:-")

        while True:
            lowered = candidate.lower().strip()
            if not lowered:
                return normalized[:limit].rstrip(" ,;:-")
            if re.search(r"\b(?:на|по|для|в|во|о|об|при|под|над|с|со|к|из|от|до|без)\s*$", lowered):
                candidate = candidate.rsplit(" ", 1)[0].rstrip(" ,;:-")
                continue
            last_word = re.sub(r"[^\wа-яА-Я-]+$", "", lowered.split()[-1])
            if last_word in _INCOMPLETE_TRAILING_WORDS:
                candidate = candidate.rsplit(" ", 1)[0].rstrip(" ,;:-")
                continue
            if _TRAILING_PREPOSITIONAL_PHRASE_RE.search(candidate):
                candidate = _TRAILING_PREPOSITIONAL_PHRASE_RE.sub("", candidate).rstrip(" ,;:-")
                continue
            break

        return candidate or normalized[:limit].rstrip(" ,;:-")

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
    def _bot_link() -> str:
        if settings.news_helper_bot_url:
            username = settings.news_helper_bot_username.strip()
            link_text = html.escape(f"@{username.lstrip('@')}")
            safe_url = html.escape(settings.news_helper_bot_url, quote=True)
            return f'<a href="{safe_url}">{link_text}</a>'
        return "@legal_ai_helper_new_bot"

    @classmethod
    def _style_hint(cls, format_type: str) -> str:
        return _CHANNEL_STYLE_HINTS.get(
            format_type,
            "Редакционный тон: полезный профессиональный пост без рекламного перегруза и клишированного хвоста.",
        )

    @classmethod
    def _cta_text(cls, cta_type: str, pillar: str) -> str:
        templates = _CTA_LIBRARY.get(cta_type, _CTA_LIBRARY["soft"])
        template = templates.get(pillar, templates.get("implementation", next(iter(templates.values()))))
        return template.format(bot_link=cls._bot_link())

    @classmethod
    def _auto_footer_text(cls, format_type: str, cta_type: str, pillar: str) -> str:
        mode = _AUTO_FOOTER_MODE_BY_FORMAT.get(format_type, "soft")
        if mode == "none":
            return ""
        return cls._cta_text(cta_type, pillar)

    @staticmethod
    def _source_block(article_url: str, format_type: str) -> str:
        safe_article_url = html.escape(article_url, quote=True)
        if article_url.startswith("internal://weekly-review"):
            return "<b>Источник</b>: внутренняя подборка сигналов недели"
        if article_url.startswith("internal://longread"):
            return "<b>Источник</b>: внутренняя подборка материалов для лонгрида"
        if article_url.startswith("internal://humor"):
            return "<b>Источник</b>: внутренняя подборка сигналов недели"
        return f'<b>Источник</b>: <a href="{safe_article_url}">оригинал статьи</a>'

    @staticmethod
    def _sentence_list(text: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", (text or "").strip())
        if not normalized:
            return []
        parts = re.split(r"(?<=[.!?…])\s+", normalized)
        return [part.strip() for part in parts if part.strip()]

    @classmethod
    def _derive_weekly_points(cls, data: dict[str, Any]) -> list[str]:
        raw_points = data.get("weekly_points")
        points: list[str] = []
        if isinstance(raw_points, list):
            for item in raw_points:
                cleaned = cls._shorten(str(item), 220)
                if cleaned:
                    points.append(cleaned)
        if len(points) >= 5:
            return points[:10]
        joined = " ".join(
            part for part in (
                str(data.get("what_happened") or ""),
                str(data.get("business_effect") or ""),
                str(data.get("legal_risks") or ""),
            )
            if part
        )
        derived = cls._sentence_list(joined)
        return [cls._shorten(item, 220) for item in derived[:10] if item]

    @staticmethod
    def _looks_complete_prose(text: str) -> bool:
        plain = html.unescape(re.sub(r"<[^>]+>", "", text or ""))
        lines = [line.strip() for line in plain.splitlines() if line.strip()]
        filtered: list[str] = []
        for line in lines:
            lowered = line.lower()
            if lowered.startswith("источник"):
                continue
            if lowered.startswith("#"):
                continue
            if lowered == "следующий шаг":
                continue
            filtered.append(line)
        if not filtered:
            return False
        last_line = filtered[-1].rstrip()
        if not last_line.endswith((".", "!", "?", "…")):
            return False
        last_word = re.sub(r"[^\wа-яА-Я-]+$", "", last_line.split()[-1].lower())
        if last_word in _INCOMPLETE_TRAILING_WORDS:
            return False
        return True

    @staticmethod
    def _blocks_look_complete(text: str) -> bool:
        plain = html.unescape(re.sub(r"<[^>]+>", "", text or ""))
        lines = [line.strip() for line in plain.splitlines() if line.strip()]
        paragraph_lines: list[str] = []
        for index, line in enumerate(lines):
            lowered = line.lower()
            if lowered.startswith("источник"):
                continue
            if lowered.startswith("#"):
                continue
            if index == 0:
                # Первая строка - заголовок поста. Для него отдельная валидация, без требования точки в конце.
                continue
            if line.startswith("• "):
                continue
            if re.match(r"^\d+\.\s", line):
                continue
            word_count = len(line.split())
            if len(line) <= 90 and word_count <= 6 and not re.search(r"[.!?…]$", line):
                # Заголовки и короткие служебные строки не валидируем как прозу.
                continue
            paragraph_lines.append(line)

        if not paragraph_lines:
            return False

        for paragraph in paragraph_lines:
            if not LLMNewsWriter._looks_complete_prose(paragraph):
                return False
        return True

    @staticmethod
    def _has_specificity_signal(text: str) -> bool:
        normalized = html.unescape(re.sub(r"<[^>]+>", "", text or "")).lower()
        if re.search(r"\d", normalized):
            return True
        if any(re.search(rf"\b{re.escape(marker)}\b", normalized) for marker in _SPELLED_NUMBER_MARKERS):
            return True
        return any(marker in normalized for marker in _QUALITY_SPECIFICITY_MARKERS)

    @staticmethod
    def _extract_daily_third_block_body(text: str) -> str:
        plain = html.unescape(re.sub(r"<[^>]+>", "", text or ""))
        lines = [line.strip() for line in plain.splitlines() if line.strip()]
        capture = False
        captured: list[str] = []
        for line in lines:
            if line in _DAILY_THIRD_BLOCK_HEADINGS:
                capture = True
                continue
            if not capture:
                continue
            if line in _DAILY_HEADING_MARKERS or line.startswith("#"):
                break
            if line.lower().startswith("источник"):
                break
            captured.append(line)
        return " ".join(captured).strip()

    @classmethod
    def _daily_tail_block(
        cls,
        *,
        rubric: str,
        pillar: str,
        business_effect: str,
        legal_risks: str,
        conclusion: str,
        steps_block: str,
    ) -> tuple[str, str]:
        legal_specific = cls._has_specificity_signal(legal_risks)
        conclusion_or_effect = conclusion or business_effect

        if rubric in _DAILY_LEGAL_RUBRICS and legal_specific:
            return "Юридический контур", html.escape(legal_risks)
        if pillar in {"implementation", "case"}:
            return "Что это значит для юрфункции", html.escape(conclusion_or_effect or legal_risks or business_effect)
        if pillar == "tools":
            return "Что это значит для команд", html.escape(conclusion_or_effect or business_effect or legal_risks)
        if pillar == "market":
            return "Что это значит для рынка", html.escape(conclusion_or_effect or business_effect or legal_risks)
        if legal_specific:
            return "Юридический контур", html.escape(legal_risks)
        return "На что смотреть дальше", html.escape(conclusion_or_effect or business_effect or html.unescape(steps_block))

    @staticmethod
    def _infer_rubric_hint(article: ArticleCandidate, pillar: str) -> str:
        haystack = " ".join(
            part for part in (article.title or "", article.summary or "", article.article_url or "") if part
        ).lower()

        if any(
            marker in haystack
            for marker in ("privacy", "gdpr", "персональн", "локализац", "трансгранич", "cross-border", "dpa")
        ):
            return "privacy"
        if any(
            marker in haystack
            for marker in ("contract", "договор", "sla", "redlining", "vendor", "platform", "procurement", "indemn")
        ):
            return "contracts"
        if any(
            marker in haystack
            for marker in (
                "litigation",
                "суд",
                "e-discovery",
                "ediscovery",
                "legal hold",
                "document review",
                "chain of custody",
                "evidence",
            )
        ):
            return "litigation"
        if any(
            marker in haystack
            for marker in (
                "ai act",
                "регулирован",
                "compliance",
                "governance",
                "sanction",
                "санкц",
                "экспорт",
                "risk classification",
            )
        ):
            return "regulation"
        if any(
            marker in haystack
            for marker in (
                "copyright",
                "ip ",
                "output",
                "training data",
                "foundation model",
                "automated decision",
                "bias",
                "discrimination",
                "explainability",
            )
        ):
            return "ai_law"
        if pillar == "market":
            return "market"
        if pillar in {"implementation", "case"}:
            return "legal_ops"
        return "market" if pillar == "tools" else "regulation"

    @classmethod
    def _rubric_template_hint(cls, rubric: str) -> str:
        return _RUBRIC_LEGAL_TEMPLATE_HINTS.get(
            rubric,
            "Юридический блок должен быть предметным и привязанным к фактам статьи, а не общим перечнем рисков.",
        )

    @classmethod
    def _infer_legal_focus_hint(cls, article: ArticleCandidate, pillar: str) -> str:
        haystack = " ".join(
            part for part in (article.title or "", article.summary or "", article.article_url or "") if part
        ).lower()
        inferred_rubric = cls._infer_rubric_hint(article, pillar)
        if any(marker in haystack for marker in ("персональн", "privacy", "gdpr", "локализац", "трансгранич")):
            return (
                "Сфокусируй юридический блок на персональных данных: правовое основание обработки, "
                "трансграничную передачу, локализацию, права доступа к данным и договорный режим с вендором. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        if any(marker in haystack for marker in ("contract", "договор", "sla", "redlining", "vendor", "platform")):
            return (
                "Сфокусируй юридический блок на договорном контуре: SLA, ответственность поставщика, "
                "ограничения по использованию output, конфиденциальность, audit rights и vendor lock-in. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        if any(marker in haystack for marker in ("litigation", "суд", "e-discovery", "ediscovery", "legal hold", "document review")):
            return (
                "Сфокусируй юридический блок на спорах и доказуемости: explainability, chain of custody, "
                "сохранность доказательств, legal hold и human-in-the-loop. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        if any(marker in haystack for marker in ("ai act", "регулирован", "compliance", "governance", "sanction", "санкц", "экспорт")):
            return (
                "Сфокусируй юридический блок на регуляторике и governance: применимость AI Act / privacy law, "
                "внутренний контроль, логирование, санкционные и экспортные ограничения, распределение ответственности. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        if pillar == "market":
            return (
                "Сфокусируй третий блок на юридико-рыночных последствиях: vendor due diligence, режим закупки, "
                "санкционные ограничения, устойчивость поставщика и contractual safeguards. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        if pillar in {"implementation", "case"}:
            return (
                "Сфокусируй юридический блок на практическом внедрении: контроль качества output, "
                "процедуры проверки юристом, конфиденциальность и распределение ответственности. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        if pillar == "tools":
            return (
                "Сфокусируй юридический блок на выборе инструмента: режим доступа к данным, SLA, "
                "права на output, аудит действий модели и ограничения использования. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        return (
            "Юридический блок должен быть предметным: укажи конкретные правовые вопросы, "
            "которые юристу придется проверить в связи с этой новостью. "
            + cls._rubric_template_hint(inferred_rubric)
        )

    @staticmethod
    def _looks_generic_legal_commentary(text: str) -> bool:
        normalized = re.sub(r"\s+", " ", html.unescape(text or "")).strip().lower()
        if not normalized:
            return True
        if any(pattern in normalized for pattern in _GENERIC_LEGAL_PATTERNS):
            return True
        generic_score = sum(1 for marker in _QUALITY_SPECIFICITY_MARKERS if marker in normalized)
        return generic_score == 0

    @classmethod
    def _fallback_legal_commentary(cls, article: ArticleCandidate, pillar: str, rubric: str) -> str:
        haystack = " ".join(
            part for part in (article.title or "", article.summary or "", article.article_url or "") if part
        ).lower()
        inferred_rubric = rubric or cls._infer_rubric_hint(article, pillar)
        if inferred_rubric == "privacy":
            return (
                "Юристу стоит проверить правовое основание обработки, трансграничную передачу, локализацию, "
                "DPA с вендором, режим доступа к данным и ограничения на повторное использование output."
            )
        if inferred_rubric == "contracts":
            return (
                "Юристу стоит проверить SLA, scope допустимого использования модели, права на output, indemnity, "
                "audit rights, распределение ответственности и риск vendor lock-in при смене поставщика."
            )
        if inferred_rubric == "litigation":
            return (
                "Юристу стоит оценить explainability модели, admissibility результата, chain of custody, "
                "legal hold, полноту document review и обязательный human-in-the-loop в спорном контуре."
            )
        if inferred_rubric == "regulation":
            return (
                "Юристу стоит проверить применимость AI Act и privacy-требований, классификацию риска, "
                "внутренний governance-контур, логирование, санкционные и экспортные ограничения."
            )
        if inferred_rubric == "ai_law":
            return (
                "Юристу стоит проверить права на output и training data, лицензионный режим модели, "
                "границы automated decision-making, explainability, human review и enforceability решений."
            )
        if any(marker in haystack for marker in ("персональн", "privacy", "gdpr", "локализац", "трансгранич")):
            return (
                "Юристу стоит проверить правовое основание обработки данных, трансграничную передачу, "
                "локализацию, режим доступа к данным и договорные ограничения на использование модели."
            )
        if any(marker in haystack for marker in ("contract", "договор", "sla", "redlining", "vendor", "platform")):
            return (
                "Юристу стоит проверить SLA, распределение ответственности поставщика, права на output, "
                "режим конфиденциальности, audit rights и риск vendor lock-in."
            )
        if any(marker in haystack for marker in ("litigation", "суд", "e-discovery", "ediscovery", "legal hold", "document review")):
            return (
                "Юристу стоит оценить explainability, порядок валидации модели, сохранность цепочки доказательств, "
                "полноту legal hold и обязательный human-in-the-loop при работе со спором."
            )
        if rubric in _DAILY_LEGAL_RUBRICS or any(marker in haystack for marker in ("ai act", "регулирован", "compliance", "governance", "sanction", "санкц", "экспорт")):
            return (
                "Юристу стоит проверить применимость AI Act и privacy-требований, внутренний governance-контур, "
                "логирование, контроль качества output и распределение ответственности между бизнесом и вендором."
            )
        if pillar == "market":
            return (
                "Для юрфункции здесь важны vendor due diligence, санкционные и экспортные ограничения, "
                "режим закупки, contractual safeguards и устойчивость поставщика в критичных сценариях."
            )
        if pillar == "tools":
            return (
                "Юристу стоит проверить режим доступа к данным, ограничения использования output, "
                "SLA, конфиденциальность и право на аудит действий модели."
            )
        return (
            "Юристу стоит проверить договорный режим использования инструмента, контур данных, "
            "контроль качества output и распределение ответственности при внедрении."
        )

    def _format_post(
        self,
        data: dict[str, Any],
        article_url: str,
        fallback_title: str,
        format_type: str,
        cta_type: str,
        pillar: str,
    ) -> tuple[str, str, str]:
        limits = _FORMAT_FIELD_LIMITS.get(format_type, _FORMAT_FIELD_LIMITS["standard"])
        title = self._shorten_title(data.get("title") or fallback_title, 110)
        default_rubric = _DEFAULT_RUBRIC_BY_PILLAR.get(pillar, "legal_ai")
        rubric = self._shorten(data.get("rubric") or default_rubric, 100)
        what_happened = self._shorten(data.get("what_happened") or "", limits["what"], prefer_sentence=True)
        business_effect = self._shorten(data.get("business_effect") or "", limits["effect"], prefer_sentence=True)
        legal_risks = self._shorten(data.get("legal_risks") or "", limits["risks"], prefer_sentence=True)
        next_steps_raw = data.get("next_steps") or ""
        hashtags_value = data.get("hashtags")

        steps: list[str] = []
        for part in str(next_steps_raw).split(";"):
            cleaned = self._shorten(part, limits["step"])
            if cleaned:
                steps.append(cleaned)
        steps = steps[: limits["steps"]]

        hashtags: list[str] = []
        if isinstance(hashtags_value, list):
            for item in hashtags_value:
                tag = self._shorten(str(item), 40)
                if tag and tag.startswith("#"):
                    hashtags.append(tag)
        if not hashtags:
            hashtags = list(_DEFAULT_HASHTAGS)
        hashtags = hashtags[: limits["hashtags"]]

        escaped_title = html.escape(title)
        escaped_what_happened = html.escape(
            what_happened or "В статье описан новый кейс внедрения AI с конкретными операционными деталями."
        )
        escaped_business_effect = html.escape(
            business_effect or "Сценарий влияет на скорость процессов, стоимость операций и управляемость качества сервиса."
        )
        escaped_legal_risks = html.escape(
            legal_risks
            or "Юристу стоит проверить контур персональных данных, договорное распределение ответственности, требования к логированию и регуляторные ограничения."
        )
        escaped_steps = [html.escape(item) for item in steps]
        steps_block = "\n".join(f"• {item}" for item in escaped_steps) if escaped_steps else "• Проверить применимость кейса к текущим процессам."
        lead = self._shorten(data.get("lead") or "", 260, prefer_sentence=True)
        escaped_lead = html.escape(lead)
        conclusion = self._shorten(data.get("conclusion") or "", 320, prefer_sentence=True)
        escaped_conclusion = html.escape(conclusion)
        cta_line = self._auto_footer_text(format_type, cta_type, pillar)
        source_block = self._source_block(article_url, format_type)
        hashtags_line = " ".join(html.escape(tag) for tag in hashtags[:4])
        next_step_block = f"<b>Следующий шаг</b>\n{cta_line}\n\n" if cta_line else ""

        if format_type == "weekly_review":
            weekly_points = self._derive_weekly_points(data)
            points_block = "\n".join(f"{index}. {html.escape(point)}" for index, point in enumerate(weekly_points[:10], start=1))
            if not points_block:
                points_block = f"1. {escaped_what_happened}"
            body = (
                f"<b>{escaped_title}</b>\n\n"
                + (f"{escaped_lead}\n\n" if escaped_lead else "")
                + f"<b>Ключевые сигналы недели</b>\n{points_block}\n\n"
                + f"<b>Что это значит для юрфункции</b>\n{escaped_business_effect}\n\n"
                + f"<b>На что смотреть юристам</b>\n{escaped_legal_risks}\n\n"
                + f"<b>Что проверить у себя</b>\n{steps_block}\n\n"
                + (f"<b>Вывод</b>\n{escaped_conclusion}\n\n" if escaped_conclusion else "")
                + f"{next_step_block}"
                + f"{source_block}\n"
                + f"{hashtags_line}"
            )
        elif format_type == "longread":
            body = (
                f"<b>{escaped_title}</b>\n\n"
                + (f"{escaped_lead}\n\n" if escaped_lead else "")
                + f"<b>Контекст</b>\n{escaped_what_happened}\n\n"
                + f"<b>Практический смысл</b>\n{escaped_business_effect}\n\n"
                + f"<b>Риски и ограничения</b>\n{escaped_legal_risks}\n\n"
                + f"<b>Что делать</b>\n{steps_block}\n\n"
                + (f"<b>Вывод</b>\n{escaped_conclusion}\n\n" if escaped_conclusion else "")
                + f"{next_step_block}"
                + f"{source_block}\n"
                + f"{hashtags_line}"
            )
        elif format_type == "humor":
            body = (
                f"<b>{escaped_title}</b>\n\n"
                + (f"{escaped_lead}\n\n" if escaped_lead else "")
                + f"<b>Ситуация недели</b>\n{escaped_what_happened}\n\n"
                + f"<b>Почему это смешно</b>\n{escaped_business_effect}\n\n"
                + f"<b>Где здесь практический смысл</b>\n{escaped_legal_risks}\n\n"
                + f"{source_block}\n"
                + f"{hashtags_line}"
            )
        elif format_type == "daily":
            daily_heading, daily_body = self._daily_tail_block(
                rubric=rubric,
                pillar=pillar,
                business_effect=business_effect,
                legal_risks=legal_risks,
                conclusion=conclusion,
                steps_block=steps_block,
            )
            body = (
                f"<b>{escaped_title}</b>\n\n"
                + (f"{escaped_lead}\n\n" if escaped_lead else "")
                + f"<b>Что произошло</b>\n{escaped_what_happened}\n\n"
                + f"<b>Почему это важно</b>\n{escaped_business_effect}\n\n"
                + f"<b>{daily_heading}</b>\n{daily_body}\n\n"
                + f"{source_block}\n"
                + f"{hashtags_line}"
            )
        else:
            body = (
                f"<b>{escaped_title}</b>\n\n"
                + (f"{escaped_lead}\n\n" if escaped_lead else "")
                + f"<b>Что произошло</b>\n{escaped_what_happened}\n\n"
                + f"<b>Бизнес-эффект</b>\n{escaped_business_effect}\n\n"
                + f"<b>Юридические риски</b>\n{escaped_legal_risks}\n\n"
                + f"<b>Что делать</b>\n{steps_block}\n\n"
                + (f"<b>Вывод</b>\n{escaped_conclusion}\n\n" if escaped_conclusion else "")
                + f"{next_step_block}"
                + f"{source_block}\n"
                + f"{hashtags_line}"
            )
        text = normalize_post_text(body)
        return title, text, rubric

    @staticmethod
    def _quality_gate_failure_reason(text: str, format_type: str) -> str | None:
        normalized = (text or "").strip()
        format_markers = {
            "weekly_review": ("Ключевые сигналы недели", "Что это значит для юрфункции", "На что смотреть юристам", "Что проверить у себя", "Источник"),
            "longread": ("Контекст", "Практический смысл", "Риски и ограничения", "Что делать", "Источник"),
            "daily": ("Что произошло", "Почему это важно", "Источник"),
            "humor": ("Ситуация недели", "Почему это смешно", "Где здесь практический смысл", "Источник"),
        }
        required_markers = format_markers.get(
            format_type,
            ("Что произошло", "Бизнес-эффект", "Юридические риски", "Что делать", "Источник"),
        )
        min_chars = _FORMAT_MIN_CHARS.get(format_type, _FORMAT_MIN_CHARS["standard"])
        if len(normalized) < min_chars:
            return f"too_short:{len(normalized)}<{min_chars}"
        for marker in required_markers:
            if marker not in normalized:
                return f"missing_marker:{marker}"
        if format_type == "daily" and not any(marker in normalized for marker in _DAILY_THIRD_BLOCK_HEADINGS):
            return "missing_daily_third_block"
        if format_type == "daily":
            third_block = LLMNewsWriter._extract_daily_third_block_body(normalized)
            if len(third_block) < 120:
                return f"weak_daily_third_block:{len(third_block)}"
        if not LLMNewsWriter._has_specificity_signal(normalized):
            return "not_specific_enough"
        if len(normalized) >= 3980:
            return f"too_long:{len(normalized)}"
        if not LLMNewsWriter._looks_complete_prose(normalized):
            return "incomplete_tail"
        if not LLMNewsWriter._blocks_look_complete(normalized):
            return "incomplete_block"
        return None

    @classmethod
    def _passes_quality_gate(cls, text: str, format_type: str) -> bool:
        return cls._quality_gate_failure_reason(text, format_type) is None

    def _repair_post(
        self,
        *,
        title: str,
        text: str,
        article_url: str,
        format_type: str,
    ) -> str:
        prompt = (
            "Ниже HTML-пост для Telegram. Его нужно аккуратно починить.\n"
            "Требования:\n"
            "1) Сохрани HTML-структуру и жирные подзаголовки.\n"
            "2) Уменьши текст так, чтобы итог был меньше 3900 символов.\n"
            "3) Никаких обрывов на полуслове, незавершенных фраз, незакрытых тегов.\n"
            "4) Не добавляй новые факты сверх исходного текста.\n"
            "5) Каждый смысловой блок должен заканчиваться законченной фразой.\n"
            "6) Верни только исправленный HTML, без пояснений.\n\n"
            f"Формат: {format_type}\n"
            f"Заголовок: {title}\n"
            f"URL: {article_url}\n\n"
            f"{text}"
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Ты шеф-редактор Telegram-канала. Чинишь HTML-посты перед публикацией."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            **self._completion_kwargs(format_type),
        )
        repaired = normalize_post_text(response.choices[0].message.content or "")
        return repaired

    def _fallback_post(self, article: ArticleCandidate, format_type: str, cta_type: str, pillar: str) -> dict[str, str]:
        title = self._shorten(article.title or "Обзор новости", 110)
        summary = self._shorten(article.summary, 1300, prefer_sentence=True)
        summary = summary or "Источник сообщил о новом кейсе внедрения AI в юридическом процессе."
        business_effect = "Кейс показывает, как сократить ручную работу и повысить скорость обработки типовых задач."
        legal_risks = "Юристу стоит заранее проверить обработку персональных данных, договорную ответственность поставщика, требования к логированию и контроль качества output."
        conclusion = ""
        if pillar == "market":
            business_effect = "Это сигнал о том, что вокруг крупных AI-вендоров усиливается рыночный, политический и регуляторный контур."
            conclusion = "Дальше стоит смотреть, как это повлияет на выбор поставщиков, закупки и корпоративные AI-стратегии."
        elif pillar == "tools":
            business_effect = "Новость показывает, как меняется контур выбора AI-инструментов и требований к вендорам со стороны корпоративных команд."
            conclusion = "Дальше важны не общие обещания вендора, а режим доступа к данным, качество output и контрактные ограничения."
        elif pillar in {"implementation", "case"}:
            conclusion = "Практический смысл здесь не в самой новости, а в том, какие процессы и роли можно пересобрать внутри юрфункции."
        base = {
            "title": title,
            "rubric": _DEFAULT_RUBRIC_BY_PILLAR.get(pillar, "legal_ai"),
            "what_happened": summary[:450],
            "business_effect": business_effect,
            "legal_risks": legal_risks,
            "next_steps": "Описать процесс и данные в нем; проверить PDn и договорные ограничения; выбрать 1-2 этапа для пилота; согласовать критерии качества и контроля",
            "conclusion": conclusion,
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
        inferred_rubric = self._infer_rubric_hint(article, pillar)
        user_prompt = (
            f"Источник: {article.source_url}\n"
            f"URL статьи: {article.article_url}\n"
            f"Заголовок: {article.title}\n"
            f"Дата публикации: {article.published_at.isoformat() if article.published_at else 'не указана'}\n\n"
            f"Целевая смысловая корзина: {pillar}\n"
            f"Предполагаемая рубрика: {inferred_rubric}\n"
            f"Стилистика канала: {self._style_hint(format_type)}\n"
            f"Приоритетный юридический угол: {self._infer_legal_focus_hint(article, pillar)}\n"
            f"Шаблон юридического комментария для этой рубрики: {self._rubric_template_hint(inferred_rubric)}\n"
            f"{format_hint}\n"
            f"{_FORMAT_SHAPE_HINTS.get(format_type, '')}\n"
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
            **self._completion_kwargs(format_type),
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
            inferred_rubric = self._shorten(
                str(data.get("rubric") or _DEFAULT_RUBRIC_BY_PILLAR.get(pillar, "legal_ai")),
                100,
            )
            if self._looks_generic_legal_commentary(str(data.get("legal_risks") or "")):
                data["legal_risks"] = self._fallback_legal_commentary(article, pillar, inferred_rubric)
            title, text, rubric = self._format_post(
                data,
                article.article_url,
                article.title[:110],
                format_type=format_type,
                cta_type=cta_type,
                pillar=pillar,
            )
            if not self._passes_quality_gate(text, format_type):
                failure_reason = self._quality_gate_failure_reason(text, format_type) or "unknown"
                try:
                    repaired = self._repair_post(
                        title=title,
                        text=text,
                        article_url=article.article_url,
                        format_type=format_type,
                    )
                    if repaired and self._passes_quality_gate(repaired, format_type):
                        logger.info(
                            "llm_post_repaired_after_quality_gate",
                            extra={"title": title[:80], "rubric": rubric, "format_type": format_type},
                        )
                        return {"title": title[:160], "text": repaired, "rubric": rubric[:100]}
                except Exception as repair_exc:
                    logger.warning(
                        "llm_post_repair_failed",
                        extra={"title": title[:80], "format_type": format_type, "error": str(repair_exc)},
                    )
                logger.warning(
                    "llm_post_failed_quality_gate",
                    extra={
                        "title": title[:80],
                        "rubric": rubric,
                        "format_type": format_type,
                        "reason": failure_reason,
                    },
                )
                if not self._allow_quality_fallback(format_type):
                    logger.info(
                        "llm_post_discarded_after_quality_gate",
                        extra={"title": title[:80], "rubric": rubric, "format_type": format_type},
                    )
                    return None
                return self._fallback_post(article, format_type=format_type, cta_type=cta_type, pillar=pillar)
            logger.info("llm_post_generated", extra={"title": title[:80], "rubric": rubric, "format_type": format_type})
            return {"title": title[:160], "text": text, "rubric": rubric[:100]}
        except Exception as exc:
            logger.warning("llm_post_parse_failed", extra={"error": str(exc), "format_type": format_type})
            return self._fallback_post(article, format_type=format_type, cta_type=cta_type, pillar=pillar)


def build_manual_footer(post_kind: str) -> str:
    template = _MANUAL_FOOTER_LIBRARY.get(post_kind)
    if not template:
        return ""
    return template.format(bot_link=LLMNewsWriter._bot_link())


def compose_manual_post_html(title: str, body: str, post_kind: str) -> str:
    normalized_title = html.escape((title or "").strip() or "Без заголовка")
    raw_body = (body or "").strip()
    body_lines = [line.strip() for line in raw_body.splitlines()]
    formatted_lines: list[str] = []
    for line in body_lines:
        if not line:
            formatted_lines.append("")
            continue
        escaped = html.escape(line)
        if line.endswith(":") and len(line) <= 80:
            formatted_lines.append(f"<b>{escaped}</b>")
        else:
            formatted_lines.append(escaped)
    body_html = "\n".join(formatted_lines).strip()
    footer = build_manual_footer(post_kind)
    parts = [f"<b>{normalized_title}</b>"]
    if body_html:
        parts.append(body_html)
    if footer:
        parts.append(f"<b>Следующий шаг</b>\n{footer}")
    return normalize_post_text("\n\n".join(part for part in parts if part))
