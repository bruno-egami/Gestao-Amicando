import sqlite3
import threading
import time
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import database
from services import product_service

DB_PATH = "amicando_stress_test.db"

def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Minimal schema for products
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            stock_quantity INTEGER,
            base_price REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_variants (
            id INTEGER PRIMARY KEY,
            product_id INTEGER,
            variant_name TEXT,
            stock_quantity INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_kits (
            id INTEGER PRIMARY KEY,
            parent_product_id INTEGER,
            child_product_id INTEGER,
            quantity INTEGER
        )
    """)
    
    # Insert dummy product with stock = 1
    cursor.execute("INSERT INTO products (id, name, stock_quantity) VALUES (1, 'Test Product', 1)")
    conn.commit()
    conn.close()

def attempt_purchase(thread_id, success_list):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Simulate slight delay to align threads
        time.sleep(0.01)
        
        # Call deduct_stock DIRECTLY (the atomic version)
        # Note: In real app, we pass cursor from an active connection.
        # Here we mimic the service logic.
        
        # product_service.deduct_stock expects a cursor.
        # It executes UPDATE ...
        
        product_service.deduct_stock(cursor, 1, 1)
        conn.commit()
        print(f"Thread {thread_id}: SUCCESS")
        success_list.append(thread_id)
        
    except Exception as e:
        conn.rollback()
        print(f"Thread {thread_id}: FAILED ({e})")
    finally:
        conn.close()

def run_stress_test():
    setup_db()
    
    threads = []
    success_list = []
    
    print("Starting Stress Test: 10 threads trying to buy 1 item (Stock=1)...")
    
    for i in range(10):
        t = threading.Thread(target=attempt_purchase, args=(i, success_list))
        threads.append(t)
        
    for t in threads:
        t.start()
        
    for t in threads:
        t.join()
        
    # Verify final stock
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    final_stock = cursor.execute("SELECT stock_quantity FROM products WHERE id=1").fetchone()[0]
    conn.close()
    
    print("-" * 30)
    print(f"Final Stock: {final_stock}")
    print(f"Successful Deductions: {len(success_list)}")
    
    if final_stock < 0:
        print("❌ CRITICAL FAIL: Stock is negative!")
    elif len(success_list) > 1:
        print("❌ FAIL: More than 1 thread succeeded!")
    elif final_stock == 0 and len(success_list) == 1:
        print("✅ PASS: Exactly 1 thread succeeded, stock is 0.")
    elif final_stock == 1 and len(success_list) == 0:
        print("⚠️ WARN: No threads succeeded?")

if __name__ == "__main__":
    run_stress_test()
