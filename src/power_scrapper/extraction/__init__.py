"""Text extraction layer with cascading fallback."""

from power_scrapper.extraction.base import ITextExtractor
from power_scrapper.extraction.cascade import CascadeTextExtractor
from power_scrapper.extraction.crawl4ai_ext import Crawl4AIExtractor
from power_scrapper.extraction.newspaper_ext import NewspaperExtractor
from power_scrapper.extraction.patchright_ext import PatchrightExtractor
from power_scrapper.extraction.readability_ext import ReadabilityExtractor
from power_scrapper.extraction.trafilatura_ext import TrafilaturaExtractor

__all__ = [
    "CascadeTextExtractor",
    "Crawl4AIExtractor",
    "ITextExtractor",
    "NewspaperExtractor",
    "PatchrightExtractor",
    "ReadabilityExtractor",
    "TrafilaturaExtractor",
]
