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
import re
from urllib.parse import urljoin, urlparse


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

    def __post_init__(self):
        self.header_generator = HeaderGenerator()
        self.retailer = self.site_config['name']
        self.retailer_country = self.site_config['retailer_country']
        self.currency = self.site_config['currency']
        self.logger = self._setup_logger()  # Changed from __setup_logger to _setup_logger
        self.headers = self.site_config.get('headers', {})
        self.base_url = self.site_config['base_url']
        self.delay = self.site_config.get('delay', 1)
        self.retries = self.site_config.get('retries', 3)
        self.data_directory = self._get_data_directory()
        ensure_directory(self.data_directory)
        self.data_file = self._get_data_filename()
        self._init_data_file()
        self.semaphore = asyncio.Semaphore(5)

    # Public methods
    async def scrape(self) -> None:
        self.logger.info(f"Starting scrape for {self.retailer}")
        page_num = 1
        total_products = 0

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=self.header_generator.generate()['User-Agent'])
                while True:
                    url = self._get_page_url(page_num)
                    self.logger.info(f"Scraping page {page_num}: {url}")
                    html_content = await self._make_request(url, context)

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

                    detailed_products = await self.__fetch_product_details(products, context)
                    self._save_products(detailed_products)
                    total_products += len(detailed_products)
                    self.logger.info(
                        f"Scraped {len(detailed_products)} products from page {page_num}.")

                    if not self._has_next_page(soup, page_num):
                        self.logger.info("No next page found. Ending scrape.")
                        break

                    page_num += 1

                    if self.site_config.get('dev_mode') and page_num > int(self.site_config.get('page_limit', 1)):
                        self.logger.info(f"Reached development mode page limit ({
                                         self.site_config['page_limit']}). Stopping scrape.")
                        break

                    await asyncio.sleep(self.delay + random.uniform(1, 3))

                await context.close()
                await browser.close()

        except Exception as e:
            self.logger.exception(
                f"An error occurred during scraping: {str(e)}")
        finally:
            self.logger.info(f"Scrape completed for {
                             self.retailer}. Total products scraped: {total_products}")

    # Parsing methods
    def _get_product_list(self, soup: BeautifulSoup) -> Optional[Tag]:
        selector = self.site_config['product_list_selector']
        return soup.select_one(selector)

    def _parse_products(self, product_list: Tag) -> List[Dict[str, Any]]:
        products = []
        product_items = product_list.select(
            self.site_config['product_item_selector'])
        self.logger.debug(f'Found {len(product_items)} product items.')
        for item in product_items:
            try:
                product = self.parse_product(item)
                if product:
                    products.append(product)
            except Exception as e:
                self.logger.error(f"Error parsing product: {e}")
        self.logger.info(f'Parsed {len(products)} products.')
        return products

    def parse_product(self, item: Tag) -> Optional[Dict[str, Any]]:
        product = {}
        try:
            fields = self.site_config['fields']
            for field, config in fields.items():
                selector = config['selector']
                # Default parser is string
                parser = config.get('parser', 'str')
                pattern = config.get('pattern', None)  # Optional regex pattern
                # Optional absolute flag
                absolute = config.get('absolute', False)
                # Optional attribute to extract
                attribute = config.get('attribute', None)

                element = item.select_one(selector)
                if element:
                    if attribute:
                        raw_value = element.get(attribute, '').strip()
                    else:
                        raw_value = element.get_text(strip=True) if isinstance(
                            element, Tag) else element
                    parsed_value = self.apply_parser(
                        raw_value, parser, field, pattern)
                    product[field] = parsed_value
                else:
                    self.logger.warning(f"Selector '{selector}' not found for field '{
                                        field}' in {self.retailer}")
                    product[field] = None

            # Extract product_id if not already present
            if 'product_id' not in product or not product['product_id']:
                product['product_id'] = self._extract_product_id(
                    product.get('link', ''))

            return product if product.get('name') and product.get('price') else None

        except Exception as e:
            self.logger.error(f"Error parsing product: {e}")
            return None

    def apply_parser(self, value: str, parser: str, field: str, pattern: Optional[str] = None) -> Any:
        try:
            if parser == 'float':
                # Remove any non-numeric characters except '.' and ','
                value_clean = re.sub(r'[^\d.,]', '', value)
                # Replace comma with dot if comma is used as decimal separator
                if ',' in value_clean and '.' not in value_clean:
                    value_clean = value_clean.replace(',', '.')
                # Remove thousands separators
                value_clean = value_clean.replace(',', '')
                return float(value_clean)
            elif parser == 'int':
                value_clean = re.sub(r'[^\d]', '', value)
                return int(value_clean)
            elif parser == 'bool':
                return 'available' in value.lower() or 'in stock' in value.lower()
            elif parser == 'url':
                # Use urljoin to handle relative and absolute URLs
                return urljoin(self.base_url, value)
            elif parser == 'regex':
                if pattern:
                    match = re.search(pattern, value)
                    if match:
                        return match.group(1)
                    else:
                        self.logger.warning(f"Regex pattern '{pattern}' did not match for field '{
                                            field}' with value: {value}")
                        return None
                else:
                    self.logger.warning(
                        f"No regex pattern provided for field '{field}'")
                    return None
            else:
                return value  # Default to string
        except ValueError:
            self.logger.warning(f"Failed to parse field '{
                                field}' with value: {value}")
            return None

    def _extract_product_id(self, url: str) -> Optional[str]:
        # Attempt to extract product_id using all 'product_id' patterns from detail_fields
        product_id_field = self.site_config['detail_fields'].get(
            'product_id', {})
        parser = product_id_field.get('parser', 'str')
        pattern = product_id_field.get('pattern', None)
        if parser == 'regex' and pattern:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
            else:
                self.logger.warning(
                    f"Regex pattern '{pattern}' did not match for URL: {url}")
                return None
        elif parser == 'str':
            return url.split('/')[-2] if '/' in url else url
        else:
            # Fallback: return the entire URL or some default
            return url

    def _has_next_page(self, soup: BeautifulSoup, current_page_num: int) -> bool:
        next_page_selector = self.site_config.get('next_page_selector')
        if not next_page_selector:
            return False
        next_page = soup.select_one(next_page_selector)
        return next_page is not None

    def _get_page_url(self, page_num: int) -> str:
        return self.site_config['pagination_url'].format(page_num)

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
                product['currency'] = self.currency
                product['scraped_at'] = datetime.now().strftime(
                    '%Y-%m-%d %H:%M:%S')
                writer.writerow(product)
                self.logger.debug(f"Saved product: {product.get('name')}")
        self.logger.info(f"Successfully saved {len(products)} products")

    async def __fetch_product_details(self, products: List[Dict[str, Any]], context) -> List[Dict[str, Any]]:
        tasks = [self.__fetch_and_parse_product(
            product, context) for product in products]
        return await asyncio.gather(*tasks)

    async def __fetch_and_parse_product(self, product: Dict[str, Any], context) -> Dict[str, Any]:
        async with self.semaphore:
            if self.site_config.get('fetch_details', True):
                details = await self.__fetch_single_product_details(product['link'], context)
                if details:
                    product.update(details)
            return product

    async def __fetch_single_product_details(self, url: str, context) -> Optional[Dict[str, str]]:
        content = await self._make_request(url, context, is_detail_page=True)
        if content:
            return self.parse_product_details(content)
        return None

    def parse_product_details(self, content: str) -> Dict[str, str]:
        soup = BeautifulSoup(content, 'html.parser')
        details = {}
        detail_fields = self.site_config.get('detail_fields', {})
        for field, config in detail_fields.items():
            selector = config['selector']
            parser = config.get('parser', 'str')
            pattern = config.get('pattern', None)
            element = soup.select_one(selector)
            if element:
                raw_value = element.get_text(strip=True) if isinstance(
                    element, Tag) else element
                parsed_value = self.apply_parser(
                    raw_value, parser, field, pattern)
                details[field] = parsed_value
            else:
                details[field] = None
                self.logger.warning(f"Selector '{selector}' not found for detail field '{
                                    field}' in {self.retailer}")
        return details

    # Request handling
    async def _make_request(self, url: str, context, is_detail_page: bool = False) -> Optional[str]:
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.debug(f"Attempting to fetch URL: {
                                  url} (Attempt {attempt}/{self.retries})")
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=60000)
                self.logger.info(f"Navigated to: {page.url}")

                await self._wait_for_content(page, is_detail_page)

                content = await page.content()
                await page.close()
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
            detail_selector = self.site_config.get('detail_info_selector')
            if detail_selector:
                await page.wait_for_selector(detail_selector, timeout=60000)

    # Logging setup
    def _setup_logger(self) -> logging.Logger:
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

        # Prevent adding multiple handlers to the logger if it already has handlers
        if not logger.handlers:
            logger.addHandler(console_handler)
            logger.addHandler(file_handler)

        return logger
