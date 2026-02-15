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

print("--- Detailed Database Inspection ---")
try:
    # 1. Inspect existing tuition(s)
    tuitions = pd.read_sql("SELECT * FROM tuitions", conn)
    print("All Tuitions:")
    print(tuitions)
    
    # 2. Inspect Active Students
    students = student_service.get_all_active_students(conn)
    print(f"\nTotal Active Students: {len(students)}")
    if not students.empty:
        print("Active Students IDs:", students['id'].tolist())
        
        # 3. Try calculation for first active student
        sid = students.iloc[0]['id']
        sname = students.iloc[0]['name']
        month = "02/2026"
        print(f"\nSimulating calculation for {sname} (ID: {sid}) for {month}...")
        
        days_count, unit_price, total_calc = student_service.calculate_tuition(conn, sid, month)
        print(f"Calculated: Days={days_count}, Unit={unit_price}, Total={total_calc}")
        
        # 4. Check if we can generate
        ok, msg = student_service.generate_tuition_record(conn, sid, month, total_calc, class_count=days_count, unit_price=unit_price)
        print(f"Generation Result: {ok}, Msg: {msg}")
        
        if ok:
            # Verify it's there and Pendente
            new_view = pd.read_sql(f"SELECT * FROM tuitions WHERE student_id={sid} AND month_year='{month}'", conn)
            print("New record in DB:")
            print(new_view)
            
            # Verify debt summary
            t_df, c_df, total_due = student_service.get_student_financial_summary(conn, sid)
            print(f"Total Due now for student {sid}: {total_due}")
            
    else:
        print("No active students found in DB.")

except Exception as e:
    import traceback
    traceback.print_exc()

conn.close()
