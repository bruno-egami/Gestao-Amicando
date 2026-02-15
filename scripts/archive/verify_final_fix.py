import sqlite3
import pandas as pd
import sys
import os

# Add current dir to sys.path to import services
sys.path.append(os.path.abspath("."))

from services import student_service
import config

# Path to DB from config
db_path = config.DB_PATH
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("--- Final Debt Verification ---")
try:
    students = student_service.get_all_active_students(conn)
    if not students.empty:
        sid = students.iloc[0]['id']
        sname = students.iloc[0]['name']
        print(f"Student: {sname} (ID: {sid})")
        
        # Current DB state for this student
        tuit, cons, total_due = student_service.get_student_financial_summary(conn, sid)
        print(f"Total Due: {total_due}")
        print("Tuitions:")
        print(tuit[['id', 'month_year', 'amount', 'amount_paid', 'status']])
        
        # Test with a new month
        month = "03/2026"
        print(f"\nGenerating tuition for {month}...")
        days, unit, total = student_service.calculate_tuition(conn, sid, month)
        ok, msg = student_service.generate_tuition_record(conn, sid, month, total, class_count=days, unit_price=unit)
        print(f"Result: {ok}, Msg: {msg}")
        
        if ok or "já gerada" in msg:
            tuit, cons, total_due = student_service.get_student_financial_summary(conn, sid)
            print(f"Updated Total Due: {total_due}")
    else:
        print("No active students.")

except Exception as e:
    import traceback
    traceback.print_exc()

conn.close()
