import sqlite3
import pandas as pd

try:
    conn = sqlite3.connect('data/ceramic_admin.db')
    
    print("--- ORDERS (3,4,5) ---")
    orders = pd.read_sql("SELECT * FROM commission_orders WHERE id IN (3,4,5)", conn)
    print(orders)

    print("--- ITEMS DETAIL (order_id 3,4,5) ---")
    items = pd.read_sql("SELECT id, order_id, product_id, quantity FROM commission_items WHERE order_id IN (3,4,5)", conn)
    print(items)

    p_ids = items['product_id'].unique().tolist()
    if p_ids:
        print(f"\n--- PRODUCTS ({p_ids}) ---")
        prods = pd.read_sql(f"SELECT id, name FROM products WHERE id IN ({','.join(map(str, p_ids))})", conn)
        print(prods)
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
