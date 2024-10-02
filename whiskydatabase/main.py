# main.py

import asyncio
import os
from utils.helpers import load_config
from dotenv import load_dotenv
from scrapers.gall_scraper import GallScraper
from scrapers.whisky_exchange_scraper import WhiskyExchangeScraper
from scrapers.drankdozijn_scraper import DrankDozijnScraper

load_dotenv()


SCRAPER_MAP = {
    # 'whisky_exchange': WhiskyExchangeScraper,
    # 'gall': GallScraper,
    'drankdozijn': DrankDozijnScraper
}

# Development mode settings
DEV_MODE = os.environ.get('SCRAPER_DEV_MODE', 'true')
DEV_PAGE_LIMIT = os.environ.get('DEV_PAGE_LIMIT', 1)


async def main():
    scraper_tasks = []

    for site_name, scraper_class in SCRAPER_MAP.items():
        site_config = load_config(site_name)

        if DEV_MODE:
            site_config['dev_mode'] = True
            site_config['page_limit'] = DEV_PAGE_LIMIT

        scraper = scraper_class(site_config)
        scraper_tasks.append(scraper.scrape())

    # Run all scrapers concurrently
    await asyncio.gather(*scraper_tasks)

if __name__ == '__main__':
    asyncio.run(main())
