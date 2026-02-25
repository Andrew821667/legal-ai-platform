# -*- coding: utf-8 -*-
"""
Cache Service - Multi-layer caching for performance optimization

Поддержка:
- In-memory caching (fast, local)
- Redis caching (distributed, persistent)
- Cache invalidation strategies
- TTL (Time-To-Live) управление
"""
import json
import hashlib
import time
from typing import Any, Optional, Callable, Dict
from functools import wraps
from loguru import logger


class CacheService:
    """
    Multi-layer cache service with Redis and in-memory fallback

    Features:
    - In-memory LRU cache (default)
    - Optional Redis backend for distributed caching
    - Automatic serialization/deserialization
    - TTL support
    - Cache invalidation by pattern
    - Decorator for easy caching
    """

    def __init__(
        self,
        use_redis: bool = False,
        redis_host: str = 'localhost',
        redis_port: int = 6379,
        redis_db: int = 0,
        default_ttl: int = 3600,
        max_memory_items: int = 1000
    ):
        """
        Initialize cache service

        Args:
            use_redis: Enable Redis backend
            redis_host: Redis server host
            redis_port: Redis server port
            redis_db: Redis database number
            default_ttl: Default TTL in seconds
            max_memory_items: Max items in memory cache
        """
        self.use_redis = use_redis
        self.default_ttl = default_ttl
        self.max_memory_items = max_memory_items

        # In-memory cache (always available)
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

        # Redis cache (optional)
        self.redis_client = None
        if use_redis:
            try:
                import redis
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True,
                    socket_connect_timeout=2
                )
                # Test connection
                self.redis_client.ping()
                logger.info(f"✓ Redis cache initialized: {redis_host}:{redis_port}")
            except Exception as e:
                logger.warning(f"Redis not available: {e}. Using in-memory cache only.")
                self.redis_client = None
                self.use_redis = False

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Strategy:
        1. Check in-memory cache first (fastest)
        2. If not found, check Redis
        3. If found in Redis, store in memory for next access

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        # Check memory cache first
        if key in self._memory_cache:
            entry = self._memory_cache[key]

            # Check if expired
            if entry['expires_at'] > time.time():
                logger.debug(f"✓ Memory cache HIT: {key}")
                return entry['value']
            else:
                # Expired, remove from memory
                logger.debug(f"✗ Memory cache EXPIRED: {key}")
                del self._memory_cache[key]

        # Check Redis if available
        if self.redis_client:
            try:
                redis_value = self.redis_client.get(key)
                if redis_value:
                    logger.debug(f"✓ Redis cache HIT: {key}")
                    # Deserialize and store in memory
                    value = json.loads(redis_value)
                    # Get TTL from Redis
                    ttl = self.redis_client.ttl(key)
                    if ttl > 0:
                        self._set_memory(key, value, ttl)
                    return value
            except Exception as e:
                logger.error(f"Redis get error: {e}")

        logger.debug(f"✗ Cache MISS: {key}")
        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time-to-live in seconds (None = use default)

        Returns:
            True if successful
        """
        if ttl is None:
            ttl = self.default_ttl

        try:
            # Set in memory cache
            self._set_memory(key, value, ttl)

            # Set in Redis if available
            if self.redis_client:
                try:
                    serialized = json.dumps(value, ensure_ascii=False)
                    self.redis_client.setex(key, ttl, serialized)
                    logger.debug(f"✓ Cached in Redis: {key} (TTL: {ttl}s)")
                except Exception as e:
                    logger.error(f"Redis set error: {e}")

            logger.debug(f"✓ Cached in memory: {key} (TTL: {ttl}s)")
            return True

        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete key from cache

        Args:
            key: Cache key

        Returns:
            True if key was deleted
        """
        deleted = False

        # Delete from memory
        if key in self._memory_cache:
            del self._memory_cache[key]
            deleted = True
            logger.debug(f"✓ Deleted from memory: {key}")

        # Delete from Redis
        if self.redis_client:
            try:
                if self.redis_client.delete(key) > 0:
                    deleted = True
                    logger.debug(f"✓ Deleted from Redis: {key}")
            except Exception as e:
                logger.error(f"Redis delete error: {e}")

        return deleted

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern

        Args:
            pattern: Pattern with wildcards (e.g., "fns:*", "contract:123:*")

        Returns:
            Number of keys deleted
        """
        count = 0

        # Delete from memory
        keys_to_delete = [k for k in self._memory_cache.keys() if self._match_pattern(k, pattern)]
        for key in keys_to_delete:
            del self._memory_cache[key]
            count += 1

        # Delete from Redis
        if self.redis_client:
            try:
                redis_keys = self.redis_client.keys(pattern)
                if redis_keys:
                    count += self.redis_client.delete(*redis_keys)
                logger.debug(f"✓ Deleted {count} keys matching pattern: {pattern}")
            except Exception as e:
                logger.error(f"Redis delete pattern error: {e}")

        return count

    def clear(self) -> bool:
        """
        Clear entire cache

        Returns:
            True if successful
        """
        # Clear memory
        self._memory_cache.clear()

        # Clear Redis
        if self.redis_client:
            try:
                self.redis_client.flushdb()
                logger.info("✓ Cleared entire cache (memory + Redis)")
            except Exception as e:
                logger.error(f"Redis flush error: {e}")
                return False

        logger.info("✓ Cleared memory cache")
        return True

    def _set_memory(self, key: str, value: Any, ttl: int):
        """Set value in memory cache with TTL"""
        # LRU eviction if cache is full
        if len(self._memory_cache) >= self.max_memory_items:
            # Remove oldest entry
            oldest_key = min(
                self._memory_cache.keys(),
                key=lambda k: self._memory_cache[k]['expires_at']
            )
            del self._memory_cache[oldest_key]
            logger.debug(f"✓ Evicted oldest entry: {oldest_key}")

        self._memory_cache[key] = {
            'value': value,
            'expires_at': time.time() + ttl
        }

    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Simple pattern matching for cache keys"""
        import re
        # Convert glob pattern to regex
        regex_pattern = pattern.replace('*', '.*').replace('?', '.')
        return bool(re.match(f"^{regex_pattern}$", key))

    def cached(
        self,
        ttl: Optional[int] = None,
        key_prefix: str = ""
    ) -> Callable:
        """
        Decorator for caching function results

        Usage:
        ```python
        @cache.cached(ttl=600, key_prefix="fns")
        def get_company_info(inn: str):
            # expensive operation
            return result
        ```

        Args:
            ttl: Cache TTL in seconds
            key_prefix: Prefix for cache key

        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key from function name and arguments
                key_parts = [key_prefix, func.__name__] if key_prefix else [func.__name__]

                # Add arguments to key
                if args:
                    args_str = json.dumps(args, sort_keys=True, ensure_ascii=False)
                    args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
                    key_parts.append(args_hash)

                if kwargs:
                    kwargs_str = json.dumps(kwargs, sort_keys=True, ensure_ascii=False)
                    kwargs_hash = hashlib.md5(kwargs_str.encode()).hexdigest()[:8]
                    key_parts.append(kwargs_hash)

                cache_key = ":".join(key_parts)

                # Try to get from cache
                cached_result = self.get(cache_key)
                if cached_result is not None:
                    logger.info(f"✓ Using cached result for {func.__name__}")
                    return cached_result

                # Call function
                result = func(*args, **kwargs)

                # Cache result
                self.set(cache_key, result, ttl=ttl)

                return result

            return wrapper
        return decorator

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dict with cache stats
        """
        stats = {
            'memory_items': len(self._memory_cache),
            'memory_max_items': self.max_memory_items,
            'default_ttl': self.default_ttl,
            'redis_enabled': self.use_redis,
            'redis_connected': self.redis_client is not None
        }

        if self.redis_client:
            try:
                info = self.redis_client.info('stats')
                stats['redis_total_commands'] = info.get('total_commands_processed', 0)
                stats['redis_keyspace_hits'] = info.get('keyspace_hits', 0)
                stats['redis_keyspace_misses'] = info.get('keyspace_misses', 0)

                # Calculate hit rate
                hits = stats['redis_keyspace_hits']
                misses = stats['redis_keyspace_misses']
                if hits + misses > 0:
                    stats['redis_hit_rate'] = hits / (hits + misses) * 100
            except Exception as e:
                logger.error(f"Error getting Redis stats: {e}")

        return stats


# Global cache instance
_cache_instance: Optional[CacheService] = None


def get_cache(
    use_redis: bool = False,
    **kwargs
) -> CacheService:
    """
    Get global cache instance (singleton pattern)

    Args:
        use_redis: Enable Redis backend
        **kwargs: Additional cache configuration

    Returns:
        CacheService instance
    """
    global _cache_instance

    if _cache_instance is None:
        _cache_instance = CacheService(use_redis=use_redis, **kwargs)
        logger.info("✓ Cache service initialized")

    return _cache_instance


__all__ = ['CacheService', 'get_cache']
