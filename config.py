import os
from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

SYMBOLS_CONFIG = {
    # MAJOR FOREX
    "EURUSD": ["EUR", "ECB", "Eurozone", "Fed", "USD"],
    "GBPUSD": ["GBP", "Pound", "BoE", "London", "USD"],
    "USDJPY": ["JPY", "Yen", "BoJ", "Tokyo", "USD"],
    
    # COMMODITY FOREX
    "AUDUSD": ["AUD", "RBA", "China", "Iron Ore", "Australia"],
    "USDCAD": ["CAD", "BoC", "Oil", "Crude", "WTI", "Canada"],
    
    # METALS
    "XAUUSD": ["Gold", "XAU", "Inflation", "Safe Haven", "Gold Prices"],
}

LOTS = 0.1
THRESHOLD = 0.1
INTERVAL = 20 * 60
CORR_LIMIT = 0.75
EQUITY_PROTECTION_RATIO = 0.8
MAGIC_NUMBER = 20260408