import sqlite3
import pandas as pd
import sys
import os

# Add current dir to sys.path to import services
sys.path.append(os.path.abspath("."))

import config

# Path to DB from config
db_path = config.DB_PATH
conn = sqlite3.connect(db_path)

print("--- Students Table Check ---")
try:
    students = pd.read_sql("SELECT * FROM students", conn)
    print("Students DF:")
    print(students)
    
    if not students.empty:
        sid = students.iloc[0]['id']
        print(f"First ID: {sid}, type: {type(sid)}")
        
        # Try query with manual cast
        res = pd.read_sql("SELECT * FROM students WHERE id=?", conn, params=(int(sid),))
        print("Query with int(sid) result length:", len(res))
        
        # Try query without cast
        res2 = pd.read_sql("SELECT * FROM students WHERE id=?", conn, params=(sid,))
        print("Query with raw sid result length:", len(res2))
except Exception as e:
    print(f"Error: {e}")

conn.close()
