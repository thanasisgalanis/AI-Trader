import time
import MetaTrader5 as mt5
from datetime import datetime
from trading_engine import MultiAssetForexAI
from config import INTERVAL

def main():
    bot = MultiAssetForexAI()
    print("DEBUG: Entering run_forever loop...")
    try:
        while bot.running:
            bot.run_cycle()
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\n" + "="*45)
        print("🛑 SYSTEM STOPPED BY USER")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Shutting down...")
        bot.running = False
        mt5.shutdown()
        print("✅ Shutdown complete. Goodbye!")
        print("="*45)
    except Exception as e:
        print(f"🔴 System Crash: {e}")
        bot.emergency_shutdown()

if __name__ == "__main__":
    main()