
import sqlite3
import pandas as pd

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', 1000)

def check_stock():
    conn = sqlite3.connect('data/ceramic_admin.db')
    
    # 1. Get current stock
    cur = conn.cursor()
    row = cur.execute("SELECT id, name, stock_level, unit FROM materials WHERE id = 2").fetchone()
    print(f"Current Stock: {row}")
    
    # 2. Get history
    print("\n--- History ---")
    df = pd.read_sql("SELECT id, date, type, quantity, notes FROM inventory_transactions WHERE material_id = 2 ORDER BY id ASC", conn)
    print(df)

if __name__ == "__main__":
    check_stock()
