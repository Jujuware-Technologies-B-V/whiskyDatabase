# scrapers/drankdozijn_scraper.py

from scrapers.base_scraper import BaseScraper
from bs4 import BeautifulSoup, Tag
from typing import Dict, Optional, Any
import re


class DrankDozijnScraper(BaseScraper):
    def __init__(self, site_config: Dict[str, Any]):
        super().__init__(site_config)

    def parse_product(self, item: Tag) -> Optional[Dict[str, Any]]:
        try:
            name_elem = item.select_one(self.site_config['name_selector'])
            price_elem = item.select_one(self.site_config['price_selector'])
            link_elem = item.select_one(self.site_config['link_selector'])

            if name_elem and price_elem and link_elem:
                name = name_elem.get_text(strip=True)
                price = self.parse_price(price_elem.get_text(strip=True))
                link = self.base_url + link_elem['href']

                return {
                    'name': name,
                    'price': price,
                    'link': link,
                }
        except Exception as e:
            self.logger.error(f"Error parsing product: {e}")
        return None

    def parse_price(self, price_string: str) -> str:
        price_string = re.sub(r'[^\d,]', '', price_string)
        price_string = price_string.replace(',', '.')
        return price_string

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
        return details
