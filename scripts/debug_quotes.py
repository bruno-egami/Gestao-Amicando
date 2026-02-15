import database
import pandas as pd

conn = database.get_connection()
try:
    print("--- QUOTES TABLE ---")
    quotes = pd.read_sql("SELECT * FROM quotes", conn)
    print(quotes)
    
    print("\n--- CLIENTS TABLE ---")
    clients = pd.read_sql("SELECT * FROM clients", conn)
    print(clients)
except Exception as e:
    print(f"Error: {e}")
