# main.py

import asyncio
import os
import yaml
from dotenv import load_dotenv
from scrapers.beverage_scraper import BeverageScraper
from scrapers.base_scraper import BaseScraper

load_dotenv()

CONFIG_DIR = 'configs'
MAX_CONCURRENT_SCRAPERS = int(os.getenv('MAX_CONCURRENT_SCRAPERS', 50))


def load_all_configs(config_dir: str):
    configs = {}
    for filename in os.listdir(config_dir):
        if filename.endswith('.yaml') or filename.endswith('.yml'):
            site_name = filename.rsplit('.', 1)[0]
            with open(os.path.join(config_dir, filename), 'r') as f:
                configs[site_name] = yaml.safe_load(f)
    return configs


async def bound_scrape(scraper: BaseScraper, semaphore: asyncio.Semaphore):
    async with semaphore:
        await scraper.scrape()


def create_scraper(site_config: dict) -> BaseScraper:
    scraper_type = site_config.get('scraper_type', 'beverage')
    if scraper_type == 'beverage':
        return BeverageScraper(site_config)
    else:
        raise ValueError(f"Unknown scraper type: {scraper_type}")


async def main():
    scraper_tasks = []
    configs = load_all_configs(CONFIG_DIR)
    dev_mode = os.environ.get('SCRAPER_DEV_MODE', 'true').lower() == 'true'
    dev_page_limit = int(os.environ.get('DEV_PAGE_LIMIT', 1))
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPERS)

    for site_name, site_config in configs.items():
        if site_config.get('enabled', True):
            if dev_mode:
                site_config['dev_mode'] = True
                site_config['page_limit'] = dev_page_limit

            try:
                scraper = create_scraper(site_config)
                scraper_tasks.append(bound_scrape(scraper, semaphore))
            except ValueError as e:
                print(f"Error creating scraper for {site_name}: {str(e)}")

    # Run all scrapers with concurrency limits
    await asyncio.gather(*scraper_tasks)

if __name__ == '__main__':
    asyncio.run(main())
