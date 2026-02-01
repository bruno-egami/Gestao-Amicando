
import sqlite3

def migrate():
    try:
        # Correct DB Path based on database.py
        db_path = "data/ceramic_admin.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column exists
        cols = [info[1] for info in cursor.execute("PRAGMA table_info(commission_items)").fetchall()]
        
        if 'notes' not in cols:
            print("Adding 'notes' column to commission_items...")
            cursor.execute("ALTER TABLE commission_items ADD COLUMN notes TEXT")
            conn.commit()
            print("Migration successful.")
        else:
            print("Column 'notes' already exists.")
            
        conn.close()
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
