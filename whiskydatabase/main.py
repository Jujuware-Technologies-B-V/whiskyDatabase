import asyncio
import os
import yaml
from dotenv import load_dotenv
from typing import Dict, Any
from scrapers.web_scraper import WebScraper
from scrapers.network_scraper import NetworkScraper
from scrapers.base_scraper import BaseScraper

load_dotenv()

CONFIG_DIR = 'configs'
SECTORS_DIR = os.path.join(CONFIG_DIR, 'sectors')
SITES_DIR = os.path.join(CONFIG_DIR, 'sites')
MAX_CONCURRENT_SCRAPERS = int(os.getenv('MAX_CONCURRENT_SCRAPERS', 50))


def load_yaml(file_path: str) -> Dict[str, Any]:
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def load_sector_config(sector: str) -> Dict[str, Any]:
    sector_file = os.path.join(SECTORS_DIR, f"{sector}.yaml")
    return load_yaml(sector_file)


def load_and_merge_config(site_file: str) -> Dict[str, Any]:
    site_config = load_yaml(site_file)
    # Default to 'beverages' if not specified
    sector = site_config.get('sector', 'beverages')
    sector_config = load_sector_config(sector)

    # Merge configurations, with site_config overriding sector_config
    merged_config = {**sector_config, **site_config}
    return merged_config


def load_all_configs() -> Dict[str, Dict[str, Any]]:
    configs = {}
    for filename in os.listdir(SITES_DIR):
        if filename.endswith('.yaml') or filename.endswith('.yml'):
            site_name = filename.rsplit('.', 1)[0]
            file_path = os.path.join(SITES_DIR, filename)
            configs[site_name] = load_and_merge_config(file_path)
    return configs


async def bound_scrape(scraper: BaseScraper, semaphore: asyncio.Semaphore):
    async with semaphore:
        await scraper.scrape()


def create_scraper(site_config: Dict[str, Any]) -> BaseScraper:
    scraper_type = site_config.get('scraper_type', 'web')

    if scraper_type == 'web':
        return WebScraper(site_config)
    elif scraper_type == 'network':
        return NetworkScraper(site_config)

    raise ValueError(f"Unknown scraper type: {scraper_type}")


async def main():
    scraper_tasks = []
    configs = load_all_configs()
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
