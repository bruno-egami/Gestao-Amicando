import database
import pandas as pd

try:
    conn = database.get_connection()
    
    # 1. List all Kits
    print("--- KITS DEFINED ---")
    kits = pd.read_sql("""
        SELECT pk.parent_product_id, p_parent.name as kit_name, 
               pk.child_product_id, p_child.name as child_name, pk.quantity
        FROM product_kits pk
        JOIN products p_parent ON pk.parent_product_id = p_parent.id
        JOIN products p_child ON pk.child_product_id = p_child.id
        ORDER BY kit_name
    """, conn)
    print(kits)
    
    # 2. Check Images for Components
    print("\n--- COMPONENT IMAGES ---")
    if not kits.empty:
        child_ids = kits['child_product_id'].unique().tolist()
        if child_ids:
            ids_str = ",".join(map(str, child_ids))
            imgs = pd.read_sql(f"SELECT id, name, image_paths FROM products WHERE id IN ({ids_str})", conn)
            print(imgs)
            
except Exception as e:
    print(f"ERROR: {e}")
