import MetaTrader5 as mt5
import requests
import time
import os
import pandas as pd
import numpy as np
import json
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

class TradeLogger:
    """Διαχείριση JSON Logs για πραγματικά (με tracking) και εικονικά trades"""
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
        """Ενημερώνει μια εγγραφή στο JSON όταν η θέση κλείνει στην MT5"""
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
        
        self.analyzer = SentimentIntensityAnalyzer()
        self.logger = TradeLogger()
        self.magic_number = 20260408
        self.symbols = list(SYMBOLS_CONFIG.keys())
        
        print(f"--- [SYSTEM] Hybrid AI Engine Active ---")
        print(f"--- [INFO] Dual JSON Logging & Ticket Tracking: ACTIVE ---")
        print(f"--- [INFO] Friday Auto-Close: ENABLED (22:30) ---\n")

    def is_market_open(self):
        now = datetime.now()
        day = now.weekday() 
        if day == 5 or (day == 4 and now.hour >= 23) or (day == 6 and now.hour < 23):
            return False
        return True

    def fetch_global_news(self):
        query = "Forex OR Fed OR ECB OR Economy OR Inflation"
        url = f'https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}'
        try:
            response = requests.get(url)
            return response.json().get('articles', [])
        except Exception as e:
            print(f"❌ News API Error: {e}")
            return []

    def get_market_structure(self, symbol):
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 200)
        if rates is None: return "NEUTRAL", 0, 0
        df = pd.DataFrame(rates)
        ema200 = df['close'].ewm(span=200, adjust=False).mean().iloc[-1]
        current_price = df['close'].iloc[-1]
        trend = "BULL" if current_price > ema200 else "BEAR"
        recent = df.tail(100)
        return trend, recent['low'].min(), recent['high'].max()

    def get_filling_mode(self, symbol):
        si = mt5.symbol_info(symbol)
        if si is None: return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_FOK if si.filling_mode & 1 else mt5.ORDER_FILLING_IOC

    def get_correlation(self, s1, s2, lookback=50):
        r1 = mt5.copy_rates_from_pos(s1, mt5.TIMEFRAME_H1, 0, lookback)
        r2 = mt5.copy_rates_from_pos(s2, mt5.TIMEFRAME_H1, 0, lookback)
        if r1 is None or r2 is None: return 0
        df = pd.DataFrame({"s1": [x['close'] for x in r1], "s2": [x['close'] for x in r2]})
        return df.corr().iloc[0, 1]

    def is_too_correlated(self, new_symbol):
        active_positions = mt5.positions_get()
        if not active_positions: return False, None, 0
        for pos in active_positions:
            if pos.symbol == new_symbol: continue
            corr = self.get_correlation(new_symbol, pos.symbol)
            if abs(corr) > CORR_LIMIT:
                return True, pos.symbol, corr
        return False, None, 0

    def is_volatility_sufficient(self, symbol, target_pips=400):
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 14)
        if rates is None: return False
        df = pd.DataFrame(rates)
        df['tr'] = np.maximum(df['high'] - df['low'], 
                              np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                         abs(df['low'] - df['close'].shift(1))))
        atr = df['tr'].mean()
        point = mt5.symbol_info(symbol).point
        return atr > (target_pips * point * 0.25)

    def is_time_safe(self):
        now = datetime.now()
        if now.weekday() == 4 and now.hour >= 20:
            return False
        return True

    def check_friday_exit(self):
        now = datetime.now()
        if now.weekday() == 4 and now.hour == 22 and now.minute >= 30:
            positions = mt5.positions_get()
            if positions:
                print(f"[{now.strftime('%H:%M:%S')}] 🛡️ Friday Exit Triggered.")
                for pos in positions:
                    self.close_position(pos)
                return True
        return False

    def close_position(self, pos):
        tick = mt5.symbol_info_tick(pos.symbol)
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": pos.symbol, "volume": pos.volume,
            "type": order_type, "position": pos.ticket, "price": price, "deviation": 10,
            "magic": self.magic_number, "comment": "Friday Auto-Close",
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": self.get_filling_mode(pos.symbol)
        }
        return mt5.order_send(request)

    def update_closed_trades(self):
        """Ελέγχει το ιστορικό της MT5 για να κλείσει τα trades στο JSON"""
        if not os.path.exists(self.logger.executed_file): return
        
        with open(self.logger.executed_file, 'r') as f:
            trades = json.load(f)
        
        open_tickets = [t['ticket'] for t in trades if t['status'] == "OPEN"]
        if not open_tickets: return

        # Ελέγχουμε το ιστορικό των τελευταίων 24 ωρών
        from_date = datetime.now().timestamp() - 86400
        history_orders = mt5.history_deals_get(from_date, datetime.now().timestamp())
        
        if history_orders:
            for deal in history_orders:
                if deal.position_id in open_tickets:
                    # Αν βρούμε deal κλεισίματος (entry=1 σημαίνει out)
                    if deal.entry == 1:
                        self.logger.update_trade_result(deal.position_id, deal.profit, deal.price)
                        print(f"✅ Ticket {deal.position_id} closed. Profit: {deal.profit} logged to JSON.")

    def execute_trade(self, symbol, order_type, sentiment, trend):
        si = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        sl = price - 200 * si.point if order_type == mt5.ORDER_TYPE_BUY else price + 200 * si.point
        tp = price + 400 * si.point if order_type == mt5.ORDER_TYPE_BUY else price - 400 * si.point

        request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": LOTS,
            "type": order_type, "price": price, "sl": sl, "tp": tp,
            "deviation": 10, "magic": self.magic_number, "comment": "AI Hybrid Strategy",
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": self.get_filling_mode(symbol),
        }
        res = mt5.order_send(request)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            trade_data = {
                "ticket": res.order, # Μοναδικό Ticket ID
                "timestamp": now, "symbol": symbol, "action": "BUY" if order_type == 0 else "SELL",
                "status": "OPEN", "price": price, "sl": sl, "tp": tp, 
                "sentiment": sentiment, "trend": trend
            }
            self.logger._append_json(self.logger.executed_file, trade_data)
            print(f"[{now}] 🚀 SUCCESS: {symbol} Executed (Ticket: {res.order})")
        else:
            print(f"[{now}] ❌ {symbol} Failed: {res.comment}")

    def save_to_csv(self, symbol, avg_score, action, headline, trend, sup, res):
        file_name = "forex_ai_trading_logs.csv"
        tick = mt5.symbol_info_tick(symbol)
        price = tick.bid if tick else 0
        new_data = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol, "price": price, "sentiment": round(avg_score, 4),
            "action": action, "trend": trend, "support": sup, "resistance": res,
            "headline": headline.replace(',', '|') if headline else "N/A"
        }])
        new_data.to_csv(file_name, index=False, mode='a', header=not os.path.exists(file_name), encoding='utf-8')

    def run_cycle(self):
        now_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not self.is_market_open(): return
        if self.check_friday_exit(): return
        
        # Ενημέρωση αποτελεσμάτων για κλειστά trades
        self.update_closed_trades()

        print(f"[{now_full}] 🟢 Scanning Market & News...")
        articles = self.fetch_global_news()
        if not articles: return

        for symbol in self.symbols:
            keywords = SYMBOLS_CONFIG[symbol]
            relevant = [a['title'] for a in articles if any(k.lower() in a['title'].lower() for k in keywords)]
            if relevant:
                avg_score = sum([self.analyzer.polarity_scores(h)['compound'] for h in relevant]) / len(relevant)
                trend, sup, res = self.get_market_structure(symbol)
                tick = mt5.symbol_info_tick(symbol)
                price = tick.bid if tick else 0
                
                action = "WAIT"
                if avg_score > THRESHOLD: action = "BUY"
                elif avg_score < -THRESHOLD: action = "SELL"
                
                final_status = action
                if action != "WAIT":
                    rejection_reason = None
                    is_corr, corr_sym, corr_val = self.is_too_correlated(symbol)
                    
                    if action == "BUY" and trend != "BULL": rejection_reason = "TREND_MISMATCH"
                    elif action == "SELL" and trend != "BEAR": rejection_reason = "TREND_MISMATCH"
                    elif action == "BUY" and (res - price) < 150 * mt5.symbol_info(symbol).point: rejection_reason = "RESISTANCE_NEAR"
                    elif action == "SELL" and (price - sup) < 150 * mt5.symbol_info(symbol).point: rejection_reason = "SUPPORT_NEAR"
                    elif len(mt5.positions_get(symbol=symbol)) > 0: rejection_reason = "POSITION_ACTIVE"
                    elif is_corr: rejection_reason = f"CORR_BLOCKED_{corr_sym}"
                    elif not self.is_time_safe(): rejection_reason = "FRIDAY_NIGHT_SKIP"
                    elif not self.is_volatility_sufficient(symbol): rejection_reason = "LOW_VOLATILITY"

                    if rejection_reason:
                        final_status = rejection_reason
                        virtual_data = {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "symbol": symbol, "intended": action, "price": price,
                            "reason": rejection_reason, "sentiment": avg_score, "trend": trend
                        }
                        self.logger._append_json(self.logger.rejected_file, virtual_data)
                    else:
                        ot = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
                        self.execute_trade(symbol, ot, avg_score, trend)

                print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 {symbol} | Sent: {avg_score:.2f} | Status: {final_status}")
                self.save_to_csv(symbol, avg_score, final_status, relevant[0], trend, sup, res)

    def run_forever(self):
        while True:
            self.run_cycle()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏳ Waiting {INTERVAL/60}m...\n")
            time.sleep(INTERVAL)

if __name__ == "__main__":
    bot = MultiAssetForexAI()
    try:
        bot.run_forever()
    except KeyboardInterrupt:
        mt5.shutdown()
        print("\n--- [SYSTEM] Stopped by user ---")