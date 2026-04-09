import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

def generate_dashboard(symbol="EURUSD"):
    file_name = "forex_ai_trading_logs.csv"
    if not os.path.exists(file_name):
        print(f"❌ Το αρχείο {file_name} δεν βρέθηκε.")
        return

    # Διαβάζουμε το CSV και προσπαθούμε να διορθώσουμε τυχόν ασυμφωνίες
    df = pd.read_csv(file_name)
    
    # Μετατροπή χρόνου
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df[df['symbol'] == symbol].sort_values('timestamp')

    if df.empty:
        print(f"⚠️ Δεν βρέθηκαν δεδομένα για το symbol: {symbol}")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    # --- Πάνω Γράφημα: Τιμή & S/R Levels ---
    ax1.plot(df['timestamp'], df['price'], color='#1f77b4', label='Market Price', linewidth=2)
    
    # Σχεδίαση Support/Resistance αν υπάρχουν
    if 'support' in df.columns and 'resistance' in df.columns:
        ax1.plot(df['timestamp'], df['resistance'], color='red', linestyle=':', alpha=0.5, label='Dynamic Resistance')
        ax1.plot(df['timestamp'], df['support'], color='green', linestyle=':', alpha=0.5, label='Dynamic Support')

    # Trade Markers
    buys = df[df['action'].str.contains('BUY', na=False)]
    sells = df[df['action'].str.contains('SELL', na=False)]
    ax1.scatter(buys['timestamp'], buys['price'], marker='^', color='green', s=100, label='BUY Signal', zorder=5)
    ax1.scatter(sells['timestamp'], sells['price'], marker='v', color='red', s=100, label='SELL Signal', zorder=5)

    ax1.set_title(f"Hybrid AI Analysis: {symbol}", fontsize=15, fontweight='bold')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # --- Κάτω Γράφημα: Sentiment ---
    ax2.fill_between(df['timestamp'], df['sentiment'], 0, where=(df['sentiment'] >= 0), color='green', alpha=0.3)
    ax2.fill_between(df['timestamp'], df['sentiment'], 0, where=(df['sentiment'] < 0), color='red', alpha=0.3)
    ax2.axhline(0, color='black', linewidth=1)
    ax2.set_ylabel("Sentiment Score")
    ax2.grid(True, alpha=0.3)

    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    generate_dashboard("EURUSD")