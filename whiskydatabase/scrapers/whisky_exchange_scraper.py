# scrapers/whisky_exchange_scraper.py

from scrapers.base_scraper import BaseScraper
from bs4 import BeautifulSoup
import time
import random
from utils.helpers import get_date_string, convert_to_eur


class WhiskyExchangeScraper(BaseScraper):
    def __init__(self, site_config):
        super().__init__(site_config)

    def scrape(self):
        page_num = 1
        total_products = 0

        while True:
            url = self.site_config['pagination_url'].format(page_num)
            self.logger.info(f"Scraping page {page_num}: {url}")
            html_content = self.make_request(url)

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

            self.save_products(products)
            total_products += len(products)
            self.logger.info(
                f"Scraped {len(products)} products from page {page_num}.")

            page_num += 1
            time.sleep(self.delay + random.uniform(1, 3))

        self.logger.info(f"Total products scraped from {
                         self.site_config['name']}: {total_products}")

    def parse_products(self, product_list):
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
                    price_eur = convert_to_eur(price_gbp, self.logger)
                    link = self.base_url + link_elem['href']
                    meta = meta_elem.get_text(strip=True) if meta_elem else ""

                    volume, abv = self.parse_meta(meta)

                    product_data = {
                        'name': name,
                        'price': price_eur,
                        'link': link,
                        'volume': volume,
                        'abv': abv,
                        'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
                    }

                    products.append(product_data)
            except Exception as e:
                self.logger.error(f"Error parsing product: {e}")
                continue

        return products

    def parse_price(self, price_string):
        return float(price_string.replace('£', '').replace(',', ''))

    def parse_meta(self, meta_string):
        if meta_string:
            parts = meta_string.split('/')
            volume = parts[0].strip() if len(parts) > 0 else None
            abv = parts[1].strip() if len(parts) > 1 else None

            volume = volume.replace('cl', '').strip() if volume else None
            abv = abv.replace('%', '').strip() if abv else None

            return volume, abv
        return None, None
