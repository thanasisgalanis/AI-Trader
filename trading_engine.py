import MetaTrader5 as mt5
import requests
import time
import os
import pandas as pd
import numpy as np
import threading
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from config import *
from logger import TradeLogger

class MultiAssetForexAI:
    def __init__(self):
        if not mt5.initialize():
            print("❌ MT5 Initialization Failed.")
            quit()
        
        print("MT5 Python Library Version:", mt5.__version__)
        self.analyzer = SentimentIntensityAnalyzer()
        self.logger = TradeLogger()
        self.magic_number = MAGIC_NUMBER
        self.symbols = list(SYMBOLS_CONFIG.keys())
        self.running = True
        
        self.heartbeat_thread = threading.Thread(target=self.start_heartbeat, daemon=True)
        self.heartbeat_thread.start()

    def start_heartbeat(self):
        while self.running:
            try:
                timestamp = float(time.time())
                if hasattr(mt5, 'global_variable_set'):
                    mt5.global_variable_set("AI_ALIVE", timestamp)
                elif hasattr(mt5, 'global_variables_set'):
                    mt5.global_variables_set("AI_ALIVE", timestamp)
            except: pass
            time.sleep(10)

    def account_protection(self):
        acc = mt5.account_info()
        if acc is None: return False
        if acc.equity < acc.balance * EQUITY_PROTECTION_RATIO:
            print(f"🚨 CRITICAL: Equity {acc.equity} dropped below threshold.")
            self.emergency_shutdown()
            return False
        return True

    def emergency_shutdown(self):
        self.running = False
        positions = mt5.positions_get()
        if positions:
            for pos in positions:
                self.close_position(pos)
        print("🛡️ Safety Protocol Executed.")
        mt5.shutdown()
        os._exit(0)

    def fetch_global_news(self):
        query = "Forex OR Fed OR ECB OR Economy OR Inflation"
        url = f'https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}'
        try:
            response = requests.get(url, timeout=10)
            return response.json().get('articles', [])
        except Exception as e:
            print(f"⚠️ News API Error: {e}")
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
        try:
            active = mt5.positions_get()
            if not active: return False, None, 0
            for pos in active:
                if pos.symbol == new_symbol: continue
                r1 = mt5.copy_rates_from_pos(new_symbol, mt5.TIMEFRAME_H1, 0, 50)
                r2 = mt5.copy_rates_from_pos(pos.symbol, mt5.TIMEFRAME_H1, 0, 50)
                if r1 is None or r2 is None: continue
                df = pd.DataFrame({"s1": [x['close'] for x in r1], "s2": [x['close'] for x in r2]})
                corr = df.corr().iloc[0, 1]
                if abs(corr) > CORR_LIMIT: return True, pos.symbol, corr
            return False, None, 0
        except: return False, None, 0

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
        self.logger.update_trade_result # reference to logic in logger
        # ... logic inside run_cycle calls logger.update_trade_result ...

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
        if not self.account_protection(): return
        
        # Ενημέρωση JSON
        if os.path.exists(self.logger.executed_file):
            with open(self.logger.executed_file, 'r') as f:
                trades = json.load(f)
            open_tickets = [t['ticket'] for t in trades if t['status'] == "OPEN"]
            if open_tickets:
                history = mt5.history_deals_get(datetime.now().timestamp() - 86400, datetime.now().timestamp())
                if history:
                    for d in history:
                        if d.position_id in open_tickets and d.entry == 1:
                            self.logger.update_trade_result(d.position_id, d.profit, d.price)

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{now_str}] 🟢 Scanning Market & News...")
        
        articles = self.fetch_global_news()
        if not articles: return

        for symbol in self.symbols:
            keywords = SYMBOLS_CONFIG[symbol]
            relevant_articles = [a['title'] for a in articles if any(k.lower() in a['title'].lower() for k in keywords)]
            
            if relevant_articles:
                headline_sample = relevant_articles[0].replace(',', '|')
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
                    
                    # Logic Filters
                    if (action == "BUY" and trend != "BULL") or (action == "SELL" and trend != "BEAR"): 
                        final_status = "TREND_MISMATCH"
                    elif len(mt5.positions_get(symbol=symbol)) > 0: 
                        final_status = "POSITION_ACTIVE"
                    elif is_corr: 
                        final_status = f"CORR_BLOCKED_{corr_sym}"
                    elif not self.is_volatility_sufficient(symbol): 
                        final_status = "LOW_VOLATILITY"
                    else:
                        # Αν περάσει, εκτελείται κανονικά
                        self.execute_trade(symbol, mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL, avg_score, trend)

                    # --- ΠΡΟΣΘΕΣΕ ΑΥΤΟ ΤΟ ΜΠΛΟΚ ΕΔΩ ---
                    if final_status not in ["BUY", "SELL"]:
                        virtual_data = {
                            "timestamp": now_str,
                            "symbol": symbol,
                            "intended": action,
                            "price": price,
                            "reason": final_status,
                            "sentiment": avg_score,
                            "trend": trend
                        }
                        # Καλούμε τον logger να γράψει στο rejected_file (virtual_backtest.json)
                        self.logger._append_json(self.logger.rejected_file, virtual_data)
                                    
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 {symbol} | Sent: {avg_score:.2f} | Status: {final_status}")
                self.logger.log_to_csv(now_str, symbol, price, avg_score, final_status, trend, sup, res, headline_sample)