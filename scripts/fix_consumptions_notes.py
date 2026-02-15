import sqlite3
import os

DB_FOLDER = 'data'
DB_NAME = 'ceramic_admin.db'
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def migrate():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("Ensuring 'notes' and 'markup' columns in 'student_consumptions'...")
        # Check if columns exist first or just try-except
        try:
            cursor.execute("ALTER TABLE student_consumptions ADD COLUMN notes TEXT")
        except: pass
        
        try:
            cursor.execute("ALTER TABLE student_consumptions ADD COLUMN markup REAL DEFAULT 0.0")
        except: pass
        
        conn.commit()
        print("Migration successful.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Column 'notes' already exists.")
        else:
            print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
