import sqlite3
import os
import sys
import pandas as pd
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services import analytics_service

DB_PATH = "amicando_analytics_test.db"

def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Schema
    cursor.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, category TEXT, base_price REAL, stock_quantity INTEGER, markup REAL)")
    cursor.execute("CREATE TABLE materials (id INTEGER PRIMARY KEY, name TEXT, stock_level REAL, type TEXT, price_per_unit REAL, category_id INTEGER)")
    cursor.execute("CREATE TABLE product_recipes (id INTEGER PRIMARY KEY, product_id INTEGER, material_id INTEGER, quantity REAL)")
    cursor.execute("CREATE TABLE product_kits (id INTEGER PRIMARY KEY, parent_product_id INTEGER, child_product_id INTEGER, quantity INTEGER)")
    
    # Data
    # Material: Clay ($10)
    cursor.execute("INSERT INTO materials (id, name, price_per_unit) VALUES (1, 'Clay', 10.0)")
    
    # Product 1: Simple ($20 Sale Price, $5 Cost)
    cursor.execute("INSERT INTO products (id, name, base_price) VALUES (1, 'Simple Mug', 20.0)")
    cursor.execute("INSERT INTO product_recipes (product_id, material_id, quantity) VALUES (1, 1, 0.5)") # 0.5 * 10 = $5 cost
    
    # Product 2: Kit ($50 Sale Price, Should be 2 * $5 = $10 Cost)
    cursor.execute("INSERT INTO products (id, name, base_price) VALUES (2, 'Mug Set', 50.0)")
    cursor.execute("INSERT INTO product_kits (parent_product_id, child_product_id, quantity) VALUES (2, 1, 2)") # 2 x Simple Mug
    
    conn.commit()
    conn.close()

def test_profitability_logic():
    conn = sqlite3.connect(DB_PATH)
    
    print("Fetching Profitability Report...")
    start_time = time.time()
    df = analytics_service.get_product_profitability(conn)
    duration = time.time() - start_time
    
    print(df[['Produto', 'Preço Venda', 'Custo Produção']])
    
    # Validation
    # Simple Mug: Cost should be 5.0
    mug = df[df['Produto'] == 'Simple Mug'].iloc[0]
    if abs(mug['Custo Produção'] - 5.0) < 0.01:
        print("✅ Simple Product Cost: Correct (5.0)")
    else:
        print(f"❌ Simple Product Cost: Failed (Got {mug['Custo Produção']})")
        
    # Mug Set (Kit): Cost should be 10.0 (2 * 5.0)
    # CURRENT IMPLEMENTATION likely returns 0 because it only checks product_recipes
    kit = df[df['Produto'] == 'Mug Set'].iloc[0]
    
    if abs(kit['Custo Produção'] - 10.0) < 0.01:
        print("✅ Kit Cost: Correct (10.0)")
    else:
        print(f"❌ Kit Cost: Failed (Got {kit['Custo Produção']}, Expected 10.0)")
        
    conn.close()

if __name__ == "__main__":
    setup_db()
    test_profitability_logic()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
