from dataclasses import dataclass
from typing import Dict, Any, List, Union
from scrapers.base_scraper import BaseScraper
from playwright.async_api import async_playwright
import json
import asyncio
from jmespath import search


@dataclass
class NetworkScraper(BaseScraper):
    def __post_init__(self):
        super().__post_init__()
        self.request_url = self.site_config['request_url']
        self.request_method = self.site_config.get('request_method', 'GET')
        self.request_payload = self.site_config.get('request_payload', {})
        self.response_mapping = self.site_config['response_mapping']
        self.dev_mode = self.site_config.get('dev_mode', False)
        self.page_limit = self.site_config.get('page_limit', float('inf'))

    async def scrape(self) -> None:
        self.logger.info(
            f"Starting network request scrape for {self.retailer}")
        if self.dev_mode:
            self.logger.info(f"Running in dev mode. Page limit: {
                             self.page_limit}")
        total_products = 0
        page = 1

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=self.header_generator.generate()['User-Agent'])
            page_context = await context.new_page()

            try:
                while page <= self.page_limit:
                    self.request_payload['page'] = page
                    full_url = f"{self.request_url}?{
                        '&'.join([f'{k}={v}' for k, v in self.request_payload.items()])}"
                    self.logger.debug(f"Requesting URL for page {
                                      page}: {full_url}")

                    response = await page_context.goto(full_url, wait_until="networkidle")

                    if response.ok:
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
                    else:
                        self.logger.error(f"Failed to fetch data for page {
                                          page}: Status {response.status}")
                        break

            except Exception as e:
                self.logger.error(f"An error occurred during scraping: {
                                  str(e)}", exc_info=True)

            finally:
                await context.close()
                await browser.close()

        self.logger.info(f"Network request scrape completed for {
                         self.retailer}. Total products scraped: {total_products}")

    def parse_response(self, json_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        products = []
        items = search(self.response_mapping['root'], json_response) or []

        if not isinstance(items, list):
            self.logger.error(f"Unexpected response structure: {type(items)}")
            return products

        for item in items:
            product = {}
            for field, mapping in self.response_mapping['fields'].items():
                value = search(mapping, item)
                product[field] = value
            products.append(product)

        self.logger.debug(f"Parsed {len(products)} products")
        return products
