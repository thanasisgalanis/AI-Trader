import os
import time
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Η διαδρομή που εντοπίσαμε στο Mac σου
SIGNAL_FILE = "/Users/tgalanis/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files/signal.txt"

def generate_ai_signal():
    """Στάδιο 1 & 2: NLP Analysis & Decision Logic"""
    analyzer = SentimentIntensityAnalyzer()
    
    # Προσομοίωση Live Feed (Εδώ θα μπορούσε να μπει News API στο μέλλον)
    news = [
        "ECB signals bullish move for Euro interest rates",
        "US Dollar index continues to weaken globally",
        "Eurozone economic sentiment beats expectations"
    ]
    
    score = sum([analyzer.polarity_scores(n)['compound'] for n in news]) / len(news)
    
    if score > 0.05: return "BUY"
    if score < -0.05: return "SELL"
    return "IDLE"

def write_signal():
    """Στάδιο 3: Autonomous Execution (File Bridge)"""
    signal = generate_ai_signal()
    
    try:
        # Δημιουργία του φακέλου αν δεν υπάρχει για κάποιο λόγο
        os.makedirs(os.path.dirname(SIGNAL_FILE), exist_ok=True)
        
        # ΚΡΙΣΙΜΟ: Χρήση utf-16-le (Little Endian) για συμβατότητα με Windows/MT5
        # Χρησιμοποιούμε 'w' για να αντικαταστήσουμε το προηγούμενο σήμα
        with open(SIGNAL_FILE, "w", encoding="utf-16-le") as f:
            # Προσθέτουμε το Byte Order Mark (BOM) για να το καταλάβει το MT5 ως Unicode
            f.write('\ufeff') 
            f.write(signal)
            f.flush()
            os.fsync(f.fileno()) # Εξαναγκασμός εγγραφής στο δίσκο ΤΩΡΑ
            
        print(f"--- Pipeline Status ---")
        print(f"✅ AI Signal '{signal}' successfully synchronized with MT5.")
        print(f"📍 Location: {SIGNAL_FILE}")
        
    except Exception as e:
        print(f"❌ Critical Error in Bridge: {e}")

if __name__ == "__main__":
    write_signal()