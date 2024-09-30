# analysis/utils.py

import re


def clean_text(text):
    """
    Cleans up text by removing unwanted characters, extra spaces, etc.
    """
    if not isinstance(text, str):
        return ''
    text = text.strip()
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    return text.lower()


def parse_volume(volume_str):
    """
    Parses volume string to get volume in centiliters.
    """
    if isinstance(volume_str, str):
        volume_str = volume_str.lower().replace('cl', '').replace('ml', '').strip()
        try:
            volume = float(volume_str)
            return volume
        except ValueError:
            return None
    elif isinstance(volume_str, (int, float)):
        return float(volume_str)
    else:
        return None


def parse_price(price_str):
    """
    Parses price string to get price as float.
    """
    if isinstance(price_str, str):
        price_str = price_str.replace(
            '€', '').replace('$', '').replace('£', '')
        price_str = price_str.replace(',', '.').strip()
        try:
            price = float(price_str)
            return price
        except ValueError:
            return None
    elif isinstance(price_str, (int, float)):
        return float(price_str)
    else:
        return None
