# main.py

from utils.helpers import load_config
# from scrapers.whisky_exchange_scraper import WhiskyExchangeScraper
from scrapers.gall_scraper import GallScraper


def main():
    # site_name = 'whisky_exchange'
    # site_config = load_config(site_name)

    # scraper = WhiskyExchangeScraper(site_config)
    # scraper.scrape()

    site_name = 'gall'
    site_config = load_config(site_name)

    scraper = GallScraper(site_config)
    scraper.scrape()


if __name__ == '__main__':
    main()
