from typing import Dict, Optional, List, Any
from abc import ABC, abstractmethod
from utils.logger import get_logger
from utils.helpers import ensure_directory, get_date_string
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
import random
import csv
import gzip
import logging
import os


class BaseScraper(ABC):
    def __init__(self, site_config: Dict[str, Any]):
        self.site_config = site_config
        self.logger = get_logger(self.site_config['name'])
        self.headers = self.site_config.get('headers', {})
        self.base_url = self.site_config['base_url']
        self.delay = self.site_config.get('delay', 1)
        self.retries = self.site_config.get('retries', 3)
        self.fieldnames = ['name', 'price',
                           'link', 'volume', 'abv', 'scraped_at']
        ensure_directory('data')
        self.data_file = os.path.join('data', f"{self.site_config['name'].lower(
        ).replace(' ', '_')}_{get_date_string()}.csv.gz")
        self.init_data_file()
        ensure_directory('data')

    @abstractmethod
    def scrape(self) -> None:
        """Abstract method to be implemented by subclasses."""
        pass

    def make_request(self, url: str, is_detail_page: bool = False) -> Optional[str]:
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.info(f"Attempting to fetch URL: {
                                 url} (Attempt {attempt}/{self.retries})")
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(
                        user_agent=self.headers.get(
                            'User-Agent', 'Mozilla/5.0')
                    )
                    page = context.new_page()
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    self.logger.info(f"Navigated to: {page.url}")

                    if not is_detail_page:
                        page.wait_for_selector(
                            self.site_config['product_list_selector'], timeout=60000)

                        previous_height = None
                        while True:
                            current_height = page.evaluate(
                                'document.body.scrollHeight')
                            if previous_height == current_height:
                                break
                            page.evaluate(
                                'window.scrollTo(0, document.body.scrollHeight)')
                            page.wait_for_timeout(2000)
                            previous_height = current_height
                    else:
                        page.wait_for_selector(
                            self.site_config['detail_info_selector'], timeout=60000)

                    content = page.content()
                    context.close()
                    browser.close()
                    time.sleep(self.delay + random.uniform(0, 1))
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
                    time.sleep(backoff_time)
            except Exception as e:
                self.logger.error(f"Error fetching {url}: {e}")
                if attempt == self.retries:
                    self.logger.error(f"Failed to fetch {url} after {
                                      self.retries} attempts.")
                    return None
                else:
                    backoff_time = self.delay * (2 ** attempt)
                    self.logger.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
        return None

    def fetch_product_details(self, url: str) -> Optional[Dict[str, str]]:
        """Fetch and parse product details from a product page."""
        content = self.make_request(url, is_detail_page=True)
        if content:
            return self.parse_product_details(content)
        return None

    def init_data_file(self):
        if not os.path.exists(self.data_file):
            with gzip.open(self.data_file, 'wt', encoding='utf-8', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                writer.writeheader()
            self.logger.info(f"Created new data file: {self.data_file}")

    def save_products(self, products):
        with gzip.open(self.data_file, 'at', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
            for product in products:
                writer.writerow(product)
                self.logger.info(f"Saved product: {product['name']}")

    @abstractmethod
    def parse_product_details(self, content: str) -> Dict[str, str]:
        """Parse the product details page. To be implemented by subclasses."""
        pass
