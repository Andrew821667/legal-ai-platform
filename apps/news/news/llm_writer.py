from __future__ import annotations

import html
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from prompts.news import (
    NEWS_FOOTER_DECISION_SYSTEM_PROMPT,
    NEWS_WRITER_SYSTEM_PROMPT,
    build_news_writer_system_prompt,
)

from news.pipeline import ArticleCandidate, RAGExample, normalize_post_text
from news.settings import settings

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = NEWS_WRITER_SYSTEM_PROMPT
_FORMAT_HINTS = {
    "signal": "Формат signal: 450-700 символов, только ключевые факты и 2-3 действия.",
    "standard": "Формат standard: 900-1400 символов, полный разбор по структуре.",
    "deep": "Формат deep: 1600-2200 символов, глубже анализ рисков и сценариев внедрения.",
    "digest": "Формат digest: 1200-1900 символов, структурируй как недельный обзор с 5-7 пунктами внутри блока 'Что произошло'.",
    "daily": "Формат daily: 1100-1700 символов, плотный ежедневный пост по новости для канала о Legal AI.",
    "weekly_review": "Формат weekly_review: 3200-3900 символов, 8-10 пунктов, без обрезки текста, это обзор недели по Legal AI и автоматизации юрфункции.",
    "longread": "Формат longread: 3200-4300 символов, это действительно длинный воскресный разбор с сильной практической частью и четкой логикой.",
    "practice": "Формат practice: 1100-1700 символов, это субботний практический разбор по Legal AI и юрфункции, без юмора и без развлекательной подачи.",
    "humor": "Формат practice: 1100-1700 символов, это субботний практический разбор по Legal AI и юрфункции, без юмора и без развлекательной подачи.",
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
        "-> «Что делать» -> «Вывод» -> источник. Это должен быть цельный, действительно длинный разбор; "
        "не используй слово «лонгрид» или longread в заголовке."
    ),
    "practice": (
        "Структура practice: короткий лид -> «Ситуация недели» -> «Где узкое место» -> «Что взять в работу» "
        "-> источник. Это практический субботний формат, а не юмор."
    ),
    "humor": (
        "Структура practice: короткий лид -> «Ситуация недели» -> «Где узкое место» -> «Что взять в работу» "
        "-> источник. Это практический субботний формат, а не юмор."
    ),
}
_FORMAT_MIN_CHARS = {
    "signal": 420,
    "standard": 750,
    "deep": 1100,
    "digest": 950,
    "daily": 900,
    "weekly_review": 2800,
    "longread": 2800,
    "practice": 1000,
    "humor": 1000,
}
_FORMAT_MAX_OUTPUT_TOKENS = {
    "signal": 1200,
    "standard": 1600,
    "deep": 2200,
    "digest": 2200,
    "daily": 1800,
    "weekly_review": 3400,
    "longread": 3400,
    "practice": 1800,
    "humor": 1800,
}
_FORMAT_FIELD_LIMITS: dict[str, dict[str, int]] = {
    "signal": {"what": 320, "effect": 240, "risks": 220, "step": 90, "steps": 3, "hashtags": 3},
    "standard": {"what": 500, "effect": 420, "risks": 380, "step": 110, "steps": 4, "hashtags": 3},
    "deep": {"what": 700, "effect": 540, "risks": 520, "step": 120, "steps": 4, "hashtags": 4},
    "digest": {"what": 900, "effect": 420, "risks": 360, "step": 95, "steps": 4, "hashtags": 4},
    "daily": {"what": 520, "effect": 360, "risks": 320, "step": 95, "steps": 3, "hashtags": 3},
    "weekly_review": {"what": 1500, "effect": 520, "risks": 420, "step": 160, "steps": 4, "hashtags": 4},
    "longread": {"what": 1300, "effect": 850, "risks": 700, "step": 130, "steps": 5, "hashtags": 4},
    "practice": {"what": 520, "effect": 360, "risks": 300, "step": 100, "steps": 3, "hashtags": 3},
    "humor": {"what": 520, "effect": 360, "risks": 300, "step": 100, "steps": 3, "hashtags": 3},
}
_CTA_LIBRARY = {
    "soft": {
        "regulation": "Если хотите разобрать, как такой регуляторный риск влияет на вашу ИИ-функцию, персональные данные или комплаенс, обсудите это с {assistant_link}.",
        "case": "Если хотите понять, как такой сценарий внедрения применим в вашей юрфункции, обсудите это с {assistant_link}.",
        "implementation": "Если хотите примерить такой сценарий автоматизации на договорную работу, заявки или внутренние процессы, обсудите это с {assistant_link}.",
        "tools": "Если хотите оценить, подходит ли такой инструмент для юротдела или практики, обсудите это с {assistant_link}.",
        "market": "Если хотите перевести этот рыночный сигнал в план действий для вашей юрфункции или продукта, обсудите это с {assistant_link}.",
    },
    "mid": {
        "regulation": "Если нужен прикладной разбор рисков, роли юристов и контура контроля для внедрения ИИ, обсудите это с {assistant_link}.",
        "case": "Если хотите разобрать ваш процесс и собрать пилот внедрения по такому кейсу, обсудите это с {assistant_link}.",
        "implementation": "Если хотите разобрать ваш контур автоматизации и выбрать реальный формат внедрения для юротдела, обсудите это с {assistant_link}.",
        "tools": "Если нужен отбор инструмента, пилот и юридические ограничения по данным и ответственности, обсудите это с {assistant_link}.",
        "market": "Если хотите понять, как этот тренд влияет на ваши процессы, продукт и архитектуру Legal AI, обсудите это с {assistant_link}.",
    },
    "hard": {
        "regulation": "Если нужен проектный формат: аудит риска, регламенты, процесс и контроль качества ИИ в юрфункции, обсудите это с {assistant_link}.",
        "case": "Если готовы переходить от идеи к проекту внедрения, обсудите следующий шаг с {assistant_link}.",
        "implementation": "Если нужен проект автоматизации заявок, договорной работы или типовых юридических процессов, обсудите это с {assistant_link}.",
        "tools": "Если нужен подбор стека, интеграция и запуск пилота для юротдела, обсудите это с {assistant_link}.",
        "market": "Если хотите из этого тренда собрать полезный продукт или сервис для юридической функции, обсудите это с {assistant_link}.",
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
    "practice": "none",
    "humor": "none",
}
_MANUAL_FOOTER_LIBRARY = {
    "promo_offer": "Если хотите понять, с чего начать внедрение Legal AI под ваш кейс, обсудите это с {assistant_link}.",
    "product_review": "Если хотите сравнить такие инструменты под задачи юротдела и выбрать рабочий стек без лишних лицензий, обсудите это с {assistant_link}.",
    "case_story": "Если хотите собрать похожий сценарий автоматизации под вашу юрфункцию, обсудите это с {assistant_link}.",
    "opinion": "",
    "problem_breakdown": "Если хотите разобрать узкое место в заявках, договорах или внутренних процессах и быстро собрать пилот, обсудите это с {assistant_link}.",
    "checklist": "Если хотите адаптировать этот чек-лист под ваш юридический процесс или команду, обсудите это с {assistant_link}.",
    "faq": "Если хотите разобрать ваши вопросы по AI и юридической функции на вашем кейсе, обсудите это с {assistant_link}.",
    "announcement": "Если тема для вас актуальна и нужен понятный следующий шаг по внедрению, обсудите это с {assistant_link}.",
    "digest": "",
    "service_page": "Если хотите уточнить услугу, формат проекта и ближайший план внедрения, обсудите это с {assistant_link}.",
}
_FOOTER_BLOCK_RE = re.compile(
    r"(?:\n\n)?<b>Следующий шаг</b>\n.*?(?=(?:\n\n<b>Следующий шаг</b>|\n\n<b>Источник</b>|\n<b>Источник</b>|\n\n#|$))",
    re.DOTALL,
)
_ASSISTANT_TOKEN = "__ASSISTANT__"
_ASSISTANT_CTA_VERB_RE = re.compile(
    r"\b(?:обсудить|обсудите|разобрать|разберите|сверить|сверьте|пройти|пройдите|написать|напишите|пишите|обратиться|обратитесь)\b",
    re.IGNORECASE,
)
_CHANNEL_STYLE_HINTS = {
    "daily": "Редакционный тон: коротко, плотно, без рекламного хвоста. Это информационный пост, а не продающий.",
    "weekly_review": "Редакционный тон: обзор недели. Никакого CTA, только редакционный вывод и ощущение собранного материала.",
    "longread": "Редакционный тон: экспертный воскресный разбор. Допустим мягкий следующий шаг, но без навязчивой продажи.",
    "practice": "Редакционный тон: субботний практический формат, короткий и прикладной. CTA не нужен.",
    "humor": "Редакционный тон: субботний практический формат, короткий и прикладной. CTA не нужен.",
}
_FOOTER_DECISION_SYSTEM_PROMPT = NEWS_FOOTER_DECISION_SYSTEM_PROMPT
_DEFAULT_HASHTAGS = ["#AIVerdict", "#LegalTech", "#AI"]
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
    "не",
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
_INCOMPLETE_TITLE_END_RE = re.compile(
    r"\b(?:и|или|не|но|а|что|чтобы|потому|поэтому|если|когда|на|по|для|в|во|о|об|при|под|над|с|со|к|из|от|до|без|через)\s*$",
    re.IGNORECASE,
)
_COMPLETE_SHORT_TITLE_WORDS = {
    "дело",
    "закон",
    "итог",
    "кейс",
    "право",
    "риск",
    "роль",
    "рынок",
    "суд",
    "цена",
}
_KNOWN_TRUNCATED_TITLE_STEMS = {
    "авто",
    "дого",
    "корп",
    "рабо",
    "регу",
    "юри",
}
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
_RELEVANCE_BIAS_MARKERS = (
    "enterprise ai",
    "business ai",
    "corporate ai",
    "foundation model",
    "frontier model",
    "frontier ai",
    "reasoning model",
    "multimodal",
    "agentic",
    "ai agent",
    "copilot",
    "assistant",
    "vendor",
    "benchmark",
    "product launch",
    "platform launch",
    "platform",
    "governance",
    "compliance",
    "privacy",
    "contract",
    "legal ops",
    "автоматизац",
    "вендор",
    "закуп",
    "регулирован",
    "локализац",
    "персональн",
)
_ADOPTION_SIGNAL_MARKERS = (
    "legal ai",
    "legaltech",
    "legal ops",
    "contract automation",
    "contract review",
    "redlining",
    "workflow",
    "automation",
    "agentic",
    "copilot",
    "assistant",
    "vendor",
    "platform",
    "product launch",
    "rollout",
    "pilot",
    "enterprise ai",
    "governance",
    "privacy",
    "compliance",
    "in-house",
    "legal department",
    "юрфунк",
    "автоматизац",
    "договор",
    "вендор",
    "пилот",
    "маршрутизац",
    "procurement",
)
_DAILY_LEGAL_RUBRICS = {"ai_law", "compliance", "privacy", "contracts", "litigation", "regulation"}
_DAILY_THIRD_BLOCK_HEADINGS = (
    "Юридический контур",
    "Что это значит для юрфункции",
    "Что это значит для команд",
    "Что это значит для рынка",
    "Где это можно применить",
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
_GENERIC_ADOPTION_PATTERNS = (
    "можно использовать в работе",
    "можно использовать у себя",
    "можно внедрить в работу",
    "можно внедрить у себя",
    "можно применять в работе",
    "подходит для внедрения",
    "интересно для внедрения",
    "может быть полезно командам",
)
_PROMPT_LEAK_MARKERS = (
    "верни строго json",
    "верни только json",
    "верни только html",
    "верни только исправленный html",
    "без markdown",
    "требования:",
    "формат weekly_review",
    "формат longread",
    "формат daily",
    "формат humor",
    "структура weekly_review",
    "структура longread",
    "структура daily",
    "структура humor",
    "cta-уровень",
    "краткое содержание статьи",
    "негативных сигналов по похожим постам не найдено",
    "шаблон юридического комментария",
    "целевая смысловая корзина",
    "приоритетный юридический угол",
    "стилистика канала",
    "role\": \"system\"",
    "ты шеф-редактор telegram-канала",
)
_TEMPORAL_RECHECK_MARKERS = (
    "ожидается",
    "ожидают",
    "ожидаемый",
    "со дня на день",
    "в ближайшие дни",
    "в ближайшие недели",
    "можно ждать",
    "должна снизиться",
    "должен снизиться",
    "может снизиться",
    "может вырасти",
    "может измениться",
)
_RU_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}
_CALENDAR_WINDOW_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"в(?:о)?\s+второй\s+половине\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)", re.IGNORECASE), 16),
    (re.compile(r"к\s+концу\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)", re.IGNORECASE), 25),
    (re.compile(r"в\s+конце\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)", re.IGNORECASE), 25),
    (re.compile(r"до\s+конца\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)", re.IGNORECASE), 25),
)
_FACT_CHECK_SYSTEM_PROMPT = (
    "Ты выпускающий редактор Telegram-канала по Legal AI. "
    "Проверяешь уже написанный HTML-пост перед тем, как он попадет в review.\n"
    "1) Не добавляй новых фактов.\n"
    "2) Исправляй перепутанные роли и субъекты действия: кто сдает, кто арендует, кто покупает, кто продает, кто подал иск, кто ответчик, кто кредитор, кто заемщик.\n"
    "3) Дата итогового поста важнее исходной временной формулировки. Если в тексте остались устаревшие прогнозы, near-term ожидания или дедлайны, перепиши их в нейтральный актуальный вид или убери.\n"
    "4) Для weekly_review нельзя оставлять устаревшие прогнозы как будто они еще впереди.\n"
    "5) Сохраняй HTML-разметку Telegram и заголовки блоков.\n"
    "6) Верни строго JSON: "
    '{"approved": true, "reason": "", "title": "исправленный заголовок", "text": "исправленный HTML-пост"}'
)
_FALLBACK_SUMMARY_META_PREFIXES = (
    "собери ",
    "обязательное требование",
    "используй только",
    "сделай ",
    "тема лонгрида",
    "опирайся ",
)
_WEEKLY_META_PREFIXES = (
    "сигналы недели",
    "ключевые сигналы недели",
    "обзор недели по legal ai",
)
_RUBRIC_LEGAL_TEMPLATE_HINTS = {
    "privacy": (
        "Если материал относится к персональным данным, юридический блок должен говорить про правовое основание обработки, "
        "трансграничную передачу, локализацию, поручение обработки, права доступа к данным и режим работы с результатом."
    ),
    "contracts": (
        "Если материал относится к договорам, юридический блок должен говорить про SLA, объем допустимого использования модели, "
        "ограничения на результат, распределение ответственности, возмещение убытков, право аудита и риск зависимости от поставщика."
    ),
    "litigation": (
        "Если материал относится к спорам, юридический блок должен говорить про объяснимость, допустимость результата, "
        "цепочку хранения доказательств, сохранение документов, проверку документов человеком и контроль качества доказательственной базы."
    ),
    "regulation": (
        "Если материал относится к регулированию, юридический блок должен говорить про применимость AI Act, законов о персональных данных, "
        "классификацию риска, управление процессом, логирование, внутренний контроль, санкционные и экспортные ограничения."
    ),
    "ai_law": (
        "Если материал относится к праву ИИ, юридический блок должен говорить про права на результат, обучение на данных, "
        "интеллектуальную собственность и лицензии, автоматизированное принятие решений, роль человека, объяснимость и исполнимость."
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
        provider_fingerprint = f"{settings.openai_base_url} {self.model}".lower()
        self._use_max_tokens_param = "deepseek" in provider_fingerprint
        self._reasoning_token_reserve = (
            max(settings.news_reasoning_token_reserve, 0) if "deepseek" in provider_fingerprint else 0
        )

    @staticmethod
    def _article_haystack(article: ArticleCandidate) -> str:
        return " ".join(
            part for part in (article.title or "", article.summary or "", article.article_url or "", article.source_url or "") if part
        ).lower()

    @classmethod
    def _should_enable_adoption_module(cls, article: ArticleCandidate, pillar: str, format_type: str) -> bool:
        if format_type == "weekly_review":
            return False
        if pillar in {"implementation", "case", "tools"}:
            return True
        haystack = cls._article_haystack(article)
        if pillar == "market" and any(marker in haystack for marker in ("vendor", "platform", "assistant", "copilot", "agentic", "procurement", "product")):
            return True
        return any(marker in haystack for marker in _ADOPTION_SIGNAL_MARKERS)

    @classmethod
    def _build_writer_system_prompt(cls, *, adoption_module_enabled: bool) -> str:
        return build_news_writer_system_prompt(adoption_module_enabled=adoption_module_enabled)

    @staticmethod
    def _build_prompt_module_note(*, adoption_module_enabled: bool) -> str:
        return (
            "Активные модули для этого материала:\n"
            "- [base]: всегда включен.\n"
            + (
                "- [adoption_pattern]: включен. Если материал сам дает практический сценарий, верни adoption_fit и adoption_patterns.\n"
                if adoption_module_enabled
                else "- [adoption_pattern]: выключен. Не придумывай паттерны применения и верни adoption_fit = none, adoption_patterns = [].\n"
            )
        )

    def _token_limit_kwargs(self, token_limit: int) -> dict[str, Any]:
        token_limit += max(int(getattr(self, "_reasoning_token_reserve", 0)), 0)
        if self._use_max_tokens_param:
            return {"max_tokens": token_limit}
        return {"max_completion_tokens": token_limit}

    def _completion_kwargs(self, format_type: str) -> dict[str, Any]:
        token_limit = _FORMAT_MAX_OUTPUT_TOKENS.get(format_type, _FORMAT_MAX_OUTPUT_TOKENS["standard"])
        return self._token_limit_kwargs(token_limit)

    @staticmethod
    def _format_dt(dt: datetime | None) -> str:
        if dt is None:
            return "не указана"
        normalized = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")

    @staticmethod
    def _plain_text(text: str) -> str:
        return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).lower()

    @classmethod
    def _calendar_window_is_elapsed(cls, text: str, target_publish_at: datetime) -> bool:
        lowered = cls._plain_text(text)
        for pattern, threshold_day in _CALENDAR_WINDOW_PATTERNS:
            match = pattern.search(lowered)
            if not match:
                continue
            month_value = _RU_MONTHS.get(match.group(1).lower())
            if month_value is None:
                continue
            if month_value < target_publish_at.month:
                return True
            if month_value == target_publish_at.month and target_publish_at.day >= threshold_day:
                return True
        return False

    @classmethod
    def _temporal_guard_failure_reason(
        cls,
        text: str,
        *,
        target_publish_at: datetime | None,
        source_published_at: datetime | None,
        format_type: str,
    ) -> str | None:
        if target_publish_at is None:
            return None
        lowered = cls._plain_text(text)
        if any(marker in lowered for marker in _TEMPORAL_RECHECK_MARKERS) and source_published_at is not None:
            source_dt = source_published_at if source_published_at.tzinfo is not None else source_published_at.replace(tzinfo=UTC)
            if abs((target_publish_at.date() - source_dt.date()).days) <= 3:
                return "needs_temporal_recheck:near_term_forecast"
        if format_type == "weekly_review" and cls._calendar_window_is_elapsed(lowered, target_publish_at):
            return "needs_temporal_recheck:elapsed_calendar_window"
        return None

    def _fact_check_post(
        self,
        *,
        article: ArticleCandidate,
        title: str,
        text: str,
        format_type: str,
        target_publish_at: datetime | None,
    ) -> tuple[str, str] | None:
        prompt = (
            f"Дата публикации итогового поста: {self._format_dt(target_publish_at)}\n"
            f"Дата исходного материала: {self._format_dt(article.published_at)}\n"
            f"Формат: {format_type}\n"
            f"URL: {article.article_url}\n"
            f"Заголовок источника: {article.title}\n\n"
            f"Краткое содержание источника:\n{article.summary[:3500]}\n\n"
            f"Текущий заголовок поста:\n{title}\n\n"
            f"Текущий HTML-пост:\n{text}"
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _FACT_CHECK_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            **self._completion_kwargs(format_type),
        )
        payload = self._extract_json(response.choices[0].message.content or "")
        if payload.get("approved") is False:
            return None
        corrected_title = self._shorten_title(str(payload.get("title") or title), 110)
        corrected_text = normalize_post_text(str(payload.get("text") or text))
        return corrected_title, corrected_text

    @staticmethod
    def _allow_quality_fallback(format_type: str) -> bool:
        return format_type in {"signal", "standard", "deep", "digest"}

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
            return json.loads(text, strict=False)
        except json.JSONDecodeError:
            left = text.find("{")
            right = text.rfind("}")
            if left != -1 and right != -1 and right > left:
                return json.loads(text[left : right + 1], strict=False)
            raise

    @staticmethod
    def _helper_bot_username() -> str:
        username = settings.news_helper_bot_username.strip().lstrip("@")
        return username or "legal_ai_helper_new_bot"

    @staticmethod
    def _helper_bot_label() -> str:
        label = (settings.news_helper_bot_label or "").strip()
        return label or "Ассистент AI Verdict"

    @classmethod
    def _helper_bot_url(cls) -> str:
        return settings.news_helper_bot_url or f"https://t.me/{cls._helper_bot_username()}"

    @classmethod
    def _bot_link(cls) -> str:
        link_text = html.escape(cls._helper_bot_label())
        safe_url = html.escape(cls._helper_bot_url(), quote=True)
        return f'<a href="{safe_url}">{link_text}</a>'

    @classmethod
    def _assistant_link(cls, case: str = "nom") -> str:
        forms = {
            "nom": "Ассистент AI Verdict",
            "dat": "Ассистенту AI Verdict",
            "ins": "Ассистентом AI Verdict",
        }
        link_text = html.escape(forms.get(case, forms["nom"]))
        safe_url = html.escape(cls._helper_bot_url(), quote=True)
        return f'<a href="{safe_url}">{link_text}</a>'

    @classmethod
    def _tokenize_assistant_mentions(cls, text: str, token: str = _ASSISTANT_TOKEN) -> str:
        content = html.unescape(str(text or ""))
        helper_label = cls._helper_bot_label()
        helper_username = cls._helper_bot_username()
        helper_url = cls._helper_bot_url()
        content = re.sub(
            rf"<a\b[^>]*href=[\"'](?:{re.escape(helper_url)}|https?://t\.me/{re.escape(helper_username)})[\"'][^>]*>.*?</a>",
            token,
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(r"<[^>]+>", " ", content)
        content = re.sub(r"@legal_ai_helper_new_bot", token, content, flags=re.IGNORECASE)
        content = re.sub(rf"@{re.escape(helper_username)}", token, content, flags=re.IGNORECASE)
        content = re.sub(rf"{re.escape(helper_url)}", token, content, flags=re.IGNORECASE)
        content = re.sub(rf"https?://t\.me/{re.escape(helper_username)}", token, content, flags=re.IGNORECASE)
        content = re.sub(rf"t\.me/{re.escape(helper_username)}", token, content, flags=re.IGNORECASE)
        content = re.sub(re.escape(helper_label), token, content, flags=re.IGNORECASE)
        content = re.sub(r"асс?истент(?:ом|у|а|е)?(?:\s+AI\s+Verdict|\s+Legal\s+AI\s+Pro)?", token, content, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", content).strip()

    @classmethod
    def _trim_repeated_assistant_mentions_in_sentence(cls, sentence: str, assistant_token: str) -> str:
        if sentence.count(assistant_token) <= 1:
            return sentence
        keep_until = sentence.find(assistant_token) + len(assistant_token)
        return sentence[:keep_until].rstrip(" ,;:") + "."

    @classmethod
    def _dedupe_assistant_sentences(cls, content: str, assistant_token: str) -> str:
        raw_sentences = [part.strip() for part in re.split(r"(?<=[.!?…])\s+", content) if part.strip()]
        if len(raw_sentences) <= 1:
            return cls._trim_repeated_assistant_mentions_in_sentence(content, assistant_token)

        deduped: list[str] = []
        seen_assistant_cta = False
        for sentence in raw_sentences:
            normalized = cls._trim_repeated_assistant_mentions_in_sentence(sentence.strip(), assistant_token)
            lowered = normalized.lower()
            has_assistant = assistant_token in normalized
            is_assistant_cta = has_assistant and bool(_ASSISTANT_CTA_VERB_RE.search(lowered))
            if is_assistant_cta and seen_assistant_cta:
                continue
            if is_assistant_cta:
                seen_assistant_cta = True
            deduped.append(normalized)
        return " ".join(deduped).strip()

    @classmethod
    def _normalize_footer_token_text(cls, footer_text: str, *, require_contact: bool = True) -> str:
        content = re.sub(r"\s+", " ", (footer_text or "").strip())
        if not content:
            return ""
        content = re.sub(r"^\s*(?:следующий шаг|footer)\s*:?\s*", "", content, flags=re.IGNORECASE).strip()
        if not content:
            return ""
        content = cls._tokenize_assistant_mentions(content)
        content = cls._dedupe_assistant_sentences(content, _ASSISTANT_TOKEN)
        if require_contact and _ASSISTANT_TOKEN not in content:
            suffix = f"Обсудить это можно с {_ASSISTANT_TOKEN}."
            if content.endswith((".", "!", "?", "…")):
                content = f"{content} {suffix}"
            else:
                content = f"{content}. {suffix}" if content else suffix
        return re.sub(r"\s+", " ", content).strip()

    @classmethod
    def _finalize_footer_html(cls, footer_text: str) -> str:
        content = cls._normalize_footer_token_text(footer_text, require_contact=True)
        if not content:
            return ""

        footer_html = html.escape(content)
        footer_html = re.sub(
            rf"(?:написать|напишите|пишите|обратиться|обратитесь)\s+(?:в|через)?\s*{_ASSISTANT_TOKEN}",
            lambda _match: f"напишите {cls._assistant_link('dat')}",
            footer_html,
            flags=re.IGNORECASE,
        )
        footer_html = re.sub(
            rf"(?:обсудить|обсудите|разобрать|разберите|сверить|сверьте|пройти|пройдите)\s+(?:это\s+)?с\s+{_ASSISTANT_TOKEN}",
            lambda match: re.sub(rf"{_ASSISTANT_TOKEN}$", cls._assistant_link("ins"), match.group(0)),
            footer_html,
            flags=re.IGNORECASE,
        )
        footer_html = re.sub(
            rf"\bс\s+{_ASSISTANT_TOKEN}\b",
            f"с {cls._assistant_link('ins')}",
            footer_html,
            flags=re.IGNORECASE,
        )
        footer_html = footer_html.replace(_ASSISTANT_TOKEN, cls._assistant_link("nom"))
        return re.sub(r"\s+", " ", footer_html).strip()

    @classmethod
    def _strip_trailing_assistant_footer_fragments(cls, text: str) -> str:
        normalized = (text or "").strip()
        if not normalized:
            return ""
        source_match = re.search(r"\n{0,2}<b>Источник</b>", normalized)
        source_block = ""
        if source_match:
            source_block = normalized[source_match.start() :].lstrip()
            body = normalized[: source_match.start()].rstrip()
        else:
            body = normalized
        paragraphs = re.split(r"\n{2,}", body)
        kept = list(paragraphs)
        for index in range(len(kept) - 1, max(-1, len(kept) - 4), -1):
            tokenized = cls._tokenize_assistant_mentions(kept[index])
            if _ASSISTANT_TOKEN in tokenized and _ASSISTANT_CTA_VERB_RE.search(tokenized):
                kept.pop(index)
        result = "\n\n".join(part.strip() for part in kept if part.strip()).strip()
        if source_block:
            result = f"{result}\n\n{source_block}" if result else source_block
        return result

    @classmethod
    def normalize_post_footer_blocks(cls, text: str) -> str:
        original = (text or "").strip()
        if not original:
            return ""
        footer_matches = list(_FOOTER_BLOCK_RE.finditer(original))
        if not footer_matches:
            return normalize_post_text(cls._strip_trailing_assistant_footer_fragments(original))

        footer_block = footer_matches[-1].group(0)
        footer_text = re.sub(r"^\s*<b>Следующий шаг</b>\s*", "", footer_block.strip(), flags=re.IGNORECASE)
        base = _FOOTER_BLOCK_RE.sub("", original).strip()
        base = cls._strip_trailing_assistant_footer_fragments(base)
        footer_html = cls._finalize_footer_html(footer_text)
        if not footer_html:
            return normalize_post_text(base)
        footer = f"<b>Следующий шаг</b>\n{footer_html}"
        source_index = base.find("<b>Источник</b>")
        if source_index != -1:
            updated = f"{base[:source_index].rstrip()}\n\n{footer}\n\n{base[source_index:].lstrip()}"
        else:
            updated = f"{base.rstrip()}\n\n{footer}"
        return normalize_post_text(updated)

    @classmethod
    def _normalize_title_for_format(cls, title: str, format_type: str, fallback_title: str) -> str:
        normalized = re.sub(r"\s+", " ", (title or "").strip())
        if format_type == "longread":
            normalized = re.sub(r"^\s*(?:лонгрид|longread)\s*[:\-–—]\s*", "", normalized, flags=re.IGNORECASE)
        if format_type in {"practice", "humor"}:
            normalized = re.sub(r"^\s*(?:юмор|humor|шутка)\s*[:\-–—]\s*", "", normalized, flags=re.IGNORECASE)
        normalized = normalized.strip(" -–—:;,.")
        if not normalized:
            normalized = re.sub(r"^\s*(?:лонгрид|longread|юмор|humor|шутка)\s*[:\-–—]?\s*", "", fallback_title, flags=re.IGNORECASE).strip()
        return normalized or fallback_title

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
        return template.format(assistant_link="Ассистентом AI Verdict")

    @classmethod
    def _auto_footer_text(cls, format_type: str, cta_type: str, pillar: str) -> str:
        if format_type == "daily":
            if pillar in {"implementation", "tools", "case"}:
                return cls._cta_text(cta_type, pillar)
            return ""
        mode = _AUTO_FOOTER_MODE_BY_FORMAT.get(format_type, "soft")
        if mode == "none":
            return ""
        return cls._cta_text(cta_type, pillar)

    def _semantic_footer_html(
        self,
        *,
        title: str,
        rubric: str,
        pillar: str,
        format_type: str,
        cta_type: str,
        lead: str,
        what_happened: str,
        business_effect: str,
        legal_risks: str,
        conclusion: str,
        adoption_fit: str | None = None,
        adoption_patterns: list[str] | None = None,
    ) -> str:
        normalized_fit = (adoption_fit or "").strip().lower()
        normalized_patterns = adoption_patterns if adoption_patterns is not None else None
        if normalized_fit == "none":
            return ""
        if normalized_fit in {"weak", "strong"} and normalized_patterns == []:
            return ""
        if not hasattr(self, "client"):
            fallback = self._auto_footer_text(format_type, cta_type, pillar)
            return self._finalize_footer_html(fallback) if fallback else ""

        post_context = "\n".join(
            part for part in (
                f"Заголовок: {title}",
                f"Формат: {format_type}",
                f"Рубрика: {rubric or '—'}",
                f"Корзина: {pillar}",
                f"Lead: {lead or '—'}",
                f"Что произошло: {what_happened or '—'}",
                f"Почему важно: {business_effect or '—'}",
                f"Правовой/практический блок: {legal_risks or '—'}",
                f"Вывод: {conclusion or '—'}",
                f"Adoption fit: {normalized_fit or '—'}",
                f"Adoption patterns: {'; '.join(normalized_patterns) if normalized_patterns else '—'}",
            ) if part
        )
        completion_kwargs = self._token_limit_kwargs(260)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _FOOTER_DECISION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Оцени пост и реши, нужен ли футер по нашим услугам.\n\n"
                            f"{post_context}\n\n"
                            f"Контакт для CTA: {self._helper_bot_label()} ({self._helper_bot_url()})"
                        ),
                    },
                ],
                temperature=0.25,
                **completion_kwargs,
            )
            payload = self._extract_json(response.choices[0].message.content or "")
            include_footer = bool(payload.get("include_footer"))
            if not include_footer:
                logger.info(
                    "llm_footer_skipped_as_not_fit",
                    extra={
                        "title": title[:80],
                        "rubric": rubric[:80],
                        "format_type": format_type,
                        "reason": str(payload.get("fit_reason") or "")[:180],
                    },
                )
                return ""
            footer_text = self._sanitize_generated_field(payload.get("footer_text") or "")
            return self._finalize_footer_html(footer_text)
        except Exception as exc:
            logger.warning(
                "llm_footer_generation_failed",
                extra={"title": title[:80], "rubric": rubric[:80], "format_type": format_type, "error": str(exc)},
            )
            return ""

    @staticmethod
    def _source_block(article_url: str, format_type: str) -> str:
        safe_article_url = html.escape(article_url, quote=True)
        if article_url.startswith("internal://weekly-review"):
            return "<b>Источник</b>: внутренняя подборка сигналов недели"
        if article_url.startswith("internal://longread"):
            return "<b>Источник</b>: внутренняя подборка материалов для лонгрида"
        if article_url.startswith("internal://practice") or article_url.startswith("internal://humor"):
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
    def _sanitize_generated_field(cls, value: Any) -> str:
        raw = html.unescape(str(value or ""))
        raw = re.sub(r"<[^>]+>", " ", raw)
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines() if line.strip()]
        cleaned: list[str] = []
        for line in lines:
            lowered = line.lower()
            if any(marker in lowered for marker in _PROMPT_LEAK_MARKERS):
                continue
            if any(lowered.startswith(prefix) for prefix in _FALLBACK_SUMMARY_META_PREFIXES):
                continue
            cleaned.append(line)
        return re.sub(r"\s+", " ", " ".join(cleaned)).strip()

    @staticmethod
    def _normalize_signature(text: str) -> str:
        return re.sub(r"[^0-9a-zа-я]+", " ", text.lower()).strip()

    @classmethod
    def _dedupe_weekly_points(cls, points: list[str]) -> list[str]:
        deduped: list[str] = []
        signatures: list[str] = []
        for point in points:
            signature = cls._normalize_signature(point)
            if not signature:
                continue
            duplicate = any(
                signature == known
                or signature in known
                or known in signature
                for known in signatures
            )
            if duplicate:
                continue
            deduped.append(point)
            signatures.append(signature)
        return deduped

    @classmethod
    def _sanitize_weekly_point(cls, value: Any) -> str:
        point = cls._sanitize_generated_field(value)
        if not point:
            return ""
        point = re.sub(r"^\d+[.)]\s*", "", point)
        point = re.sub(r"^[•\-–—]\s*", "", point)
        lowered = point.lower()
        if any(lowered.startswith(prefix) for prefix in _WEEKLY_META_PREFIXES):
            point = re.sub(r"^[^:]+:\s*", "", point)
            lowered = point.lower()
        if any(lowered.startswith(prefix) for prefix in _FALLBACK_SUMMARY_META_PREFIXES):
            return ""
        if " — " in point:
            left, right = point.split(" — ", 1)
            left = left.strip(" -—:;,.")
            right = right.strip(" -—:;,.")
            if right.lower().startswith(left.lower()):
                right = right[len(left):].strip(" -—:;,.")
            point = f"{left}. {right}" if right else left
        point = re.sub(r"\s+", " ", point).strip(" -—:;,.")
        if not point or re.fullmatch(r"\d+[.)]?", point):
            return ""
        point = cls._shorten(point, 260, prefer_sentence=True) or cls._shorten(point, 260)
        point = point.strip()
        if len(point) < 24:
            return ""
        lowered_point = point.lower()
        if any(lowered_point.startswith(prefix) for prefix in _WEEKLY_META_PREFIXES):
            return ""
        last_word = re.sub(r"[^\wа-яА-Я-]+$", "", lowered_point.split()[-1]) if lowered_point.split() else ""
        if last_word in _INCOMPLETE_TRAILING_WORDS:
            return ""
        if len(point.split()) < 7:
            return ""
        if not point.endswith((".", "!", "?", "…")) and len(point.split()) >= 7:
            point = f"{point}."
        return point

    @classmethod
    def _weekly_point_headline(cls, point: str) -> str:
        sentences = cls._sentence_list(point)
        if not sentences:
            return ""
        headline = sentences[0].strip()
        if len(headline.split()) < 4:
            return ""
        if not headline.endswith((".", "!", "?", "…")):
            headline = f"{headline}."
        return headline

    @classmethod
    def _derive_weekly_points(cls, data: dict[str, Any]) -> list[str]:
        raw_points = data.get("weekly_points")
        points: list[str] = []
        if isinstance(raw_points, list):
            for item in raw_points:
                cleaned = cls._sanitize_weekly_point(item)
                cleaned = cls._weekly_point_headline(cleaned) if cleaned else ""
                if cleaned:
                    points.append(cleaned)
        points = cls._dedupe_weekly_points(points)
        if len(points) >= 8:
            return points[:10]
        joined = " ".join(
            part for part in (
                cls._sanitize_generated_field(data.get("what_happened") or ""),
                cls._sanitize_generated_field(data.get("business_effect") or ""),
                cls._sanitize_generated_field(data.get("legal_risks") or ""),
            )
            if part
        )
        derived = cls._sentence_list(joined)
        for item in derived:
            cleaned = cls._sanitize_weekly_point(item)
            cleaned = cls._weekly_point_headline(cleaned) if cleaned else ""
            if cleaned:
                points.append(cleaned)
            if len(points) >= 10:
                break
        return cls._dedupe_weekly_points(points)[:10]

    @staticmethod
    def _sanitize_summary_for_fallback(summary: str) -> str:
        raw = html.unescape(str(summary or ""))
        raw = re.sub(r"<[^>]+>", " ", raw)
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines() if line.strip()]
        cleaned: list[str] = []
        for line in lines:
            lowered = line.lower()
            meta_probe = re.sub(r"^\d+[.)]\s*", "", lowered)
            if any(meta_probe.startswith(prefix) for prefix in _FALLBACK_SUMMARY_META_PREFIXES):
                continue
            if any(marker in lowered for marker in _PROMPT_LEAK_MARKERS):
                continue
            cleaned.append(line)
        return "\n".join(cleaned).strip()

    @classmethod
    def _extract_internal_weekly_points(cls, summary: str) -> list[str]:
        points: list[str] = []
        for raw_line in str(summary or "").splitlines():
            line = raw_line.strip()
            match = re.match(r"^\d+[.)]\s*(.+)$", line)
            if not match:
                continue
            payload = cls._sanitize_weekly_point(match.group(1))
            payload = cls._weekly_point_headline(payload) if payload else ""
            if payload:
                points.append(payload)
        points = cls._dedupe_weekly_points(points)
        if len(points) >= 8:
            return points[:10]
        sentences = cls._sentence_list(cls._sanitize_summary_for_fallback(summary))
        for sentence in sentences:
            candidate = cls._sanitize_weekly_point(sentence)
            candidate = cls._weekly_point_headline(candidate) if candidate else ""
            if candidate and candidate not in points:
                points.append(candidate)
            if len(points) >= 10:
                break
        return cls._dedupe_weekly_points(points)[:10]

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

    @classmethod
    def _extract_adoption_patterns(cls, data: dict[str, Any]) -> tuple[str, list[str]]:
        fit = str(data.get("adoption_fit") or "none").strip().lower()
        if fit not in {"none", "weak", "strong"}:
            fit = "none"

        raw_patterns = data.get("adoption_patterns")
        if not isinstance(raw_patterns, list):
            return fit, []

        patterns: list[str] = []
        seen: set[str] = set()
        for item in raw_patterns[:3]:
            cleaned = cls._sanitize_generated_field(item)
            cleaned = cls._shorten(cleaned, 180, prefer_sentence=True) or cls._shorten(cleaned, 180)
            lowered = cleaned.lower().strip(" .")
            if not cleaned or len(cleaned.split()) < 5:
                continue
            if any(marker in lowered for marker in _GENERIC_ADOPTION_PATTERNS):
                continue
            signature = cls._normalize_signature(cleaned)
            if not signature or signature in seen:
                continue
            seen.add(signature)
            if not cleaned.endswith((".", "!", "?", "…")) and len(cleaned.split()) >= 6:
                cleaned = f"{cleaned}."
            patterns.append(cleaned)
        if not patterns:
            return "none", []
        return fit if fit in {"weak", "strong"} else "weak", patterns

    @staticmethod
    def _adoption_block_html(patterns: list[str]) -> str:
        if not patterns:
            return ""
        escaped = [html.escape(item) for item in patterns]
        return "\n".join(f"• {item}" for item in escaped)

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
                "трансграничную передачу, локализацию, права доступа к данным и договорный режим с поставщиком. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        if any(marker in haystack for marker in ("contract", "договор", "sla", "redlining", "vendor", "platform")):
            return (
                "Сфокусируй юридический блок на договорном контуре: SLA, ответственность поставщика, "
                "ограничения по использованию результата, конфиденциальность, право аудита и риск зависимости от поставщика. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        if any(marker in haystack for marker in ("litigation", "суд", "e-discovery", "ediscovery", "legal hold", "document review")):
            return (
                "Сфокусируй юридический блок на спорах и доказуемости: объяснимость, цепочка хранения доказательств, "
                "сохранность доказательств, фиксация документов и участие человека в проверке. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        if any(marker in haystack for marker in ("ai act", "регулирован", "compliance", "governance", "sanction", "санкц", "экспорт")):
            return (
                "Сфокусируй юридический блок на регулировании и управлении процессом: применимость AI Act / законов о персональных данных, "
                "внутренний контроль, логирование, санкционные и экспортные ограничения, распределение ответственности. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        if pillar == "market":
            return (
                "Сфокусируй третий блок на юридико-рыночных последствиях: проверка поставщика, режим закупки, "
                "санкционные ограничения, устойчивость поставщика и договорные гарантии. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        if pillar in {"implementation", "case"}:
            return (
                "Сфокусируй юридический блок на практическом внедрении: контроль качества результата, "
                "процедуры проверки юристом, конфиденциальность и распределение ответственности. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        if pillar == "tools":
            return (
                "Сфокусируй юридический блок на выборе инструмента: режим доступа к данным, SLA, "
                "права на результат, аудит действий модели и ограничения использования. "
                + cls._rubric_template_hint(inferred_rubric)
            )
        return (
            "Юридический блок должен быть предметным: укажи конкретные правовые вопросы, "
            "которые юристу придется проверить в связи с этой новостью. "
            + cls._rubric_template_hint(inferred_rubric)
        )

    @staticmethod
    def _relevance_bias_hint(article: ArticleCandidate, pillar: str) -> str:
        haystack = " ".join(
            part for part in (article.title or "", article.summary or "", article.article_url or "") if part
        ).lower()
        hits = sum(1 for marker in _RELEVANCE_BIAS_MARKERS if marker in haystack)
        if hits < 2:
            return ""
        if pillar in {"market", "tools", "implementation", "case", "regulation"}:
            return (
                "Это пограничный, но приоритетный ИИ-сигнал: если в статье есть влияние на выбор поставщика, "
                "архитектуру внедрения, корпоративные ИИ-процессы, управление, закупку, договоры, данные "
                "или автоматизацию бизнес-/юридических процессов, трактуй материал как релевантный."
            )
        return ""

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
                "поручение обработки с поставщиком, режим доступа к данным и ограничения на повторное использование результата."
            )
        if inferred_rubric == "contracts":
            return (
                "Юристу стоит проверить SLA, объем допустимого использования модели, права на результат, возмещение убытков, "
                "право аудита, распределение ответственности и риск зависимости от поставщика."
            )
        if inferred_rubric == "litigation":
            return (
                "Юристу стоит оценить объяснимость модели, допустимость результата, цепочку хранения доказательств, "
                "сохранение документов, полноту проверки документов и обязательное участие человека в спорном контуре."
            )
        if inferred_rubric == "regulation":
            return (
                "Юристу стоит проверить применимость AI Act и требований к персональным данным, классификацию риска, "
                "внутренний контур управления, логирование, санкционные и экспортные ограничения."
            )
        if inferred_rubric == "ai_law":
            return (
                "Юристу стоит проверить права на результат и обучающие данные, лицензионный режим модели, "
                "границы автоматизированного принятия решений, объяснимость, проверку человеком и исполнимость решений."
            )
        if any(marker in haystack for marker in ("персональн", "privacy", "gdpr", "локализац", "трансгранич")):
            return (
                "Юристу стоит проверить правовое основание обработки данных, трансграничную передачу, "
                "локализацию, режим доступа к данным и договорные ограничения на использование модели."
            )
        if any(marker in haystack for marker in ("contract", "договор", "sla", "redlining", "vendor", "platform")):
            return (
                "Юристу стоит проверить SLA, распределение ответственности поставщика, права на результат, "
                "режим конфиденциальности, право аудита и риск зависимости от поставщика."
            )
        if any(marker in haystack for marker in ("litigation", "суд", "e-discovery", "ediscovery", "legal hold", "document review")):
            return (
                "Юристу стоит оценить объяснимость, порядок проверки модели, сохранность цепочки доказательств, "
                "полноту фиксации документов и обязательное участие человека при работе со спором."
            )
        if rubric in _DAILY_LEGAL_RUBRICS or any(marker in haystack for marker in ("ai act", "регулирован", "compliance", "governance", "sanction", "санкц", "экспорт")):
            return (
                "Юристу стоит проверить применимость AI Act и требований к персональным данным, внутренний контур управления, "
                "логирование, контроль качества результата и распределение ответственности между бизнесом и поставщиком."
            )
        if pillar == "market":
            return (
                "Для юрфункции здесь важны проверка поставщика, санкционные и экспортные ограничения, "
                "режим закупки, договорные гарантии и устойчивость поставщика в критичных сценариях."
            )
        if pillar == "tools":
            return (
                "Юристу стоит проверить режим доступа к данным, ограничения использования результата, "
                "SLA, конфиденциальность и право на аудит действий модели."
            )
        return (
            "Юристу стоит проверить договорный режим использования инструмента, контур данных, "
            "контроль качества результата и распределение ответственности при внедрении."
        )

    def _format_post(
        self,
        data: dict[str, Any],
        article_url: str,
        fallback_title: str,
        format_type: str,
        cta_type: str,
        pillar: str,
        intelligent_footer_enabled: bool = True,
    ) -> tuple[str, str, str]:
        limits = _FORMAT_FIELD_LIMITS.get(format_type, _FORMAT_FIELD_LIMITS["standard"])
        raw_title = self._sanitize_generated_field(data.get("title") or fallback_title)
        title = self._shorten_title(self._normalize_title_for_format(raw_title, format_type, fallback_title), 110)
        default_rubric = _DEFAULT_RUBRIC_BY_PILLAR.get(pillar, "legal_ai")
        rubric = self._shorten(self._sanitize_generated_field(data.get("rubric") or default_rubric), 100)
        what_happened = self._shorten(
            self._sanitize_generated_field(data.get("what_happened") or ""),
            limits["what"],
            prefer_sentence=True,
        )
        business_effect = self._shorten(
            self._sanitize_generated_field(data.get("business_effect") or ""),
            limits["effect"],
            prefer_sentence=True,
        )
        legal_risks = self._shorten(
            self._sanitize_generated_field(data.get("legal_risks") or ""),
            limits["risks"],
            prefer_sentence=True,
        )
        next_steps_raw = data.get("next_steps") or ""
        hashtags_value = data.get("hashtags")

        steps: list[str] = []
        for part in str(next_steps_raw).split(";"):
            cleaned_part = self._sanitize_generated_field(part)
            cleaned = self._shorten(cleaned_part, limits["step"], prefer_sentence=True) or self._shorten(
                cleaned_part,
                limits["step"],
            )
            if cleaned and not cleaned.endswith((".", "!", "?", "…")) and len(cleaned.split()) >= 6:
                cleaned = f"{cleaned}."
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
            what_happened or "В статье описан новый кейс внедрения ИИ с конкретными операционными деталями."
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
        lead = self._shorten(self._sanitize_generated_field(data.get("lead") or ""), 260, prefer_sentence=True)
        escaped_lead = html.escape(lead)
        conclusion = self._shorten(
            self._sanitize_generated_field(data.get("conclusion") or ""),
            320,
            prefer_sentence=True,
        )
        escaped_conclusion = html.escape(conclusion)
        adoption_fit, adoption_patterns = self._extract_adoption_patterns(data)
        adoption_block = self._adoption_block_html(adoption_patterns)
        cta_line = ""
        if intelligent_footer_enabled:
            cta_line = self._semantic_footer_html(
                title=title,
                rubric=rubric,
                pillar=pillar,
                format_type=format_type,
                cta_type=cta_type,
                lead=lead,
                what_happened=what_happened,
                business_effect=business_effect,
                legal_risks=legal_risks,
                conclusion=conclusion,
                adoption_fit=adoption_fit,
                adoption_patterns=adoption_patterns,
            )
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
                + (f"<b>Где это можно применить</b>\n{adoption_block}\n\n" if adoption_block else "")
                + f"<b>Риски и ограничения</b>\n{escaped_legal_risks}\n\n"
                + f"<b>Что делать</b>\n{steps_block}\n\n"
                + (f"<b>Вывод</b>\n{escaped_conclusion}\n\n" if escaped_conclusion else "")
                + f"{next_step_block}"
                + f"{source_block}\n"
                + f"{hashtags_line}"
            )
        elif format_type in {"practice", "humor"}:
            body = (
                f"<b>{escaped_title}</b>\n\n"
                + (f"{escaped_lead}\n\n" if escaped_lead else "")
                + f"<b>Ситуация недели</b>\n{escaped_what_happened}\n\n"
                + f"<b>Где узкое место</b>\n{escaped_business_effect}\n\n"
                + f"<b>Что взять в работу</b>\n{steps_block}\n\n"
                + f"{source_block}\n"
                + f"{hashtags_line}"
            )
        elif format_type == "daily":
            if adoption_block:
                daily_heading, daily_body = "Где это можно применить", adoption_block
            else:
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
                + (f"<b>Где это можно применить</b>\n{adoption_block}\n\n" if adoption_block else "")
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
    def _plain_text_for_language_gate(text: str) -> str:
        plain = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
        plain = re.sub(r"https?://\S+", " ", plain)
        plain = re.sub(r"\b(?:Источник|AIVerdict|LegalTech|Legal AI|AI)\b", " ", plain, flags=re.IGNORECASE)
        lines = []
        for line in plain.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.lower().startswith("источник"):
                continue
            lines.append(stripped)
        return re.sub(r"\s+", " ", " ".join(lines)).strip()

    @classmethod
    def _language_gate_failure_reason(cls, text: str) -> str | None:
        plain = cls._plain_text_for_language_gate(text)
        if not plain:
            return "language_empty"

        title_match = re.search(r"<b>\s*(.*?)\s*</b>", text or "", flags=re.IGNORECASE | re.DOTALL)
        title = html.unescape(re.sub(r"<[^>]+>", " ", title_match.group(1))).strip() if title_match else plain[:180]
        if title and not re.search(r"[А-Яа-яЁё]", title):
            return "language_title_not_russian"

        cyrillic_count = len(re.findall(r"[А-Яа-яЁё]", plain))
        latin_count = len(re.findall(r"[A-Za-z]", plain))
        if latin_count > max(cyrillic_count * 1.25, cyrillic_count + 80):
            return f"language_latin_dominant:{latin_count}>{cyrillic_count}"
        return None

    @staticmethod
    def _title_gate_failure_reason(text: str) -> str | None:
        title_match = re.search(r"<b>\s*(.*?)\s*</b>", text or "", flags=re.IGNORECASE | re.DOTALL)
        if title_match is None:
            return "missing_title"
        title = html.unescape(re.sub(r"<[^>]+>", " ", title_match.group(1)))
        title = re.sub(r"\s+", " ", title).strip(" ,;:-")
        if not title:
            return "missing_title"
        if _INCOMPLETE_TITLE_END_RE.search(title):
            return "incomplete_title"
        last_word_match = re.search(r"([А-Яа-яЁё-]+)$", title)
        if last_word_match is not None:
            last_word = last_word_match.group(1).lower().replace("ё", "е")
            body = html.unescape(re.sub(r"<[^>]+>", " ", (text or "")[title_match.end():])).lower()
            exact_word = re.search(rf"\b{re.escape(last_word)}\b", body)
            longer_word = re.search(rf"\b{re.escape(last_word)}[а-яё]{{2,}}\b", body)
            suspicious_stem = last_word in _KNOWN_TRUNCATED_TITLE_STEMS or (
                len(last_word) >= 7 and last_word.endswith("н")
            )
            if (
                suspicious_stem
                and last_word not in _COMPLETE_SHORT_TITLE_WORDS
                and exact_word is None
                and longer_word is not None
            ):
                return "incomplete_title_word"
        return None

    @staticmethod
    def _quality_gate_failure_reason(text: str, format_type: str) -> str | None:
        normalized = (text or "").strip()
        plain_lower = html.unescape(re.sub(r"<[^>]+>", "", normalized)).lower()
        for marker in _PROMPT_LEAK_MARKERS:
            if marker in plain_lower:
                return f"prompt_leak:{marker}"
        if "&lt;" in normalized or "&gt;" in normalized:
            return "escaped_markup"
        title_failure = LLMNewsWriter._title_gate_failure_reason(normalized)
        if title_failure:
            return title_failure
        if plain_lower.count("(") != plain_lower.count(")"):
            return "unbalanced_parentheses"
        if plain_lower.count("«") != plain_lower.count("»"):
            return "unbalanced_quotes"
        format_markers = {
            "weekly_review": ("Ключевые сигналы недели", "Что это значит для юрфункции", "На что смотреть юристам", "Что проверить у себя", "Источник"),
            "longread": ("Контекст", "Практический смысл", "Риски и ограничения", "Что делать", "Источник"),
            "daily": ("Что произошло", "Почему это важно", "Источник"),
            "practice": ("Ситуация недели", "Где узкое место", "Что взять в работу", "Источник"),
            "humor": ("Ситуация недели", "Где узкое место", "Что взять в работу", "Источник"),
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
        if format_type == "weekly_review":
            raw_points = re.findall(r"(?m)^\s*\d+\.\s*(.+)$", normalized)
            points_count = len(raw_points)
            if points_count < 8:
                return f"weak_weekly_points:{points_count}"
            cleaned_points = [
                point for point in (LLMNewsWriter._sanitize_weekly_point(item) for item in raw_points)
                if point
            ]
            if len(cleaned_points) < 8:
                return f"weak_weekly_points_clean:{len(cleaned_points)}"
            if len(LLMNewsWriter._dedupe_weekly_points(cleaned_points)) < 8:
                return "weak_weekly_points_duplicates"
        language_failure = LLMNewsWriter._language_gate_failure_reason(normalized)
        if language_failure:
            return language_failure
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
            "6) Для weekly_review оставь 8-10 пунктов без дублей и без служебных фраз.\n"
            "7) Не оставляй в тексте HTML-эскейпы (&lt; и &gt;).\n"
            "8) Верни только исправленный HTML, без пояснений.\n\n"
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

    def _fallback_post(
        self,
        article: ArticleCandidate,
        format_type: str,
        cta_type: str,
        pillar: str,
        *,
        intelligent_footer_enabled: bool = True,
    ) -> dict[str, str]:
        title = self._shorten(article.title or "Обзор новости", 110)
        summary_raw = self._sanitize_summary_for_fallback(article.summary)
        summary = self._shorten(summary_raw, 1300, prefer_sentence=True)
        summary = summary or "Источник сообщил о новом кейсе внедрения ИИ в юридическом процессе."
        business_effect = "Кейс показывает, как сократить ручную работу и повысить скорость обработки типовых задач."
        legal_risks = "Юристу стоит заранее проверить обработку персональных данных, договорную ответственность поставщика, требования к логированию и контроль качества результата."
        conclusion = ""
        if pillar == "market":
            business_effect = "Это сигнал о том, что вокруг крупных поставщиков ИИ усиливается рыночный, политический и регуляторный контур."
            conclusion = "Дальше стоит смотреть, как это повлияет на выбор поставщиков, закупки и корпоративные стратегии внедрения ИИ."
        elif pillar == "tools":
            business_effect = "Новость показывает, как меняется контур выбора ИИ-инструментов и требований к поставщикам со стороны корпоративных команд."
            conclusion = "Дальше важны не общие обещания поставщика, а режим доступа к данным, качество результата и договорные ограничения."
        elif pillar in {"implementation", "case"}:
            conclusion = (
                "Практический вывод: до пилота нужно зафиксировать процесс, входные данные, владельца проверки "
                "и метрику результата. Если это нельзя описать заранее, внедрение рано масштабировать."
            )
        base: dict[str, Any] = {
            "title": title,
            "rubric": _DEFAULT_RUBRIC_BY_PILLAR.get(pillar, "legal_ai"),
            "what_happened": summary[:450],
            "business_effect": business_effect,
            "legal_risks": legal_risks,
            "next_steps": (
                "Описать процесс и данные в нем; проверить персональные данные и договорные ограничения; "
                "выбрать 1-2 этапа для пилота; согласовать критерии качества и контроля"
            ),
            "conclusion": conclusion,
            "hashtags": list(_DEFAULT_HASHTAGS),
        }
        if format_type == "weekly_review":
            weekly_points = self._extract_internal_weekly_points(summary_raw)
            weekly_points.extend(
                [
                    "Команды все чаще считают KPI не по количеству ИИ-функций, а по скорости прохождения юридического цикла, качеству исходящих документов и снижению операционных ошибок на повторяющихся задачах.",
                    "Выбор ИИ-поставщика смещается в сторону прозрачности процессов, управляемости данных, стабильности SLA и готовности поставщика подтверждать контроль качества результата в критичных сценариях.",
                    "Роль юриста усиливается в точках контроля качества результата, настройки правил эскалации и принятия финального решения там, где цена ошибки для бизнеса выше среднего.",
                    "Внедрение переходит из режима «тест инструмента» в режим «операционная система юрфункции», где важны регламенты, метрики, ответственность и предсказуемость результата.",
                    "Рынок показывает, что без связки юридических операций, персональных данных, управления процессом и контрактного контура даже сильный ИИ-инструмент не дает стабильного эффекта в рабочем режиме.",
                    "Команды, которые заранее фиксируют участие человека в проверке и регламенты контроля результата, быстрее масштабируют Legal AI без роста операционных и правовых инцидентов.",
                    "Бизнес-клиенты ожидают от юрфункции не экспериментов с инструментами, а стабильного SLA по срокам договорной и претензионной работы с прозрачной ответственностью.",
                    "Пилоты с четкими метриками, ответственными ролями и аудитом качества показывают лучший эффект, чем внедрения без формализованного контура управления.",
                ]
            )
            weekly_points = self._dedupe_weekly_points(weekly_points)
            base.update(
                {
                    "lead": (
                        "Неделя показала, что рынок Legal AI ускоряется, но устойчивый результат получают только команды, "
                        "которые одновременно управляют процессом, риском и качеством юридического результата. "
                        "Ключевой сдвиг: от отдельных экспериментов к системной модели работы юрфункции."
                    ),
                    "weekly_points": weekly_points[:10],
                    "what_happened": (
                        "За неделю проявилось несколько устойчивых сигналов на стыке Legal AI, автоматизации процессов и требований к управлению рисками. "
                        "Во многих кейсах фокус сместился с «демо-возможностей» на практические вопросы масштабирования, интеграции в процессы и управляемости качества."
                    ),
                    "business_effect": (
                        "Для юрфункции это означает переход от точечных экспериментов к операционной модели, "
                        "где важны скорость цикла, качество проверки, предсказуемость результата и экономическая эффективность на длинной дистанции. "
                        "Бизнес ожидает не просто автоматизации шага, а устойчивого сокращения срока обработки обращений, договоров и внутренних запросов."
                    ),
                    "legal_risks": (
                        "Юристу важно заранее определить контур данных, договорные ограничения, ответственность поставщика, "
                        "режим логирования и контроль качества результата в критичных сценариях. "
                        "Отдельный акцент нужен на правах на данные и результат, трансграничной передаче, зависимости от поставщика, "
                        "праве аудита и понятной модели эскалации при ошибках системы."
                    ),
                    "next_steps": (
                        "Переоценить приоритеты автоматизации на ближайший квартал и выбрать 2-3 процесса с максимальным эффектом; "
                        "зафиксировать критерии качества, SLA и метрики для каждого этапа; "
                        "обновить договорный контур, контур персональных данных и контур управления до запуска масштабного потока; "
                        "назначить ответственные роли за проверку результата и эскалацию юридических рисков"
                    ),
                    "conclusion": (
                        "Главный вывод недели: эффект дает не отдельная модель, а связка процессов, юридического контроля и "
                        "дисциплины внедрения. На следующем витке выиграют команды, которые строят воспроизводимый контур работы, "
                        "а не зависят от единичных ручных экспериментов."
                    ),
                }
            )
        _, text, rubric = self._format_post(
            base,
            article.article_url,
            title,
            format_type=format_type,
            cta_type=cta_type,
            pillar=pillar,
            intelligent_footer_enabled=intelligent_footer_enabled,
        )
        if format_type == "weekly_review" and len(text) < _FORMAT_MIN_CHARS["weekly_review"]:
            booster_block = (
                "<b>Фокус следующей недели</b>\n"
                "Приоритетом становится не количество ИИ-инструментов, а управляемость процесса: "
                "кто отвечает за качество результата, как устроена эскалация спорных кейсов, где фиксируются отклонения и "
                "как команда доказывает воспроизводимость результата при росте нагрузки. "
                "Именно эта дисциплина отделяет устойчивые внедрения от красивых, но краткоживущих пилотов."
            )
            marker = "\n\n<b>Источник</b>"
            if marker in text:
                text = text.replace(marker, f"\n\n{booster_block}{marker}", 1)
            else:
                text = normalize_post_text(f"{text}\n\n{booster_block}")
        return {"title": title, "text": text, "rubric": rubric}

    def _fallback_post_checked(
        self,
        article: ArticleCandidate,
        *,
        format_type: str,
        cta_type: str,
        pillar: str,
        intelligent_footer_enabled: bool = True,
    ) -> dict[str, str] | None:
        fallback = self._fallback_post(
            article,
            format_type=format_type,
            cta_type=cta_type,
            pillar=pillar,
            intelligent_footer_enabled=intelligent_footer_enabled,
        )
        failure_reason = self._quality_gate_failure_reason(fallback.get("text", ""), format_type)
        if failure_reason:
            logger.warning(
                "fallback_post_failed_quality_gate",
                extra={
                    "article_url": article.article_url,
                    "format_type": format_type,
                    "reason": failure_reason,
                },
            )
            return None
        return fallback

    def generate_post(
        self,
        article: ArticleCandidate,
        rag_examples: list[RAGExample],
        format_type: str = "standard",
        cta_type: str = "soft",
        pillar: str = "implementation",
        negative_feedback_context: str = "",
        target_publish_at: datetime | None = None,
        intelligent_footer_enabled: bool = True,
    ) -> dict[str, str] | None:
        format_hint = _FORMAT_HINTS.get(format_type, _FORMAT_HINTS["standard"])
        inferred_rubric = self._infer_rubric_hint(article, pillar)
        relevance_bias_hint = self._relevance_bias_hint(article, pillar)
        adoption_module_enabled = self._should_enable_adoption_module(article, pillar, format_type)
        system_prompt = self._build_writer_system_prompt(adoption_module_enabled=adoption_module_enabled)
        user_prompt = (
            f"Источник: {article.source_url}\n"
            f"URL статьи: {article.article_url}\n"
            f"Заголовок: {article.title}\n"
            f"Дата публикации: {article.published_at.isoformat() if article.published_at else 'не указана'}\n\n"
            f"Дата публикации итогового поста: {target_publish_at.isoformat() if target_publish_at else 'не указана'}\n"
            "Временной режим: считай дату публикации итогового поста главной. Не переноси в текст устаревшие прогнозы и ближайшие ожидания как будто они еще впереди.\n\n"
            f"{self._build_prompt_module_note(adoption_module_enabled=adoption_module_enabled)}\n"
            f"Целевая смысловая корзина: {pillar}\n"
            f"Предполагаемая рубрика: {inferred_rubric}\n"
            f"Стилистика канала: {self._style_hint(format_type)}\n"
            f"Приоритетный юридический угол: {self._infer_legal_focus_hint(article, pillar)}\n"
            f"{relevance_bias_hint}\n"
            f"Шаблон юридического комментария для этой рубрики: {self._rubric_template_hint(inferred_rubric)}\n"
            f"{format_hint}\n"
            f"{_FORMAT_SHAPE_HINTS.get(format_type, '')}\n"
            f"CTA-уровень: {cta_type}\n\n"
            f"Краткое содержание статьи:\n{article.summary[:3000]}\n\n"
            f"{self._build_context(rag_examples)}\n\n"
            f"{negative_feedback_context or 'Негативных сигналов по похожим постам не найдено.'}"
        )

        raw = ""
        for attempt in range(3):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.35,
                **self._completion_kwargs(format_type),
            )
            raw = response.choices[0].message.content or ""
            try:
                self._extract_json(raw)
                break
            except Exception as parse_exc:
                logger.warning(
                    "llm_post_parse_retry",
                    extra={"attempt": attempt + 1, "error": str(parse_exc), "format_type": format_type},
                )
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
                intelligent_footer_enabled=intelligent_footer_enabled,
            )
            fact_checked = self._fact_check_post(
                article=article,
                title=title,
                text=text,
                format_type=format_type,
                target_publish_at=target_publish_at,
            )
            if fact_checked is None:
                logger.info(
                    "llm_post_rejected_by_fact_check",
                    extra={"title": title[:80], "format_type": format_type, "article_url": article.article_url},
                )
                return None
            title, text = fact_checked
            temporal_failure = self._temporal_guard_failure_reason(
                text,
                target_publish_at=target_publish_at,
                source_published_at=article.published_at,
                format_type=format_type,
            )
            if temporal_failure is not None:
                logger.info(
                    "llm_post_rejected_by_temporal_guard",
                    extra={
                        "title": title[:80],
                        "format_type": format_type,
                        "article_url": article.article_url,
                        "reason": temporal_failure,
                    },
                )
                return None
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
                    if format_type == "weekly_review":
                        fallback_weekly = self._fallback_post(
                            article,
                            format_type=format_type,
                            cta_type=cta_type,
                            pillar=pillar,
                            intelligent_footer_enabled=intelligent_footer_enabled,
                        )
                        if self._passes_quality_gate(fallback_weekly.get("text", ""), format_type):
                            logger.info(
                                "llm_weekly_replaced_with_fallback",
                                extra={"title": title[:80], "rubric": rubric, "format_type": format_type},
                            )
                            return fallback_weekly
                    logger.info(
                        "llm_post_discarded_after_quality_gate",
                        extra={"title": title[:80], "rubric": rubric, "format_type": format_type},
                    )
                    return None
                return self._fallback_post_checked(
                    article,
                    format_type=format_type,
                    cta_type=cta_type,
                    pillar=pillar,
                    intelligent_footer_enabled=intelligent_footer_enabled,
                )
            logger.info("llm_post_generated", extra={"title": title[:80], "rubric": rubric, "format_type": format_type})
            return {"title": title[:160], "text": text, "rubric": rubric[:100]}
        except Exception as exc:
            logger.warning("llm_post_parse_failed", extra={"error": str(exc), "format_type": format_type})
            return self._fallback_post_checked(
                article,
                format_type=format_type,
                cta_type=cta_type,
                pillar=pillar,
                intelligent_footer_enabled=intelligent_footer_enabled,
            )

    def fallback_post(
        self,
        article: ArticleCandidate,
        *,
        format_type: str = "standard",
        cta_type: str = "soft",
        pillar: str = "implementation",
        intelligent_footer_enabled: bool = True,
    ) -> dict[str, str]:
        """Build a fallback only when it passes the same public quality gate."""
        fallback = self._fallback_post_checked(
            article,
            format_type=format_type,
            cta_type=cta_type,
            pillar=pillar,
            intelligent_footer_enabled=intelligent_footer_enabled,
        )
        if fallback is None:
            raise RuntimeError("fallback_post_failed_quality_gate")
        return fallback

def build_manual_footer(post_kind: str) -> str:
    template = _MANUAL_FOOTER_LIBRARY.get(post_kind)
    if not template:
        return ""
    return template.format(assistant_link="Ассистентом AI Verdict")


def compose_manual_post_html(title: str, body: str, post_kind: str, *, footer_text: str | None = None) -> str:
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
    footer = (footer_text or "").strip() if footer_text is not None else build_manual_footer(post_kind)
    parts = [f"<b>{normalized_title}</b>"]
    if body_html:
        parts.append(body_html)
    if footer:
        parts.append(f"<b>Следующий шаг</b>\n{LLMNewsWriter._finalize_footer_html(footer)}")
    return normalize_post_text("\n\n".join(part for part in parts if part))
