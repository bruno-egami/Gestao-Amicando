import database
import sys

conn = database.get_connection()
cursor = conn.cursor()

try:
    print("Checking quotes table...")
    # Check if column exists
    cursor.execute("PRAGMA table_info(quotes)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'delivery_terms' not in columns:
        print("Adding 'delivery_terms' column...")
        cursor.execute("ALTER TABLE quotes ADD COLUMN delivery_terms TEXT")
    
    if 'payment_terms' not in columns:
        print("Adding 'payment_terms' column...")
        cursor.execute("ALTER TABLE quotes ADD COLUMN payment_terms TEXT")
        
    conn.commit()
    print("Columns added successfully.")

except Exception as e:
    print(f"Error: {e}")
