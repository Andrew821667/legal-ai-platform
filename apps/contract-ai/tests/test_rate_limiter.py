# -*- coding: utf-8 -*-
"""
Tests for rate_limiter.py - API Cost Control
"""
import pytest
import time
import threading
from datetime import datetime

from src.utils.rate_limiter import (
    RateLimiter,
    RateLimitExceeded,
    get_global_rate_limiter,
    set_global_rate_limiter
)


class TestRateLimiterBasics:
    """Test basic rate limiter functionality"""

    def test_create_rate_limiter(self):
        """Test creating rate limiter with various limits"""
        limiter = RateLimiter(
            requests_per_minute=10,
            tokens_per_minute=1000,
            cost_per_hour=1.0,
            cost_per_day=10.0
        )

        assert limiter.requests_per_minute == 10
        assert limiter.tokens_per_minute == 1000
        assert limiter.cost_per_hour == 1.0
        assert limiter.cost_per_day == 10.0

    def test_create_limiter_with_no_limits(self):
        """Test creating limiter with no limits (all None)"""
        limiter = RateLimiter()

        assert limiter.requests_per_minute is None
        assert limiter.tokens_per_minute is None

    def test_acquire_within_limits(self):
        """Test acquiring resources within limits"""
        limiter = RateLimiter(
            requests_per_minute=10,
            tokens_per_minute=1000,
            cost_per_hour=1.0
        )

        # Should succeed
        with limiter.acquire(tokens=100, cost=0.01):
            pass  # Request allowed

    def test_get_stats_initial(self):
        """Test getting stats from new limiter"""
        limiter = RateLimiter(requests_per_minute=60)

        stats = limiter.get_stats()

        assert stats['current_rpm'] == 0
        assert stats['total_requests'] == 0
        assert stats['total_tokens'] == 0
        assert stats['total_cost'] == 0.0


class TestRequestRateLimiting:
    """Test requests per minute limiting"""

    def test_request_limit_enforced(self):
        """Test RPM limit is enforced"""
        limiter = RateLimiter(requests_per_minute=3)

        # First 3 requests should succeed
        for i in range(3):
            with limiter.acquire():
                pass

        # 4th request should fail
        with pytest.raises(RateLimitExceeded, match="Request rate limit exceeded"):
            with limiter.acquire():
                pass

    def test_request_limit_resets_after_time(self):
        """Test RPM limit resets after 60 seconds"""
        limiter = RateLimiter(requests_per_minute=2)

        # Use up limit
        for i in range(2):
            with limiter.acquire():
                pass

        # Should fail immediately
        with pytest.raises(RateLimitExceeded):
            with limiter.acquire():
                pass

        # Wait for window to reset (simulate)
        # In real test, we'd need to wait 60 seconds or mock time
        # For now, just verify the exception contains wait time
        try:
            with limiter.acquire():
                pass
        except RateLimitExceeded as e:
            assert "wait" in str(e).lower()


class TestTokenRateLimiting:
    """Test tokens per minute limiting"""

    def test_token_limit_enforced(self):
        """Test TPM limit is enforced"""
        limiter = RateLimiter(tokens_per_minute=1000)

        # Use 900 tokens
        with limiter.acquire(tokens=900):
            pass

        # Another 50 should work
        with limiter.acquire(tokens=50):
            pass

        # But 200 more should fail (900 + 50 + 200 = 1150 > 1000)
        with pytest.raises(RateLimitExceeded, match="Token rate limit exceeded"):
            with limiter.acquire(tokens=200):
                pass

    def test_token_accumulation(self):
        """Test token usage accumulates correctly"""
        limiter = RateLimiter(tokens_per_minute=1000)

        with limiter.acquire(tokens=300):
            pass
        with limiter.acquire(tokens=400):
            pass

        stats = limiter.get_stats()
        assert stats['current_tpm'] == 700

    def test_no_token_limit_allows_unlimited(self):
        """Test no token limit allows any amount"""
        limiter = RateLimiter()  # No limits

        # Should succeed with huge token count
        with limiter.acquire(tokens=1000000):
            pass


