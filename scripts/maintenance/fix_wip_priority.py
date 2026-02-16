import sqlite3
import os

DB_FOLDER = "data"
DB_NAME = "ceramic_admin.db"
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("Adding 'priority' column to production_wip...")
        cursor.execute("ALTER TABLE production_wip ADD COLUMN priority INTEGER DEFAULT 0")
        conn.commit()
        print("Migration successful!")
    except Exception as e:
        if "duplicate column name" in str(e).lower():
            print("Column 'priority' already exists.")
        else:
            print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
