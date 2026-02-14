"""
Product Service Module
Handles business logic related to products, stock, and categories.
"""
import streamlit as st
import pandas as pd
import ast
import os
import sqlite3
import audit
from datetime import datetime
from utils.logging_config import get_logger, log_exception

logger = get_logger(__name__)

def get_valid_path(paths_str):
    """Parses a string representation of a list of paths and returns the first valid one."""
    try:
        p = ast.literal_eval(paths_str)
        if p and len(p) > 0: return p[0]
        return None
    except (ValueError, SyntaxError):
        return None

@st.cache_data(ttl=60, show_spinner=False)
def get_all_products(_conn):
    """Fetches all products for the catalog view."""
    query = "SELECT id, name, base_price, stock_quantity, image_paths, category FROM products"
    df = pd.read_sql(query, _conn)
    
    # Pre-calculate thumb paths for UI efficiency
    if not df.empty:
        df['thumb_path'] = df['image_paths'].apply(lambda x: get_valid_path(x) if x else None)
    else:
        df['thumb_path'] = None
        
    return df

@st.cache_data(ttl=60, show_spinner=False)
def get_all_materials(_conn):
    """Fetches all materials for reports/stock view."""
    query = """
        SELECT m.name as 'Nome', mc.name as 'Categoria', m.stock_level as 'Estoque',
               m.unit as 'Unidade', m.price_per_unit as 'Preço Unit.',
               (m.stock_level * m.price_per_unit) as 'Valor Total',
               m.min_stock_alert, m.type, m.id
        FROM materials m
        LEFT JOIN material_categories mc ON m.category_id = mc.id
        WHERE m.type = 'Material'
        ORDER BY m.name
    """
    return pd.read_sql(query, _conn)

@st.cache_data(ttl=60, show_spinner=False)
def get_wip_stock_value(_conn):
    """Calculates WIP (Work In Process) value for reports."""
    wip_query = """
        SELECT 
            'WIP: ' || p.name as 'Nome', 
            'Em Produção' as 'Categoria',
            w.quantity as 'Estoque',
            'un' as 'Unidade',
            SUM(pr.quantity * m.price_per_unit) as 'Preço Unit.',  -- Estimated Material Cost per Unit
            (w.quantity * SUM(pr.quantity * m.price_per_unit)) as 'Valor Total',
            w.product_id
        FROM production_wip w
        JOIN products p ON w.product_id = p.id
        JOIN product_recipes pr ON p.id = pr.product_id
        JOIN materials m ON pr.material_id = m.id
        WHERE w.materials_deducted = 1
        GROUP BY w.id
    """
    try:
        df = pd.read_sql(wip_query, _conn)
        if not df.empty:
            df['Tipo'] = 'WIP (Em Processo)'
        return df
    except Exception:
        return pd.DataFrame()

def get_product_by_id(conn, product_id):
    """Fetches a single product by ID."""
    query = "SELECT * FROM products WHERE id = ?"
    df = pd.read_sql(query, conn, params=(product_id,))
    return df.iloc[0] if not df.empty else None

@st.cache_data(ttl=300, show_spinner=False)
def get_categories(_conn, from_products_df=None):
    """
    Fetches categories. Prioritizes 'product_categories' table, 
    falls back to unique values in 'products' table.
    """
    try:
        cats = pd.read_sql("SELECT name FROM product_categories", _conn)['name'].tolist()
        if cats: return cats
    except (sqlite3.Error, pd.io.sql.DatabaseError):
        pass
    
    # Fallback
    if from_products_df is not None:
        return from_products_df['category'].dropna().unique().tolist()
    
    # DB Fallback
    try:
        return pd.read_sql("SELECT DISTINCT category FROM products WHERE category IS NOT NULL", _conn)['category'].tolist()
    except (sqlite3.Error, pd.io.sql.DatabaseError):
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
        except (ValueError, SyntaxError) as e:
            logger.warning(f"Failed to parse image paths for product {product_id}: {e}")
        
    # 2. Kit components images
    kit_children = get_kit_components(conn, product_id)
    comp_imgs = []
    if not kit_children.empty:
        ids_list = kit_children['child_product_id'].tolist()
        placeholders = ','.join(['?'] * len(ids_list))
        c_imgs_df = pd.read_sql(f"SELECT image_paths FROM products WHERE id IN ({placeholders})", conn, params=ids_list)
        
        for _, ci_row in c_imgs_df.iterrows():
            if ci_row['image_paths']:
                try:
                    ci_list = ast.literal_eval(ci_row['image_paths'])
                    if ci_list: comp_imgs.extend(ci_list)
                except (ValueError, SyntaxError) as e:
                    logger.warning(f"Failed to parse image paths for kit component in product {product_id}: {e}")
    
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

