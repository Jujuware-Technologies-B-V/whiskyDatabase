# main.py

import asyncio
from utils.helpers import load_config
from scrapers.gall_scraper import GallScraper
from scrapers.whisky_exchange_scraper import WhiskyExchangeScraper
from scrapers.drankdozijn_scraper import DrankDozijnScraper


async def main():
    # Load configurations for all sites
    site_names = ['drankdozijn']
    scraper_tasks = []

    for site_name in site_names:
        site_config = load_config(site_name)
        if site_name == 'gall':
            scraper = GallScraper(site_config)
        elif site_name == 'whisky_exchange':
            scraper = WhiskyExchangeScraper(site_config)
        elif site_name == 'drankdozijn':
            scraper = DrankDozijnScraper(site_config)
        else:
            continue
        scraper_tasks.append(scraper.scrape())

    # Run all scrapers concurrently
    await asyncio.gather(*scraper_tasks)

if __name__ == '__main__':
    asyncio.run(main())
