import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import database
from services import product_service

DB_PATH = "amicando_bom_test.db"

def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Schema
    cursor.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, stock_quantity INTEGER)")
    cursor.execute("CREATE TABLE product_variants (id INTEGER PRIMARY KEY, product_id INTEGER, variant_name TEXT, stock_quantity INTEGER)")
    cursor.execute("CREATE TABLE product_kits (id INTEGER PRIMARY KEY, parent_product_id INTEGER, child_product_id INTEGER, quantity INTEGER)")
    cursor.execute("CREATE TABLE materials (id INTEGER PRIMARY KEY, name TEXT, stock_level REAL, type TEXT, price_per_unit REAL)")
    cursor.execute("CREATE TABLE product_recipes (id INTEGER PRIMARY KEY, product_id INTEGER, material_id INTEGER, quantity REAL)")
    cursor.execute("CREATE TABLE inventory_transactions (id INTEGER PRIMARY KEY, date TEXT, material_id INTEGER, quantity REAL, type TEXT, cost REAL, user_id TEXT, notes TEXT)")
    
    # 1. Materials
    cursor.execute("INSERT INTO materials (id, name, stock_level, type, price_per_unit) VALUES (1, 'Clay A', 100.0, 'Material', 10.0)")
    cursor.execute("INSERT INTO materials (id, name, stock_level, type, price_per_unit) VALUES (2, 'Glaze B', 50.0, 'Material', 20.0)")
    
    # 2. Products
    # P1: Mug (Uses 0.5 Clay A)
    cursor.execute("INSERT INTO products (id, name, stock_quantity) VALUES (1, 'Mug', 0)")
    cursor.execute("INSERT INTO product_recipes (product_id, material_id, quantity) VALUES (1, 1, 0.5)")
    
    # P2: Plate (Uses 1.0 Clay A)
    cursor.execute("INSERT INTO products (id, name, stock_quantity) VALUES (2, 'Plate', 0)")
    cursor.execute("INSERT INTO product_recipes (product_id, material_id, quantity) VALUES (2, 1, 1.0)")
    
    # P3: Set (Kit: 2 Mugs + 1 Plate) + Extra Glaze (Recipe on Kit itself?) -> Usually kits don't have recipes directly but checking logic
    # Let's say Kit uses Glaze B for packaging (0.1)
    cursor.execute("INSERT INTO products (id, name, stock_quantity) VALUES (3, 'Dinner Set', 0)")
    cursor.execute("INSERT INTO product_kits (parent_product_id, child_product_id, quantity) VALUES (3, 1, 2)") # 2 Mugs
    cursor.execute("INSERT INTO product_kits (parent_product_id, child_product_id, quantity) VALUES (3, 2, 1)") # 1 Plate
    cursor.execute("INSERT INTO product_recipes (product_id, material_id, quantity) VALUES (3, 2, 0.1)") # 0.1 Glaze B
    
    conn.commit()
    conn.close()

def test_bom_calculation():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Testing BOM Calculation for 'Dinner Set' (Kit)...")
    # Expected:
    # 2 Mugs * 0.5 Clay = 1.0 Clay
    # 1 Plate * 1.0 Clay = 1.0 Clay
    # Kit Self * 0.1 Glaze = 0.1 Glaze
    # Total Clay: 2.0
    # Total Glaze: 0.1
    
    bom = product_service.get_product_bom(cursor, 3, 1.0)
    
    clay_qty = bom.get(1, {}).get('needed', 0)
    glaze_qty = bom.get(2, {}).get('needed', 0)
    
    print(f"Clay Needed: {clay_qty} (Expected 2.0)")
    print(f"Glaze Needed: {glaze_qty} (Expected 0.1)")
    
    if abs(clay_qty - 2.0) < 0.001 and abs(glaze_qty - 0.1) < 0.001:
        print("✅ BOM Calculation PASSED")
    else:
        print("❌ BOM Calculation FAILED")
        conn.close()
        return

    print("\nTesting Deduction...")
    # Deduct 1 Kit
    product_service.deduct_production_materials_central(cursor, 3, 1.0)
    conn.commit()
    
    # Verify Stock
    # Initial Clay: 100 - 2.0 = 98.0
    # Initial Glaze: 50 - 0.1 = 49.9
    curr_clay = cursor.execute("SELECT stock_level FROM materials WHERE id=1").fetchone()[0]
    curr_glaze = cursor.execute("SELECT stock_level FROM materials WHERE id=2").fetchone()[0]
    
    print(f"Stock Clay: {curr_clay} (Expected 98.0)")
    print(f"Stock Glaze: {curr_glaze} (Expected 49.9)")
    
    if abs(curr_clay - 98.0) < 0.001 and abs(curr_glaze - 49.9) < 0.001:
         print("✅ Deduction PASSED")
    else:
         print("❌ Deduction FAILED")
         
    conn.close()

if __name__ == "__main__":
    setup_db()
    test_bom_calculation()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
