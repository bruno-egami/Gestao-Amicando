import sqlite3
import os

DB_PATH = "data/ceramic_admin.db"

def check_schema():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get columns
    cursor.execute("PRAGMA table_info(sales)")
    columns = [info[1] for info in cursor.fetchall()]
    print(f"Current 'sales' columns: {columns}")
    
    if 'order_id' in columns:
        print("'order_id' column ALREADY EXISTS.")
    else:
        print("'order_id' column MISSING. Attempting to add...")
        try:
            cursor.execute("ALTER TABLE sales ADD COLUMN order_id TEXT")
            conn.commit()
            print("Successfully added 'order_id' column.")
        except Exception as e:
            print(f"FAILED to add column: {e}")

    conn.close()

if __name__ == "__main__":
    check_schema()
