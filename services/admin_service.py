"""
Admin Service Module
Handles User Management, Data Import, and Data Export logic.
"""
import pandas as pd
import sqlite3
import auth
import audit
from datetime import datetime
from utils.logging_config import get_logger, log_exception

logger = get_logger(__name__)

# ==============================================================================
# USER MANAGEMENT
# ==============================================================================

def get_all_users(conn):
    """Fetches all users."""
    return pd.read_sql("SELECT id, username, name, role, active, last_login FROM users ORDER BY username", conn)

def get_user_by_id(conn, user_id):
    """Fetches a single user by ID."""
    df = pd.read_sql("SELECT * FROM users WHERE id = ?", conn, params=(user_id,))
    return df.iloc[0] if not df.empty else None

def create_user(conn, username, password, name, role, active):
    """Creates a new user."""
    cursor = conn.cursor()
    try:
        # Check if username exists
        existing = pd.read_sql("SELECT id FROM users WHERE username=?", conn, params=(username,))
        if not existing.empty:
            raise ValueError("Este usuário já existe.")

        cursor.execute("""
            INSERT INTO users (username, password_hash, role, name, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username, auth.hash_password(password), role, name, int(active), datetime.now().isoformat()))
        new_id = cursor.lastrowid
        conn.commit()
        
        audit.log_action(conn, 'CREATE', 'users', new_id, None,
            {'username': username, 'name': name, 'role': role})
        return new_id
    except ValueError:
        raise
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error creating user {username}", e)
        raise

def update_user(conn, user_id, name, role, active, password=None):
    """Updates an existing user."""
    cursor = conn.cursor()
    try:
        # Get old data for audit
        old_user = get_user_by_id(conn, user_id)
        old_data = old_user.to_dict() if old_user is not None else {}
        
        if password:
            cursor.execute("""
                UPDATE users SET name=?, role=?, active=?, password_hash=? WHERE id=?
            """, (name, role, int(active), auth.hash_password(password), user_id))
        else:
            cursor.execute("""
                UPDATE users SET name=?, role=?, active=? WHERE id=?
            """, (name, role, int(active), user_id))
            
        conn.commit()
        
        audit.log_action(conn, 'UPDATE', 'users', user_id, old_data,
            {'name': name, 'role': role, 'active': active})
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error updating user {user_id}", e)
        raise

def delete_user(conn, user_id):
    """Deletes a user."""
    cursor = conn.cursor()
    try:
        # Check if it's the last admin
        user = get_user_by_id(conn, user_id)
        if user['role'] == 'admin':
            admin_count = pd.read_sql("SELECT count(*) as c FROM users WHERE role='admin' AND active=1", conn).iloc[0]['c']
            if admin_count <= 1:
                raise ValueError("Não é possível excluir o último administrador.")
        
        old_data = user.to_dict() if user is not None else {}
        cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        
        audit.log_action(conn, 'DELETE', 'users', user_id, old_data, None)
        return True
    except ValueError:
        raise
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error deleting user {user_id}", e)
        raise

# ==============================================================================
# DATA EXPORT
# ==============================================================================

def export_materials_for_balance(conn):
    """Exports materials for stock taking."""
    query = """
        SELECT 
            m.name as Nome, 
            m.price_per_unit as Preço, 
            m.unit as Unidade, 
            m.stock_level as Estoque, 
            m.type as Tipo,
            mc.name as Categoria,
            s.name as Fornecedor
        FROM materials m
        LEFT JOIN material_categories mc ON m.category_id = mc.id
        LEFT JOIN suppliers s ON m.supplier_id = s.id
        ORDER BY m.name
    """
    return pd.read_sql(query, conn)

def export_products(conn):
    """Exports products with composition."""
    query = """
        SELECT 
            p.id as ID_INTERNO,
            p.name as "Nome", 
            p.base_price as "Preço Base", 
            p.stock_quantity as "Estoque", 
            p.category as "Categoria",
            p.weight_g as "Peso (g)"
        FROM products p
        ORDER BY p.name
    """
    products_df = pd.read_sql(query, conn)
    
    comp_list = []
    for _, prow in products_df.iterrows():
        pid = prow['ID_INTERNO']
        comp_str = ""
        
        # 1. Check if Kit
        kits = pd.read_sql("""
            SELECT pk.quantity, p.name 
            FROM product_kits pk
            JOIN products p ON pk.child_product_id = p.id
            WHERE pk.parent_product_id = ?
        """, conn, params=(pid,))
        
        if not kits.empty:
            items = [f"{k['name'].replace(';', ',')}: {k['quantity']}" for _, k in kits.iterrows()]
            comp_str = "KIT: " + "; ".join(items)
        else:
            # 2. Check Recipe
            recipes = pd.read_sql("""
                SELECT m.name, pr.quantity
                FROM product_recipes pr
                JOIN materials m ON pr.material_id = m.id
                WHERE pr.product_id = ?
            """, conn, params=(pid,))
            
            if not recipes.empty:
                items = [f"{r['name'].replace(';', ',')}: {r['quantity']}" for _, r in recipes.iterrows()]
                comp_str = "RECIPE: " + "; ".join(items)
        
        comp_list.append(comp_str)
    
    products_df['Composição'] = comp_list
    del products_df['ID_INTERNO']
    return products_df

def export_sales(conn):
    """Exports sales data."""
    query = """
        SELECT 
            s.id as ID, 
            s.date as Data, 
            p.name as Produto, 
            s.quantity as Qtd, 
            s.total_price as Total, 
            c.name as Cliente, 
            s.status as Status
        FROM sales s
        LEFT JOIN products p ON s.product_id = p.id
        LEFT JOIN clients c ON s.client_id = c.id
        ORDER BY s.date DESC
    """
    return pd.read_sql(query, conn)

def export_expenses(conn):
    """Exports expenses data."""
    query = """
        SELECT 
            id as ID,
            date as "Data (AAAA-MM-DD)", 
            description as "Descrição", 
            amount as "Valor", 
            category as "Categoria"
        FROM expenses
        ORDER BY date DESC
    """
    return pd.read_sql(query, conn)

def export_suppliers(conn):
    """Exports suppliers."""
    return pd.read_sql("SELECT name as Nome, email as Email, phone as Telefone FROM suppliers ORDER BY name", conn)

def export_clients(conn):
    """Exports clients."""
    return pd.read_sql("SELECT name as Nome, phone as Telefone, email as Email, date_of_birth as 'Data Nascimento' FROM clients ORDER BY name", conn)

# ==============================================================================
# DATA IMPORT HELPERS
# ==============================================================================

def upsert_material(cursor, row, user_id=1):
    """Upserts a material from import row."""
    # 1. Foreign Keys
    cat_name = str(row['Categoria']).strip()
    cursor.execute("SELECT id FROM material_categories WHERE name=?", (cat_name,))
    res = cursor.fetchone()
    if res: cat_id = res[0]
    else:
        cursor.execute("INSERT INTO material_categories (name) VALUES (?)", (cat_name,))
        cat_id = cursor.lastrowid
        
    sup_name = str(row['Fornecedor']).strip()
    cursor.execute("SELECT id FROM suppliers WHERE name=?", (sup_name,))
    res = cursor.fetchone()
    if res: sup_id = res[0]
    else:
        cursor.execute("INSERT INTO suppliers (name) VALUES (?)", (sup_name,))
        sup_id = cursor.lastrowid

    # 2. Check Duplicate
    cursor.execute("SELECT id, stock_level FROM materials WHERE name=?", (row['Nome'],))
    mat_res = cursor.fetchone()
    
    if mat_res:
        # UPDATE
        target_id = mat_res[0]
        curr_stock = float(mat_res[1]) if mat_res[1] else 0.0
        new_stock = float(row['Estoque'])
        
        cursor.execute("""
            UPDATE materials 
            SET price_per_unit=?, unit=?, stock_level=?, type=?, category_id=?, supplier_id=?
            WHERE id=?
        """, (row['Preço'], row['Unidade'], new_stock, row['Tipo'], cat_id, sup_id, target_id))
        
        if abs(new_stock - curr_stock) > 0.001:
            diff = new_stock - curr_stock
            cursor.execute("""
                INSERT INTO inventory_transactions (material_id, date, type, quantity, cost, notes, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (target_id, datetime.now().isoformat(), 'AJUSTE', abs(diff), 0.0, "Importação em Massa", user_id))
    else:
        # INSERT
        cursor.execute("""
            INSERT INTO materials (name, price_per_unit, unit, stock_level, type, category_id, supplier_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (row['Nome'], row['Preço'], row['Unidade'], row['Estoque'], row['Tipo'], cat_id, sup_id))

def upsert_product_and_composition(cursor, row, user_id=1, username='system'):
    """Upserts a product and its composition."""
    # 1. Product
    cursor.execute("SELECT id, stock_quantity FROM products WHERE name=?", (row['Nome'],))
    prod_res = cursor.fetchone()
    
    if prod_res:
        target_id = prod_res[0]
        curr_stock = int(prod_res[1]) if prod_res[1] else 0
        new_stock = int(row['Estoque'])
        
        cursor.execute("""
            UPDATE products 
            SET base_price=?, stock_quantity=?, category=?, weight_g=?
            WHERE id=?
        """, (row['Preço Base'], new_stock, row['Categoria'], row['Peso (g)'], target_id))
        
        if new_stock != curr_stock:
            diff = new_stock - curr_stock
            cursor.execute("""
                INSERT INTO production_history (timestamp, product_id, product_name, quantity, user_id, username, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (datetime.now().isoformat(), target_id, row['Nome'], diff, user_id, username, "Importação em Massa"))
    else:
        cursor.execute("""
            INSERT INTO products (name, base_price, stock_quantity, category, weight_g)
            VALUES (?, ?, ?, ?, ?)
        """, (row['Nome'], row['Preço Base'], row['Estoque'], row['Categoria'], row['Peso (g)']))
        target_id = cursor.lastrowid

    # 2. Composition
    comp_str = str(row.get('Composição', '')).strip()
    if comp_str and target_id:
        try:
            cursor.execute("DELETE FROM product_recipes WHERE product_id=?", (target_id,))
            cursor.execute("DELETE FROM product_kits WHERE parent_product_id=?", (target_id,))
            
            parts = comp_str.split(':', 1)
            if len(parts) == 2:
                ctype = parts[0].strip().upper()
                items_str = parts[1].strip()
                items = [i.strip() for i in items_str.split(';') if i.strip()]
                
                if ctype == 'RECIPE':
                    for item in items:
                        iparts = item.rsplit(':', 1)
                        if len(iparts) == 2:
                            m_name = iparts[0].strip()
                            m_qty = float(iparts[1].strip())
                            cursor.execute("SELECT id FROM materials WHERE name=?", (m_name,))
                            m_res = cursor.fetchone()
                            if m_res:
                                cursor.execute("INSERT INTO product_recipes (product_id, material_id, quantity) VALUES (?, ?, ?)", (target_id, m_res[0], m_qty))
                            else:
                                logger.warning(f"Import Warning: Material '{m_name}' not found for product '{row['Nome']}'")

                elif ctype == 'KIT':
                    for item in items:
                        iparts = item.rsplit(':', 1)
                        if len(iparts) == 2:
                            p_name = iparts[0].strip()
                            p_qty = int(float(iparts[1].strip()))
                            cursor.execute("SELECT id FROM products WHERE name=?", (p_name,))
                            p_res = cursor.fetchone()
                            if p_res:
                                if p_res[0] != target_id:
                                    cursor.execute("INSERT INTO product_kits (parent_product_id, child_product_id, quantity) VALUES (?, ?, ?)", (target_id, p_res[0], p_qty))
                            else:
                                logger.warning(f"Import Warning: Component '{p_name}' not found for kit '{row['Nome']}'")
        except Exception as e:
            logger.error(f"Composition Parse Error for '{row['Nome']}': {e}")

def upsert_expense(cursor, row):
    """Upserts an expense."""
    row_id = row.get('ID')
    target_id = None
    
    if pd.notna(row_id) and str(row_id).strip() != '':
            try: 
                tid = int(row_id)
                cursor.execute("SELECT id FROM expenses WHERE id=?", (tid,))
                if cursor.fetchone(): target_id = tid
            except Exception: pass
    
    if target_id:
        cursor.execute("""
            UPDATE expenses SET date=?, description=?, amount=?, category=?
            WHERE id=?
        """, (row['Data (AAAA-MM-DD)'], row['Descrição'], row['Valor'], row['Categoria'], target_id))
    else:
        cursor.execute("""
            INSERT INTO expenses (date, description, amount, category)
            VALUES (?, ?, ?, ?)
        """, (row['Data (AAAA-MM-DD)'], row['Descrição'], row['Valor'], row['Categoria']))

def upsert_sale(cursor, row):
    """Upserts a sale."""
    # Resolve Product
    prod_name = str(row['Produto']).strip()
    cursor.execute("SELECT id FROM products WHERE name=?", (prod_name,))
    pres = cursor.fetchone()
    prod_id = pres[0] if pres else None
    
    # Resolve Client
    cli_name = str(row['Cliente']).strip()
    cursor.execute("SELECT id FROM clients WHERE name=?", (cli_name,))
    cres = cursor.fetchone()
    if cres: client_id = cres[0]
    else:
        cursor.execute("INSERT INTO clients (name, contact_info) VALUES (?, ?)", (cli_name, 'Importado'))
        client_id = cursor.lastrowid

    # Check ID
    row_id = row.get('ID')
    target_id = None
    if pd.notna(row_id) and str(row_id).strip() != '':
            try: 
                tid = int(row_id)
                cursor.execute("SELECT id FROM sales WHERE id=?", (tid,))
                if cursor.fetchone(): target_id = tid
            except Exception: pass
    
    if target_id:
        cursor.execute("""
            UPDATE sales SET date=?, product_id=?, quantity=?, total_price=?, client_id=?, status=?
            WHERE id=?
        """, (row['Data'], prod_id, row['Qtd'], row['Total'], client_id, row['Status'], target_id))
    else:
        cursor.execute("""
            INSERT INTO sales (date, product_id, quantity, total_price, client_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (row['Data'], prod_id, row['Qtd'], row['Total'], client_id, row['Status']))

def upsert_supplier(cursor, row):
    """Upserts a supplier."""
    name = str(row['Nome']).strip()
    cursor.execute("SELECT id FROM suppliers WHERE name=?", (name,))
    res = cursor.fetchone()
    
    if res:
        cursor.execute("""
            UPDATE suppliers SET contact_info=?, email=?, phone=?
            WHERE id=?
        """, (f"{row['Telefone']} / {row['Email']}", row['Email'], row['Telefone'], res[0]))
    else:
        cursor.execute("""
            INSERT INTO suppliers (name, contact_info, email, phone)
            VALUES (?, ?, ?, ?)
        """, (name, f"{row['Telefone']} / {row['Email']}", row['Email'], row['Telefone']))

def upsert_client(cursor, row):
    """Upserts a client."""
    name = str(row['Nome']).strip()
    cursor.execute("SELECT id FROM clients WHERE name=?", (name,))
    res = cursor.fetchone()
    
    dob = None
    if pd.notna(row['Data Nascimento']) and str(row['Data Nascimento']).strip():
        try: dob = pd.to_datetime(row['Data Nascimento']).strftime('%Y-%m-%d')
        except Exception: pass

    if res:
        cursor.execute("""
            UPDATE clients SET contact_info=?, email=?, phone=?, date_of_birth=?
            WHERE id=?
        """, (f"{row['Telefone']} / {row['Email']}", row['Email'], row['Telefone'], dob, res[0]))
    else:
        cursor.execute("""
            INSERT INTO clients (name, contact_info, email, phone, date_of_birth)
            VALUES (?, ?, ?, ?, ?)
        """, (name, f"{row['Telefone']} / {row['Email']}", row['Email'], row['Telefone'], dob))
