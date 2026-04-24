from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

DB_PATH = RAW_DATA_DIR / "rates.db"
PROCESSED_DATA_PATH = PROCESSED_DATA_DIR / "portfolio.parquet"
METADATA_PATH = PROCESSED_DATA_DIR / "portfolio_metadata.json"

for directory in (RAW_DATA_DIR, PROCESSED_DATA_DIR):
    directory.mkdir(parents=True, exist_ok=True)


NBP_API_BASE_URL = "https://api.nbp.pl/api/exchangerates/rates"
API_TIMEOUT_SECONDS = 15
API_LOOKBACK_BUFFER_DAYS = 7
NBP_MAX_DAYS_PER_REQUEST = 93


DEFAULT_INVESTMENT_AMOUNT_PLN = 1000.0
DEFAULT_HOLDING_PERIOD_DAYS = 30
DEFAULT_START_DATE = date.today() - timedelta(days=DEFAULT_HOLDING_PERIOD_DAYS)
DEFAULT_ALLOCATION = {
    "USD": 0.30,
    "EUR": 0.40,
    "HUF": 0.30,
}

SUPPORTED_CURRENCIES = (
    "AUD",
    "CAD",
    "CHF",
    "CZK",
    "DKK",
    "EUR",
    "GBP",
    "HUF",
    "JPY",
    "NOK",
    "SEK",
    "USD",
)

CURRENCY_COLORS = {
    "USD": "#1d4ed8",
    "EUR": "#059669",
    "HUF": "#dc2626",
    "GBP": "#7c3aed",
    "CHF": "#ea580c",
    "JPY": "#0f766e",
    "CZK": "#9333ea",
    "AUD": "#2563eb",
    "CAD": "#ef4444",
    "NOK": "#0ea5e9",
    "SEK": "#14b8a6",
    "DKK": "#f59e0b",
}


logger = logging.getLogger("inwestomat.pipeline")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)

logger.setLevel(logging.INFO)
logger.propagate = False
