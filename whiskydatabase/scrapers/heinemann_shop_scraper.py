# scrapers/heinemann_shop_scraper.py

from .base_scraper import BaseScraper
from bs4 import BeautifulSoup, Tag
from typing import Dict, Optional, Any
import re
from datetime import datetime
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


class HeinemannShopScraper(BaseScraper):
    def __init__(self, site_config: Dict[str, Any]):
        super().__init__(site_config)

    def parse_product(self, item: Tag) -> Optional[Dict[str, Any]]:
        try:
            name_elem = item.select_one(self.site_config['name_selector'])
            price_elem = item.select_one(self.site_config['price_selector'])
            original_price_elem = item.select_one(
                self.site_config['original_price_selector'])
            link_elem = item.select_one(self.site_config['link_selector'])
            image_elem = item.select_one(self.site_config['image_selector'])

            if name_elem and price_elem and link_elem:
                product = {
                    'name': name_elem.get_text(strip=True),
                    'price': self._parse_price(price_elem.get_text(strip=True)),
                    'link': self.base_url + link_elem['href'],
                    'image_url': image_elem['src'] if image_elem else None,
                    'scraped_at': datetime.now().isoformat()
                }

                if original_price_elem:
                    product['original_price'] = self._parse_price(
                        original_price_elem.get_text(strip=True))

                # Extract product ID from the link
                product_id_match = re.search(r'/p/(\d+)/', product['link'])
                if product_id_match:
                    product['product_id'] = product_id_match.group(1)

                return product
        except Exception as e:
            self.logger.error(f"Error parsing product: {e}")
        return None

    def parse_product_details(self, content: str) -> Dict[str, str]:
        soup = BeautifulSoup(content, 'html.parser')
        details = {}

        try:
            # Extract product preview details
            product_preview = soup.select_one(
                self.site_config['detail_info_selector'])
            if product_preview:
                # Extract product image
                image_elem = product_preview.select_one(
                    self.site_config['product_image_selector'])
                if image_elem:
                    details['image_url'] = image_elem.get('src', '').strip()

            # Extract description
            description = soup.select_one(
                self.site_config['description_selector'])
            if description:
                details['description'] = description.get_text(strip=True)

            # Extract product details from the table
            details_table = soup.select_one(
                self.site_config['product_details_table_selector'])
            if details_table:
                rows = details_table.find_all(
                    'tr', class_='c-product-details-table__row')
                for row in rows:
                    key_elem = row.select_one('.c-product-details-table__key')
                    value_elem = row.select_one(
                        '.c-product-details-table__value')
                    if key_elem and value_elem:
                        key_text = key_elem.get_text(strip=True).lower()
                        value_text = value_elem.get_text(strip=True)

                        self.logger.debug(
                            f"Parsing key: '{key_text}' with value: '{value_text}'")

                        if 'trade name' in key_text:
                            details['category'] = value_text
                        elif 'item no.' in key_text:
                            details['product_id'] = value_text
                        elif 'whisky region' in key_text:
                            details['region'] = value_text
                        elif 'country of origin' in key_text:
                            details['country'] = value_text
                        elif 'alcohol by volume' in key_text:
                            # Extract numeric value and convert to float
                            abv_match = re.search(r'([\d,.]+)', value_text)
                            if abv_match:
                                abv_str = abv_match.group(1).replace(',', '.')
                                try:
                                    details['abv'] = float(abv_str)
                                except ValueError:
                                    self.logger.warning(
                                        f"Failed to parse ABV value: {abv_str}")
                        elif 'manufacturer information' in key_text:
                            # Extract brand from manufacturer information
                            brand_match = re.search(r'^([^,]+)', value_text)
                            if brand_match:
                                details['brand'] = brand_match.group(1).strip()

            else:
                self.logger.warning("Product details table not found.")

            # Extract stock information
            in_stock_elem = soup.select_one(
                self.site_config['in_stock_selector'])
            if in_stock_elem:
                stock_text = in_stock_elem.get_text(strip=True).lower()
                details['in_stock'] = 'Yes' if 'available' in stock_text else 'No'

        except Exception as e:
            self.logger.error(f"Error parsing product details: {
                              e}", exc_info=True)

        return details

    def _get_page_url(self, page_num: int) -> str:
        return self.site_config['pagination_url'].format(page_num)

    def _parse_price(self, price_string: str) -> float:
        # Remove any non-digit characters except for ',' and '.'
        price_string = re.sub(r'[^\d,.]', '', price_string)

        # Replace comma with dot if comma is used as decimal separator
        if ',' in price_string and '.' not in price_string:
            price_string = price_string.replace(',', '.')

        # Remove any thousands separators
        price_string = price_string.replace(',', '')

        # Convert to float
        try:
            return float(price_string)
        except ValueError:
            self.logger.error(f"Unable to parse price: {price_string}")
            return 0.0

    def _has_next_page(self, soup: BeautifulSoup, current_page_num: int) -> bool:
        next_page_link = soup.select_one(
            self.site_config['next_page_selector'])
        return next_page_link is not None and 'chevron-right-light' in next_page_link.select_one('use')['xlink:href']
