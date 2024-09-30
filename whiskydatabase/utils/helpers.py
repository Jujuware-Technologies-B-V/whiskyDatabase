# utils/helpers.py

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


def convert_to_eur(price_gbp, logger):
    c = CurrencyRates()
    exchange_rate = None
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            exchange_rate = c.get_rate('GBP', 'EUR')
            logger.info(f"Fetched exchange rate: 1 GBP = {exchange_rate} EUR")
            break
        except RequestException as e:
            logger.warning(f"Request error fetching exchange rate (attempt {
                           attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(
                    "Max retries reached. Using fallback exchange rate.")
                exchange_rate = 1.15  # Fallback to a reasonable fixed rate
        except Exception as e:
            logger.error(f"Unexpected error fetching exchange rate: {e}")
            exchange_rate = 1.15  # Fallback to a reasonable fixed rate
            break

    logger.info(f"Using exchange rate: 1 GBP = {exchange_rate} EUR")
    return round(price_gbp * exchange_rate, 2)
