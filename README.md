# Premium Whisky Price Scraper

## Overview

This project is designed to scrape premium whisky prices from online stores to detect pricing anomalies. The data is stored in compressed CSV files, with each execution saving to a new file to prevent overwriting previous data.

## Project Structure

- `configs/`: Configuration files for each site.
- `data/`: Compressed CSV files with scraped data.
- `logs/`: Log files for each site.
- `scrapers/`: Scraper classes.
- `utils/`: Utility functions.
- `main.py`: Entry point for the scraper.

## Usage

To run the scraper, use the following command:

```bash
python main.py --site <site_name>
```

Replace `<site_name>` with the name of the site you want to scrape.

## Requirements

- Python 3.7 or higher
- Poetry for dependency management

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/whisky_scraper.git
   cd whisky_scraper
   ```

2. **Install Dependencies**

   ```bash
   poetry install
   ```