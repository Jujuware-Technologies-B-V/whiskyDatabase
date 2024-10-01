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
from bs4 import BeautifulSoup, Tag
import time
import uuid
from datetime import datetime


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
        self.data_directory = self.get_data_directory()
        ensure_directory(self.data_directory)
        self.data_file = self.get_data_filename()
        self.init_data_file()
        self.semaphore = asyncio.Semaphore(10)

    async def scrape(self) -> None:
        page_num = 1
        total_products = 0

        while True:
            url = self.get_page_url(page_num)
            self.logger.info(f"Scraping page {page_num}: {url}")
            html_content = await self.make_request(url)

            if html_content is None:
                self.logger.warning(f"No content retrieved for page {
                                    page_num}. Stopping scrape.")
                break

            soup = BeautifulSoup(html_content, 'html.parser')
            product_list = self.get_product_list(soup)

            if not product_list:
                self.logger.info(f"No product list found on page {
                                 page_num}. Ending scrape.")
                break

            products = self.parse_products(product_list)

            if not products:
                self.logger.info(f"No products found on page {
                                 page_num}. Ending scrape.")
                break

            # Create tasks for fetching product details concurrently
            detail_tasks = [self.fetch_and_parse_product(
                product) for product in products]
            detailed_products = await asyncio.gather(*detail_tasks)

            # Save products
            self.save_products(detailed_products)
            total_products += len(detailed_products)
            self.logger.info(
                f"Scraped {len(detailed_products)} products from page {page_num}.")

            if not self.has_next_page(soup, page_num):
                self.logger.info("No next page found. Ending scrape.")
                break

            page_num += 1
            await asyncio.sleep(self.delay + random.uniform(1, 3))

        self.logger.info(f"Total products scraped from {
                         self.site_config['name']}: {total_products}")

    def get_page_url(self, page_num: int) -> str:
        return self.site_config['pagination_url'].format(page_num)

    async def make_request(self, url: str, is_detail_page: bool = False) -> Optional[str]:
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.info(f"Attempting to fetch URL: {
                                 url} (Attempt {attempt}/{self.retries})")
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(user_agent=self.headers.get('User-Agent', 'Mozilla/5.0'))
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

    def get_product_list(self, soup: BeautifulSoup) -> Optional[Tag]:
        selector = self.site_config['product_list_selector']
        product_list = soup.select_one(selector)
        return product_list

    def parse_products(self, product_list: Tag) -> List[Dict[str, Any]]:
        products = []
        product_item_selector = self.site_config['product_item_selector']
        product_items = product_list.select(product_item_selector)

        for item in product_items:
            try:
                product = self.parse_product(item)
                if product:
                    products.append(product)
            except Exception as e:
                self.logger.error(f"Error parsing product: {e}")
                continue
        return products

    @abstractmethod
    def parse_product(self, item: Tag) -> Optional[Dict[str, Any]]:
        pass

    async def fetch_and_parse_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        async with self.semaphore:
            if self.site_config.get('fetch_details', True):
                details = await self.fetch_product_details(product['link'])
                if details:
                    product.update(details)
            product['scraped_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
            return product

    async def fetch_product_details(self, url: str) -> Optional[Dict[str, str]]:
        content = await self.make_request(url, is_detail_page=True)
        if content:
            return self.parse_product_details(content)
        return None

    def has_next_page(self, soup: BeautifulSoup, current_page_num: int) -> bool:
        next_page_selector = self.site_config.get('next_page_selector')
        if next_page_selector:
            next_page = soup.select_one(next_page_selector)
            return next_page is not None
        else:
            # If no selector is provided, assume pagination continues until no products
            return True

    def init_data_file(self):
        if not os.path.exists(self.data_file):
            with gzip.open(self.data_file, 'wt', encoding='utf-8', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                writer.writeheader()
            self.logger.info(f"Created new data file: {self.data_file}")

    def get_data_directory(self) -> str:
        now = datetime.now()
        return os.path.join('data', 'raw', str(now.year), f"{now.month:02d}", f"{now.day:02d}")

    def get_data_filename(self) -> str:
        return os.path.join(self.data_directory, f"{self.site_config['name'].lower().replace(' ', '_')}-{uuid.uuid4()}.csv.gz")

    def init_data_file(self):
        ensure_directory(os.path.dirname(self.data_file))
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
        pass