def deduct_stock(cursor, product_id, quantity, check_kits=True, variant_id=None):
    """
    Deducts stock from a product. If variant_id is provided, deducts from variant.
    If it's a kit (and no variant_id), deducts from components.
    Returns a list of log messages.
    """
    logs = []
    
    if variant_id:
        # Variant Deduction (Direct)
        cursor.execute("UPDATE product_variants SET stock_quantity = stock_quantity - ? WHERE id = ?", (quantity, int(variant_id)))
        if cursor.rowcount > 0:
             # logs.append(f" - Deducted {quantity} from Variant ID {variant_id}")
             pass
        else:
             logs.append(f"⚠️ FAILED to update stock for Variant ID {variant_id}")
        return logs

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
            
    # Clear cache since stock changed
    get_all_products.clear()
            
    return logs

def check_recipe_availability(cursor, product_id, quantity, filter_type=None, exclude_ids=None):
    """
    Checks if all required materials for a product (and its kit components) are available in stock.
    Returns (True, []) if all available, or (False, [missing_items_list]) if not.
    """
    recipes_needed = []
    
    def collect_recipes(pid, mul):
        query = "SELECT m.id, m.name, r.quantity as qty_per_unit, m.stock_level FROM product_recipes r JOIN materials m ON r.material_id = m.id WHERE r.product_id=?"
        cursor.execute(query, (int(pid),))
        for mid, mname, qty_unit, s_level in cursor.fetchall():
            recipes_needed.append({
                'id': mid,
                'name': mname,
                'needed': qty_unit * mul * quantity,
                'available': s_level
            })
            
        cursor.execute("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", (int(pid),))
        for child_id, child_qty in cursor.fetchall():
            collect_recipes(child_id, mul * child_qty)
            
    collect_recipes(product_id, 1.0)
    
    missing = []
    for r in recipes_needed:
        is_clay = any(keyword in r['name'].lower() for keyword in ['massa', 'argila'])
        
        apply_check = False
        if filter_type == 'clay' and is_clay:
            apply_check = True
        elif filter_type == 'others' and not is_clay:
            if not exclude_ids or r['id'] not in exclude_ids:
                apply_check = True
        elif filter_type is None:
            apply_check = True
            
        if apply_check and r['needed'] > r['available']:
            missing.append(f"{r['name']} (Necessário: {r['needed']:.3f}, Disponível: {r['available']:.3f})")
            
    if missing:
        return False, missing
    return True, []

