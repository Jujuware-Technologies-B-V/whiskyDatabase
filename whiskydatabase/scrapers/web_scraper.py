import asyncio
import random
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag
from playwright.async_api import async_playwright, Page, BrowserContext, TimeoutError as PlaywrightTimeoutError
from typing import Dict, Any, List, Optional
from utils.helpers import apply_parser
from scrapers.base_scraper import BaseScraper


@dataclass
class WebScraper(BaseScraper):
    def __post_init__(self):
        super().__post_init__()
        self.product_list_selector = self.site_config['product_list_selector']
        self.product_item_selector = self.site_config['product_item_selector']
        self.fields = self.site_config['fields']
        self.detail_fields = self.site_config.get('detail_fields', {})

    async def scrape(self) -> None:
        self.logger.info(f"Starting web scrape for {self.retailer}")
        page_num = 1
        total_products = 0

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=self.header_generator.generate()['User-Agent'])

            while True:
                url = self._get_page_url(page_num)
                self.logger.info(f"Scraping page {page_num}: {url}")
                content = await self._make_request(url, context)

                if not content:
                    break

                soup = BeautifulSoup(content, 'html.parser')
                product_list = self._get_product_list(soup)

                if not product_list:
                    break

                products = self._parse_products(product_list)

                if not products:
                    break

                detailed_products = await self._fetch_product_details(products, context)
                self._save_products(detailed_products)
                total_products += len(detailed_products)

                if not self._has_next_page(soup, page_num):
                    break

                page_num += 1
                await asyncio.sleep(self.delay)

            await context.close()
            await browser.close()

        self.logger.info(f"Web scrape completed for {
                         self.retailer}. Total products scraped: {total_products}")

    def _get_product_list(self, soup: BeautifulSoup) -> Optional[Tag]:
        return soup.select_one(self.product_list_selector)

    def _parse_products(self, product_list: Tag) -> List[Dict[str, Any]]:
        products = []
        product_items = product_list.select(self.product_item_selector)
        self.logger.debug(f'Found {len(product_items)} product items.')
        for item in product_items:
            try:
                product = self._parse_product(item)
                if product:
                    products.append(product)
            except Exception as e:
                self.logger.error(f"Error parsing product: {e}")
        self.logger.info(f'Parsed {len(products)} products.')
        return products

    def _parse_product(self, item: Tag) -> Optional[Dict[str, Any]]:
        product = {}
        for field, config in self.fields.items():
            selector = config['selector']
            parser = config.get('parser', 'str')
            pattern = config.get('pattern', None)
            attribute = config.get('attribute', None)
            required = config.get('required', False)

            element = item.select_one(selector)
            if element:
                if attribute:
                    raw_value = element.get(attribute, '').strip()
                else:
                    raw_value = element.get_text(strip=True) if isinstance(
                        element, Tag) else element
                parsed_value = apply_parser(
                    raw_value, parser, field, pattern, self.base_url)
                product[field] = parsed_value
            elif required:
                self.logger.warning(f"Required field '{
                                    field}' not found for {self.retailer}")
                return None
            else:
                product[field] = None

        return product if product.get('name') and product.get('price') else None

    async def _fetch_product_details(self, products: List[Dict[str, Any]], context) -> List[Dict[str, Any]]:
        tasks = [self._fetch_and_parse_product(
            product, context) for product in products]
        return await asyncio.gather(*tasks)

    async def _fetch_and_parse_product(self, product: Dict[str, Any], context) -> Dict[str, Any]:
        async with self.semaphore:
            if self.site_config.get('fetch_details', True):
                details = await self._fetch_single_product_details(product['link'], context)
                if details:
                    product.update(details)
            return product

    async def _fetch_single_product_details(self, url: str, context) -> Optional[Dict[str, str]]:
        content = await self._make_request(url, context, is_detail_page=True)
        if content:
            return self._parse_product_details(content)
        return None

    def _parse_product_details(self, content: str) -> Dict[str, str]:
        soup = BeautifulSoup(content, 'html.parser')
        details = {}
        for field, config in self.detail_fields.items():
            selector = config['selector']
            parser = config.get('parser', 'str')
            pattern = config.get('pattern', None)
            required = config.get('required', False)
            element = soup.select_one(selector)
            if element:
                raw_value = element.get_text(strip=True) if isinstance(
                    element, Tag) else element
                parsed_value = apply_parser(
                    raw_value, parser, field, pattern, self.base_url)
                details[field] = parsed_value
            elif required:
                self.logger.warning(f"Required detail field '{
                                    field}' not found for {self.retailer}")
            else:
                details[field] = None
        return details

    def _get_page_url(self, page_num: int) -> str:
        return self.site_config['pagination_url'].format(page_num)

    def _has_next_page(self, soup: BeautifulSoup, page_num: int) -> bool:
        next_page_selector = self.site_config.get('next_page_selector')
        if not next_page_selector:
            return False
        next_page = soup.select_one(next_page_selector)
        return next_page is not None

    async def _make_request(self, url: str, context: BrowserContext, is_detail_page: bool = False) -> Optional[str]:
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.debug(f"Attempting to fetch URL: {
                                  url} (Attempt {attempt}/{self.retries})")
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=self.max_timeout)
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

    async def _wait_for_content(self, page: Page, is_detail_page: bool):
        if not is_detail_page:
            await page.wait_for_selector(self.product_list_selector, timeout=self.max_timeout)
        else:
            detail_selector = self.site_config.get('detail_info_selector')
            if detail_selector:
                await page.wait_for_selector(detail_selector, timeout=self.max_timeout)
