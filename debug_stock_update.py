import sqlite3
import pandas as pd

DB_PATH = 'data/ceramic_admin.db'

def test_update():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Check Initial
    row = cursor.execute("SELECT id, name, stock_quantity FROM products WHERE id=7").fetchone()
    print(f"INITIAL: {row}")
    
    if not row:
        print("Product 7 not found")
        return

    curr_stock = row[2]
    
    # 2. Update (Simulate Sale of 1)
    print("Executing UPDATE products SET stock_quantity = stock_quantity - 1 WHERE id = 7")
    cursor.execute("UPDATE products SET stock_quantity = stock_quantity - 1 WHERE id = 7")
    print(f"Rowcount: {cursor.rowcount}")
    
    # 3. Verify inside transaction
    mid_stock = cursor.execute("SELECT stock_quantity FROM products WHERE id=7").fetchone()[0]
    print(f"INSIDE TX: {mid_stock}")
    
    # 4. Commit
    conn.commit()
    print("Committed.")
    
    # 5. Verify New Connection
    conn.close()
    
    conn2 = sqlite3.connect(DB_PATH)
    final_stock = conn2.execute("SELECT stock_quantity FROM products WHERE id=7").fetchone()[0]
    print(f"FINAL (New Conn): {final_stock}")
    conn2.close()

if __name__ == "__main__":
    test_update()