def deduct_production_materials_central(cursor, product_id, quantity, filter_type=None, exclude_ids=None, note_suffix=""):
    """
    Deducts raw materials from stock based on product recipe (recursive for kits).
    filter_type: 'clay' (only materials with Massa/Argila in name), 
                 'others' (everything except clay and material_ids in exclude_ids)
    """
    from datetime import date
    
    # 1. Validation Logic
    available, missing = check_recipe_availability(cursor, product_id, quantity, filter_type, exclude_ids)
    if not available:
        raise ValueError(f"Estoque insuficiente para os seguintes insumos: {', '.join(missing)}")

    # 2. Collect all recipes (Recursive for Kits)
    recipes_to_deduct = []
    
    def collect_recipes(pid, mul):
        # Direct recipes for this product
        query = "SELECT m.id, m.name, r.quantity as qty_per_unit FROM product_recipes r JOIN materials m ON r.material_id = m.id WHERE r.product_id=?"
        cursor.execute(query, (int(pid),))
        for mid, mname, qty_unit in cursor.fetchall():
            recipes_to_deduct.append({
                'id': mid,
                'name': mname,
                'qty_total': qty_unit * mul * quantity
            })
            
        # If it's a kit, collect children recipes
        cursor.execute("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", (int(pid),))
        for child_id, child_qty in cursor.fetchall():
            collect_recipes(child_id, mul * child_qty)
            
    collect_recipes(product_id, 1.0)
    
    logs = []
    for r in recipes_to_deduct:
        is_clay = any(keyword in r['name'].lower() for keyword in ['massa', 'argila'])
        
        should_deduct = False
        if filter_type == 'clay' and is_clay:
            should_deduct = True
        elif filter_type == 'others' and not is_clay:
            if not exclude_ids or r['id'] not in exclude_ids:
                should_deduct = True
        elif filter_type is None:
            should_deduct = True
            
        if should_deduct:
            d_qty = r['qty_total']
            cursor.execute("UPDATE materials SET stock_level = stock_level - ? WHERE id=?", (d_qty, r['id']))
            cursor.execute("INSERT INTO inventory_transactions (date, material_id, quantity, type, notes) VALUES (?, ?, ?, 'SAIDA', ?)", 
                          (date.today().isoformat(), r['id'], d_qty, f"Produção ID {product_id} {note_suffix}"))
            logs.append(f"Deduzido {d_qty} de {r['name']}")
            
    return logs

