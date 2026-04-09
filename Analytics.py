import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

def generate_dashboard(symbol="EURUSD"):
    # 1. Φόρτωση δεδομένων
    file_name = "forex_ai_trading_logs.csv"
    if not os.path.exists(file_name):
        print(f"❌ Το αρχείο {file_name} δεν βρέθηκε.")
        return

    df = pd.read_csv(file_name)

    # Διόρθωση ονομάτων στηλών αν διαφέρουν
    # Αντιστοιχίζουμε τα ονόματα του CSV με αυτά που θέλει το script
    rename_dict = {
        'current_price': 'price',
        'sentiment_score': 'sentiment'
    }
    df = df.rename(columns=rename_dict)

    # 2. Φιλτράρισμα και Μετατροπή
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df[df['symbol'] == symbol].sort_values('timestamp')

    if df.empty:
        print(f"⚠️ Δεν βρέθηκαν δεδομένα για το symbol: {symbol}")
        print("Διαθέσιμα symbols στο CSV:", df['symbol'].unique() if 'symbol' in df.columns else "Κανένα")
        return

    # 3. Visualization
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    plt.subplots_adjust(hspace=0.2)

    # --- Πάνω Γράφημα: Τιμή & Trade Markers ---
    ax1.plot(df['timestamp'], df['price'], color='#1f77b4', label='Market Price', linewidth=2, alpha=0.8)
    
    # Προσθήκη Markers για τα Trades
    buys = df[df['action'].str.contains('BUY', na=False)]
    sells = df[df['action'].str.contains('SELL', na=False)]
    
    ax1.scatter(buys['timestamp'], buys['price'], marker='^', color='green', s=100, label='Buy Signal', zorder=5)
    ax1.scatter(sells['timestamp'], sells['price'], marker='v', color='red', s=100, label='Sell Signal', zorder=5)

    ax1.set_title(f"Forex AI Real-Time Analysis: {symbol}", fontsize=15, fontweight='bold', pad=20)
    ax1.set_ylabel("Price ($)", fontsize=12)
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper left')

    # --- Κάτω Γράφημα: Sentiment Score ---
    ax2.fill_between(df['timestamp'], df['sentiment'], 0, 
                     where=(df['sentiment'] >= 0), color='green', alpha=0.3)
    ax2.fill_between(df['timestamp'], df['sentiment'], 0, 
                     where=(df['sentiment'] < 0), color='red', alpha=0.3)
    
    ax2.plot(df['timestamp'], df['sentiment'], color='black', linewidth=0.5, alpha=0.5)
    
    # Threshold lines
    ax2.axhline(0.1, color='green', linestyle='--', alpha=0.4, label='Buy Threshold')
    ax2.axhline(-0.1, color='red', linestyle='--', alpha=0.4, label='Sell Threshold')
    ax2.axhline(0, color='black', linewidth=1)

    ax2.set_ylabel("AI Sentiment Score", fontsize=12)
    ax2.set_xlabel("Time (Server Time)", fontsize=12)
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend(loc='upper left')

    # Format Time Axis
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
    plt.xticks(rotation=45)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    generate_dashboard("XAUUSD")