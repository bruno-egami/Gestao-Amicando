import sqlite3
import pandas as pd
import os

DB_PATH = r"d:\GitHub\Gestao-Amicando\data\ceramic_admin.db"

def query_db():
    conn = sqlite3.connect(DB_PATH)
    
    print("--- QUOTE DETAILS (ID: 19) ---")
    quote = pd.read_sql("SELECT * FROM quotes WHERE id = 19", conn)
    print(quote if not quote.empty else "Quote not found")
    
    print("\n--- QUOTE ITEMS (ID: 19) ---")
    quote_items = pd.read_sql("""
        SELECT qi.*, p.name 
        FROM quote_items qi 
        JOIN products p ON qi.product_id = p.id 
        WHERE qi.quote_id = 19
    """, conn)
    print(quote_items if not quote_items.empty else "No items found")
    
    print("\n--- ORDER DETAILS (ID: 39) ---")
    order = pd.read_sql("SELECT * FROM commission_orders WHERE id = 39", conn)
    print(order if not order.empty else "Order not found")
    
    print("\n--- ORDER ITEMS (ID: 39) ---")
    order_items = pd.read_sql("""
        SELECT ci.*, p.name 
        FROM commission_items ci 
        JOIN products p ON ci.product_id = p.id 
        WHERE ci.order_id = 39
    """, conn)
    print(order_items if not order_items.empty else "No items found")
    
    print("\n--- INVENTORY TRANSACTIONS FOR RELEVANT PRODUCTS ---")
    if not order_items.empty:
        p_ids = tuple(order_items['product_id'].tolist())
        if len(p_ids) == 1:
            query = f"SELECT * FROM inventory_transactions WHERE material_id IN ({p_ids[0]})"
        else:
            query = f"SELECT * FROM inventory_transactions WHERE material_id IN {p_ids}"
        # Wait, inventory_transactions uses 'material_id'. 
        # Is product_id same as material_id? 
        # Looking at database.py, inventory_transactions is for materials.
        # Let's check if there's an audit log for products or if sales/orders are logged elsewhere.
        print("Checking inventory_transactions (assuming products might be materials or tracked there)...")
        trans = pd.read_sql(query, conn)
        print(trans if not trans.empty else "No transactions found")
        
    print("\n--- AUDIT LOG ---")
    # Looking for actions related to these IDs or products
    audit = pd.read_sql("""
        SELECT * FROM audit_log 
        WHERE (table_name = 'quotes' AND record_id = 19)
           OR (table_name = 'commission_orders' AND record_id = 39)
        ORDER BY timestamp DESC
    """, conn)
    print(audit if not audit.empty else "No audit logs found")

    conn.close()

if __name__ == "__main__":
    query_db()
