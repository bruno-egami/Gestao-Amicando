import database
import pandas as pd

conn = database.get_connection()
try:
    print("--- QUOTE ITEMS ---")
    items = pd.read_sql("SELECT id, quote_id, product_id, quantity FROM quote_items", conn)
    print(items)
    print("\n--- TYPES ---")
    print(items.dtypes)
    
    # Check specific value for the buggy item
    print("\n--- DETAILED INSPECTION ---")
    cursor = conn.cursor()
    cursor.execute("SELECT product_id FROM quote_items WHERE quote_id > 5")
    rows = cursor.fetchall()
    for row in rows:
        print(f"Row: {row}, Type: {type(row[0])}")

except Exception as e:
    print(f"Error: {e}")
