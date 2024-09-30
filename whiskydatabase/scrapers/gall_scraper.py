from scrapers.base_scraper import BaseScraper
from bs4 import BeautifulSoup, Tag
from typing import List, Dict, Optional, Any
import time
import random
import csv
import gzip
import os
from utils.helpers import get_date_string
import re


class GallScraper(BaseScraper):
    def __init__(self, site_config: Dict[str, Any]):
        super().__init__(site_config)

    def scrape(self) -> None:
        page_num: int = 0
        total_products: int = 0

        while True:
            url: str = self.site_config['pagination_url'].format(page_num * 12)
            self.logger.info(f"Scraping page {page_num + 1}: {url}")
            html_content: Optional[str] = self.make_request(url)

            if html_content is None:
                self.logger.warning(f"No content retrieved for page {
                                    page_num + 1}. Stopping scrape.")
                break

            soup: BeautifulSoup = BeautifulSoup(html_content, 'html.parser')
            product_list: List[Tag] = soup.select(
                self.site_config['product_list_selector'])

            if not product_list:
                self.logger.info(f"No product list found on page {
                                 page_num + 1}. Ending scrape.")
                break

            products: List[Dict[str, str]] = self.parse_products(
                product_list[0])

            if not products:
                self.logger.info(f"No products found on page {
                                 page_num + 1}. Ending scrape.")
                break

            self.save_products(products)
            total_products += len(products)
            self.logger.info(
                f"Scraped {len(products)} products from page {page_num + 1}.")

            page_num += 1
            time.sleep(self.delay + random.uniform(1, 3))

        self.logger.info(f"Total products scraped from {
                         self.site_config['name']}: {total_products}")

    def parse_products(self, product_list: Tag) -> List[Dict[str, str]]:
        products: List[Dict[str, str]] = []
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

                    details: Optional[Dict[str, str]
                                      ] = self.fetch_product_details(link)

                    product_data: Dict[str, str] = {
                        'name': name,
                        'price': price,
                        'link': link,
                        'volume': details.get('volume', '') if details else '',
                        'abv': details.get('abv', '') if details else '',
                        'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
                    }

                    products.append(product_data)
            except Exception as e:
                self.logger.error(f"Error parsing product: {e}")
                continue

        return products

    def parse_price(self, price_string: str) -> str:
        # Remove any newline characters and extra spaces
        price_string = ' '.join(price_string.split())

        # Check if the price ends with a dot
        if price_string.endswith('.'):
            return f"{price_string}99"

        # If it's already a valid price, return as is
        if re.match(r'^\d+\.\d{2}$', price_string):
            return price_string

        # If it's just a number, add .00
        if price_string.isdigit():
            return f"{price_string}.00"

        # If we can't parse it, return as is
        return price_string

    def parse_product_details(self, content: str) -> Dict[str, str]:
        soup: BeautifulSoup = BeautifulSoup(content, 'html.parser')
        details: Dict[str, str] = {}

        info_elem: Optional[Tag] = soup.select_one(
            self.site_config['detail_info_selector'])
        if info_elem:
            volume_match: Optional[re.Match] = re.search(
                r'(\d+)CL', info_elem.get_text())
            if volume_match:
                details['volume'] = volume_match.group(1)

            abv_match: Optional[re.Match] = re.search(
                r'(\d+(?:\.\d+)?)%', info_elem.get_text())
            if abv_match:
                details['abv'] = abv_match.group(1)

        return details
