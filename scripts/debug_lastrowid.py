import database
import pandas as pd

conn = database.get_connection()
cursor = conn.cursor()

try:
    # Create a dummy entry to check lastrowid type
    print("--- INSERTING DUMMY ---")
    cursor.execute("CREATE TABLE IF NOT EXISTS debug_types (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)")
    cursor.execute("INSERT INTO debug_types (val) VALUES ('test')")
    last_id = cursor.lastrowid
    
    print(f"Lastrowid Value: {last_id}")
    print(f"Lastrowid Type: {type(last_id)}")
    print(f"Is bytes? {isinstance(last_id, bytes)}")
    
    conn.rollback() # Don't keep garbage
    
    # Check existing corrupt data in quote_items
    print("\n--- CHECKING QUOTE ITEMS ---")
    items = pd.read_sql("SELECT product_id FROM quote_items WHERE quote_id > 5", conn)
    print(items)
    if not items.empty:
        pid = items.iloc[0]['product_id']
        print(f"Stored Product ID Value: {pid}")
        print(f"Stored Product ID Type: {type(pid)}")

except Exception as e:
    print(f"Error: {e}")
