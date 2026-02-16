import sqlite3
import time
import os
import sys

# Find DB path (using relative path to database.py or config logic)
# Assuming database.py is in root and config.py specifies data/ceramic_admin.db
DB_PATH = os.path.join(os.getcwd(), 'data', 'ceramic_admin.db')

def migrate():
    print(f"Connecting to {DB_PATH}...")
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10) # 10s timeout
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        
        # Try adding columns
        cols = [
            ("tuitions", "amount_paid", "REAL DEFAULT 0"),
            ("student_consumptions", "amount_paid", "REAL DEFAULT 0")
        ]
        
        changes = 0
        for table, col, definition in cols:
            try:
                print(f"Adding {col} to {table}...")
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
                changes += 1
                print(" -> Success")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f" -> Column {col} already exists.")
                else:
                    raise e
        
        conn.commit()
        conn.close()
        print(f"Migration completed. Applied {changes} changes.")
        return True
        
    except sqlite3.OperationalError as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    for i in range(5):
        if migrate():
            sys.exit(0)
        print(f"Retrying in 2 seconds... ({i+1}/5)")
        time.sleep(2)
    sys.exit(1)
