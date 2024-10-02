# scrapers/drankdozijn_scraper.py

from .base_scraper import BaseScraper
from bs4 import BeautifulSoup, Tag
from typing import Dict, Optional, Any
import re
from datetime import datetime


class DrankDozijnScraper(BaseScraper):
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
                    'price': self._parse_price(price_elem['content']),
                    'currency': 'EUR',
                    'link': self.base_url + link_elem['href'],
                    'image_url': image_elem['src'] if image_elem else None,
                    'scraped_at': datetime.now().isoformat()
                }

                if original_price_elem:
                    product['original_price'] = self._parse_price(
                        original_price_elem.get_text(strip=True))

                # Extract product ID from the link
                product_id_match = re.search(
                    r'/artikel/(.+)$', product['link'])
                if product_id_match:
                    product['product_id'] = product_id_match.group(1)

                return product
        except Exception as e:
            self.logger.error(f"Error parsing product: {e}")
        return None

    def parse_product_details(self, content: str) -> Dict[str, str]:
        soup = BeautifulSoup(content, 'html.parser')
        details = {}

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
                    elif key_text == 'Categorie':
                        details['category'] = value_text
                    elif key_text == 'Merk':
                        details['brand'] = value_text
                    elif key_text == 'Land':
                        details['country'] = value_text
                    elif key_text == 'Smaakprofiel':
                        details['subcategory'] = value_text
                    elif key_text == 'Serie':
                        details['series'] = value_text

        description = soup.select_one(self.site_config['description_selector'])
        if description:
            details['description'] = description.get_text(strip=True)

        rating_score = soup.select_one(self.site_config['rating_selector'])
        if rating_score:
            details['rating'] = rating_score.get_text(strip=True)

        review_count = soup.select_one(
            self.site_config['review_count_selector'])
        if review_count:
            details['num_reviews'] = review_count.get_text(
                strip=True).replace('(', '').replace(')', '').split()[0]

        in_stock_elem = soup.select_one(self.site_config['in_stock_selector'])
        if in_stock_elem and 'Direct leverbaar' in in_stock_elem.get_text(strip=True):
            details['in_stock'] = 'Yes'
        else:
            details['in_stock'] = 'No'

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
