import pandas as pd
import MetaTrader5 as mt5
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from datetime import datetime, timedelta

# 1. Φόρτωση του Kaggle CSV
# Αντικατάστησε το όνομα του αρχείου με αυτό που κατέβασες
df_news = pd.read_csv("inputs/forex_news_backtest.csv") 
df_news['date'] = pd.to_datetime(df_news['date'], format='ISO8601', utc=True)

analyzer = SentimentIntensityAnalyzer()

def run_historical_backtest(symbol, news_limit=100):
    if not mt5.initialize(): return
    
    results = []
    # Παίρνουμε ένα δείγμα ειδήσεων για το σύμβολο (ή γενικά οικονομικά)
    # Εδώ μπορείς να φιλτράρεις π.χ. df_news[df_news['stock'] == 'AAPL'] ή keywords
    sample_news = df_news.head(news_limit) 

    for index, row in sample_news.iterrows():
        headline = row['headline']
        news_time = row['date']
        
        # Sentiment Analysis
        score = analyzer.polarity_scores(headline)['compound']
        
        if abs(score) > 0.1: # Το THRESHOLD μας
            # Ζητάμε την τιμή από την MT5 εκείνη τη συγκεκριμένη στιγμή
            # Προσοχή: Η MT5 πρέπει να έχει φορτωμένα ιστορικά δεδομένα
            utc_from = news_time.timestamp()
            rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_H1, int(utc_from), 1)
            
            if rates is None or len(rates) == 0:
                print(f"❌ Δεν βρέθηκαν δεδομένα για το {symbol} στις {news_time}")
                continue # Προσπερνάει αυτή την είδηση
            else:
                entry_price = rates[0]['close']
                
                # Έλεγχος μετά από 24 ώρες (γιατί οι ειδήσεις σου έχουν μόνο ημερομηνία)
                future_time = int(utc_from + (24 * 3600)) 
                future_rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_H1, future_time, 1)
                
                if future_rates is not None and len(future_rates) > 0:
                    exit_price = future_rates[0]['close']
                    # Υπολογισμός profit σε Pips/Points
                    diff = exit_price - entry_price
                    profit = diff if score > 0 else -diff
    
    mt5.shutdown()
    return pd.DataFrame(results)

# Εκτέλεση
backtest_results = run_historical_backtest("XAUUSD", 500)
print(backtest_results)