# scrapers/base_scraper.py

from typing import Dict, Optional, List, Any
from abc import ABC, abstractmethod
from utils.logger import get_logger
from utils.helpers import ensure_directory, get_date_string
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import random
import csv
import gzip
import os


class BaseScraper(ABC):
    def __init__(self, site_config: Dict[str, Any]):
        self.site_config = site_config
        self.retailer = self.site_config['name']
        self.logger = get_logger(self.site_config['name'])
        self.headers = self.site_config.get('headers', {})
        self.base_url = self.site_config['base_url']
        self.delay = self.site_config.get('delay', 1)
        self.retries = self.site_config.get('retries', 3)
        self.fieldnames = ['retailer', 'name', 'price',
                           'link', 'volume', 'abv', 'scraped_at']
        ensure_directory('data')
        self.data_file = os.path.join(
            'data',
            f"{self.site_config['name'].lower().replace(' ', '_')}_{
                get_date_string()}.csv.gz"
        )
        self.init_data_file()

    @abstractmethod
    async def scrape(self) -> None:
        """Abstract method to be implemented by subclasses."""
        pass

    async def make_request(self, url: str, is_detail_page: bool = False) -> Optional[str]:
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.info(f"Attempting to fetch URL: {
                                 url} (Attempt {attempt}/{self.retries})")
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(
                        user_agent=self.headers.get(
                            'User-Agent', 'Mozilla/5.0')
                    )
                    page = await context.new_page()
                    await page.goto(url, wait_until="networkidle", timeout=60000)
                    self.logger.info(f"Navigated to: {page.url}")

                    if not is_detail_page:
                        await page.wait_for_selector(self.site_config['product_list_selector'], timeout=60000)
                        # Implement scrolling if necessary
                    else:
                        await page.wait_for_selector(self.site_config['detail_info_selector'], timeout=60000)

                    content = await page.content()
                    await context.close()
                    await browser.close()
                    await asyncio.sleep(self.delay + random.uniform(0, 1))
                    return content
            except PlaywrightTimeoutError as e:
                self.logger.error(f"Timeout when fetching {url}: {e}")
                if attempt == self.retries:
                    self.logger.error(f"Failed to fetch {url} after {
                                      self.retries} attempts.")
                    return None
                else:
                    backoff_time = self.delay * (2 ** attempt)
                    self.logger.info(f"Retrying in {backoff_time} seconds...")
                    await asyncio.sleep(backoff_time)
            except Exception as e:
                self.logger.error(f"Error fetching {url}: {e}")
                if attempt == self.retries:
                    self.logger.error(f"Failed to fetch {url} after {
                                      self.retries} attempts.")
                    return None
                else:
                    backoff_time = self.delay * (2 ** attempt)
                    self.logger.info(f"Retrying in {backoff_time} seconds...")
                    await asyncio.sleep(backoff_time)
        return None

    async def fetch_product_details(self, url: str) -> Optional[Dict[str, str]]:
        """Fetch and parse product details from a product page."""
        content = await self.make_request(url, is_detail_page=True)
        if content:
            return self.parse_product_details(content)
        return None

    def init_data_file(self):
        if not os.path.exists(self.data_file):
            with gzip.open(self.data_file, 'wt', encoding='utf-8', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                writer.writeheader()
            self.logger.info(f"Created new data file: {self.data_file}")

    def save_products(self, products: List[Dict[str, Any]]):
        with gzip.open(self.data_file, 'at', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
            for product in products:
                product['retailer'] = self.retailer
                writer.writerow(product)
                self.logger.info(f"Saved product: {product['name']}")

    @abstractmethod
    def parse_product_details(self, content: str) -> Dict[str, str]:
        """Parse the product details page. To be implemented by subclasses."""
        pass
