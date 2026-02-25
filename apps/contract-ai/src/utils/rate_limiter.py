# -*- coding: utf-8 -*-
"""
Rate Limiter - Защита от превышения лимитов LLM API

Функции:
- Ограничение частоты вызовов API (requests per minute)
- Ограничение общей стоимости (cost per hour/day)
- Ограничение токенов (tokens per minute)
- Thread-safe реализация
"""
import time
import threading
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from collections import deque
from loguru import logger


class RateLimitExceeded(Exception):
    """Исключение при превышении rate limit"""
    pass


class RateLimiter:
    """
    Rate limiter с поддержкой нескольких лимитов

    Пример использования:
        limiter = RateLimiter(
            # Global limits
            requests_per_minute=600,
            tokens_per_minute=500000,
            cost_per_hour=1.0
        )

        with limiter.acquire(tokens=1000, cost=0.001):
            # Выполнить API запрос
            pass
    """

    def __init__(
        self,
        requests_per_minute: Optional[int] = None,
        tokens_per_minute: Optional[int] = None,
        cost_per_hour: Optional[float] = None,
        cost_per_day: Optional[float] = None
    ):
        """
        Инициализация rate limiter

        Args:
            requests_per_minute: Максимум запросов в минуту
            tokens_per_minute: Максимум токенов в минуту
            cost_per_hour: Максимальная стоимость в час (USD)
            cost_per_day: Максимальная стоимость в день (USD)
        """
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.cost_per_hour = cost_per_hour
        self.cost_per_day = cost_per_day

        # Deques для хранения временных меток
        self.request_times: deque = deque()
        self.token_usage: deque = deque()  # (timestamp, tokens)
        self.hourly_costs: deque = deque()  # (timestamp, cost)
        self.daily_costs: deque = deque()  # (timestamp, cost)

        # Thread safety
        self.lock = threading.Lock()

        # Статистика
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.start_time = datetime.now()

        logger.info(
            f"Rate limiter initialized: "
            f"RPM={requests_per_minute}, "
            f"TPM={tokens_per_minute}, "
            f"$/hour={cost_per_hour}, "
            f"$/day={cost_per_day}"
        )

    def _cleanup_old_entries(self, queue: deque, max_age_seconds: int) -> None:
        """Удалить старые записи из deque"""
        cutoff_time = time.time() - max_age_seconds

        while queue and queue[0][0] < cutoff_time:
            queue.popleft()

    def _check_request_limit(self) -> None:
        """Проверить лимит запросов в минуту"""
        if self.requests_per_minute is None:
            return

        # Очистить старые записи (старше 1 минуты)
        self._cleanup_old_entries(self.request_times, 60)

        # Проверить лимит
        if len(self.request_times) >= self.requests_per_minute:
            oldest_time = self.request_times[0][0]
            wait_time = 60 - (time.time() - oldest_time)

            raise RateLimitExceeded(
                f"Request rate limit exceeded: {self.requests_per_minute} RPM. "
                f"Please wait {wait_time:.1f} seconds."
            )

    def _check_token_limit(self, tokens: int) -> None:
        """Проверить лимит токенов в минуту"""
        if self.tokens_per_minute is None:
            return

        # Очистить старые записи
        self._cleanup_old_entries(self.token_usage, 60)

        # Подсчитать токены за последнюю минуту
        current_tokens = sum(t[1] for t in self.token_usage)

        if current_tokens + tokens > self.tokens_per_minute:
            raise RateLimitExceeded(
                f"Token rate limit exceeded: {self.tokens_per_minute} TPM. "
                f"Current: {current_tokens}, requested: {tokens}"
            )

    def _check_cost_limit(self, cost: float) -> None:
        """Проверить лимиты стоимости"""
        now = time.time()

        # Проверить hourly limit
        if self.cost_per_hour is not None:
            self._cleanup_old_entries(self.hourly_costs, 3600)  # 1 час
            current_hourly_cost = sum(c[1] for c in self.hourly_costs)

            if current_hourly_cost + cost > self.cost_per_hour:
                raise RateLimitExceeded(
                    f"Hourly cost limit exceeded: ${self.cost_per_hour:.2f}/hour. "
                    f"Current: ${current_hourly_cost:.4f}, requested: ${cost:.4f}"
                )

        # Проверить daily limit
        if self.cost_per_day is not None:
            self._cleanup_old_entries(self.daily_costs, 86400)  # 24 часа
            current_daily_cost = sum(c[1] for c in self.daily_costs)

            if current_daily_cost + cost > self.cost_per_day:
                raise RateLimitExceeded(
                    f"Daily cost limit exceeded: ${self.cost_per_day:.2f}/day. "
                    f"Current: ${current_daily_cost:.4f}, requested: ${cost:.4f}"
                )

    def acquire(self, tokens: int = 0, cost: float = 0.0) -> 'RateLimiterContext':
        """
        Получить разрешение на выполнение запроса

        Args:
            tokens: Количество токенов для запроса
            cost: Стоимость запроса в USD

        Returns:
            Context manager для использования в with statement

        Raises:
            RateLimitExceeded: Если превышен какой-либо лимит
        """
        return RateLimiterContext(self, tokens, cost)

    def _record_usage(self, tokens: int, cost: float) -> None:
        """Записать использование ресурсов"""
        now = time.time()

        with self.lock:
            # Проверить все лимиты
            self._check_request_limit()
            self._check_token_limit(tokens)
            self._check_cost_limit(cost)

            # Записать использование
            self.request_times.append((now, 1))

            if tokens > 0:
                self.token_usage.append((now, tokens))

            if cost > 0:
                self.hourly_costs.append((now, cost))
                self.daily_costs.append((now, cost))

            # Обновить статистику
            self.total_requests += 1
            self.total_tokens += tokens
            self.total_cost += cost

            logger.debug(
                f"Rate limiter usage recorded: "
                f"tokens={tokens}, cost=${cost:.4f}, "
                f"total_requests={self.total_requests}"
            )

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику использования"""
        with self.lock:
            runtime = (datetime.now() - self.start_time).total_seconds()

            # Очистить старые записи
            self._cleanup_old_entries(self.request_times, 60)
            self._cleanup_old_entries(self.token_usage, 60)
            self._cleanup_old_entries(self.hourly_costs, 3600)
            self._cleanup_old_entries(self.daily_costs, 86400)

            # Подсчитать текущее использование
            current_rpm = len(self.request_times)
            current_tpm = sum(t[1] for t in self.token_usage)
            current_hourly_cost = sum(c[1] for c in self.hourly_costs)
            current_daily_cost = sum(c[1] for c in self.daily_costs)

            return {
                # Текущее использование
                'current_rpm': current_rpm,
                'current_tpm': current_tpm,
                'current_hourly_cost': current_hourly_cost,
                'current_daily_cost': current_daily_cost,

                # Лимиты
                'limit_rpm': self.requests_per_minute,
                'limit_tpm': self.tokens_per_minute,
                'limit_hourly_cost': self.cost_per_hour,
                'limit_daily_cost': self.cost_per_day,

                # Использование в процентах
                'rpm_usage_pct': (current_rpm / self.requests_per_minute * 100) if self.requests_per_minute else 0,
                'tpm_usage_pct': (current_tpm / self.tokens_per_minute * 100) if self.tokens_per_minute else 0,
                'hourly_cost_usage_pct': (current_hourly_cost / self.cost_per_hour * 100) if self.cost_per_hour else 0,
                'daily_cost_usage_pct': (current_daily_cost / self.cost_per_day * 100) if self.cost_per_day else 0,

                # Общая статистика
                'total_requests': self.total_requests,
                'total_tokens': self.total_tokens,
                'total_cost': self.total_cost,
                'runtime_seconds': runtime,
                'avg_rps': self.total_requests / runtime if runtime > 0 else 0,
            }

    def reset_stats(self) -> None:
        """Сбросить статистику"""
        with self.lock:
            self.request_times.clear()
            self.token_usage.clear()
            self.hourly_costs.clear()
            self.daily_costs.clear()

            self.total_requests = 0
            self.total_tokens = 0
            self.total_cost = 0.0
            self.start_time = datetime.now()

            logger.info("Rate limiter stats reset")


class RateLimiterContext:
    """Context manager для rate limiter"""

    def __init__(self, limiter: RateLimiter, tokens: int, cost: float):
        self.limiter = limiter
        self.tokens = tokens
        self.cost = cost

    def __enter__(self):
        """Проверить лимиты и записать использование"""
        self.limiter._record_usage(self.tokens, self.cost)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup (если нужно)"""
        pass


# Глобальный rate limiter (можно настроить через settings)
_global_limiter: Optional[RateLimiter] = None


def get_global_rate_limiter() -> RateLimiter:
    """Получить глобальный rate limiter"""
    global _global_limiter

    if _global_limiter is None:
        # Создать с дефолтными лимитами
        from config.settings import settings

        _global_limiter = RateLimiter(
            requests_per_minute=60,  # Консервативный лимит
            tokens_per_minute=100000,  # gpt-4o-mini: 200k TPM, берём 50%
            cost_per_hour=5.0,  # $5/час максимум
            cost_per_day=50.0  # $50/день максимум
        )

    return _global_limiter


def set_global_rate_limiter(limiter: RateLimiter) -> None:
    """Установить глобальный rate limiter"""
    global _global_limiter
    _global_limiter = limiter


__all__ = [
    'RateLimiter',
    'RateLimitExceeded',
    'get_global_rate_limiter',
    'set_global_rate_limiter',
]
