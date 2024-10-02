from .base_scraper import BaseScraper
from bs4 import BeautifulSoup, Tag
from typing import Dict, Optional, Any, List
import re
from urllib.parse import urljoin


class ClubWhiskyScraper(BaseScraper):
    def __init__(self, site_config: Dict[str, Any]):
        super().__init__(site_config)

    def parse_product(self, item: Tag) -> Optional[Dict[str, Any]]:
        try:
            name_elem = item.select_one(self.site_config['name_selector'])
            price_container = item.select_one(
                self.site_config['price_container_selector'])
            link_elem = item.select_one(self.site_config['link_selector'])
            image_elem = item.select_one(self.site_config['image_selector'])

            if name_elem and price_container and link_elem:
                # Attempt to extract current price using the primary selector
                current_price_elem = price_container.select_one(
                    self.site_config['current_price_selector'])

                if current_price_elem:
                    price = self._parse_price(
                        current_price_elem.get_text(strip=True))
                else:
                    # Fallback: Extract price directly from the price container
                    price_text = price_container.get_text(strip=True)
                    price = self._parse_price(price_text)
                    self.logger.debug(
                        "Using fallback selector for current price.")

                # Attempt to extract original price
                original_price_elem = price_container.select_one(
                    self.site_config['original_price_selector'])
                if original_price_elem:
                    original_price = self._parse_price(
                        original_price_elem.get_text(strip=True))
                else:
                    original_price = price  # If no original price, set it equal to current price

                # Extract and handle the product link
                href = link_elem.get('href')
                product_link = urljoin(self.base_url, href) if href else None

                if product_link:
                    product = {
                        'name': name_elem.get_text(strip=True),
                        'price': price,
                        'original_price': original_price,
                        'link': product_link,
                        'image_url': image_elem['src'] if image_elem else None,
                    }

                    # Extract product ID from the link
                    product_id_match = re.search(
                        r'/([^/]+)\.html$', product_link)
                    if product_id_match:
                        product['product_id'] = product_id_match.group(1)

                    self.logger.debug(f"Successfully parsed product: {
                        product['name']}")
                    return product
                else:
                    self.logger.warning("Missing product link.")
            else:
                self.logger.warning("Missing required elements for product.")
        except Exception as e:
            self.logger.error(f"Error parsing product: {e}", exc_info=True)
        return None

    def parse_product_details(self, content: str) -> Dict[str, str]:
        soup = BeautifulSoup(content, 'html.parser')
        details = {}

        specs_table = soup.select_one(self.site_config['detail_info_selector'])
        if specs_table:
            spec_lines = specs_table.select('.spec-line')
            for line in spec_lines:
                key = line.select_one('.spec-title:first-child')
                value = line.select_one('.spec-title:last-child')
                if key and value:
                    key_text = key.get_text(strip=True).replace(':', '')
                    value_text = value.get_text(strip=True)
                    if key_text == 'Merk':
                        details['brand'] = value_text
                    elif key_text == 'Land':
                        details['country'] = value_text
                    elif key_text == 'Regio':
                        details['region'] = value_text
                    elif key_text == 'Alcohol':
                        details['abv'] = value_text.replace('%', '').strip()
                    elif key_text == 'Inhoud':
                        details['volume'] = value_text
                    elif key_text == 'Type':
                        details['category'] = value_text

        description = soup.select_one(self.site_config['description_selector'])
        if description:
            details['description'] = description.get_text(strip=True)

        rating_score = soup.select_one(self.site_config['rating_selector'])
        if rating_score:
            filled_stars = rating_score.select('i.fa-star:not(.o)')
            details['rating'] = str(len(filled_stars))

        review_count = soup.select_one(
            self.site_config['review_count_selector'])
        if review_count:
            count = re.search(r'\d+', review_count.get_text(strip=True))
            if count:
                details['num_reviews'] = count.group()

        in_stock_elem = soup.select_one(self.site_config['in_stock_selector'])
        if in_stock_elem and 'vandaag verzonden' in in_stock_elem.get_text(strip=True).lower():
            details['in_stock'] = 'Yes'
        else:
            details['in_stock'] = 'No'

        return details

    def _get_page_url(self, page_num: int) -> str:
        return self.site_config['pagination_url'].format(page_num)

    def _parse_price(self, price_string: str) -> float:
        """
        Parses a price string and converts it to a float.
        Handles European number formats (comma as decimal separator) and others.

        Args:
            price_string (str): The price string to parse.

        Returns:
            float: The parsed price. Returns 0.0 if parsing fails.
        """
        # Remove any non-digit, non-separator characters (e.g., currency symbols)
        price_clean = re.sub(r'[^\d,.-]', '', price_string)

        # Find the positions of the last comma and last dot
        last_comma = price_clean.rfind(',')
        last_dot = price_clean.rfind('.')

        if last_comma > last_dot:
            # Comma is the decimal separator
            # Remove dots (thousands separators) and replace comma with dot
            price_clean = price_clean.replace('.', '').replace(',', '.')
        elif last_dot > last_comma:
            # Dot is the decimal separator
            # Remove commas (thousands separators)
            price_clean = price_clean.replace(',', '')
        else:
            # Only one type of separator exists
            if ',' in price_clean:
                # Assume comma is the decimal separator
                price_clean = price_clean.replace(',', '.')
            elif '.' in price_clean:
                # Assume dot is the decimal separator
                price_clean = price_clean.replace(',', '')
            # If no separator, leave as is

        try:
            parsed_price = float(price_clean)
            self.logger.debug(
                f"Parsed price '{price_string}' to {parsed_price}")
            return parsed_price
        except ValueError:
            self.logger.error(f"Unable to parse price: '{
                price_string}' (cleaned: '{price_clean}')")
            return 0.0
