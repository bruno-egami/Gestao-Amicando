import database
import pandas as pd

conn = database.get_connection()
try:
    print("--- QUOTES DETAILS ---")
    quotes = pd.read_sql("SELECT id, client_id, date_created, status FROM quotes", conn)
    print(quotes)
except Exception as e:
    print(f"Error: {e}")
