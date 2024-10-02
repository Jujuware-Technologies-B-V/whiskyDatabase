# scrapers/scraper_factory.py

from scrapers.base_scraper import BaseScraper
from typing import Dict, Any


class ScraperFactory:
    @staticmethod
    def create_scraper(site_config: Dict[str, Any]) -> BaseScraper:
        return BaseScraper(site_config)
