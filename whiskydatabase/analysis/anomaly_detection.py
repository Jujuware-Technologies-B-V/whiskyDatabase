# analysis/anomaly_detection.py

import pandas as pd
from sklearn.ensemble import IsolationForest
from data_processing import preprocess_data


def detect_anomalies(data, contamination=0.1):
    anomalies = pd.DataFrame()
    data_ml = data[['product_group', 'price_per_liter', 'retailer']].dropna()

    for group_id in data_ml['product_group'].unique():
        group_data = data_ml[data_ml['product_group'] == group_id].copy()
        if len(group_data['retailer'].unique()) > 1:  # Ensure multiple retailers
            model = IsolationForest(
                contamination=contamination, random_state=42)
            model.fit(group_data[['price_per_liter']])
            group_data.loc[:, 'anomaly'] = model.predict(
                group_data[['price_per_liter']]) == -1
            anomalies = pd.concat(
                [anomalies, group_data[group_data['anomaly']]], ignore_index=True)

    # Merge anomalies with original data
    anomalies = anomalies.merge(
        data, on=['product_group', 'price_per_liter', 'retailer'], how='left')
    return anomalies


def main():
    data = preprocess_data()
    anomalies = detect_anomalies(data)

    print("Anomalies detected:")
    print(anomalies[['name', 'price', 'volume', 'price_per_liter', 'anomaly']])

    # Save anomalies to a CSV file
    anomalies.to_csv('anomalies.csv', index=False)


if __name__ == '__main__':
    main()
