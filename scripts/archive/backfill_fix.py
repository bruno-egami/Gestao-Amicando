import database
import sqlite3
from datetime import datetime

print("Connecting to DB...")
try:
    conn = database.get_connection()
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        print("CRITICAL: 'users' table not found via database.get_connection()")
        # Try to see where it is connecting
        print(f"DB Path from config: {database.DB_PATH}")
    else:
        print("'users' table found.")

    # 1. Backfill Cost
    print("Backfilling Cost...")
    cursor.execute("""
        UPDATE inventory_transactions 
        SET cost = quantity * (SELECT price_per_unit FROM materials WHERE materials.id = inventory_transactions.material_id) 
        WHERE cost IS NULL OR cost = 0
    """)
    print(f"Updated {cursor.rowcount} rows for Cost.")
    
    # 2. Backfill User
    print("Backfilling User...")
    # Get admin id
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    res = cursor.fetchone()
    if res:
        admin_id = res[0]
        # set user_id for nulls
        cursor.execute("UPDATE inventory_transactions SET user_id = ? WHERE user_id IS NULL", (admin_id,))
        print(f"Updated {cursor.rowcount} rows for User ID (set to Admin).")
        
        # Also update username in production_history if needed (though user complained about Insumos history)
        # inventory_transactions joins with users table, so setting user_id is enough.
    else:
        print("Admin user not found! Valid users:")
        cursor.execute("SELECT id, username FROM users")
        print(cursor.fetchall())
        
    conn.commit()
    conn.close()
    print("Done.")
except Exception as e:
    print(f"Error: {e}")
