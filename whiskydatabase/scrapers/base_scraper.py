# scrapers/base_scraper.py

from typing import Dict, Optional, List, Any
from abc import ABC, abstractmethod
from utils.helpers import ensure_directory
from utils.headers import HeaderGenerator
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import random
import csv
import gzip
import os
from bs4 import BeautifulSoup, Tag
import time
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import ClassVar
import logging
from logging.handlers import RotatingFileHandler


@dataclass
class BaseScraper(ABC):
    site_config: Dict[str, Any]
    logger: logging.Logger = field(init=False)
    semaphore: asyncio.Semaphore = field(init=False)
    data_file: str = field(init=False)
    header_generator: HeaderGenerator = field(init=False)

    fieldnames: ClassVar[List[str]] = [
        'retailer', 'retailer_country', 'name', 'price', 'original_price',
        'currency', 'link', 'volume', 'abv', 'category', 'subcategory', 'brand', 'country',
        'region', 'description', 'rating', 'num_reviews', 'in_stock', 'image_url', 'product_id', 'series',
        'scraped_at'
    ]

    # Public methods
    async def scrape(self) -> None:
        self.logger.info(f"Starting scrape for {self.retailer}")
        page_num = 1
        total_products = 0

        try:
            while True:
                url = self._get_page_url(page_num)
                self.logger.info(f"Scraping page {page_num}: {url}")
                html_content = await self._make_request(url)

                if not html_content:
                    self.logger.warning(f"No content retrieved for page {
                                        page_num}. Stopping scrape.")
                    break

                soup = BeautifulSoup(html_content, 'html.parser')
                product_list = self._get_product_list(soup)

                if not product_list:
                    self.logger.info(f"No product list found on page {
                                     page_num}. Ending scrape.")
                    break

                products = self._parse_products(product_list)

                if not products:
                    self.logger.info(f"No products found on page {
                                     page_num}. Ending scrape.")
                    break

                detailed_products = await self.__fetch_product_details(products)
                self._save_products(detailed_products)
                total_products += len(detailed_products)
                self.logger.info(
                    f"Scraped {len(detailed_products)} products from page {page_num}.")

                if not self._has_next_page(soup, page_num):
                    self.logger.info("No next page found. Ending scrape.")
                    break

                page_num += 1

                if self.site_config.get('dev_mode') and page_num > int(self.site_config.get('page_limit')):
                    self.logger.info(f"Reached development mode page limit ({
                                     self.site_config['page_limit']}). Stopping scrape.")
                    break

                await asyncio.sleep(self.delay + random.uniform(1, 3))

        except Exception as e:
            self.logger.exception(
                f"An error occurred during scraping: {str(e)}")
        finally:
            self.logger.info(f"Scrape completed for {
                             self.retailer}. Total products scraped: {total_products}")

    # Abstract methods
    @abstractmethod
    def parse_product(self, item: Tag) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def parse_product_details(self, content: str) -> Dict[str, str]:
        pass

    @abstractmethod
    def _get_page_url(self, page_num: int) -> str:
        pass

    # Protected methods
    def _get_product_list(self, soup: BeautifulSoup) -> Optional[Tag]:
        selector = self.site_config['product_list_selector']
        return soup.select_one(selector)

    def _parse_products(self, product_list: Tag) -> List[Dict[str, Any]]:
        products = []
        product_items = product_list.select(
            self.site_config['product_item_selector'])

        for item in product_items:
            try:
                product = self.parse_product(item)
                if product:
                    products.append(product)
            except Exception as e:
                self.logger.error(f"Error parsing product: {e}")
        return products

    def _has_next_page(self, soup: BeautifulSoup, current_page_num: int) -> bool:
        next_page_selector = self.site_config.get('next_page_selector')
        return soup.select_one(next_page_selector) is not None if next_page_selector else True

    def _get_data_directory(self) -> str:
        now = datetime.now()
        return os.path.join('data', 'raw', str(now.year), f"{now.month:02d}", f"{now.day:02d}")

    def _get_data_filename(self) -> str:
        return os.path.join(self.data_directory, f"{self.retailer.lower().replace(' ', '_')}-{uuid.uuid4()}.csv.gz")

    def _init_data_file(self):
        ensure_directory(os.path.dirname(self.data_file))
        if not os.path.exists(self.data_file):
            with gzip.open(self.data_file, 'wt', encoding='utf-8', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                writer.writeheader()
            self.logger.info(f"Created new data file: {self.data_file}")

    def _save_products(self, products: List[Dict[str, Any]]):
        self.logger.info(f"Saving {len(products)} products to {
                         self.data_file}")
        with gzip.open(self.data_file, 'at', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
            for product in products:
                product['retailer'] = self.retailer
                product['retailer_country'] = self.retailer_country
                writer.writerow(product)
                self.logger.debug(f"Saved product: {product['name']}")
        self.logger.info(f"Successfully saved {len(products)} products")

    async def _make_request(self, url: str, is_detail_page: bool = False) -> Optional[str]:
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.debug(f"Attempting to fetch URL: {
                                  url} (Attempt {attempt}/{self.retries})")
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(user_agent=self.header_generator.generate()['User-Agent'])
                    page = await context.new_page()
                    await page.goto(url, wait_until="networkidle", timeout=60000)
                    self.logger.info(f"Navigated to: {page.url}")

                    await self._wait_for_content(page, is_detail_page)

                    content = await page.content()
                    await context.close()
                    await browser.close()
                    await asyncio.sleep(self.delay + random.uniform(0, 1))
                    self.logger.debug(f"Successfully fetched URL: {url}")
                    return content
            except PlaywrightTimeoutError as e:
                self.logger.warning(f"Timeout when fetching {url}: {e}")
            except Exception as e:
                self.logger.error(f"Error fetching {url}: {e}", exc_info=True)

            if attempt == self.retries:
                self.logger.error(f"Failed to fetch {url} after {
                                  self.retries} attempts.")
                return None
            else:
                backoff_time = self.delay * (2 ** attempt)
                self.logger.info(f"Retrying in {backoff_time} seconds...")
                await asyncio.sleep(backoff_time)
        return None

    async def _wait_for_content(self, page, is_detail_page: bool):
        if not is_detail_page:
            await page.wait_for_selector(self.site_config['product_list_selector'], timeout=60000)
        else:
            await page.wait_for_selector(self.site_config['detail_info_selector'], timeout=60000)

    # Private methods
    async def __fetch_product_details(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tasks = [self.__fetch_and_parse_product(
            product) for product in products]
        return await asyncio.gather(*tasks)

    async def __fetch_and_parse_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        async with self.semaphore:
            if self.site_config.get('fetch_details', True):
                details = await self.__fetch_single_product_details(product['link'])
                if details:
                    product.update(details)
            product['scraped_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
            return product

    async def __fetch_single_product_details(self, url: str) -> Optional[Dict[str, str]]:
        content = await self._make_request(url, is_detail_page=True)
        return self.parse_product_details(content) if content else None

    # Setup methods
    def __post_init__(self):
        self.header_generator: HeaderGenerator = HeaderGenerator()
        self.retailer: str = self.site_config['name']
        self.retailer_country: str = self.site_config['retailer_country']
        self.logger: logging.Logger = self.__setup_logger()
        self.headers: Dict[str, str] = self.site_config.get('headers', {})
        self.base_url: str = self.site_config['base_url']
        self.delay: int = self.site_config.get('delay', 1)
        self.retries: int = self.site_config.get('retries', 3)
        self.data_directory: str = self._get_data_directory()
        ensure_directory(self.data_directory)
        self.data_file: str = self._get_data_filename()
        self._init_data_file()
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(5)

    def __setup_logger(self) -> logging.Logger:
        logger = logging.getLogger(self.retailer)
        logger.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_format)

        # File handler
        log_file = f"logs/{self.retailer.lower()}_scraper.log"
        ensure_directory(os.path.dirname(log_file))
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        return logger
