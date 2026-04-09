import json
import os
from datetime import datetime

class TradeLogger:
    def __init__(self):
        self.executed_file = "logs/executed_trades.json"
        self.rejected_file = "logs/virtual_backtest.json"
        self.csv_file = "logs/forex_ai_trading_logs.csv"
        
        if not os.path.exists('logs'):
            os.makedirs('logs')

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

    def log_to_csv(self, now_str, symbol, price, avg_score, final_status, trend, sup, res, headline):
        file_exists = os.path.isfile(self.csv_file)
        with open(self.csv_file, "a", encoding='utf-8') as f:
            if not file_exists:
                f.write("timestamp,symbol,price,sentiment,action,trend,support,resistance,headline\n")
            f.write(f"{now_str},{symbol},{price:.5f},{avg_score:.4f},{final_status},{trend},{sup:.5f},{res:.5f},{headline}\n")