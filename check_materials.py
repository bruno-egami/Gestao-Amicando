import sqlite3
import pandas as pd

DB_PATH = r"d:\GitHub\Gestao-Amicando\data\ceramic_admin.db"

def check_materials():
    conn = sqlite3.connect(DB_PATH)
    
    print("--- RECIPE FOR PRODUCT ID 8 ---")
    recipe = pd.read_sql("""
        SELECT pr.*, m.name as material_name, m.stock_level 
        FROM product_recipes pr
        JOIN materials m ON pr.material_id = m.id
        WHERE pr.product_id = 8
    """, conn)
    print(recipe if not recipe.empty else "No recipe found for product 8")

    print("\n--- MATERIAL TRANSACTIONS (RECENT) ---")
    # There is no direct link entre production and material transactions table besides notes if implemented.
    # Looking at pages/9_Encomendas.py, it doesn't seem to insert into inventory_transactions, 
    # it just updates materials stock_level directly.
    # Actually, inventory_transactions is for 'ENTRADA', 'SAIDA', etc.
    # Let's check audit log for materials.
    
    audit_m = pd.read_sql("""
        SELECT * FROM audit_log 
        WHERE table_name = 'materials'
        ORDER BY timestamp DESC LIMIT 10
    """, conn)
    print(audit_m if not audit_m.empty else "No material audit logs found")

    conn.close()

if __name__ == "__main__":
    check_materials()
