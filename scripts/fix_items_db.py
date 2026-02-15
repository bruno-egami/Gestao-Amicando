import database
import pandas as pd

conn = database.get_connection()
cursor = conn.cursor()

try:
    print("Cleaning up corrupted items...")
    
    # Delete where product_id is not an integer (sqlite typeof)
    cursor.execute("DELETE FROM quote_items WHERE typeof(product_id) != 'integer'")
    deleted_count = cursor.rowcount
    print(f"Deleted {deleted_count} non-integer product_id items.")
    
    # Also clean quotes with no items? No, logic allows empty quotes.
    
    conn.commit()
    print("Cleanup complete.")
    
except Exception as e:
    print(f"Error: {e}")