def create_variant(conn, product_id, name, stock, price_adder, material_id=None, material_quantity=0.0):
    """Creates a new variant for a product."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO product_variants (product_id, variant_name, stock_quantity, price_adder, material_id, material_quantity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (int(product_id), name, int(stock), float(price_adder), material_id if material_id else None, float(material_quantity)))
        conn.commit()
        return True
    except sqlite3.Error as e:
        log_exception(logger, f"Error creating variant for product {product_id}", e)
        return False

def get_product_variants(conn, product_id):
    """Returns a DataFrame of variants for a given product."""
    query = """
        SELECT pv.*, m.name as material_name 
        FROM product_variants pv
        LEFT JOIN materials m ON pv.material_id = m.id
        WHERE pv.product_id = ?
    """
    return pd.read_sql(query, conn, params=(int(product_id),))

def get_variant_by_id(conn, variant_id):
    """Fetches a single variant by ID."""
    query = "SELECT * FROM product_variants WHERE id = ?"
    df = pd.read_sql(query, conn, params=(int(variant_id),))
    return df.iloc[0] if not df.empty else None

def update_variant_stock(conn, variant_id, new_quantity):
    """Updates the stock quantity of a variant."""
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE product_variants SET stock_quantity = ? WHERE id = ?", (int(new_quantity), int(variant_id)))
        conn.commit()
        return True
    except sqlite3.Error as e:
        log_exception(logger, f"Error updating variant stock {variant_id}", e)
        return False

def delete_variant(conn, variant_id):
    """Deletes a variant."""
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM product_variants WHERE id = ?", (int(variant_id),))
        conn.commit()
        return True
    except sqlite3.Error as e:
        log_exception(logger, f"Error deleting variant {variant_id}", e)
        return False

def update_variant_price(conn, variant_id, new_adder):
    """Updates the price adder of a variant."""
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE product_variants SET price_adder = ? WHERE id = ?", (float(new_adder), int(variant_id)))
        conn.commit()
        return True
    except sqlite3.Error as e:
        log_exception(logger, f"Error updating variant price {variant_id}", e)
        return False


# ─────────────────────────────────────────────────────────
# CATEGORY MANAGEMENT
# ─────────────────────────────────────────────────────────

def get_category_list(conn):
    """Returns a list of category names from product_categories table."""
    try:
        cat_df = pd.read_sql("SELECT name FROM product_categories", conn)
        return cat_df['name'].tolist()
    except (sqlite3.Error, pd.io.sql.DatabaseError):
        return ["Utilitário", "Decorativo", "Outros"]


def add_category(conn, name):
    """Inserts a new category. Returns True on success."""
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO product_categories (name) VALUES (?)", (name,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        log_exception(logger, f"Error adding category '{name}'", e)
        raise


def delete_category(conn, name):
    """Deletes a category by name."""
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM product_categories WHERE name=?", (name,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        log_exception(logger, f"Error deleting category '{name}'", e)
        raise


# ─────────────────────────────────────────────────────────
# PRODUCT CRUD
# ─────────────────────────────────────────────────────────

def create_product(conn, name, description, category, markup):
    """Creates a new product. Returns the new product ID."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO products (name, description, category, markup, image_paths, stock_quantity, base_price)
            VALUES (?, ?, ?, ?, '[]', 0, 0)
        """, (name, description, category, markup))
        new_id = cursor.lastrowid
        audit.log_action(conn, 'CREATE', 'products', new_id, None, {'name': name}, commit=False)
        conn.commit()
        return new_id
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error creating product '{name}'", e)
        raise


def duplicate_product(conn, source_product_id, source_product):
    """
    Duplicates a product with its recipes and kit components.
    source_product: dict/Series with name, description, category, markup.
    Returns the new product ID.
    """
    cursor = conn.cursor()
    try:
        new_name = f"{source_product['name']} (Cópia)"
        cursor.execute("""
            INSERT INTO products (name, description, category, markup, image_paths, stock_quantity, base_price)
            VALUES (?, ?, ?, ?, '[]', 0, 0)
        """, (new_name, source_product['description'], source_product['category'], source_product['markup']))
        conn.commit()
        new_prod_id = cursor.lastrowid

        # Copy recipes
        recipes = pd.read_sql("""
            SELECT material_id, quantity FROM product_recipes WHERE product_id = ?
        """, conn, params=(source_product_id,))
        for _, rec in recipes.iterrows():
            cursor.execute("""
                INSERT INTO product_recipes (product_id, material_id, quantity)
                VALUES (?, ?, ?)
            """, (new_prod_id, rec['material_id'], rec['quantity']))

        # Copy kit components
        kits = pd.read_sql("""
            SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id = ?
        """, conn, params=(source_product_id,))
        for _, kit in kits.iterrows():
            cursor.execute("""
                INSERT INTO product_kits (parent_product_id, child_product_id, quantity)
                VALUES (?, ?, ?)
            """, (new_prod_id, kit['child_product_id'], kit['quantity']))

        conn.commit()

        audit.log_action(conn, 'CREATE', 'products', new_prod_id, None, {
            'name': new_name, 'duplicated_from': source_product_id
        })
        return new_prod_id
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error duplicating product {source_product_id}", e)
        raise


def delete_product(conn, product_id, product_name):
    """Deletes a product and its associated recipes, kits, and variants."""
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM product_recipes WHERE product_id=?", (product_id,))
        cursor.execute("DELETE FROM product_kits WHERE parent_product_id=?", (product_id,))
        cursor.execute("DELETE FROM product_variants WHERE product_id=?", (product_id,))
        cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
        audit.log_action(conn, 'DELETE', 'products', product_id, {'name': product_name}, None, commit=False)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error deleting product {product_id}", e)
        raise


def update_product_details(conn, product_id, name, category, description, stock_quantity,
                           old_name=None, old_stock=None):
    """Updates product details (name, category, description, stock)."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE products SET name=?, category=?, description=?, stock_quantity=? WHERE id=?",
            (name, category, description, stock_quantity, product_id)
        )
        audit.log_action(conn, 'UPDATE', 'products', product_id,
                         {'name': old_name, 'stock': old_stock},
                         {'name': name, 'stock': stock_quantity}, commit=False)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error updating product {product_id}", e)
        raise


