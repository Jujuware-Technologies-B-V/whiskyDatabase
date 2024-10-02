# main.py

import asyncio
import os
from utils.helpers import load_config
from dotenv import load_dotenv
from scrapers.gall_scraper import GallScraper
from scrapers.whisky_exchange_scraper import WhiskyExchangeScraper
from scrapers.clubwhisky_nl_scraper import ClubWhiskyScraper
from scrapers.drankdozijn_scraper import DrankDozijnScraper
from scrapers.whisky_nl_scraper import WhiskyNLScraper
from scrapers.heinemann_shop_scraper import HeinemannShopScraper
load_dotenv()


SCRAPER_MAP = {
    # 'whisky_exchange': WhiskyExchangeScraper,
    # 'gall': GallScraper,
    # 'drankdozijn': DrankDozijnScraper,
    # 'club_whisky': ClubWhiskyScraper,
    # 'whisky_nl': WhiskyNLScraper,
    'heinemann_shop': HeinemannShopScraper
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
