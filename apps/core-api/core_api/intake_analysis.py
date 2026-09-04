"""Разбор юридического обращения языковой моделью.

Обращения приходят короткими: клиент описывает ситуацию в двух-трёх фразах.
Задача разбора — не заменить юриста, а подготовить его работу: назвать область
права, отметить срочность, перечислить недостающие документы и вопросы,
которые стоит задать.

Модель намеренно не даёт правовых оценок и не советует, что делать. Такой
вывод был бы консультацией, ответственность за которую несёт юрист, а не
машина. Границы заданы в системном промпте и проверяются тестами.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Цены за миллион токенов. Вынесены сюда, чтобы правка тарифов не требовала
# изменения логики; актуальные значения — на странице тарифов вендора.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-5.6-sol": (4.00, 20.00),
    "gpt-5.6-luna": (4.00, 20.00),
    "gpt-5.5-pro": (5.00, 30.00),
    "gpt-6-astra": (10.00, 50.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}

DEFAULT_MODEL = "gpt-5.6-sol"

SYSTEM_PROMPT = (
    "Ты — помощник юридической практики AI Verdict. Ты готовишь материал для юриста "
    "по обращению клиента.\n\n"
    "Сделай краткий разбор по структуре:\n"
    "1. Суть обращения — одно-два предложения своими словами.\n"
    "2. Область права.\n"
    "3. Срочность и почему: есть ли признаки горящих сроков.\n"
    "4. Каких документов не хватает для полноценного разбора.\n"
    "5. Два-три уточняющих вопроса клиенту.\n"
    "6. На что юристу обратить внимание в первую очередь.\n\n"
    "Строгие ограничения:\n"
    "— не давай правовых оценок и не предсказывай исход дела;\n"
    "— не советуй клиенту, что делать;\n"
    "— не называй конкретные статьи и суммы, если их нет в обращении;\n"
    "— если данных мало, так и напиши, а не достраивай ситуацию догадками.\n\n"
    "Пиши по-русски, деловым языком, без канцелярита и без воды."
)


@dataclass
class AnalysisResult:
    """Итог разбора: текст для юриста и стоимость обращения к модели."""

    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    error: str | None = None
    meta: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text)


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Стоимость запроса в долларах по тарифам модели."""
    price_in, price_out = MODEL_PRICING.get(model, (0.0, 0.0))
    return (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000


def format_cost(value: float) -> str:
    """Стоимость с пятью знаками после запятой — суммы здесь очень малы."""
    return f"${value:.5f}"


def _build_prompt(intake: dict[str, object]) -> str:
    parts = [f"Описание: {intake.get('description') or 'не указано'}"]
    for label, key in (
        ("Тип клиента", "client_type"),
        ("Область", "legal_area"),
        ("Срочность", "urgency"),
        ("Срок", "deadline"),
        ("Регион", "region"),
    ):
        value = intake.get(key)
        if value:
            parts.append(f"{label}: {value}")
    return "\n".join(parts)


def analyze_intake(
    intake: dict[str, object],
    *,
    api_key: str,
    base_url: str = "https://api.openai.com/v1",
    model: str = DEFAULT_MODEL,
    proxy_url: str | None = None,
    timeout: float = 90.0,
    max_output_tokens: int = 900,
) -> AnalysisResult:
    """Отправляет обращение модели и возвращает разбор со стоимостью.

    Сбой разбора не должен ломать приём обращения: при любой ошибке
    возвращается результат с заполненным error, а вызывающая сторона просто
    отправляет уведомление без аналитики.
    """
    if not api_key:
        return AnalysisResult(text="", model=model, error="api_key_missing")

    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_prompt(intake)},
            ],
            "max_completion_tokens": max_output_tokens,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    # Прямой доступ к вендору с production-хоста закрыт по региону, поэтому
    # запрос идёт через локальный прокси — тот же, что используется для Telegram.
    if proxy_url:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )
    else:
        opener = urllib.request.build_opener()

    started = time.monotonic()
    try:
        with opener.open(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:200] if exc.fp else ""
        logger.warning("intake_analysis_http_error", extra={"status": exc.code})
        return AnalysisResult(text="", model=model, error=f"http_{exc.code}: {detail[:80]}")
    except Exception as exc:  # noqa: BLE001 — разбор не критичен для приёма обращения
        logger.warning("intake_analysis_failed", extra={"error": type(exc).__name__})
        return AnalysisResult(text="", model=model, error=type(exc).__name__)

    if "error" in body:
        message = str(body["error"].get("message", ""))[:120]
        return AnalysisResult(text="", model=model, error=f"api_error: {message}")

    choices = body.get("choices") or []
    text = (choices[0].get("message", {}).get("content") or "").strip() if choices else ""
    usage = body.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    used_model = str(body.get("model") or model)

    return AnalysisResult(
        text=text,
        model=used_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=estimate_cost(used_model, prompt_tokens, completion_tokens),
        meta={"latency_ms": int((time.monotonic() - started) * 1000)},
    )
