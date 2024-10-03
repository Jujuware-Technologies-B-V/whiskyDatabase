from dataclasses import dataclass, field
import logging
import asyncio
from typing import Dict, Any, List
import os
import uuid
import gzip
import csv
from datetime import datetime
from abc import ABC, abstractmethod

from utils.helpers import ensure_directory
from utils.headers import HeaderGenerator
from utils.logger import setup_logger


@dataclass
class BaseScraper(ABC):
    site_config: Dict[str, Any]
    logger: logging.Logger = field(init=False)
    semaphore: asyncio.Semaphore = field(init=False)
    data_file: str = field(init=False)
    header_generator: HeaderGenerator = field(init=False)
    fieldnames: List[str] = field(init=False)

    def __post_init__(self):
        self.header_generator = HeaderGenerator()
        self.retailer = self.site_config['name']
        self.retailer_country = self.site_config['retailer_country']
        self.currency = self.site_config['currency']
        self.logger = setup_logger(self.retailer)
        self.headers = self.site_config.get('headers', {})
        self.base_url = self.site_config['base_url']
        self.delay = self.site_config.get('delay', 1)
        self.retries = self.site_config.get('retries', 3)
        self.data_directory = self._get_data_directory()
        ensure_directory(self.data_directory)
        self.data_file = self._get_data_filename()
        self.semaphore = asyncio.Semaphore(5)
        self.max_timeout = self.site_config.get('max_timeout', 60000)
        self.fieldnames = self.site_config.get('fieldnames', [])
        self._init_data_file()

    @abstractmethod
    async def scrape(self) -> None:
        pass

    def get_fieldnames(self) -> List[str]:
        return self.fieldnames

    def _get_data_directory(self) -> str:
        now = datetime.now()
        return os.path.join('data', 'raw', str(now.year), f"{now.month:02d}", f"{now.day:02d}")

    def _get_data_filename(self) -> str:
        return os.path.join(self.data_directory, f"{self.retailer.lower().replace(' ', '_')}-{uuid.uuid4()}.csv.gz")

    def _init_data_file(self):
        ensure_directory(os.path.dirname(self.data_file))
        if not os.path.exists(self.data_file):
            with gzip.open(self.data_file, 'wt', encoding='utf-8', newline='') as csvfile:
                writer = csv.DictWriter(
                    csvfile, fieldnames=self.get_fieldnames())
                writer.writeheader()
            self.logger.info(f"Created new data file: {self.data_file}")

    def _save_products(self, products: List[Dict[str, Any]]):
        self.logger.info(f"Saving {len(products)} products to {
                         self.data_file}")
        with gzip.open(self.data_file, 'at', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.get_fieldnames())
            for product in products:
                product['retailer'] = self.retailer
                product['retailer_country'] = self.retailer_country
                product['currency'] = self.currency
                product['scraped_at'] = datetime.now().strftime(
                    '%Y-%m-%d %H:%M:%S')
                writer.writerow(product)
                self.logger.debug(f"Saved product: {product.get('name')}")
        self.logger.info(f"Successfully saved {len(products)} products")
