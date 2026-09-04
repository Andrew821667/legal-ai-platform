"""Общий вызов языковой модели.

Вынесен из разбора обращений, когда к модели добавился второй потребитель —
помощник, ведущий диалог с клиентом. Держать здесь две копии обращения к
вендору было бы приглашением к расхождению: прокси, обработка ошибок и учёт
стоимости должны меняться в одном месте.

Прямой доступ к вендору с боевого хоста закрыт по региону, поэтому запрос
идёт через локальный прокси — тот же, что используется для Telegram.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Цены за миллион токенов: ввод, вывод. Вынесены сюда, чтобы правка тарифов не
# требовала изменения логики; актуальные значения — на странице тарифов вендора.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-5.6-sol": (4.00, 20.00),
    "gpt-5.6-luna": (4.00, 20.00),
    "gpt-5.5-pro": (5.00, 30.00),
    "gpt-6-astra": (10.00, 50.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}

DEFAULT_MODEL = "gpt-5.6-sol"


@dataclass
class ChatResult:
    """Ответ модели вместе со стоимостью обращения."""

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


def chat(
    messages: list[dict[str, str]],
    *,
    api_key: str,
    base_url: str = "https://api.openai.com/v1",
    model: str = DEFAULT_MODEL,
    proxy_url: str | None = None,
    timeout: float = 90.0,
    max_output_tokens: int = 900,
    response_format: dict | None = None,
) -> ChatResult:
    """Обращение к модели.

    Исключения не выпускают наружу: у обоих потребителей сбой модели не должен
    ломать основной сценарий. Ошибка возвращается полем error, а вызывающая
    сторона решает, чем её заменить.
    """
    if not api_key:
        return ChatResult(text="", model=model, error="api_key_missing")

    request_body: dict[str, object] = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_output_tokens,
    }
    if response_format is not None:
        request_body["response_format"] = response_format

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

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
        logger.warning("model_http_error", extra={"status": exc.code})
        return ChatResult(text="", model=model, error=f"http_{exc.code}: {detail[:80]}")
    except Exception as exc:  # noqa: BLE001 — сбой модели не критичен для сценария
        logger.warning("model_call_failed", extra={"error": type(exc).__name__})
        return ChatResult(text="", model=model, error=type(exc).__name__)

    if "error" in body:
        message = str(body["error"].get("message", ""))[:120]
        return ChatResult(text="", model=model, error=f"api_error: {message}")

    choices = body.get("choices") or []
    text = (choices[0].get("message", {}).get("content") or "").strip() if choices else ""
    usage = body.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    used_model = str(body.get("model") or model)

    return ChatResult(
        text=text,
        model=used_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=estimate_cost(used_model, prompt_tokens, completion_tokens),
        meta={"latency_ms": int((time.monotonic() - started) * 1000)},
    )
