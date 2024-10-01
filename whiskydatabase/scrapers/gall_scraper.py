# scrapers/gall_scraper.py

from .base_scraper import BaseScraper
from bs4 import BeautifulSoup, Tag
from typing import Dict, Optional, Any
import re


class GallScraper(BaseScraper):
    def __init__(self, site_config: Dict[str, Any]):
        super().__init__(site_config)

    # Abstract method implementations
    def parse_product(self, item: Tag) -> Optional[Dict[str, Any]]:
        try:
            name_elem = item.select_one(self.site_config['name_selector'])
            price_elem = item.select_one(self.site_config['price_selector'])
            link_elem = item.select_one(self.site_config['link_selector'])

            if name_elem and price_elem and link_elem:
                return {
                    'name': name_elem.get_text(strip=True),
                    'price': self.parse_price(price_elem.get_text(strip=True)),
                    'link': self.base_url + link_elem['href'],
                }
        except Exception as e:
            self.logger.error(f"Error parsing product: {e}")
        return None

    def parse_product_details(self, content: str) -> Dict[str, str]:
        soup = BeautifulSoup(content, 'html.parser')
        details = {}

        info_elem = soup.select_one(self.site_config['detail_info_selector'])
        if info_elem:
            volume_match = re.search(r'(\d+)CL', info_elem.get_text())
            if volume_match:
                details['volume'] = volume_match.group(1)
            abv_match = re.search(r'(\d+(?:\.\d+)?)%', info_elem.get_text())
            if abv_match:
                details['abv'] = abv_match.group(1)
        return details

    def _get_page_url(self, page_num: int) -> str:
        offset = (page_num - 1) * 12
        return self.site_config['pagination_url'].format(offset)

    # Protected methods
    def _parse_price(self, price_string: str) -> str:
        price_string = ' '.join(price_string.split())
        if price_string.endswith('.'):
            return f"{price_string}99"
        if re.match(r'^\d+\.\d{2}$', price_string):
            return price_string
        if price_string.isdigit():
            return f"{price_string}.00"
        return price_string
