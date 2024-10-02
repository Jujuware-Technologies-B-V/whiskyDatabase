# main.py (Updated)

import asyncio
import os
import yaml
from utils.helpers import ensure_directory
from dotenv import load_dotenv
from scrapers.base_scraper import BaseScraper
from scrapers.scraper_factory import ScraperFactory

load_dotenv()

CONFIG_DIR = 'configs'
MAX_CONCURRENT_SCRAPERS = int(
    os.getenv('MAX_CONCURRENT_SCRAPERS', 50))  # Adjust as needed


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

            scraper = ScraperFactory.create_scraper(site_config)
            scraper_tasks.append(bound_scrape(scraper, semaphore))

    # Run all scrapers with concurrency limits
    await asyncio.gather(*scraper_tasks)

if __name__ == '__main__':
    asyncio.run(main())
