"""Tests for the adaptive rate limiter."""

from __future__ import annotations

import pytest

from power_scrapper.utils.rate_limiter import AdaptiveRateLimiter


class TestHumanDelay:
    def test_returns_positive_float(self) -> None:
        limiter = AdaptiveRateLimiter(base_delay=1.0, max_delay=3.0)
        delay = limiter.human_delay()
        assert isinstance(delay, float)
        assert delay > 0

    def test_respects_minimum_bound(self) -> None:
        limiter = AdaptiveRateLimiter(base_delay=2.0, max_delay=4.0)
        # Run multiple times to check lower bound.
        for _ in range(100):
            delay = limiter.human_delay()
            assert delay >= 1.0  # base_delay * 0.5

    def test_varies_between_calls(self) -> None:
        limiter = AdaptiveRateLimiter(base_delay=2.0, max_delay=10.0)
        delays = [limiter.human_delay() for _ in range(50)]
        # With Poisson distribution, we should see variation.
        assert len(set(delays)) > 1


class TestBackoff:
    def test_record_block_returns_true_for_first_stages(self) -> None:
        limiter = AdaptiveRateLimiter()
        assert limiter.record_block("example.com") is True  # Level 1
        assert limiter.record_block("example.com") is True  # Level 2
        assert limiter.record_block("example.com") is True  # Level 3

    def test_record_block_returns_false_when_exhausted(self) -> None:
        limiter = AdaptiveRateLimiter()
        limiter.record_block("example.com")  # Level 1
        limiter.record_block("example.com")  # Level 2
        limiter.record_block("example.com")  # Level 3
        assert limiter.record_block("example.com") is False  # Exhausted

    def test_should_skip_after_exhaustion(self) -> None:
        limiter = AdaptiveRateLimiter()
        assert limiter.should_skip("example.com") is False
        for _ in range(4):
            limiter.record_block("example.com")
        assert limiter.should_skip("example.com") is True

    def test_record_success_resets_backoff(self) -> None:
        limiter = AdaptiveRateLimiter()
        limiter.record_block("example.com")
        limiter.record_block("example.com")
        limiter.record_success("example.com")
        assert limiter.should_skip("example.com") is False

    def test_domains_tracked_independently(self) -> None:
        limiter = AdaptiveRateLimiter()
        limiter.record_block("a.com")
        limiter.record_block("a.com")
        limiter.record_block("a.com")
        limiter.record_block("a.com")
        assert limiter.should_skip("a.com") is True
        assert limiter.should_skip("b.com") is False


class TestAILabyrinth:
    def test_normal_link_not_detected(self) -> None:
        assert AdaptiveRateLimiter.is_ai_labyrinth_link(
            "https://example.com/article",
            rel="",
        ) is False

    def test_cloudflare_cgi_detected(self) -> None:
        assert AdaptiveRateLimiter.is_ai_labyrinth_link(
            "https://example.com/cdn-cgi/something",
        ) is True

    def test_challenge_platform_detected(self) -> None:
        assert AdaptiveRateLimiter.is_ai_labyrinth_link(
            "https://example.com/challenge-platform/page",
        ) is True

    def test_nofollow_with_random_path_detected(self) -> None:
        assert AdaptiveRateLimiter.is_ai_labyrinth_link(
            "https://example.com/a/b/c/1234567890abcdef1234567890/9876543210abcdef1234567890/xyz",
            rel="nofollow",
        ) is True

    def test_nofollow_with_normal_path_not_detected(self) -> None:
        assert AdaptiveRateLimiter.is_ai_labyrinth_link(
            "https://example.com/about",
            rel="nofollow",
        ) is False
