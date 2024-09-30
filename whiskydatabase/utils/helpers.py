# utils/helpers.py

import logging
import asyncio
import aiohttp
import yaml
import os
import datetime
from requests.exceptions import RequestException
import time
from forex_python.converter import CurrencyRates


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


async def fetch_exchange_rate(logger: logging.Logger) -> float:
    """Fetches the GBP to EUR exchange rate asynchronously."""
    exchange_rate = None
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.exchangerate-api.com/v4/latest/GBP') as resp:
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
