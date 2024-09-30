# scrapers/drankdozijn_scraper.py

from scrapers.base_scraper import BaseScraper
from bs4 import BeautifulSoup, Tag
from typing import List, Dict, Optional, Any
import time
import random
import asyncio
import re


class DrankDozijnScraper(BaseScraper):
    def __init__(self, site_config: Dict[str, Any]):
        super().__init__(site_config)
        self.semaphore = asyncio.Semaphore(5)  # Limit concurrent tasks

    async def scrape(self) -> None:
        page_num: int = 1
        total_products: int = 0

        while True:
            url: str = self.site_config['pagination_url'].format(page_num)
            self.logger.info(f"Scraping page {page_num}: {url}")
            html_content: Optional[str] = await self.make_request(url)

            if html_content is None:
                self.logger.warning(f"No content retrieved for page {
                                    page_num}. Stopping scrape.")
                break

            soup: BeautifulSoup = BeautifulSoup(html_content, 'html.parser')
            product_list: List[Tag] = soup.select(
                self.site_config['product_list_selector'])

            if not product_list:
                self.logger.info(f"No product list found on page {
                                 page_num}. Ending scrape.")
                break

            products: List[Dict[str, Any]] = self.parse_products(
                product_list[0])

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

            # Check if there's a next page
            next_page = soup.select_one('a.next')
            if not next_page:
                self.logger.info("No next page found. Ending scrape.")
                break

            page_num += 1
            await asyncio.sleep(self.delay + random.uniform(1, 3))

        self.logger.info(f"Total products scraped from {
                         self.site_config['name']}: {total_products}")

    def parse_products(self, product_list: Tag) -> List[Dict[str, Any]]:
        products: List[Dict[str, Any]] = []
        product_items: List[Tag] = product_list.select(
            self.site_config['product_item_selector'])

        for item in product_items:
            try:
                name_elem: Optional[Tag] = item.select_one(
                    self.site_config['name_selector'])
                price_elem: Optional[Tag] = item.select_one(
                    self.site_config['price_selector'])
                link_elem: Optional[Tag] = item.select_one(
                    self.site_config['link_selector'])

                if name_elem and price_elem and link_elem:
                    name: str = name_elem.get_text(strip=True)
                    price: str = self.parse_price(
                        price_elem.get_text(strip=True))
                    link: str = self.base_url + link_elem['href']

                    product_data: Dict[str, Any] = {
                        'name': name,
                        'price': price,
                        'link': link,
                        # 'volume' and 'abv' will be filled later
                    }

                    products.append(product_data)
            except Exception as e:
                self.logger.error(f"Error parsing product: {e}")
                continue

        return products

    async def fetch_and_parse_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        async with self.semaphore:
            details = await self.fetch_product_details(product['link'])
            if details:
                product['volume'] = details.get('volume', '')
                product['abv'] = details.get('abv', '')
            else:
                product['volume'] = ''
                product['abv'] = ''
            product['scraped_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
            return product

    def parse_price(self, price_string: str) -> str:
        # Remove any non-digit characters except for the decimal point
        price_string = re.sub(r'[^\d,]', '', price_string)
        # Replace comma with dot for decimal point
        price_string = price_string.replace(',', '.')
        return price_string

    def parse_product_details(self, content: str) -> Dict[str, str]:
        soup: BeautifulSoup = BeautifulSoup(content, 'html.parser')
        details: Dict[str, str] = {}

        specs_table = soup.select_one(self.site_config['detail_info_selector'])
        if specs_table:
            rows = specs_table.find_all('tr')
            for row in rows:
                key = row.select_one('.key')
                value = row.select_one('.value')
                if key and value:
                    key_text = key.get_text(strip=True)
                    value_text = value.get_text(strip=True)
                    if key_text == 'Inhoud':
                        details['volume'] = value_text
                    elif key_text == 'Alcoholpercentage':
                        details['abv'] = value_text.replace('%', '').strip()

        return details