def log_stock_adjustment(conn, product_id, product_name, diff, user_id=None, username='system'):
    """Logs a manual stock adjustment in production_history."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO production_history (timestamp, product_id, product_name, quantity, user_id, username, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now().isoformat(), product_id, product_name, diff, user_id, username, "Ajuste Manual"))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error logging stock adjustment for product {product_id}", e)
        raise


def get_kit_detail_for_edit(conn, product_id):
    """Returns kit components with stock info for editing view."""
    return pd.read_sql("""
        SELECT pk.quantity, p.stock_quantity as child_stock, p.name
        FROM product_kits pk
        JOIN products p ON pk.child_product_id = p.id
        WHERE pk.parent_product_id = ?
    """, conn, params=(product_id,))


# ─────────────────────────────────────────────────────────
# RECIPE MANAGEMENT
# ─────────────────────────────────────────────────────────

def get_materials_list(conn):
    """Returns all materials for recipe dropdowns."""
    return pd.read_sql("SELECT id, name, unit, price_per_unit FROM materials ORDER BY name", conn)


def get_materials_for_variants(conn):
    """Returns materials excluding labor type for variant dropdowns."""
    return pd.read_sql(
        "SELECT id, name, unit, price_per_unit FROM materials WHERE type != 'Mão de Obra' ORDER BY name", conn
    )


def add_recipe_item(conn, product_id, material_id, quantity):
    """Adds a material to a product's recipe."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO product_recipes (product_id, material_id, quantity) VALUES (?, ?, ?)",
            (product_id, material_id, quantity)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error adding recipe item to product {product_id}", e)
        raise


def get_product_recipe(conn, product_id):
    """Returns the recipe (materials) for a product with details."""
    return pd.read_sql("""
        SELECT pr.id, m.name, pr.quantity, m.unit, m.price_per_unit
        FROM product_recipes pr
        JOIN materials m ON pr.material_id = m.id
        WHERE pr.product_id = ?
    """, conn, params=(product_id,))


def delete_recipe_item(conn, recipe_id):
    """Removes a recipe item by its ID."""
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM product_recipes WHERE id=?", (recipe_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error deleting recipe item {recipe_id}", e)
        raise


# ─────────────────────────────────────────────────────────
# KIT MANAGEMENT
# ─────────────────────────────────────────────────────────

def get_products_for_kit(conn, exclude_product_id):
    """Returns products available for kit composition (excludes self)."""
    return pd.read_sql(
        "SELECT id, name FROM products WHERE id != ? ORDER BY name",
        conn, params=(exclude_product_id,)
    )


