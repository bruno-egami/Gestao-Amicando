import sqlite3
import pandas as pd
import sys
import os

# Add current dir to sys.path to import services
sys.path.append(os.path.abspath("."))

from services import student_service
from datetime import datetime
import config

# Path to DB from config
db_path = config.DB_PATH
print(f"Connecting to: {db_path}")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("--- Database Check ---")
try:
    cursor = conn.cursor()
    tuitions_count = cursor.execute("SELECT count(*) FROM tuitions").fetchone()[0]
    print(f"Total tuitions in DB: {tuitions_count}")
    
    last_5 = pd.read_sql("SELECT * FROM tuitions ORDER BY id DESC LIMIT 5", conn)
    print("Last 5 tuitions:")
    print(last_5)
    
    # Check for Pendente tuitions
    pending = pd.read_sql("SELECT * FROM tuitions WHERE status='Pendente'", conn)
    print(f"Total pending tuitions: {len(pending)}")
    
    # Check a specific student with pending tuitions
    if not pending.empty:
        sid = pending.iloc[0]['student_id']
        tuit, cons, total = student_service.get_student_financial_summary(conn, sid)
        print(f"\nStudent ID {sid} summary:")
        print(f"Total Due Calculated: {total}")
        print("Tuitions DF:")
        print(tuit[['id', 'amount', 'amount_paid', 'status']])
        
        # Manually calculate to see if there's a type issue
        manual_sum = (tuit['amount'].astype(float) - tuit['amount_paid'].fillna(0).astype(float)).sum()
        print(f"Manual sum of tuitions: {manual_sum}")
    else:
        print("No pending tuitions found to analyze.")
    
except Exception as e:
    import traceback
    traceback.print_exc()

conn.close()
