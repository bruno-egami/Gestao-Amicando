import database
import pandas as pd

conn = database.get_connection()
cursor = conn.cursor()

try:
    # Delete corrupted quotes (IDs 1 to 5 based on debug output)
    cursor.execute("DELETE FROM quote_items WHERE quote_id IN (1, 2, 3, 4, 5)")
    cursor.execute("DELETE FROM quotes WHERE id IN (1, 2, 3, 4, 5)")
    conn.commit()
    print("Corrupted quotes deleted successfully.")
except Exception as e:
    print(f"Error: {e}")
