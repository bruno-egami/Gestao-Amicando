"""
Product Service Module
Handles business logic related to products, stock, and categories.
"""
import pandas as pd
import ast
import os

def get_valid_path(paths_str):
    """Parses a string representation of a list of paths and returns the first valid one."""
    try:
        p = ast.literal_eval(paths_str)
        if p and len(p) > 0: return p[0]
        return None
    except Exception:
        return None

def get_all_products(conn):
    """Fetches all products for the catalog view."""
    query = "SELECT id, name, base_price, stock_quantity, image_paths, category FROM products"
    df = pd.read_sql(query, conn)
    
    # Pre-calculate thumb paths for UI efficiency
    if not df.empty:
        df['thumb_path'] = df['image_paths'].apply(lambda x: get_valid_path(x) if x else None)
    else:
        df['thumb_path'] = None
        
    return df

def get_product_by_id(conn, product_id):
    """Fetches a single product by ID."""
    query = "SELECT * FROM products WHERE id = ?"
    df = pd.read_sql(query, conn, params=(product_id,))
    return df.iloc[0] if not df.empty else None

def get_categories(conn, from_products_df=None):
    """
    Fetches categories. Prioritizes 'product_categories' table, 
    falls back to unique values in 'products' table.
    """
    try:
        cats = pd.read_sql("SELECT name FROM product_categories", conn)['name'].tolist()
        if cats: return cats
    except Exception:
        pass
    
    # Fallback
    if from_products_df is not None:
        return from_products_df['category'].dropna().unique().tolist()
    
    # DB Fallback
    try:
        return pd.read_sql("SELECT DISTINCT category FROM products WHERE category IS NOT NULL", conn)['category'].tolist()
    except:
        return []

def get_kit_components(conn, product_id):
    """Returns a DataFrame of component IDs and quantities for a given kit (parent) product."""
    query = "SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?"
    return pd.read_sql(query, conn, params=(product_id,))

def get_kit_stock_status(conn, product_id):
    """
    Calculates the maximum available stock for a kit based on its components.
    Returns (is_kit, display_stock).
    """
    kit_stock_df = pd.read_sql("""
        SELECT pk.quantity, p.stock_quantity as child_stock 
        FROM product_kits pk
        JOIN products p ON pk.child_product_id = p.id
        WHERE pk.parent_product_id = ?
    """, conn, params=(product_id,))
    
    if kit_stock_df.empty:
        return False, 0
    
    kit_stock_df['max'] = kit_stock_df['child_stock'] // kit_stock_df['quantity']
    display_stock = int(kit_stock_df['max'].min())
    if display_stock < 0: display_stock = 0
    
    return True, display_stock

def get_product_images(conn, product_id):
    """
    Retrieves all image paths for a product, including component images if it's a kit.
    Returns a list of image paths.
    """
    # 1. Product's own images
    prod = pd.read_sql("SELECT image_paths FROM products WHERE id=?", conn, params=(product_id,))
    if prod.empty: return []
    
    own_imgs = []
    raw_paths = prod.iloc[0]['image_paths']
    if raw_paths:
        try:
            parsed = ast.literal_eval(raw_paths)
            if parsed: own_imgs.extend(parsed)
        except: pass
        
    # 2. Kit components images
    kit_children = get_kit_components(conn, product_id)
    comp_imgs = []
    if not kit_children.empty:
        c_ids = ",".join(map(str, kit_children['child_product_id'].tolist()))
        c_imgs_df = pd.read_sql(f"SELECT image_paths FROM products WHERE id IN ({c_ids})", conn)
        
        for _, ci_row in c_imgs_df.iterrows():
            if ci_row['image_paths']:
                try:
                    ci_list = ast.literal_eval(ci_row['image_paths'])
                    if ci_list: comp_imgs.extend(ci_list)
                except: pass
    
    # Prepend components (Prioritize dynamic/component detail) + Own images
    all_imgs = comp_imgs + own_imgs
    
    # Dedup preserving order
    seen = set()
    unique_imgs = []
    for x in all_imgs:
        if x not in seen:
            unique_imgs.append(x)
            seen.add(x)
            
    return unique_imgs

def deduct_stock(cursor, product_id, quantity, check_kits=True):
    """
    Deducts stock from a product. If it's a kit, deducts from components.
    Returns a list of log messages.
    """
    logs = []
    if check_kits:
        # Check if Kit
        # Note: We need a connection for read_sql usually, or we use cursor.execute
        # Cursor is for transaction, so we should stick to cursor if possible, 
        # but read_sql needs connection. 
        # Workaround: Use simple execute for kit check to avoid passing whole conn object if transaction is active?
        # Or pass conn explicitly? Standard practice: pass conn or cursor. 
        # READ operations can use conn, WRITE on cursor.
        pass
        # I'll use cursor.execute for fetching kit data to be safe inside transaction
    
    # Helper to fetch kit components using cursor
    cursor.execute("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", (product_id,))
    kit_comps = cursor.fetchall() # List of tuples (child_id, qty)
    
    if kit_comps:
        logs.append(f"ℹ️ Item ID {product_id} is a KIT. Deducting components...")
        for child_id, needed_qty in kit_comps:
            total_deduct = quantity * needed_qty
            cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?", (int(total_deduct), int(child_id)))
            logs.append(f" - Deducted {total_deduct} from Component ID {child_id}")
    else:
        cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?", (quantity, int(product_id)))
        if cursor.rowcount == 0:
            logs.append(f"⚠️ FAILED to update stock for Product ID {product_id} (Not found?)")
        else:
            # logs.append(f" - Deducted {quantity} from Product ID {product_id}")
            pass
            
    return logs
