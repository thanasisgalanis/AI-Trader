import MetaTrader5 as mt5
import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

load_dotenv()

# --- CONFIGURATION ---
NEWS_API_KEY = os.getenv("NEWS_API_KEY")  # Αντικατάστησε με το κλειδί από newsapi.org
SYMBOL = "EURUSD"                # Το ζεύγος προς διαπραγμάτευση
LOTS = 0.1                       # Μέγεθος θέσης (0.10 = 10,000 units)
THRESHOLD = 0.1                  # Ευαισθησία Sentiment (-1 έως 1)
INTERVAL = 5*60                   # Κύκλος ελέγχου (5 λεπτά)

class WindowsForexMasterAI:
    def __init__(self):
        # 1. Σύνδεση με το MT5 API
        if not mt5.initialize():
            print("❌ MT5 Initialization Failed. Βεβαιωθείτε ότι το MT5 είναι ανοιχτό.")
            quit()
        
        self.analyzer = SentimentIntensityAnalyzer()
        self.magic_number = 20260408 # Μοναδικό ID για τα trades του Bot
        
        print(f"--- [SYSTEM] Native Windows AI Engine Active ---")
        print(f"--- [INFO] Connected to {SYMBOL} | Interval: {INTERVAL/60}m ---\n")

    def is_market_open(self):
        """Weekend Guardrail: Σταματάει την ανάλυση τα Σαββατοκύριακα"""
        now = datetime.now()
        day = now.weekday() # 0=Mon, 5=Sat, 6=Sun
        hour = now.hour
        if day == 5 or (day == 4 and hour >= 23) or (day == 6 and hour < 23):
            return False
        return True

    def fetch_live_news(self):
        """Data Stage: Συλλογή ειδήσεων σε πραγματικό χρόνο"""
        url = f'https://newsapi.org/v2/everything?q=EUR+USD+ECB+Fed&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}'
        try:
            response = requests.get(url)
            data = response.json()
            articles = data.get('articles', [])
            return [a['title'] for a in articles[:10]]
        except Exception as e:
            print(f"❌ News API Error: {e}")
            return []

    def check_existing_positions(self):
        """Risk Guardrail: Αποφυγή over-trading"""
        positions = mt5.positions_get(symbol=SYMBOL)
        return len(positions) > 0

    def execute_trade(self, order_type):
        """Execution Stage: Άμεση αποστολή εντολής στον Broker"""
        symbol_info = mt5.symbol_info(SYMBOL)
        if symbol_info is None:
            print(f"❌ {SYMBOL} not found.")
            return

        # Υπολογισμός τιμών, SL και TP
        tick = mt5.symbol_info_tick(SYMBOL)
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        point = symbol_info.point
        
        # SL στα 20 pips, TP στα 40 pips
        sl = price - 200 * point if order_type == mt5.ORDER_TYPE_BUY else price + 200 * point
        tp = price + 400 * point if order_type == mt5.ORDER_TYPE_BUY else price - 400 * point

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": SYMBOL,
            "volume": LOTS,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 10,
            "magic": self.magic_number,
            "comment": "AI News Sentiment Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Αποστολή εντολής
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Execution Failed: {result.comment} (Code: {result.retcode})")
        else:
            print(f"🚀 SUCCESS: {SYMBOL} {('BUY' if order_type==0 else 'SELL')} at {price}")

    def run_forever(self):
        """Autonomous Loop"""
        while True:
            current_time = datetime.now().strftime("%H:%M:%S")
            
            if not self.is_market_open():
                print(f"[{current_time}] 💤 Market Closed. Hibernating...")
            
            elif self.check_existing_positions():
                print(f"[{current_time}] ⏳ Position already active. Monitoring...")
            
            else:
                print(f"[{current_time}] 🟢 Scanning Live News...")
                headlines = self.fetch_live_news()
                if headlines:
                    scores = [self.analyzer.polarity_scores(h)['compound'] for h in headlines]
                    avg_score = sum(scores) / len(scores)
                    
                    print(f"📊 Sentiment Score: {avg_score:.4f}")
                    
                    if avg_score > THRESHOLD:
                        self.execute_trade(mt5.ORDER_TYPE_BUY)
                    elif avg_score < -THRESHOLD:
                        self.execute_trade(mt5.ORDER_TYPE_SELL)
                    else:
                        print("😴 Neutral Sentiment. No action.")

            print(f"⏳ Next cycle in {INTERVAL/60} minutes.\n")
            time.sleep(INTERVAL)

if __name__ == "__main__":
    bot = WindowsForexMasterAI()
    try:
        bot.run_forever()
    except KeyboardInterrupt:
        mt5.shutdown()
        print("\n--- [SYSTEM] Bot stopped by user ---")