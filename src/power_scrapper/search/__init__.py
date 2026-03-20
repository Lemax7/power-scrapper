"""Search strategies for power_scrapper."""

from power_scrapper.search.base import BrowserSearchStrategy, ISearchStrategy
from power_scrapper.search.google_news import GoogleNewsStrategy
from power_scrapper.search.google_search import GoogleSearchStrategy
from power_scrapper.search.searxng import SearXNGStrategy
from power_scrapper.search.yandex import YandexSearchStrategy

__all__ = [
    "BrowserSearchStrategy",
    "ISearchStrategy",
    "GoogleNewsStrategy",
    "GoogleSearchStrategy",
    "SearXNGStrategy",
    "YandexSearchStrategy",
]
