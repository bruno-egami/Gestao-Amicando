import database
import sys

conn = database.get_connection()
cursor = conn.cursor()

try:
    print("Checking quote_items table...")
    # Check if column exists
    cursor.execute("PRAGMA table_info(quote_items)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'item_notes' in columns:
        print("'item_notes' column already exists.")
    else:
        print("Adding 'item_notes' column...")
        cursor.execute("ALTER TABLE quote_items ADD COLUMN item_notes TEXT")
        conn.commit()
        print("Column added successfully.")

except Exception as e:
    print(f"Error: {e}")
