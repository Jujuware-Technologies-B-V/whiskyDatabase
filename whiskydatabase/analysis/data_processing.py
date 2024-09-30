# analysis/data_processing.py

import pandas as pd
import glob
from rapidfuzz import process, fuzz
from utils import clean_text, parse_volume, parse_price


def load_data(data_folder='data'):
    """
    Loads all CSV files from the data folder and combines them into a single DataFrame.
    """
    files = glob.glob(f'{data_folder}/*.csv.gz')
    df_list = [pd.read_csv(file, compression='gzip') for file in files]
    combined_df = pd.concat(df_list, ignore_index=True)
    return combined_df


def normalize_prices(data):
    """
    Normalizes prices based on volume to get price per liter.
    Assumes volume is in centiliters (cl).
    """
    # Clean and parse volume and price
    data['volume_cl'] = data['volume'].apply(parse_volume)
    data['volume_l'] = data['volume_cl'] / 100  # Convert to liters
    data['price'] = data['price'].apply(parse_price)
    # Calculate price per liter
    data['price_per_liter'] = data['price'] / data['volume_l']
    return data


def standardize_product_names(data, threshold=90):
    """
    Uses rapidfuzz to group similar product names and assigns a standardized name or group ID.
    """
    # Clean product names
    data['name_clean'] = data['name'].apply(clean_text)

    # Combine attributes to create a matching key
    data['matching_key'] = data.apply(
        lambda row: f"{row['name_clean']} {row['volume']}cl {row['abv']}%", axis=1
    )

    unique_products = data['matching_key'].unique()
    product_to_group = {}
    group_id = 0

    for product in unique_products:
        if product not in product_to_group:
            # Find similar products
            matches = process.extract(
                product, unique_products, scorer=fuzz.token_sort_ratio, limit=None)
            # Keep matches above the threshold
            similars = [match for match, score,
                        _ in matches if score >= threshold]
            # Assign group ID to similar products
            for similar_product in similars:
                product_to_group[similar_product] = group_id
            group_id += 1

    data['product_group'] = data['matching_key'].map(product_to_group)
    return data


def preprocess_data(data_folder='data', threshold=90):
    """
    Loads data, normalizes prices, and standardizes product names.
    """
    data = load_data(data_folder)
    data = normalize_prices(data)
    data = standardize_product_names(data, threshold)
    return data


if __name__ == '__main__':
    data = preprocess_data()
    print(data.head())
