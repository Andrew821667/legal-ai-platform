# -*- coding: utf-8 -*-
"""
Async API Client - Asynchronous HTTP client for external APIs

Преимущества:
- Параллельные запросы к внешним API
- Значительное ускорение batch операций
- Connection pooling
- Automatic retry logic
- Timeout management
"""
import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional, Callable
from loguru import logger


class AsyncAPIClient:
    """
    Asynchronous HTTP client for external API calls

    Features:
    - Parallel requests with connection pooling
    - Automatic retries with exponential backoff
    - Timeout management
    - Response caching support
    - Rate limiting
    """

    def __init__(
        self,
        timeout: int = 30,
        max_connections: int = 100,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rate_limit_requests: Optional[int] = None,
        rate_limit_period: float = 1.0
    ):
        """
        Initialize async API client

        Args:
            timeout: Request timeout in seconds
            max_connections: Max concurrent connections
            max_retries: Max retry attempts
            retry_delay: Initial retry delay (exponential backoff)
            rate_limit_requests: Max requests per period (None = unlimited)
            rate_limit_period: Rate limit window in seconds
        """
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_connections = max_connections
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Rate limiting
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_period = rate_limit_period
        self._rate_limit_tokens = rate_limit_requests if rate_limit_requests else float('inf')
        self._rate_limit_last_refill = time.time()

        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def _ensure_session(self):
        """Ensure aiohttp session is created"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=10,
                ttl_dns_cache=300
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout
            )
            logger.debug(f"✓ Async session created (max_connections: {self.max_connections})")

    async def close(self):
        """Close aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("✓ Async session closed")

    async def _wait_for_rate_limit(self):
        """Rate limiting with token bucket algorithm"""
        if self.rate_limit_requests is None:
            return

        now = time.time()
        elapsed = now - self._rate_limit_last_refill

        # Refill tokens
        if elapsed >= self.rate_limit_period:
            self._rate_limit_tokens = self.rate_limit_requests
            self._rate_limit_last_refill = now

        # Wait if no tokens available
        if self._rate_limit_tokens <= 0:
            wait_time = self.rate_limit_period - elapsed
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self._rate_limit_tokens = self.rate_limit_requests
                self._rate_limit_last_refill = time.time()

        self._rate_limit_tokens -= 1

    async def get(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        retry: bool = True
    ) -> Dict[str, Any]:
        """
        Async GET request

        Args:
            url: Request URL
            params: Query parameters
            headers: HTTP headers
            retry: Enable automatic retries

        Returns:
            Response JSON or raises exception
        """
        await self._ensure_session()
        await self._wait_for_rate_limit()

        attempt = 0
        last_error = None

        while attempt < (self.max_retries if retry else 1):
            try:
                async with self._session.get(url, params=params, headers=headers) as response:
                    response.raise_for_status()
                    return await response.json()

            except aiohttp.ClientError as e:
                last_error = e
                attempt += 1

                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** (attempt - 1))
                    logger.warning(f"Request failed, retrying in {wait_time}s... (attempt {attempt}/{self.max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Max retries reached for {url}: {e}")

        raise last_error or Exception("Request failed")

    async def post(
        self,
        url: str,
        json: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        retry: bool = True
    ) -> Dict[str, Any]:
        """
        Async POST request

        Args:
            url: Request URL
            json: JSON payload
            data: Form data payload
            headers: HTTP headers
            retry: Enable automatic retries

        Returns:
            Response JSON or raises exception
        """
        await self._ensure_session()
        await self._wait_for_rate_limit()

        attempt = 0
        last_error = None

        while attempt < (self.max_retries if retry else 1):
            try:
                async with self._session.post(url, json=json, data=data, headers=headers) as response:
                    response.raise_for_status()
                    return await response.json()

            except aiohttp.ClientError as e:
                last_error = e
                attempt += 1

                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** (attempt - 1))
                    logger.warning(f"Request failed, retrying in {wait_time}s... (attempt {attempt}/{self.max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Max retries reached for {url}: {e}")

        raise last_error or Exception("Request failed")

    async def batch_get(
        self,
        urls: List[str],
        params: Optional[List[Dict]] = None,
        headers: Optional[Dict] = None
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Batch async GET requests (parallel)

        Args:
            urls: List of URLs
            params: List of params for each URL (or None)
            headers: Common headers for all requests

        Returns:
            List of responses (None for failed requests)
        """
        await self._ensure_session()

        if params is None:
            params = [None] * len(urls)

        tasks = [
            self._safe_get(url, p, headers)
            for url, p in zip(urls, params)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to None
        return [
            result if not isinstance(result, Exception) else None
            for result in results
        ]

    async def _safe_get(
        self,
        url: str,
        params: Optional[Dict],
        headers: Optional[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Safe GET that returns None on error instead of raising"""
        try:
            return await self.get(url, params=params, headers=headers)
        except Exception as e:
            logger.error(f"Request failed for {url}: {e}")
            return None

    async def batch_post(
        self,
        url: str,
        payloads: List[Dict],
        headers: Optional[Dict] = None
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Batch async POST requests to same endpoint (parallel)

        Args:
            url: Target URL
            payloads: List of JSON payloads
            headers: Common headers

        Returns:
            List of responses (None for failed requests)
        """
        await self._ensure_session()

        tasks = [
            self._safe_post(url, payload, headers)
            for payload in payloads
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            result if not isinstance(result, Exception) else None
            for result in results
        ]

    async def _safe_post(
        self,
        url: str,
        json: Dict,
        headers: Optional[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Safe POST that returns None on error instead of raising"""
        try:
            return await self.post(url, json=json, headers=headers)
        except Exception as e:
            logger.error(f"Request failed for {url}: {e}")
            return None

    async def parallel_different_requests(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Execute different requests in parallel

        Args:
            requests: List of request dicts with keys:
                - method: 'get' or 'post'
                - url: Target URL
                - params: (optional) Query params for GET
                - json: (optional) JSON payload for POST
                - headers: (optional) Headers

        Returns:
            List of responses
        """
        await self._ensure_session()

        tasks = []
        for req in requests:
            method = req.get('method', 'get').lower()

            if method == 'get':
                task = self._safe_get(
                    req['url'],
                    req.get('params'),
                    req.get('headers')
                )
            elif method == 'post':
                task = self._safe_post(
                    req['url'],
                    req.get('json'),
                    req.get('headers')
                )
            else:
                logger.error(f"Unknown method: {method}")
                task = asyncio.sleep(0)  # Dummy task

            tasks.append(task)

        return await asyncio.gather(*tasks, return_exceptions=True)


# Utility functions for running async code from sync context

def run_async(coro):
    """
    Run async coroutine from sync context

    Args:
        coro: Coroutine to run

    Returns:
        Coroutine result
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)


async def parallel_api_calls(
    api_function: Callable,
    arguments_list: List[tuple],
    max_concurrent: int = 10
) -> List[Any]:
    """
    Execute API calls in parallel with concurrency limit

    Args:
        api_function: Async function to call
        arguments_list: List of argument tuples for each call
        max_concurrent: Max concurrent calls

    Returns:
        List of results

    Example:
    ```python
    async def fetch_company(inn):
        # API call
        return data

    results = await parallel_api_calls(
        fetch_company,
        [('1234567890',), ('0987654321',)],
        max_concurrent=5
    )
    ```
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def limited_call(args):
        async with semaphore:
            return await api_function(*args)

    tasks = [limited_call(args) for args in arguments_list]
    return await asyncio.gather(*tasks, return_exceptions=True)


__all__ = ['AsyncAPIClient', 'run_async', 'parallel_api_calls']
