"""
LLM Provider module
Unified interface for different LLM providers (OpenAI, Perplexity).
"""

from typing import Dict, List, Optional, Tuple
from openai import AsyncOpenAI
import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = structlog.get_logger()


class LLMProvider:
    """Unified LLM provider interface."""

    def __init__(self, provider: str = None):
        """
        Initialize LLM provider.

        Args:
            provider: Provider name ('openai', 'perplexity', or 'deepseek').
                     If None, uses default from settings.
        """
        self.provider = provider or settings.default_llm_provider
        self._openai_client = None
        self._deepseek_client = None

    async def _track_usage_safe(
        self,
        *,
        db: Optional[AsyncSession],
        provider: str,
        model: str,
        operation: str,
        prompt_tokens: int,
        completion_tokens: int,
        article_id: Optional[int] = None,
        draft_id: Optional[int] = None,
    ) -> None:
        """Track API usage without breaking user-facing generation on legacy DB drift."""
        if db is None:
            return

        try:
            from app.modules.api_usage_tracker import track_api_usage

            await track_api_usage(
                db=db,
                provider=provider,
                model=model,
                operation=operation,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                article_id=article_id,
                draft_id=draft_id,
            )
        except Exception as exc:
            logger.warning(
                "api_usage_tracking_skipped",
                provider=provider,
                model=model,
                operation=operation,
                error=str(exc),
            )
            try:
                await db.rollback()
            except Exception:
                logger.warning("api_usage_tracking_rollback_failed", provider=provider, operation=operation)

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        operation: str = "completion",
        db: Optional[AsyncSession] = None,
        article_id: Optional[int] = None,
        draft_id: Optional[int] = None
    ) -> str:
        """
        Generate completion using selected provider.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Temperature for generation (default from settings)
            max_tokens: Max tokens (default from settings)
            operation: Operation type for tracking (ranking, draft_generation, etc)
            db: Database session for usage tracking (optional)
            article_id: Article ID for tracking (optional)
            draft_id: Draft ID for tracking (optional)

        Returns:
            Generated text
        """
        if self.provider == "openai":
            return await self._generate_openai(messages, temperature, max_tokens, operation, db, article_id, draft_id)
        elif self.provider == "perplexity":
            return await self._generate_perplexity(messages, temperature, max_tokens, operation, db, article_id, draft_id)
        elif self.provider == "deepseek":
            return await self._generate_deepseek(messages, temperature, max_tokens, operation, db, article_id, draft_id)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _generate_openai(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        operation: str = "completion",
        db: Optional[AsyncSession] = None,
        article_id: Optional[int] = None,
        draft_id: Optional[int] = None
    ) -> str:
        """Generate completion using OpenAI API."""
        if self._openai_client is None:
            client_kwargs = {"api_key": settings.openai_api_key}
            if settings.openai_base_url_normalized:
                client_kwargs["base_url"] = settings.openai_base_url_normalized
            self._openai_client = AsyncOpenAI(**client_kwargs)

        model_name = settings.resolved_openai_model_analysis

        try:
            response = await self._openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature or settings.openai_temperature,
                max_tokens=max_tokens or settings.openai_max_tokens
            )

            result = response.choices[0].message.content.strip()

            await self._track_usage_safe(
                db=db,
                provider="openai",
                model=model_name,
                operation=operation,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                article_id=article_id,
                draft_id=draft_id,
            )

            logger.info("openai_completion_generated",
                       model=model_name,
                       tokens=response.usage.total_tokens)
            return result

        except Exception as e:
            logger.error("openai_generation_error", error=str(e))
            raise

    async def _generate_perplexity(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        operation: str = "completion",
        db: Optional[AsyncSession] = None,
        article_id: Optional[int] = None,
        draft_id: Optional[int] = None
    ) -> str:
        """Generate completion using Perplexity API."""
        url = "https://api.perplexity.ai/chat/completions"

        headers = {
            "Authorization": f"Bearer {settings.perplexity_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": settings.perplexity_model,
            "messages": messages,
            "temperature": temperature or settings.perplexity_temperature,
            "max_tokens": max_tokens or settings.perplexity_max_tokens
        }

        try:
            logger.info("perplexity_request",
                       model=payload["model"],
                       messages_count=len(messages),
                       temperature=payload["temperature"],
                       max_tokens=payload["max_tokens"])

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=60.0)

                # Логируем детали ответа перед проверкой статуса
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error("perplexity_api_error",
                               status_code=response.status_code,
                               error=error_detail,
                               payload=payload)

                response.raise_for_status()

                data = response.json()
                result = data["choices"][0]["message"]["content"].strip()

                usage = data.get("usage", {})
                if usage:
                    await self._track_usage_safe(
                        db=db,
                        provider="perplexity",
                        model=settings.perplexity_model,
                        operation=operation,
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        article_id=article_id,
                        draft_id=draft_id,
                    )

                logger.info("perplexity_completion_generated",
                           model=settings.perplexity_model,
                           tokens=usage.get("total_tokens"))
                return result

        except httpx.HTTPStatusError as e:
            # Автоматический fallback на OpenAI при ошибках авторизации или rate limit
            if e.response.status_code in [401, 429]:
                logger.warning("perplexity_fallback_to_openai",
                             status_code=e.response.status_code,
                             reason="API key issue or rate limit - automatically switching to OpenAI",
                             error=str(e))
                # Используем OpenAI как fallback
                return await self._generate_openai(messages, temperature, max_tokens, operation, db, article_id, draft_id)
            else:
                logger.error("perplexity_http_error",
                            status_code=e.response.status_code,
                            error=str(e),
                            response_text=e.response.text)
                raise
        except httpx.TimeoutException as e:
            logger.warning("perplexity_timeout_fallback",
                         error=str(e),
                         reason="Timeout - automatically switching to OpenAI")
            # Fallback на OpenAI при timeout
            return await self._generate_openai(messages, temperature, max_tokens, operation, db, article_id, draft_id)
        except Exception as e:
            logger.error("perplexity_generation_error", error=str(e))
            raise

    async def _generate_deepseek(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        operation: str = "completion",
        db: Optional[AsyncSession] = None,
        article_id: Optional[int] = None,
        draft_id: Optional[int] = None
    ) -> str:
        """Generate completion using DeepSeek API (OpenAI-compatible)."""
        if self._deepseek_client is None:
            api_key = settings.resolved_deepseek_api_key
            if not api_key:
                raise RuntimeError("DeepSeek API key is not configured")
            self._deepseek_client = AsyncOpenAI(
                api_key=api_key,
                base_url=settings.resolved_deepseek_base_url
            )

        model_name = settings.resolved_deepseek_model

        try:
            response = await self._deepseek_client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature or settings.deepseek_temperature,
                max_tokens=max_tokens or settings.deepseek_max_tokens
            )

            result = response.choices[0].message.content.strip()

            await self._track_usage_safe(
                db=db,
                provider="deepseek",
                model=model_name,
                operation=operation,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                article_id=article_id,
                draft_id=draft_id,
            )

            logger.info("deepseek_completion_generated",
                       model=model_name,
                       tokens=response.usage.total_tokens)
            return result

        except Exception as e:
            logger.error("deepseek_generation_error", error=str(e))
            # Fallback на OpenAI при ошибках
            logger.warning("deepseek_fallback_to_openai", reason="DeepSeek API error")
            return await self._generate_openai(messages, temperature, max_tokens, operation, db, article_id, draft_id)


# Global LLM provider instance
_llm_provider = None


def get_llm_provider(provider: str = None) -> LLMProvider:
    """
    Get LLM provider instance.

    Args:
        provider: Provider name or None for default

    Returns:
        LLMProvider instance
    """
    global _llm_provider
    if _llm_provider is None or (provider and _llm_provider.provider != provider):
        _llm_provider = LLMProvider(provider)
    return _llm_provider
