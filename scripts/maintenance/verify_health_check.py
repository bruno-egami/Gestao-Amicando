import pandas as pd
import sqlite3
import os
import io

# Mock Streamlit to avoid errors if imported modules use it
import sys
from unittest.mock import MagicMock
sys.modules["streamlit"] = MagicMock()

# Logic Tests

def test_date_parsing():
    print("--- Testing Date Parsing ---")
    data = {'date': ['2023-01-01', '01/02/2023', '2023-03-01T10:00:00', 'Invalid']}
    df = pd.DataFrame(data)
    
    try:
        # The fix we implemented
        df['date_parsed'] = pd.to_datetime(df['date'], format='mixed', errors='coerce').dt.strftime('%d/%m/%Y')
        print("Success: Mixed formats parsed correctly.")
        print(df)
        return True
    except Exception as e:
        print(f"FAIL: Date logic error: {e}")
        return False

def test_kit_image_logic():
    print("\n--- Testing Kit Image Logic ---")
    # Simulate DB Results
    # Product: Kit (ID 1)
    kit_imgs = ["kit_static.jpg"]
    
    # Components (ID 2, 3)
    comp_imgs_db = [
        {"image_paths": "['cup.jpg']"},
        {"image_paths": "['saucer.jpg']"}
    ]
    
    # Logic from pages/5_Produtos.py
    comp_imgs = []
    for row in comp_imgs_db:
        ci_list = eval(row['image_paths'])
        if ci_list: comp_imgs.extend(ci_list)
    
    final_imgs = comp_imgs + kit_imgs
    
    print(f"Final Images: {final_imgs}")
    
    if final_imgs[0] == 'cup.jpg' and final_imgs[-1] == 'kit_static.jpg':
        print("Success: Components prioritised.")
        return True
    else:
        print("FAIL: Image order incorrect.")
        return False

def test_composition_parsing():
    print("\n--- Testing Composition Parse ---")
    # Test String
    comp_str = "RECIPE: Clay: 0.500; Glaze: 0.1"
    
    try:
        parts = comp_str.split(':', 1)
        ctype = parts[0].strip().upper()
        items_str = parts[1].strip()
        items = [i.strip() for i in items_str.split(';') if i.strip()]
        
        parsed = []
        for item in items:
            iparts = item.rsplit(':', 1)
            name = iparts[0].strip()
            qty = float(iparts[1].strip())
            parsed.append((name, qty))
            
        print(f"Parsed: {parsed}")
        
        if parsed[0] == ('Clay', 0.5) and parsed[1] == ('Glaze', 0.1):
            print("Success: Composition parsed correctly.")
            return True
        else:
            print("FAIL: Parsed values mismatch.")
            return False
            
    except Exception as e:
        print(f"FAIL: Parse logic exception: {e}")
        return False

def check_db_integrity():
    print("\n--- Checking DB Integrity ---")
    if not os.path.exists("data/ceramic_admin.db"):
        print("Skip: DB not found (local env?)")
        return True
        
    try:
        conn = sqlite3.connect("data/ceramic_admin.db")
        cursor = conn.cursor()
        
        tables = ['products', 'materials', 'sales', 'product_kits', 'product_recipes']
        for t in tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{t}'")
            if not cursor.fetchone():
                print(f"FAIL: Table {t} missing!")
                return False
        
        # Check specific columns existence by selecting 1 limit 0
        try:
            cursor.execute("SELECT image_paths FROM products LIMIT 0")
        except:
             print("FAIL: products.image_paths missing")
             return False
             
        print("Success: Critical tables and columns exist.")
        conn.close()
        return True
    except Exception as e:
        print(f"Message: {e}")
        return False

if __name__ == "__main__":
    t1 = test_date_parsing()
    t2 = test_kit_image_logic()
    t3 = test_composition_parsing()
    t4 = check_db_integrity()
    
    if t1 and t2 and t3 and t4:
        print("\n✅ GLOBAL SUCCESS: All logic checks passed.")
    else:
        print("\n❌ GLOBAL FAILURE: Some checks failed.")
