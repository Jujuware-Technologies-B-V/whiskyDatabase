from typing import Dict, Optional, List, Any
from bs4 import Tag
from dataclasses import dataclass
from .base_scraper import BaseScraper


@dataclass
class BeverageScraper(BaseScraper):
    def get_fieldnames(self) -> List[str]:
        return [
            'retailer', 'retailer_country', 'name', 'price', 'original_price',
            'currency', 'link', 'volume', 'abv', 'category', 'subcategory', 'brand', 'country',
            'region', 'description', 'rating', 'num_reviews', 'in_stock', 'image_url', 'product_id', 'series',
            'scraped_at'
        ]
