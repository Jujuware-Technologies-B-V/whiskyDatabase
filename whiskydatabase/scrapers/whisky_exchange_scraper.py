# scrapers/whisky_exchange_scraper.py

from scrapers.base_scraper import BaseScraper
from utils.helpers import fetch_exchange_rate
from bs4 import BeautifulSoup, Tag
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from typing import Dict, Any, Optional
import asyncio
import random


class WhiskyExchangeScraper(BaseScraper):
    def __init__(self, site_config):
        super().__init__(site_config)
        self.exchange_rate = None

    async def scrape(self):
        self.exchange_rate = await fetch_exchange_rate(self.logger)
        await super().scrape()

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

                    await page.wait_for_selector(self.site_config['product_list_selector'], timeout=60000)
                    previous_height = None
                    while True:
                        current_height = await page.evaluate('document.body.scrollHeight')
                        if previous_height == current_height:
                            break
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        await asyncio.sleep(2)
                        previous_height = current_height

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

    def parse_product(self, item: Tag) -> Optional[Dict[str, Any]]:
        try:
            name_elem = item.select_one(self.site_config['name_selector'])
            price_elem = item.select_one(self.site_config['price_selector'])
            link_elem = item.select_one(self.site_config['link_selector'])
            meta_elem = item.select_one(self.site_config['meta_selector'])

            if name_elem and price_elem and link_elem:
                name = name_elem.get_text(strip=True)
                price_gbp = self.parse_price(price_elem.get_text(strip=True))
                link = self.base_url + link_elem['href']
                meta = meta_elem.get_text(strip=True) if meta_elem else ""

                volume, abv = self.parse_meta(meta)
                price = round(price_gbp * self.exchange_rate, 2)

                return {
                    'name': name,
                    'price': price,
                    'link': link,
                    'volume': volume,
                    'abv': abv,
                }
        except Exception as e:
            self.logger.error(f"Error parsing product: {e}")
        return None

    def parse_price(self, price_string):
        return float(price_string.replace('£', '').replace(',', ''))

    def parse_meta(self, meta_string):
        if meta_string:
            parts = meta_string.split('/')
            volume = parts[0].strip().replace(
                'cl', '').strip() if len(parts) > 0 else ''
            abv = parts[1].strip().replace(
                '%', '').strip() if len(parts) > 1 else ''
            return volume, abv
        return '', ''

    def parse_product_details(self, content: str) -> Dict[str, str]:
        return {}