def add_kit_item(conn, parent_product_id, child_product_id, quantity):
    """Adds a component to a kit."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO product_kits (parent_product_id, child_product_id, quantity) VALUES (?, ?, ?)",
            (parent_product_id, child_product_id, quantity)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error adding kit component to product {parent_product_id}", e)
        raise


def get_kit_items_detail(conn, parent_product_id):
    """Returns kit items with component names."""
    return pd.read_sql("""
        SELECT pk.id, p.name as component_name, pk.quantity
        FROM product_kits pk
        JOIN products p ON pk.child_product_id = p.id
        WHERE pk.parent_product_id = ?
    """, conn, params=(parent_product_id,))


def delete_kit_item(conn, kit_id):
    """Removes a kit component by its ID."""
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM product_kits WHERE id=?", (kit_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error deleting kit item {kit_id}", e)
        raise


# ─────────────────────────────────────────────────────────
# IMAGE MANAGEMENT
# ─────────────────────────────────────────────────────────

def update_product_images(conn, product_id, image_paths_list):
    """Updates the image_paths for a product."""
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE products SET image_paths=? WHERE id=?", (str(image_paths_list), product_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error updating product images {product_id}", e)
        raise


def get_kit_component_images(conn, parent_product_id):
    """Returns component product names and image_paths for a kit."""
    comps = pd.read_sql(
        "SELECT child_product_id FROM product_kits WHERE parent_product_id=?",
        conn, params=(parent_product_id,)
    )
    if comps.empty:
        return pd.DataFrame()
    comp_ids = comps['child_product_id'].tolist()
    placeholders = ",".join(["?"] * len(comp_ids))
    return pd.read_sql(
        f"SELECT name, image_paths FROM products WHERE id IN ({placeholders})",
        conn, params=comp_ids
    )


# ─────────────────────────────────────────────────────────
# PRICING
# ─────────────────────────────────────────────────────────

def save_product_pricing(conn, product_id, markup, base_price):
    """Saves markup and base_price for a product."""
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE products SET markup = ?, base_price = ? WHERE id = ?",
                       (markup, base_price, product_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error saving pricing for product {product_id}", e)
        raise


def get_pricing_kit_components(conn, product_id):
    """Returns kit components with name and base_price for pricing calculation."""
    return pd.read_sql("""
        SELECT pk.quantity, p.name, p.base_price
        FROM product_kits pk
        JOIN products p ON pk.child_product_id = p.id
        WHERE pk.parent_product_id = ?
    """, conn, params=(product_id,))


def get_pricing_recipe_items(conn, product_id):
    """Returns recipe items with material prices for cost calculation."""
    return pd.read_sql("""
        SELECT m.name, pr.quantity, m.price_per_unit, m.unit
        FROM product_recipes pr
        JOIN materials m ON pr.material_id = m.id
        WHERE pr.product_id = ?
    """, conn, params=(product_id,))


def get_material_price(conn, material_id):
    """Returns price and unit for a material."""
    return pd.read_sql(
        "SELECT price_per_unit, unit FROM materials WHERE id=?",
        conn, params=(material_id,)
    )


# ─────────────────────────────────────────────────────────
# PRODUCTION — CATALOG TAB
# ─────────────────────────────────────────────────────────

def get_recipe_for_production(conn, product_id, quantity):
    """Returns recipe with needed amounts for production check."""
    return pd.read_sql("""
        SELECT m.id, m.name, m.stock_level, (pr.quantity * ?) as needed, m.unit, m.type
        FROM product_recipes pr
        JOIN materials m ON pr.material_id = m.id
        WHERE pr.product_id = ?
    """, conn, params=(quantity, product_id))


def get_material_for_variant(conn, material_id):
    """Returns material info for variant production check."""
    return pd.read_sql(
        "SELECT id, name, stock_level, unit, type FROM materials WHERE id=?",
        conn, params=(material_id,)
    )


def produce_from_kit(conn, product_id, product_name, quantity, target_variant_id,
                     prod_target_label, user_id=None, username='system'):
    """
    Assembles a kit: deducts component stock, adds product/variant stock, logs history.
    Returns True on success.
    """
    cursor = conn.cursor()
    try:
        kits = pd.read_sql(
            "SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?",
            conn, params=(product_id,)
        )

        # Check availability
        for _, kit_item in kits.iterrows():
            needed_total = kit_item['quantity'] * quantity
            child_stock = pd.read_sql(
                "SELECT stock_quantity, name FROM products WHERE id=?",
                conn, params=(kit_item['child_product_id'],)
            ).iloc[0]
            if child_stock['stock_quantity'] < needed_total:
                raise ValueError(
                    f"Estoque insuficiente: {child_stock['name']} "
                    f"(Precisa {needed_total}, Tem {child_stock['stock_quantity']})"
                )

        # Deduct components
        for _, kit_item in kits.iterrows():
            needed_total = kit_item['quantity'] * quantity
            cursor.execute(
                "UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?",
                (needed_total, kit_item['child_product_id'])
            )

        # Add stock to target
        if target_variant_id:
            cursor.execute(
                "UPDATE product_variants SET stock_quantity = stock_quantity + ? WHERE id = ?",
                (quantity, int(target_variant_id))
            )
        else:
            cursor.execute(
                "UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?",
                (quantity, product_id)
            )

        # Log history
        notes = 'Produção de Kit (Variação)' if target_variant_id else 'Produção de Kit'
        cursor.execute(
            "INSERT INTO production_history (timestamp, product_id, product_name, quantity, user_id, username, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), product_id, f"{product_name} ({prod_target_label})",
             quantity, user_id, username, notes)
        )
        conn.commit()
        return True
    except ValueError:
        raise
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error producing kit {product_id}", e)
        raise


def produce_regular(conn, product_id, product_name, quantity, recipe_df, extra_mat_needed,
                    target_variant_id, prod_target_label, user_id=None, username='system'):
    """
    Regular production: deducts recipe materials, extra variant materials,
    adds product/variant stock, logs history + audit.
    recipe_df: DataFrame from get_recipe_for_production.
    extra_mat_needed: list of dicts with id, needed.
    Returns True on success.
    """
    cursor = conn.cursor()
    try:
        # Deduct base recipe (physical materials only)
        for _, mat in recipe_df.iterrows():
            is_skip = (
                (mat['unit'] == 'fornada') or
                (str(mat['name']).startswith('Queima')) or
                (mat['type'] == 'Queima') or
                (mat['type'] == 'Mão de Obra') or
                (mat['unit'] == 'hora (mão de obra)')
            )
            if not is_skip:
                needed_py = float(mat['needed'])
                cursor.execute(
                    "UPDATE materials SET stock_level = stock_level - ? WHERE id = ?",
                    (needed_py, int(mat['id']))
                )
                cursor.execute(
                    "INSERT INTO inventory_transactions (material_id, date, type, quantity, notes, user_id) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (int(mat['id']), datetime.now().isoformat(), 'SAIDA', needed_py,
                     f"Prod: {quantity}x {product_name}", user_id)
                )

        # Deduct variant-specific materials
        for em in extra_mat_needed:
            needed_py = float(em['needed'])
            cursor.execute(
                "UPDATE materials SET stock_level = stock_level - ? WHERE id = ?",
                (needed_py, int(em['id']))
            )
            cursor.execute(
                "INSERT INTO inventory_transactions (material_id, date, type, quantity, notes, user_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (int(em['id']), datetime.now().isoformat(), 'SAIDA', needed_py,
                 f"Prod Var: {quantity}x {product_name}", user_id)
            )

        # Update stock
        if target_variant_id:
            cursor.execute(
                "UPDATE product_variants SET stock_quantity = stock_quantity + ? WHERE id = ?",
                (quantity, int(target_variant_id))
            )
        else:
            cursor.execute(
                "UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?",
                (quantity, product_id)
            )

        # Log production history
        cursor.execute(
            "INSERT INTO production_history (timestamp, product_id, product_name, quantity, user_id, username, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), product_id, f"{product_name} ({prod_target_label})",
             quantity, user_id, username, 'Produção Geral')
        )
        hist_id = cursor.lastrowid
        audit.log_action(conn, 'CREATE', 'production_history', hist_id, None,
                         {'product_id': product_id, 'quantity': quantity, 'variant_id': target_variant_id},
                         commit=False)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error in regular production for product {product_id}", e)
        raise


# ─────────────────────────────────────────────────────────
# PRODUCTION HISTORY TAB
# ─────────────────────────────────────────────────────────

def get_production_history_product_names(conn):
    """Returns distinct product names from production_history."""
    return pd.read_sql(
        "SELECT DISTINCT product_name FROM production_history ORDER BY product_name", conn
    )


def get_production_history_usernames(conn):
    """Returns distinct usernames from production_history."""
    return pd.read_sql(
        "SELECT DISTINCT username FROM production_history ORDER BY username", conn
    )


def get_production_history_filtered(conn, query, params):
    """Runs a filtered production history query."""
    return pd.read_sql(query, conn, params=params)


def update_production_history_qty(conn, history_id, new_qty, old_qty, product_id):
    """Updates production history quantity and adjusts product stock accordingly."""
    cursor = conn.cursor()
    try:
        diff = new_qty - old_qty
        cursor.execute("UPDATE production_history SET quantity = ? WHERE id = ?", (new_qty, history_id))
        cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (diff, product_id))
        conn.commit()
        audit.log_action(conn, 'UPDATE', 'production_history', history_id,
                         {'quantity': old_qty}, {'quantity': new_qty})
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error updating production history {history_id}", e)
        raise


def delete_production_history(conn, history_id, product_id, quantity, product_name):
    """Deletes a production history record and reverts product stock."""
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?", (quantity, product_id))
        cursor.execute("DELETE FROM production_history WHERE id = ?", (history_id,))
        conn.commit()
        audit.log_action(conn, 'DELETE', 'production_history', history_id,
                         {'product_name': product_name, 'quantity': quantity}, None)
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error deleting production history {history_id}", e)
        raise
