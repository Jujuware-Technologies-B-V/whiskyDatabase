# scrapers/whisky_exchange_scraper.py

from scrapers.base_scraper import BaseScraper
from utils.helpers import fetch_exchange_rate
from bs4 import BeautifulSoup
import time
import random
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from typing import List, Dict, Any, Optional


class WhiskyExchangeScraper(BaseScraper):
    def __init__(self, site_config):
        super().__init__(site_config)
        self.exchange_rate = None
        self.semaphore = asyncio.Semaphore(5)

    async def scrape(self):
        """Main scraping method."""
        # Fetch exchange rate once
        self.exchange_rate = await fetch_exchange_rate(self.logger)

        page_num = 1
        total_products = 0

        while True:
            url = self.site_config['pagination_url'].format(page_num)
            self.logger.info(f"Scraping page {page_num}: {url}")
            html_content = await self.make_request(url)

            if html_content is None:
                self.logger.warning(f"No content retrieved for page {
                                    page_num}. Stopping scrape.")
                break

            soup = BeautifulSoup(html_content, 'html.parser')
            product_list = soup.select(
                self.site_config['product_list_selector'])

            if not product_list:
                self.logger.info(f"No product list found on page {
                                 page_num}. Ending scrape.")
                break

            products = self.parse_products(product_list[0])

            if not products:
                self.logger.info(f"No products found on page {
                                 page_num}. Ending scrape.")
                break

            # Process products
            for product in products:
                # Convert GBP to EUR using self.exchange_rate
                product['price'] = round(
                    product['price_gbp'] * self.exchange_rate, 2)
                product['scraped_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
                # Remove 'price_gbp' as it's not needed in the CSV output
                del product['price_gbp']

            # Save products
            self.save_products(products)
            total_products += len(products)
            self.logger.info(
                f"Scraped {len(products)} products from page {page_num}.")

            page_num += 1
            await asyncio.sleep(self.delay + random.uniform(1, 3))

        self.logger.info(f"Total products scraped from {
                         self.site_config['name']}: {total_products}")

    async def make_request(self, url: str) -> Optional[str]:
        """Makes a request to the given URL and returns the HTML content."""
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

                    # Implement scrolling specific to Whisky Exchange
                    await page.wait_for_selector(self.site_config['product_list_selector'], timeout=60000)
                    # Scroll to the bottom of the page to load all products
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

    def parse_products(self, product_list) -> List[Dict[str, Any]]:
        """Parses the product list and extracts product data."""
        products = []
        product_items = product_list.select(
            self.site_config['product_item_selector'])

        for item in product_items:
            try:
                name_elem = item.select_one(self.site_config['name_selector'])
                price_elem = item.select_one(
                    self.site_config['price_selector'])
                link_elem = item.select_one(self.site_config['link_selector'])
                meta_elem = item.select_one(self.site_config['meta_selector'])

                if name_elem and price_elem and link_elem:
                    name = name_elem.get_text(strip=True)
                    price_gbp = self.parse_price(
                        price_elem.get_text(strip=True))
                    link = self.base_url + link_elem['href']
                    meta = meta_elem.get_text(strip=True) if meta_elem else ""

                    volume, abv = self.parse_meta(meta)

                    product_data = {
                        'name': name,
                        'price_gbp': price_gbp,
                        'link': link,
                        'volume': volume,
                        'abv': abv,
                        # 'price' and 'scraped_at' will be added later
                    }

                    products.append(product_data)
            except Exception as e:
                self.logger.error(f"Error parsing product: {e}")
                continue

        return products

    def parse_price(self, price_string):
        """Parses the price string and converts it to a float."""
        return float(price_string.replace('£', '').replace(',', ''))

    def parse_meta(self, meta_string):
        """Parses the meta string to extract volume and alcohol by volume (ABV)."""
        if meta_string:
            parts = meta_string.split('/')
            volume = parts[0].strip() if len(parts) > 0 else ''
            abv = parts[1].strip() if len(parts) > 1 else ''

            volume = volume.replace('cl', '').strip() if volume else ''
            abv = abv.replace('%', '').strip() if abv else ''

            return volume, abv
        return '', ''

    def parse_product_details(self, content: str) -> Dict[str, str]:
        """Not used since all required data is available from the product list."""
        return {}
