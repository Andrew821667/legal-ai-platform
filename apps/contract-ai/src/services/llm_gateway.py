"""
LLM Gateway - Единая точка доступа ко всем LLM провайдерам
Поддержка: Claude, GPT-4, Perplexity, YandexGPT, DeepSeek, Qwen
"""
import json
import hashlib
from typing import Dict, Any, Literal, Optional, Union
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
from datetime import datetime

from config.settings import settings
from ..utils.rate_limiter import get_global_rate_limiter, RateLimitExceeded


class LLMGateway:
    """Unified gateway for all LLM providers"""

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        """
        =8F80;870F8O gateway

        Args:
            provider: 0720=85 ?@>20945@0 8;8 None 4;O 8A?>;L7>20=8O default
        """
        self.provider = provider or settings.default_llm_provider
        self._client = None
        self._initialize_client()
        self.model = model
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Rate limiting
        self.use_rate_limiter = True
        self.rate_limiter = get_global_rate_limiter()

    def _initialize_client(self):
        """Инициализирует клиента для выбранного провайдера"""
        if self.provider == "claude":
            from anthropic import Anthropic
            self._client = Anthropic(api_key=settings.anthropic_api_key)

        elif self.provider == "openai":
            from openai import OpenAI
            self._client = OpenAI(api_key=settings.openai_api_key)

        elif self.provider == "perplexity":
            from openai import OpenAI
            self._client = OpenAI(
                api_key=settings.perplexity_api_key,
                base_url="https://api.perplexity.ai"
            )

        elif self.provider == "yandex":
            from yandex_cloud_ml_sdk import YCloudML
            self._client = YCloudML(
                folder_id=settings.yandex_folder_id,
                auth=settings.yandex_api_key
            )

        elif self.provider == "deepseek":
            from openai import OpenAI
            self._client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url="https://api.deepseek.com"
            )

        elif self.provider == "qwen":
            import dashscope
            dashscope.api_key = settings.qwen_api_key
            self._client = dashscope

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        logger.info(f"LLM Gateway initialized with provider: {self.provider}")

    def _generate_cache_key(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int, response_format: str) -> str:
        """Генерирует хэш-ключ для кэширования"""
        cache_string = f"{self.provider}:{self.model}:{prompt}:{system_prompt}:{temperature}:{max_tokens}:{response_format}"
        return hashlib.sha256(cache_string.encode('utf-8')).hexdigest()

    def _get_from_cache(self, cache_key: str, db_session=None) -> Optional[str]:
        """Получает ответ из кэша"""
        if not db_session:
            return None
        
        try:
            from src.models.database import LLMCache
            cached = db_session.query(LLMCache).filter(
                LLMCache.prompt_hash == cache_key
            ).first()
            
            if cached:
                # Update hit count and last accessed
                cached.hit_count += 1
                cached.last_accessed = datetime.utcnow()
                db_session.commit()
                
                logger.info(f"Cache HIT: {cache_key[:16]}... (hits: {cached.hit_count})")
                return cached.response
            
            return None
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
            return None

    def _save_to_cache(self, cache_key: str, prompt: str, system_prompt: Optional[str], response: str, 
                      temperature: float, max_tokens: int, response_format: str, 
                      input_tokens: int, output_tokens: int, cost: float, db_session=None):
        """Сохраняет ответ в кэш"""
        if not db_session:
            return
        
        try:
            from src.models.database import LLMCache
            
            cache_entry = LLMCache(
                prompt_hash=cache_key,
                provider=self.provider,
                model=self.model or "gpt-4o-mini",
                prompt=prompt[:5000],  # Limit to 5000 chars
                system_prompt=system_prompt[:2000] if system_prompt else None,
                response=response[:10000] if isinstance(response, str) else json.dumps(response)[:10000],
                response_format=response_format,
                temperature=temperature,
                max_tokens=max_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                hit_count=0
            )
            
            db_session.add(cache_entry)
            db_session.commit()
            logger.info(f"Cache SAVE: {cache_key[:16]}...")
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")
            db_session.rollback()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Literal["text", "json"] = "text",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_cache: bool = True,
        db_session = None,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """
        Универсальный вызов LLM

        Args:
            prompt: "5:AB 70?@>A0
            system_prompt: !8AB5<=K9 ?@><?B (>?F8>=0;L=>)
            response_format: $>@<0B >B25B0: "text" 8;8 "json"
            temperature: "5<?5@0BC@0 35=5@0F88
            max_tokens: 0:A8<0;L=>5 :>;8G5AB2> B>:5=>2
            **kwargs: >?>;=8B5;L=K5 ?0@0<5B@K 4;O :>=:@5B=>3> ?@>20945@0

        Returns:
            str 8;8 dict 2 7028A8<>AB8 >B response_format
        """
        temperature = temperature if temperature is not None else settings.llm_temperature
        max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens

        logger.debug(f"LLM call to {self.provider}: prompt_length={len(prompt)}")

        # Check cache first
        if use_cache and db_session:
            cache_key = self._generate_cache_key(prompt, system_prompt, temperature, max_tokens, response_format)
            cached_response = self._get_from_cache(cache_key, db_session)
            if cached_response:
                # Parse if JSON format
                if response_format == "json":
                    try:
                        return json.loads(cached_response)
                    except:
                        pass
                return cached_response

        # Rate limiting check
        estimated_tokens = len(prompt) // 4 + (len(system_prompt) // 4 if system_prompt else 0) + max_tokens
        estimated_cost = self._estimate_cost(estimated_tokens)

        if self.use_rate_limiter and self.rate_limiter:
            try:
                # Acquire rate limit (will raise exception if exceeded)
                with self.rate_limiter.acquire(tokens=estimated_tokens, cost=estimated_cost):
                    # Make API call within rate limit context
                    response = self._make_api_call(prompt, system_prompt, temperature, max_tokens, **kwargs)
            except RateLimitExceeded as e:
                logger.error(f"Rate limit exceeded: {e}")
                raise
        else:
            # No rate limiting
            response = self._make_api_call(prompt, system_prompt, temperature, max_tokens, **kwargs)

            # Парсинг JSON если требуется
            if response_format == "json":
                try:
                    # Clean markdown code blocks if present
                    cleaned_response = response.strip()

                    # Remove markdown code fences
                    if cleaned_response.startswith("```"):
                        lines = cleaned_response.split('\n')
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].strip() == "```":
                            lines = lines[:-1]
                        cleaned_response = '\n'.join(lines).strip()

                    return json.loads(cleaned_response)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.error(f"Raw response: {response[:500]}")

                    # Попытка извлечь JSON из текста
                    import re
                    json_match = re.search(r'(\[.*\]|\{.*\})', response, re.DOTALL)
                    if json_match:
                        try:
                            logger.info("Attempting to extract JSON from text response...")
                            return json.loads(json_match.group(1))
                        except:
                            pass

                    raise ValueError(f"LLM returned invalid JSON. Response starts with: {response[:200]}")

            return response

        return response

    def _make_api_call(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int, **kwargs) -> str:
        """Execute actual API call to LLM provider"""
        if self.provider == "claude":
            return self._call_claude(prompt, system_prompt, temperature, max_tokens, **kwargs)
        elif self.provider in ["openai", "perplexity", "deepseek"]:
            return self._call_openai_compatible(prompt, system_prompt, temperature, max_tokens, **kwargs)
        elif self.provider == "yandex":
            return self._call_yandex(prompt, system_prompt, temperature, max_tokens, **kwargs)
    def _estimate_cost(self, tokens: int) -> float:
        """Estimate cost based on tokens (rough approximation)"""
        model = self.model or "gpt-4o-mini"
        pricing = settings.llm_pricing.get(model, {"input": 0.15, "output": 0.60})

        # Assume 60% input, 40% output split
        input_tokens = int(tokens * 0.6)
        output_tokens = int(tokens * 0.4)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def _call_claude(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int, **kwargs) -> str:
        """Вызов Claude API"""
        messages = [{"role": "user", "content": prompt}]

        params = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages
        }

        if system_prompt:
            params["system"] = system_prompt

        response = self._client.messages.create(**params)
        return response.content[0].text

    def _call_openai_compatible(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int, **kwargs) -> str:
        """Вызов OpenAI-совместимого API (OpenAI, Perplexity, DeepSeek)"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        # >45;L 2 7028A8<>AB8 >B ?@>20945@0
        # Используем модель из self.model, если она указана
        if self.model:
            model = self.model
        elif self.provider == "openai":
            model = "gpt-4o-mini"  # По умолчанию дешёвая модель
        elif self.provider == "perplexity":
            model = "llama-3.1-sonar-large-128k-online"
        elif self.provider == "deepseek":
            model = "deepseek-chat"
        else:
            model = "gpt-4"

        logger.info(f"🔍 DEBUG: API call with model = {model}, self.model = {self.model}")
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Отслеживаем использование токенов
        if hasattr(response, 'usage'):
            self.total_input_tokens += response.usage.prompt_tokens
            self.total_output_tokens += response.usage.completion_tokens
            logger.debug(f"Tokens used: {response.usage.prompt_tokens} input, {response.usage.completion_tokens} output")

        return response.choices[0].message.content

    def _call_yandex(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int, **kwargs) -> str:
        """Вызов YandexGPT API"""
        model = self._client.models.completions("yandexgpt")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "text": system_prompt})
        messages.append({"role": "user", "text": prompt})

        result = model.configure(temperature=temperature).run(messages)

        # 72;5:05< B5:AB 87 @57C;LB0B0
        for alternative in result:
            return alternative.text

        return ""

    def _call_qwen(self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int, **kwargs) -> str:
        """K7>2 Qwen API (Alibaba Cloud)"""
        from dashscope import Generation

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = Generation.call(
            model="qwen-max",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            result_format='message'
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            raise Exception(f"Qwen API error: {response.message}")

    def count_tokens(self, text: str) -> int:
        """
        >4AGQB B>:5=>2 (?@81;878B5;L=K9)

        Args:
            text: "5:AB 4;O ?>4AGQB0

        Returns:
            @8<5@=>5 :>;8G5AB2> B>:5=>2
        """
        # @>AB0O M2@8AB8:0: ~4 A8<2>;0 = 1 B>:5= 4;O @CAA:>3> O7K:0
        return len(text) // 4


    def get_token_stats(self) -> Dict[str, Any]:
        """
        Статистика использования токенов

        Returns:
            Словарь с информацией о токенах и стоимости
        """
        # Определяем текущую модель
        current_model = self.model or "gpt-4o-mini"
        
        # Получаем цены из настроек
        pricing = settings.llm_pricing.get(current_model, {"input": 0, "output": 0})
        
        # Расчёт стоимости (цена за 1M токенов)
        input_cost = (self.total_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.total_output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd": round(total_cost, 6),
            "model": current_model
        }

    def reset_token_stats(self):
        """Сбросить счётчик токенов"""
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def get_provider_info(self) -> Dict[str, Any]:
        """
        =D>@<0F8O > B5:CI5< ?@>20945@5

        Returns:
            !;>20@L A 8=D>@<0F859 > ?@>20945@5
        """
        return {
            "provider": self.provider,
            "available": self._client is not None,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens
        }


# Utility DC=:F88 4;O 8A?>;L7>20=8O 2 4@C38E <>4C;OE
def llm_call(
    prompt: str,
    provider: Optional[str] = None,
    system_prompt: Optional[str] = None,
    response_format: Literal["text", "json"] = "text",
    **kwargs
) -> Union[str, Dict[str, Any]]:
    """
    KAB@K9 2K7>2 LLM 157 A>740=8O M:75<?;O@0 gateway

    Args:
        prompt: "5:AB 70?@>A0
        provider: @>20945@ (None 4;O default)
        system_prompt: !8AB5<=K9 ?@><?B
        response_format: $>@<0B >B25B0
        **kwargs: >?>;=8B5;L=K5 ?0@0<5B@K

    Returns:
        B25B LLM
    """
    gateway = LLMGateway(provider=provider)
    return gateway.call(
        prompt=prompt,
        system_prompt=system_prompt,
        response_format=response_format,
        **kwargs
    )


__all__ = ["LLMGateway", "llm_call"]
