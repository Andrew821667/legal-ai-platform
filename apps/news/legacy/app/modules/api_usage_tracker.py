"""
API Usage Tracking Module
Отслеживание использования и стоимости OpenAI/Perplexity API.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import APIUsage, MonthlyAPIStats
import structlog

logger = structlog.get_logger()


# Стоимость за 1M токенов в USD (актуально на январь 2025)
PRICING = {
    "openai": {
        "gpt-4o": {
            "prompt": 2.50,      # $2.50 per 1M prompt tokens
            "completion": 10.00  # $10.00 per 1M completion tokens
        },
        "gpt-4o-mini": {
            "prompt": 0.150,     # $0.15 per 1M prompt tokens
            "completion": 0.600  # $0.60 per 1M completion tokens
        },
        "gpt-4": {
            "prompt": 30.00,
            "completion": 60.00
        },
        "gpt-3.5-turbo": {
            "prompt": 0.50,
            "completion": 1.50
        }
    },
    "perplexity": {
        "sonar": {
            "prompt": 0.20,      # $0.20 per 1M tokens (примерная цена)
            "completion": 0.20   # Flat rate
        },
        "llama-3.1-sonar-large-128k-online": {
            "prompt": 1.00,
            "completion": 1.00
        }
    },
    "deepseek": {
        "deepseek-chat": {
            "prompt": 0.27,      # $0.27 per 1M input tokens
            "completion": 1.10   # $1.10 per 1M output tokens
        },
        "deepseek-reasoner": {
            "prompt": 0.55,      # $0.55 per 1M input tokens
            "completion": 2.19   # $2.19 per 1M output tokens
        }
    }
}


def calculate_cost(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int
) -> Decimal:
    """
    Рассчитать стоимость API запроса в USD.

    Args:
        provider: openai или perplexity
        model: Название модели
        prompt_tokens: Количество токенов в промпте
        completion_tokens: Количество токенов в ответе

    Returns:
        Стоимость в USD
    """
    if provider not in PRICING:
        logger.warning(f"Unknown provider: {provider}")
        return Decimal("0.0")

    if model not in PRICING[provider]:
        # Пытаемся найти похожую модель (например, gpt-4o-mini-2024-07-18 → gpt-4o-mini)
        for known_model in PRICING[provider]:
            if known_model in model:
                model = known_model
                break
        else:
            logger.warning(f"Unknown model: {model} for provider {provider}")
            return Decimal("0.0")

    pricing = PRICING[provider][model]

    # Стоимость = (prompt_tokens / 1_000_000) * prompt_price + (completion_tokens / 1_000_000) * completion_price
    prompt_cost = Decimal(str(prompt_tokens)) / Decimal("1000000") * Decimal(str(pricing["prompt"]))
    completion_cost = Decimal(str(completion_tokens)) / Decimal("1000000") * Decimal(str(pricing["completion"]))

    total_cost = prompt_cost + completion_cost

    logger.debug(
        "api_cost_calculated",
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=float(total_cost)
    )

    return total_cost


async def track_api_usage(
    db: AsyncSession,
    provider: str,
    model: str,
    operation: str,
    prompt_tokens: int,
    completion_tokens: int,
    article_id: Optional[int] = None,
    draft_id: Optional[int] = None
) -> APIUsage:
    """
    Записать использование API в БД.

    Args:
        db: Сессия БД
        provider: openai или perplexity
        model: Название модели
        operation: Тип операции (ranking, draft_generation, etc)
        prompt_tokens: Токены промпта
        completion_tokens: Токены ответа
        article_id: ID статьи (опционально)
        draft_id: ID драфта (опционально)

    Returns:
        Созданная запись APIUsage
    """
    total_tokens = prompt_tokens + completion_tokens
    cost_usd = calculate_cost(provider, model, prompt_tokens, completion_tokens)

    usage = APIUsage(
        provider=provider,
        model=model,
        operation=operation,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        article_id=article_id,
        draft_id=draft_id,
        date=datetime.utcnow().date()
    )

    db.add(usage)
    await db.commit()

    logger.info(
        "api_usage_tracked",
        provider=provider,
        model=model,
        operation=operation,
        total_tokens=total_tokens,
        cost_usd=float(cost_usd)
    )

    # Обновляем месячную статистику
    await update_monthly_stats(db, provider, cost_usd, total_tokens)

    return usage


async def update_monthly_stats(
    db: AsyncSession,
    provider: str,
    cost_usd: Decimal,
    tokens: int
):
    """Обновить агрегированную статистику за текущий месяц."""
    now = datetime.utcnow()
    year = now.year
    month = now.month

    # Ищем существующую запись
    result = await db.execute(
        select(MonthlyAPIStats).where(
            MonthlyAPIStats.year == year,
            MonthlyAPIStats.month == month,
            MonthlyAPIStats.provider == provider
        )
    )
    stats = result.scalar_one_or_none()

    if stats:
        # Обновляем существующую
        stats.total_requests += 1
        stats.total_tokens += tokens
        stats.total_cost_usd += cost_usd
        stats.updated_at = datetime.utcnow()
    else:
        # Создаем новую
        stats = MonthlyAPIStats(
            year=year,
            month=month,
            provider=provider,
            total_requests=1,
            total_tokens=tokens,
            total_cost_usd=cost_usd
        )
        db.add(stats)

    await db.commit()


async def get_current_month_cost(db: AsyncSession) -> Dict[str, Any]:
    """
    Получить стоимость API за текущий месяц.

    Returns:
        Dict с детальной статистикой по провайдерам
    """
    now = datetime.utcnow()
    year = now.year
    month = now.month

    # Получаем статистику за текущий месяц
    result = await db.execute(
        select(MonthlyAPIStats).where(
            MonthlyAPIStats.year == year,
            MonthlyAPIStats.month == month
        )
    )
    stats = result.scalars().all()

    # Формируем ответ
    total_cost = Decimal("0.0")
    total_tokens = 0
    total_requests = 0
    by_provider = {}

    for stat in stats:
        total_cost += stat.total_cost_usd
        total_tokens += stat.total_tokens
        total_requests += stat.total_requests

        by_provider[stat.provider] = {
            "cost_usd": float(stat.total_cost_usd),
            "tokens": stat.total_tokens,
            "requests": stat.total_requests
        }

    return {
        "year": year,
        "month": month,
        "month_name": datetime(year, month, 1).strftime("%B %Y"),
        "total_cost_usd": float(total_cost),
        "total_tokens": total_tokens,
        "total_requests": total_requests,
        "by_provider": by_provider
    }


async def get_daily_cost(db: AsyncSession, days: int = 7) -> Dict[str, Any]:
    """
    Получить стоимость за последние N дней.

    Args:
        db: Сессия БД
        days: Количество дней назад

    Returns:
        Статистика по дням
    """
    # Группируем по дате и считаем суммы
    result = await db.execute(
        select(
            APIUsage.date,
            APIUsage.provider,
            func.sum(APIUsage.total_tokens).label("tokens"),
            func.sum(APIUsage.cost_usd).label("cost"),
            func.count(APIUsage.id).label("requests")
        ).where(
            APIUsage.date >= datetime.utcnow().date() - timedelta(days=days)
        ).group_by(
            APIUsage.date,
            APIUsage.provider
        ).order_by(
            APIUsage.date.desc()
        )
    )

    daily_stats = {}
    for row in result:
        date_str = row.date.strftime("%Y-%m-%d")
        if date_str not in daily_stats:
            daily_stats[date_str] = {
                "total_cost": 0.0,
                "total_tokens": 0,
                "by_provider": {}
            }

        daily_stats[date_str]["total_cost"] += float(row.cost)
        daily_stats[date_str]["total_tokens"] += row.tokens
        daily_stats[date_str]["by_provider"][row.provider] = {
            "cost_usd": float(row.cost),
            "tokens": row.tokens,
            "requests": row.requests
        }

    return daily_stats


from datetime import timedelta