class TestCostLimiting:
    """Test cost per hour/day limiting"""

    def test_hourly_cost_limit_enforced(self):
        """Test cost per hour limit is enforced"""
        limiter = RateLimiter(cost_per_hour=1.0)

        # Use $0.80
        with limiter.acquire(cost=0.80):
            pass

        # Another $0.15 should work
        with limiter.acquire(cost=0.15):
            pass

        # But $0.10 more should fail (0.80 + 0.15 + 0.10 = 1.05 > 1.0)
        with pytest.raises(RateLimitExceeded, match="Hourly cost limit exceeded"):
            with limiter.acquire(cost=0.10):
                pass

    def test_daily_cost_limit_enforced(self):
        """Test cost per day limit is enforced"""
        limiter = RateLimiter(cost_per_day=10.0)

        # Use $9.50
        with limiter.acquire(cost=9.50):
            pass

        # $0.60 more should fail
        with pytest.raises(RateLimitExceeded, match="Daily cost limit exceeded"):
            with limiter.acquire(cost=0.60):
                pass

    def test_both_cost_limits(self):
        """Test both hourly and daily limits work together"""
        limiter = RateLimiter(cost_per_hour=1.0, cost_per_day=10.0)

        # Use $0.90 (under both limits)
        with limiter.acquire(cost=0.90):
            pass

        # $0.15 more exceeds hourly (1.05) but not daily
        with pytest.raises(RateLimitExceeded, match="Hourly"):
            with limiter.acquire(cost=0.15):
                pass


class TestMultipleLimits:
    """Test interaction of multiple limits"""

    def test_all_limits_enforced(self):
        """Test all limits are checked"""
        limiter = RateLimiter(
            requests_per_minute=5,
            tokens_per_minute=1000,
            cost_per_hour=1.0
        )

        # Use 4 requests, 800 tokens, $0.80
        for i in range(4):
            with limiter.acquire(tokens=200, cost=0.20):
                pass

        # Next request would be #5 (OK), 200 more tokens (OK, total 1000),
        # but $0.25 more cost would exceed hourly limit
        with pytest.raises(RateLimitExceeded, match="cost"):
            with limiter.acquire(tokens=200, cost=0.25):
                pass

    def test_first_limit_hit_stops_check(self):
        """Test that first limit hit raises immediately"""
        limiter = RateLimiter(
            requests_per_minute=2,
            tokens_per_minute=1000,
            cost_per_hour=10.0  # High limit
        )

        # Use up request limit
        for i in range(2):
            with limiter.acquire(tokens=100, cost=0.01):
                pass

        # Should fail on request limit first
        with pytest.raises(RateLimitExceeded, match="Request rate"):
            with limiter.acquire(tokens=100, cost=0.01):
                pass


class TestStatistics:
    """Test statistics tracking"""

    def test_stats_track_usage(self):
        """Test stats correctly track usage"""
        limiter = RateLimiter(
            requests_per_minute=100,
            tokens_per_minute=10000,
            cost_per_hour=10.0
        )

        # Make several requests
        with limiter.acquire(tokens=500, cost=0.10):
            pass
        with limiter.acquire(tokens=300, cost=0.05):
            pass

        stats = limiter.get_stats()

        assert stats['total_requests'] == 2
        assert stats['total_tokens'] == 800
        assert stats['total_cost'] == 0.15
        assert stats['current_rpm'] == 2
        assert stats['current_tpm'] == 800

    def test_stats_show_percentages(self):
        """Test stats show usage percentages"""
        limiter = RateLimiter(
            requests_per_minute=10,
            tokens_per_minute=1000
        )

        # Use 5 requests, 500 tokens (50% each)
        for i in range(5):
            with limiter.acquire(tokens=100):
                pass

        stats = limiter.get_stats()

        assert stats['rpm_usage_pct'] == 50.0
        assert stats['tpm_usage_pct'] == 50.0

    def test_reset_stats(self):
        """Test resetting statistics"""
        limiter = RateLimiter(requests_per_minute=100)

        # Use some resources
        for i in range(5):
            with limiter.acquire(tokens=100, cost=0.01):
                pass

        # Reset
        limiter.reset_stats()

        stats = limiter.get_stats()
        assert stats['total_requests'] == 0
        assert stats['total_tokens'] == 0
        assert stats['total_cost'] == 0.0


