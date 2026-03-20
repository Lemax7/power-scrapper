"""Tests for the API interceptor search strategy."""

from __future__ import annotations

from datetime import datetime

import pytest

from power_scrapper.search.api_interceptor import APIInterceptorStrategy
from power_scrapper.search.base import ISearchStrategy


class TestAPIInterceptorStrategy:
    def test_implements_interface(self) -> None:
        strategy = APIInterceptorStrategy()
        assert isinstance(strategy, ISearchStrategy)

    def test_name(self) -> None:
        assert APIInterceptorStrategy().name == "api_interception"

    def test_extract_from_json_flat(self) -> None:
        strategy = APIInterceptorStrategy()
        data = {
            "url": "https://example.com/article",
            "title": "Test Article Title",
            "snippet": "A test snippet.",
        }
        results = strategy._extract_from_json(data, "test")
        assert len(results) == 1
        assert results[0].url == "https://example.com/article"
        assert results[0].title == "Test Article Title"
        assert results[0].source_type == "api_interception"

    def test_extract_from_json_nested(self) -> None:
        strategy = APIInterceptorStrategy()
        data = {
            "results": [
                {
                    "url": "https://a.com/1",
                    "title": "First Result",
                    "description": "Desc 1",
                },
                {
                    "url": "https://b.com/2",
                    "title": "Second Result",
                    "description": "Desc 2",
                },
            ]
        }
        results = strategy._extract_from_json(data, "test")
        assert len(results) == 2

    def test_extract_from_json_ignores_invalid(self) -> None:
        strategy = APIInterceptorStrategy()
        data = {
            "url": "",
            "title": "",
        }
        results = strategy._extract_from_json(data, "test")
        assert len(results) == 0

    def test_extract_from_json_ignores_non_http(self) -> None:
        strategy = APIInterceptorStrategy()
        data = {
            "url": "javascript:void(0)",
            "title": "Bad Link",
        }
        results = strategy._extract_from_json(data, "test")
        assert len(results) == 0

    def test_extract_from_json_depth_limit(self) -> None:
        strategy = APIInterceptorStrategy()
        # Deep nesting should not infinite loop.
        data: dict = {"nested": {"nested": {"nested": {"nested": {"nested": {
            "url": "https://deep.com",
            "title": "Deep Article",
        }}}}}}
        results = strategy._extract_from_json(data, "test")
        assert len(results) == 1

    def test_extract_source_from_url(self) -> None:
        source = APIInterceptorStrategy._extract_source("https://www.example.com/path")
        assert source == "www.example.com"

    def test_is_api_response_json_content_type(self) -> None:
        class MockResponse:
            status = 200
            headers = {"content-type": "application/json"}

        assert APIInterceptorStrategy._is_api_response(
            "https://google.com/search?q=test", MockResponse()
        )

    def test_is_api_response_non_json(self) -> None:
        class MockResponse:
            status = 200
            headers = {"content-type": "text/html"}

        assert not APIInterceptorStrategy._is_api_response(
            "https://google.com/search?q=test", MockResponse()
        )
