from typing import Dict, Any, List
from jmespath import search
import jmespath
from scrapers.base_scraper import BaseScraper
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import asyncio
import json
import logging


class ShopifyScraper(BaseScraper):
    async def scrape(self) -> None:
        self.logger.info(f"Starting Shopify scrape for {self.retailer}")
        self.request_payload = self.site_config.get('request_payload', {})
        self.pagination = self.site_config.get('pagination', {})
        self.request_method = self.site_config.get('request_method', 'GET')
        self.request_url = self.site_config['request_url']
        self.response_mapping = self.site_config['response_mapping']
        total_products = 0
        page = 1

        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(headless=True)
            context: BrowserContext = await browser.new_context(
                user_agent=self.header_generator.generate()['User-Agent']
            )
            page_context: Page = await context.new_page()

            try:
                while page <= self.page_limit:
                    self._update_payload(page)
                    full_url = self._construct_url()
                    self.logger.debug(f"Requesting Shopify URL for page {
                                      page}: {full_url}")

                    response = await page_context.goto(full_url, wait_until="networkidle", timeout=self.max_timeout)

                    if response and response.ok:
                        json_response = await response.json()
                        self.logger.debug(f"Raw JSON response: {
                                          json.dumps(json_response, indent=2)}")

                        products = self.parse_response(json_response)

                        if not products:
                            self.logger.info(f"No more products found on page {
                                             page}. Stopping pagination.")
                            break

                        self._save_products(products)
                        total_products += len(products)
                        self.logger.info(
                            f"Scraped {len(products)} products from page {page}")

                        if self.dev_mode and page >= self.page_limit:
                            self.logger.info(f"Reached dev mode page limit ({
                                             self.page_limit}). Stopping scrape.")
                            break

                        page += 1
                        await asyncio.sleep(self.delay)
                    elif response and response.status == 429:  # Too Many Requests
                        retry_after = int(response.headers.get(
                            'Retry-After', 60))  # Default to 60 seconds
                        self.logger.warning(f"Rate limited. Retrying after {
                                            retry_after} seconds.")
                        await asyncio.sleep(retry_after)
                    else:
                        status = response.status if response else 'No Response'
                        self.logger.error(f"Failed to fetch data for page {
                                          page}: Status {status}")
                        break

            except Exception as e:
                self.logger.error(f"An error occurred during Shopify scraping: {
                                  str(e)}", exc_info=True)

            finally:
                await context.close()
                await browser.close()

        self.logger.info(f"Shopify scrape completed for {
                         self.retailer}. Total products scraped: {total_products}")

    def _construct_url(self) -> str:
        if self.request_method.upper() == 'GET':
            query_params = '&'.join(
                [f"{k}={v}" for k, v in self.request_payload.items()])
            return f"{self.request_url}?{query_params}" if query_params else self.request_url
        return self.request_url

    def _update_payload(self, page: int):
        if self.pagination.get('type') == 'page':
            page_param = self.pagination.get('page_param', 'page')
            self.request_payload[page_param] = page
        elif self.pagination.get('type') == 'cursor':
            cursor_param = self.pagination.get('cursor_param', 'cursor')
            if hasattr(self, 'next_cursor'):
                self.request_payload[cursor_param] = self.next_cursor

    def parse_response(self, json_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        products = []
        items = search(self.response_mapping.get(
            'root', 'products'), json_response) or []

        if not isinstance(items, list):
            self.logger.error(f"Unexpected response structure: {type(items)}")
            return products

        for item in items:
            product = {}
            for field, mapping in self.response_mapping.get('fields', {}).items():
                try:
                    value = search(mapping, item)
                    if value is None and '||' in mapping:
                        value = self._handle_default(mapping)
                    product[field] = value
                except jmespath.exceptions.JMESPathError as e:
                    self.logger.error(f"Error parsing field '{
                                      field}' with mapping '{mapping}': {str(e)}")
                    product[field] = None

            products.append(product)

        self.logger.info(f"Parsed {len(products)} products")
        return products

    def _handle_default(self, mapping: str) -> Any:
        parts = mapping.split('||')
        if len(parts) > 1:
            default = parts[1].strip().strip('`').strip("'").strip('"')
            return default if default.lower() != 'null' else None
        return None
