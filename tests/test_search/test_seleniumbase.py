"""Tests for the SeleniumBase CDP strategy."""

from __future__ import annotations

import pytest

from power_scrapper.search.base import ISearchStrategy
from power_scrapper.search.seleniumbase_strategy import SeleniumBaseCDPStrategy


class TestSeleniumBaseCDPStrategy:
    def test_implements_interface(self) -> None:
        strategy = SeleniumBaseCDPStrategy()
        assert isinstance(strategy, ISearchStrategy)

    def test_name(self) -> None:
        assert SeleniumBaseCDPStrategy().name == "seleniumbase_cdp"

    async def test_is_available_when_not_installed(self) -> None:
        strategy = SeleniumBaseCDPStrategy()
        # This will return True or False depending on whether
        # seleniumbase is installed in the test environment.
        result = await strategy.is_available()
        assert isinstance(result, bool)

    async def test_is_available_caches_result(self) -> None:
        strategy = SeleniumBaseCDPStrategy()
        result1 = await strategy.is_available()
        result2 = await strategy.is_available()
        assert result1 == result2
        assert strategy._available is not None
