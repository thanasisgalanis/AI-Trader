import os
from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

SYMBOLS_CONFIG = {
    "EURUSD": ["EUR", "ECB", "Eurozone", "Fed", "USD"],
    "GBPUSD": ["GBP", "Pound", "BoE", "London", "USD"],
    "XAUUSD": ["Gold", "XAU", "Inflation", "Safe Haven"],
    "USDJPY": ["JPY", "Yen", "BoJ", "Tokyo", "USD"]
}

LOTS = 0.1
THRESHOLD = 0.1
INTERVAL = 5 * 60
CORR_LIMIT = 0.75
EQUITY_PROTECTION_RATIO = 0.8
MAGIC_NUMBER = 20260408