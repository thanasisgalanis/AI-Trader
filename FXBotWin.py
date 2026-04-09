import MetaTrader5 as mt5
import requests
import time
import os
import pandas as pd
import numpy as np
import json
import threading
from datetime import datetime
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

load_dotenv()

# --- CONFIGURATION ---
NEWS_API_KEY = os.getenv("NEWS_API_KEY") 
SYMBOLS_CONFIG = {
    "EURUSD": ["EUR", "ECB", "Eurozone", "Fed", "USD"],
    "GBPUSD": ["GBP", "Pound", "BoE", "London", "USD"],
    "XAUUSD": ["Gold", "XAU", "Inflation", "Safe Haven"],
    "USDJPY": ["JPY", "Yen", "BoJ", "Tokyo", "USD"]
}
LOTS = 0.1
THRESHOLD = 0.1
INTERVAL = 5*60 
CORR_LIMIT = 0.75
EQUITY_PROTECTION_RATIO = 0.8  # 20% Drawdown Kill Switch

class TradeLogger:
    def __init__(self):
        self.executed_file = "executed_trades.json"
        self.rejected_file = "virtual_backtest.json"

    def _append_json(self, file_name, data):
        if not os.path.exists(file_name):
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump([data], f, indent=4, ensure_ascii=False)
        else:
            with open(file_name, 'r+', encoding='utf-8') as f:
                try:
                    file_data = json.load(f)
                except json.JSONDecodeError:
                    file_data = []
                file_data.append(data)
                f.seek(0)
                f.truncate()
                json.dump(file_data, f, indent=4, ensure_ascii=False)

    def update_trade_result(self, ticket, profit, exit_price):
        if not os.path.exists(self.executed_file): return
        with open(self.executed_file, 'r+', encoding='utf-8') as f:
            trades = json.load(f)
            updated = False
            for trade in trades:
                if trade.get("ticket") == ticket and trade.get("status") == "OPEN":
                    trade["status"] = "CLOSED"
                    trade["exit_price"] = exit_price
                    trade["profit"] = round(profit, 2)
                    trade["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    updated = True
                    break
            if updated:
                f.seek(0)
                f.truncate()
                json.dump(trades, f, indent=4, ensure_ascii=False)

class MultiAssetForexAI:
    def __init__(self):
        if not mt5.initialize():
            print("❌ MT5 Initialization Failed.")
            quit()
        
        print("MT5 Python Library Version:", mt5.__version__)

        self.analyzer = SentimentIntensityAnalyzer()
        self.logger = TradeLogger()
        self.magic_number = 20260408
        self.symbols = list(SYMBOLS_CONFIG.keys())
        self.running = True
        
        # Start Heartbeat Thread
        self.heartbeat_thread = threading.Thread(target=self.start_heartbeat, daemon=True)
        self.heartbeat_thread.start()

        print(f"--- [SYSTEM] Hybrid Master Engine Active ---")
        print(f"--- [INFO] Heartbeat & Kill-Switch: ACTIVE ---")

    def start_heartbeat(self):
        """Heartbeat Fix για Version 5.0.5735"""
        while self.running:
            try:
                # Στην έκδοση 2026, η MT5 δέχεται τα Global Variables κυρίως ως floats
                timestamp = float(time.time())
                
                # Δοκιμή της συγκεκριμένης σύνταξης για 5.0.5735
                success = mt5.global_variable_set("AI_ALIVE", timestamp)
                
                if not success:
                    # Εναλλακτική αν η παραπάνω επιστρέψει False
                    mt5.initialize()
            except:
                pass
            time.sleep(10)

    def account_protection(self):
        """Εσωτερικό Kill Switch για προστασία Equity"""
        acc = mt5.account_info()
        if acc is None: return False
        
        if acc.equity < acc.balance * EQUITY_PROTECTION_RATIO:
            print(f"🚨 CRITICAL: Equity {acc.equity} dropped below 20%. Emergency Stop.")
            self.emergency_shutdown()
            return False
        return True

    def emergency_shutdown(self):
        self.running = False
        positions = mt5.positions_get()
        if positions:
            for pos in positions:
                self.close_position(pos)
        print("🛡️ Safety Protocol: All positions closed. Bot stopped.")
        mt5.shutdown()
        os._exit(0)

    def fetch_global_news(self):
        query = "Forex OR Fed OR ECB OR Economy OR Inflation"
        url = f'https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}'
        try:
            response = requests.get(url, timeout=10)
            return response.json().get('articles', [])
        except Exception as e:
            print(f"⚠️ News API Timeout/Error: {e}")
            return []

    def get_market_structure(self, symbol):
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 200)
        if rates is None: return "NEUTRAL", 0, 0
        df = pd.DataFrame(rates)
        ema200 = df['close'].ewm(span=200, adjust=False).mean().iloc[-1]
        trend = "BULL" if df['close'].iloc[-1] > ema200 else "BEAR"
        recent = df.tail(100)
        return trend, recent['low'].min(), recent['high'].max()

    def get_filling_mode(self, symbol):
        si = mt5.symbol_info(symbol)
        if si is None: return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_FOK if si.filling_mode & 1 else mt5.ORDER_FILLING_IOC

    def is_too_correlated(self, new_symbol):
        """Risk Guardrail: Έλεγχος συσχέτισης με ανοιχτές θέσεις"""
        try:
            active = mt5.positions_get()
            if not active: return False, None, 0
            for pos in active:
                if pos.symbol == new_symbol: continue
                
                # Λήψη δεδομένων για συσχέτιση
                r1 = mt5.copy_rates_from_pos(new_symbol, mt5.TIMEFRAME_H1, 0, 50)
                r2 = mt5.copy_rates_from_pos(pos.symbol, mt5.TIMEFRAME_H1, 0, 50)
                
                if r1 is None or r2 is None: continue
                
                df = pd.DataFrame({
                    "s1": [x['close'] for x in r1], 
                    "s2": [x['close'] for x in r2]
                })
                corr = df.corr().iloc[0, 1]
                if abs(corr) > CORR_LIMIT: 
                    return True, pos.symbol, corr
            return False, None, 0
        except Exception as e:
            print(f"⚠️ Correlation calculation error: {e}")
            return False, None, 0

    def is_volatility_sufficient(self, symbol):
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 14)
        if rates is None: return False
        df = pd.DataFrame(rates)
        df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
        atr = df['tr'].mean()
        return atr > (400 * mt5.symbol_info(symbol).point * 0.25)

    def close_position(self, pos):
        tick = mt5.symbol_info_tick(pos.symbol)
        t = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        p = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        req = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": pos.symbol, "volume": pos.volume,
            "type": t, "position": pos.ticket, "price": p, "deviation": 10,
            "magic": self.magic_number, "type_filling": self.get_filling_mode(pos.symbol)
        }
        return mt5.order_send(req)

    def update_closed_trades(self):
        if not os.path.exists(self.logger.executed_file): return
        with open(self.logger.executed_file, 'r') as f:
            trades = json.load(f)
        open_tickets = [t['ticket'] for t in trades if t['status'] == "OPEN"]
        if not open_tickets: return
        history = mt5.history_deals_get(datetime.now().timestamp() - 86400, datetime.now().timestamp())
        if history:
            for d in history:
                if d.position_id in open_tickets and d.entry == 1:
                    self.logger.update_trade_result(d.position_id, d.profit, d.price)

    def execute_trade(self, symbol, order_type, sentiment, trend):
        si = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        sl = price - 200 * si.point if order_type == mt5.ORDER_TYPE_BUY else price + 200 * si.point
        tp = price + 400 * si.point if order_type == mt5.ORDER_TYPE_BUY else price - 400 * si.point

        req = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": LOTS,
            "type": order_type, "price": price, "sl": sl, "tp": tp,
            "deviation": 10, "magic": self.magic_number, "type_filling": self.get_filling_mode(symbol),
        }
        res = mt5.order_send(req)
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            data = {"ticket": res.order, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "symbol": symbol, "status": "OPEN", "price": price, "sl": sl, "tp": tp, "sentiment": sentiment, "trend": trend}
            self.logger._append_json(self.logger.executed_file, data)

    def run_cycle(self):
        """Εκτέλεση ενός πλήρους κύκλου ανάλυσης και σωστή καταγραφή σε CSV"""
        if not self.account_protection(): return
        
        # Ενημέρωση αποτελεσμάτων για κλειστά trades στο JSON
        self.update_closed_trades()

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{now_str}] 🟢 Scanning Market & News...")
        
        articles = self.fetch_global_news()
        if not articles:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ No news found in this cycle.")
            return

        for symbol in self.symbols:
            keywords = SYMBOLS_CONFIG[symbol]
            # Παίρνουμε το Headline για να το γράψουμε στο CSV
            relevant_articles = [a['title'] for a in articles if any(k.lower() in a['title'].lower() for k in keywords)]
            
            if relevant_articles:
                headline_sample = relevant_articles[0].replace(',', '|') # Αντικατάσταση κόμματος για να μη χαλάει το CSV
                avg_score = sum([self.analyzer.polarity_scores(h)['compound'] for h in relevant_articles]) / len(relevant_articles)
                
                trend, sup, res = self.get_market_structure(symbol)
                tick = mt5.symbol_info_tick(symbol)
                price = tick.bid if tick else 0
                
                action = "WAIT"
                if avg_score > THRESHOLD: action = "BUY"
                elif avg_score < -THRESHOLD: action = "SELL"
                
                final_status = action
                if action != "WAIT":
                    is_corr, corr_sym, _ = self.is_too_correlated(symbol)
                    
                    if (action == "BUY" and trend != "BULL") or (action == "SELL" and trend != "BEAR"): 
                        final_status = "TREND_MISMATCH"
                    elif len(mt5.positions_get(symbol=symbol)) > 0: 
                        final_status = "POSITION_ACTIVE"
                    elif is_corr: 
                        final_status = f"CORR_BLOCKED_{corr_sym}"
                    elif not self.is_volatility_sufficient(symbol): 
                        final_status = "LOW_VOLATILITY"
                    else:
                        self.execute_trade(symbol, mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL, avg_score, trend)
                
                # Εμφάνιση στην κονσόλα
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 {symbol} | Sent: {avg_score:.2f} | Status: {final_status}")
                
                # --- Η ΔΙΟΡΘΩΜΕΝΗ ΕΓΓΡΑΦΗ ΣΤΟ CSV ---
                file_exists = os.path.isfile("forex_ai_trading_logs.csv")
                with open("forex_ai_trading_logs.csv", "a", encoding='utf-8') as f:
                    # Αν το αρχείο είναι καινούργιο, γράψε τα headers
                    if not file_exists:
                        f.write("timestamp,symbol,price,sentiment,action,trend,support,resistance,headline\n")
                    
                    # Εγγραφή όλων των δεδομένων
                    f.write(f"{now_str},{symbol},{price:.5f},{avg_score:.4f},{final_status},{trend},{sup:.5f},{res:.5f},{headline_sample}\n")

    def run_forever(self):
        try:
            while self.running:
                self.run_cycle()
                time.sleep(INTERVAL)
        except Exception as e:
            print(f"🔴 System Crash: {e}")
            self.emergency_shutdown()

if __name__ == "__main__":
    bot = MultiAssetForexAI()
    try:
        bot.run_forever()
    except KeyboardInterrupt:
        print("\n" + "="*45)
        print("🛑 SYSTEM STOPPED BY USER")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Finalizing logs and shutting down...")
        
        # Απενεργοποίηση του Heartbeat
        bot.running = False
        
        # Κλείσιμο σύνδεσης με MT5
        mt5.shutdown()
        
        print("✅ Shutdown complete. Goodbye!")
        print("="*45)