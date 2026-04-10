import pandas as pd

# Φόρτωση του μεγάλου αρχείου
file_name = "inputs/raw_analyst_ratings.csv" # Ή όπως λέγεται το αρχείο σου
print("⏳ Φορτώνω το αρχείο... κάνε υπομονή!")
df = pd.read_csv(file_name)

# Λίστα με λέξεις-κλειδιά που μας ενδιαφέρουν για το Forex/Gold
keywords = ['Gold', 'XAU', 'Fed', 'Inflation', 'Dollar', 'USD', 'ECB', 'EUR', 'Interest Rate']

# Φιλτράρισμα: Κράτα μόνο όσα Headlines περιέχουν κάποιο keyword
print("🧹 Καθαρίζω τα δεδομένα...")
mask = df['headline'].str.contains('|'.join(keywords), case=False, na=False)
df_filtered = df[mask]

# Αποθήκευση σε ένα νέο, μικρότερο αρχείο
df_filtered.to_csv("logs/forex_news_backtest.csv", index=False)
print(f"✅ Έτοιμο! Το νέο αρχείο έχει {len(df_filtered)} ειδήσεις και είναι πανάλαφρο.")