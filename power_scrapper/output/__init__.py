"""Output writers for scraped article data."""

from power_scrapper.output.base import IOutputWriter
from power_scrapper.output.csv_writer import CsvWriter
from power_scrapper.output.excel import ExcelWriter
from power_scrapper.output.json_writer import JsonWriter

__all__ = [
    "CsvWriter",
    "ExcelWriter",
    "IOutputWriter",
    "JsonWriter",
]
