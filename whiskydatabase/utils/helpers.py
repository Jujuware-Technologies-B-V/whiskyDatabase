# utils/helpers.py

import logging
import asyncio
import aiohttp
import yaml
import os
import datetime
from urllib.parse import urljoin
import re
from typing import Optional, Any
import logging


def load_config(site_name):
    config_file = f'configs/{site_name}.yaml'
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Config file {config_file} does not exist.")
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config


def ensure_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


def get_date_string():
    return datetime.datetime.now().strftime('%Y%m%d')


async def fetch_exchange_rate_GBP_EUR(logger: logging.Logger) -> float:
    """Fetches the GBP to EUR exchange rate asynchronously."""
    exchange_rate = None
    max_retries = 3
    retry_delay = 5  # seconds
    API_URL = 'https://api.exchangerate-api.com/v4/latest/GBP'
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(API_URL) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        exchange_rate = data['rates']['EUR']
                        logger.info(f"Fetched exchange rate: 1 GBP = {
                                    exchange_rate} EUR")
                        return exchange_rate
                    else:
                        raise Exception(f"HTTP error: {resp.status}")
        except Exception as e:
            logger.warning(f"Error fetching exchange rate (attempt {
                           attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(
                    "Max retries reached. Using fallback exchange rate.")
                exchange_rate = 1.15  # Fallback to a reasonable fixed rate
                return exchange_rate

    # In case all retries failed
    logger.info(f"Using exchange rate: 1 GBP = {exchange_rate} EUR")
    return exchange_rate


def apply_parser(value: str, parser: str, field: str, pattern: Optional[str] = None, base_url: str = None) -> Any:
    logger = logging.getLogger(__name__)
    try:
        if parser == 'float':
            # Remove any non-numeric characters except '.' and ','
            value_clean = re.sub(r'[^\d.,]', '', value)
            # Replace comma with dot if comma is used as decimal separator
            if ',' in value_clean and '.' not in value_clean:
                value_clean = value_clean.replace(',', '.')
            # Remove thousands separators
            value_clean = value_clean.replace(',', '')
            return float(value_clean)
        elif parser == 'int':
            value_clean = re.sub(r'[^\d]', '', value)
            return int(value_clean)
        elif parser == 'bool':
            return 'available' in value.lower() or 'in stock' in value.lower()
        elif parser == 'url':
            # Use urljoin to handle relative and absolute URLs
            return urljoin(base_url, value)
        elif parser == 'regex':
            if pattern:
                match = re.search(pattern, value)
                if match:
                    return match.group(1)
                else:
                    logger.warning(f"Regex pattern '{pattern}' did not match for field '{
                        field}' with value: {value}")
                    return None
            else:
                logger.warning(
                    f"No regex pattern provided for field '{field}'")
                return None
        else:
            return value  # Default to string
    except ValueError:
        logger.warning(f"Failed to parse field '{
            field}' with value: {value}")
        return None
