# utils/logger.py
from utils.helpers import ensure_directory
from logging.handlers import RotatingFileHandler
import logging
import os


def setup_logger(retailer: str) -> logging.Logger:
    logger = logging.getLogger(retailer)
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)

    # File handler
    log_file = f"logs/{retailer.lower()}_scraper.log"
    ensure_directory(os.path.dirname(log_file))
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)

    # Prevent adding multiple handlers to the logger if it already has handlers
    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger
