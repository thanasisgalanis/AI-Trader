import os
import time
import requests
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

load_dotenv()

# --- CONFIGURATION ---
NEWS_API_KEY= os.getenv("NEWS_API_KEY")
# Η διαδρομή που επιβεβαιώσαμε ότι το MT5 "διαβάζει"
SIGNAL_PATH = "/Users/tgalanis/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files/signal.txt"
SYMBOL = "EURUSD"
THRESHOLD = 0.1  # Ευαισθησία: Όσο πιο μικρό, τόσο πιο συχνά κάνει trades
INTERVAL = 5 * 60

class ForexAutonomousAI:
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        print("--- [SYSTEM] Autonomous AI Engine Started ---")
        print(f"--- [INFO] Loop interval: {INTERVAL/60} minutes ---\n")

    def fetch_live_news(self):
        url = f'https://newsapi.org/v2/everything?q=EUR+USD+ECB+Fed&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}'
        try:
            response = requests.get(url)
            data = response.json()
            articles = data.get('articles', [])
            return [a['title'] for a in articles[:10]]
        except Exception as e:
            print(f"❌ News API Error: {e}")
            return []

    def send_to_mt5(self, signal):
        try:
            with open(SIGNAL_PATH, "w", encoding="utf-16-le") as f:
                f.write('\ufeff')
                f.write(signal)
                f.flush()
                os.fsync(f.fileno())
            return True
        except Exception as e:
            print(f"❌ Bridge Error: {e}")
            return False

    def run_forever(self):
        while True:
            current_time = time.strftime("%H:%M:%S")
            print(f"[{current_time}] Starting New Analysis Cycle...")
            
            headlines = self.fetch_live_news()
            if headlines:
                scores = [self.analyzer.polarity_scores(h)['compound'] for h in headlines]
                avg_score = sum(scores) / len(scores)
                
                decision = "BUY" if avg_score > THRESHOLD else "SELL" if avg_score < -THRESHOLD else "IDLE"
                print(f"📊 Sentiment Score: {avg_score:.4f} | Decision: {decision}")
                
                if decision != "IDLE":
                    if self.send_to_mt5(decision):
                        print(f"🚀 Signal '{decision}' synchronized with MT5.")
                else:
                    print("😴 Market is neutral. No action.")
            
            print(f"⏳ Waiting {INTERVAL/60} minutes for the next cycle...\n")
            time.sleep(INTERVAL)

if __name__ == "__main__":
    bot = ForexAutonomousAI()
    try:
        bot.run_forever()
    except KeyboardInterrupt:
        print("\n--- [SYSTEM] AI Bot stopped by user ---")