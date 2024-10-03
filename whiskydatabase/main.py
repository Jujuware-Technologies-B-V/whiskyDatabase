import asyncio
import os
import yaml
from dotenv import load_dotenv
from typing import Dict, Any
from scrapers.web_scraper import WebScraper
from scrapers.network_scraper import NetworkScraper
from scrapers.base_scraper import BaseScraper
from scrapers.shopify_scraper import ShopifyScraper

load_dotenv()

CONFIG_DIR = 'configs'
SITES_DIR = os.path.join(CONFIG_DIR, 'sites')
MAX_CONCURRENT_SCRAPERS = int(os.getenv('MAX_CONCURRENT_SCRAPERS', 5))


def load_yaml(file_path: str) -> Dict[str, Any]:
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def load_fields_config(category: str) -> Dict[str, Any]:
    fields_file = os.path.join(SITES_DIR, category, "fields.yaml")
    if os.path.exists(fields_file):
        return load_yaml(fields_file)
    return {}


def load_and_merge_config(category: str, site_file: str) -> Dict[str, Any]:
    site_config = load_yaml(site_file)
    fields_config = load_fields_config(category)

    # Merge configurations, with site_config overriding fields_config
    merged_config = {**fields_config, **site_config}
    merged_config['category'] = category  # Add category to the config
    return merged_config


def load_all_configs() -> Dict[str, Dict[str, Any]]:
    configs = {}
    for category in os.listdir(SITES_DIR):
        category_path = os.path.join(SITES_DIR, category)
        if os.path.isdir(category_path):
            for filename in os.listdir(category_path):
                if filename.endswith(('.yaml', '.yml')) and filename != 'fields.yaml':
                    site_name = f"{category}_{filename.rsplit('.', 1)[0]}"
                    file_path = os.path.join(category_path, filename)
                    configs[site_name] = load_and_merge_config(
                        category, file_path)
    return configs


async def bound_scrape(scraper: BaseScraper, semaphore: asyncio.Semaphore):
    async with semaphore:
        await scraper.scrape()


def create_scraper(site_config: Dict[str, Any]) -> BaseScraper:
    scraper_type = site_config.get('scraper_type', 'web').lower()

    if scraper_type == 'web':
        return WebScraper(site_config)
    elif scraper_type == 'network':
        return NetworkScraper(site_config)
    elif scraper_type == 'shopify':
        return ShopifyScraper(site_config)

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
