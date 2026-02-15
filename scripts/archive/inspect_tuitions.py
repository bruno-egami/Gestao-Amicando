import sqlite3
import pandas as pd
import sys
import os
import config

# Add current dir to sys.path
sys.path.append(os.path.abspath("."))

db_path = config.DB_PATH
conn = sqlite3.connect(db_path)

print("--- FULL TUITION INSPECTION ---")
try:
    tuitions = pd.read_sql("SELECT * FROM tuitions", conn)
    print(tuitions)
except Exception as e:
    print(f"Error: {e}")

conn.close()