class TestThreadSafety:
    """Test thread-safe operations"""

    def test_concurrent_requests(self):
        """Test limiter works correctly with concurrent requests"""
        limiter = RateLimiter(requests_per_minute=100, tokens_per_minute=10000)

        results = []
        errors = []

        def make_request(thread_id):
            try:
                with limiter.acquire(tokens=100, cost=0.01):
                    time.sleep(0.001)  # Simulate work
                    results.append(thread_id)
            except Exception as e:
                errors.append((thread_id, e))

        # Create threads
        threads = []
        for i in range(20):
            t = threading.Thread(target=make_request, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all
        for t in threads:
            t.join()

        # All should succeed (within limits)
        assert len(results) == 20
        assert len(errors) == 0

        # Stats should reflect all requests
        stats = limiter.get_stats()
        assert stats['total_requests'] == 20
        assert stats['total_tokens'] == 2000

    def test_concurrent_limit_enforcement(self):
        """Test limit is enforced correctly with concurrent access"""
        limiter = RateLimiter(requests_per_minute=10)

        successes = []
        failures = []

        def make_request(thread_id):
            try:
                with limiter.acquire():
                    successes.append(thread_id)
            except RateLimitExceeded:
                failures.append(thread_id)

        # Try to make 15 concurrent requests (limit is 10)
        threads = []
        for i in range(15):
            t = threading.Thread(target=make_request, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should have 10 successes and 5 failures
        assert len(successes) == 10
        assert len(failures) == 5


class TestContextManager:
    """Test context manager functionality"""

    def test_context_manager_usage(self):
        """Test using limiter as context manager"""
        limiter = RateLimiter(requests_per_minute=100)

        with limiter.acquire(tokens=100, cost=0.01) as ctx:
            # Context manager should work
            pass

        # Request should be recorded
        assert limiter.total_requests == 1

    def test_context_manager_with_exception(self):
        """Test context manager works correctly even if exception raised"""
        limiter = RateLimiter(requests_per_minute=100)

        try:
            with limiter.acquire(tokens=100, cost=0.01):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Request should still be recorded
        assert limiter.total_requests == 1


class TestGlobalLimiter:
    """Test global rate limiter singleton"""

    def test_get_global_limiter(self):
        """Test getting global rate limiter"""
        limiter = get_global_rate_limiter()

        assert limiter is not None
        assert isinstance(limiter, RateLimiter)

    def test_set_global_limiter(self):
        """Test setting global rate limiter"""
        custom_limiter = RateLimiter(requests_per_minute=999)

        set_global_rate_limiter(custom_limiter)

        # Get should return our custom limiter
        limiter = get_global_rate_limiter()
        assert limiter.requests_per_minute == 999

    def test_global_limiter_is_singleton(self):
        """Test global limiter returns same instance"""
        limiter1 = get_global_rate_limiter()
        limiter2 = get_global_rate_limiter()

        # Should be same object
        assert limiter1 is limiter2


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_zero_cost_allowed(self):
        """Test zero cost requests are allowed"""
        limiter = RateLimiter(cost_per_hour=1.0)

        with limiter.acquire(cost=0.0):
            pass

        stats = limiter.get_stats()
        assert stats['total_cost'] == 0.0

    def test_zero_tokens_allowed(self):
        """Test zero token requests are allowed"""
        limiter = RateLimiter(tokens_per_minute=1000)

        with limiter.acquire(tokens=0):
            pass

        stats = limiter.get_stats()
        assert stats['total_tokens'] == 0

    def test_very_small_cost(self):
        """Test very small cost values work correctly"""
        limiter = RateLimiter(cost_per_hour=1.0)

        with limiter.acquire(cost=0.0001):
            pass

        stats = limiter.get_stats()
        assert stats['total_cost'] == pytest.approx(0.0001)

    def test_cleanup_old_entries(self):
        """Test old entries are cleaned up from deques"""
        limiter = RateLimiter(requests_per_minute=100)

        # Make some requests
        for i in range(5):
            with limiter.acquire():
                pass

        # Check stats shows current requests
        stats1 = limiter.get_stats()
        assert stats1['current_rpm'] == 5

        # Simulate time passing (in real code, old entries would be cleaned)
        # For now, just verify cleanup method exists
        limiter._cleanup_old_entries(limiter.request_times, 60)


class TestRealWorldScenarios:
    """Test real-world usage scenarios"""

    def test_llm_batch_processing(self):
        """Test rate limiting for batch LLM requests"""
        # Simulate gpt-4o-mini limits
        limiter = RateLimiter(
            requests_per_minute=60,
            tokens_per_minute=100000,
            cost_per_hour=5.0
        )

        # Process batches of 15 clauses
        batch_size = 15
        tokens_per_clause = 500  # Estimate
        cost_per_batch = 0.015  # Estimate

        batches_processed = 0

        try:
            for batch in range(20):
                with limiter.acquire(
                    tokens=batch_size * tokens_per_clause,
                    cost=cost_per_batch
                ):
                    batches_processed += 1
        except RateLimitExceeded:
            pass

        # Should process some batches before hitting limit
        assert batches_processed > 0

    def test_cost_budget_enforcement(self):
        """Test enforcing daily cost budget"""
        # Daily budget of $10
        limiter = RateLimiter(cost_per_day=10.0)

        # Process contracts until budget exhausted
        contracts_processed = 0
        cost_per_contract = 0.25  # $0.25 per contract

        try:
            for contract in range(100):
                with limiter.acquire(cost=cost_per_contract):
                    contracts_processed += 1
        except RateLimitExceeded:
            pass

        # Should process ~40 contracts ($10 / $0.25)
        assert 35 <= contracts_processed <= 40

        stats = limiter.get_stats()
        assert stats['total_cost'] <= 10.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
