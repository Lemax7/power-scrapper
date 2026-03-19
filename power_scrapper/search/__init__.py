"""Search strategies for power_scrapper."""

from power_scrapper.search.base import ISearchStrategy
from power_scrapper.search.searxng import SearXNGStrategy

__all__ = [
    "ISearchStrategy",
    "SearXNGStrategy",
]
