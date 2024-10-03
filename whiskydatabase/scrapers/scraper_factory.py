# scrapers/scraper_factory.py

from scrapers.beverage_scraper import BeverageScraper
from typing import Dict, Any


class ScraperFactory:
    @staticmethod
    def create_beverage_scraper(site_config: Dict[str, Any]) -> BeverageScraper:
        return BeverageScraper(site_config)
