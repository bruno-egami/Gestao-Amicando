import sqlite3
import pandas as pd
import sys
import os
import config

# Add current dir to sys.path
sys.path.append(os.path.abspath("."))

db_path = config.DB_PATH
conn = sqlite3.connect(db_path)

print("--- DETAILED TUITION LIST ---")
try:
    tuitions = pd.read_sql("SELECT * FROM tuitions", conn)
    print(tuitions[['id', 'student_id', 'month_year', 'amount', 'status', 'class_count', 'unit_price']])
    
    # 03/2026 is definitely mine.
    # 02/2026 might be mine if I ran it in a previous step.
    
    # Delete test records
    print("\nCleaning up test records (02/2026 and 03/2026)...")
    c = conn.cursor()
    c.execute("DELETE FROM tuitions WHERE month_year IN ('02/2026', '03/2026')")
    print(f"Deleted {c.rowcount} records.")
    conn.commit()
    
except Exception as e:
    print(f"Error: {e}")

conn.close()
