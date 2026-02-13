"""
Order Service Module
Handles logic for creating sales, commission orders, and managing order items.
Now includes: Clients, Quotes, and Sales History Management.
"""
import pandas as pd
from datetime import date, datetime
import audit

# ==============================================================================
# SALES (POS & History)
# ==============================================================================

def create_sale(cursor, sale_data):
    """
    Creates a new sale record.
    sale_data dict must contain:
    - date, product_id, quantity, total_price, status, client_id, discount, payment_method, notes, salesperson, order_id
    Optional: variant_id
    """
    query = """
        INSERT INTO sales (date, product_id, quantity, total_price, status, client_id, discount, payment_method, notes, salesperson, order_id, variant_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(query, (
        sale_data['date'], 
        int(sale_data['product_id']) if sale_data['product_id'] else None, 
        sale_data['quantity'], 
        sale_data['total_price'], 
        sale_data['status'], 
        sale_data['client_id'], 
        sale_data['discount'], 
        sale_data['payment_method'], 
        sale_data['notes'], 
        sale_data['salesperson'], 
        sale_data['order_id'],
        int(sale_data['variant_id']) if sale_data.get('variant_id') else None
    ))
    return cursor.lastrowid

def get_sales(conn, filters=None):
    """
    Fetches sales based on filters.
    filters dict: start_date, end_date, client_name, payment_method, salesperson
    Returns DataFrame
    """
    query = """
        SELECT s.id, s.order_id, s.date, c.name as cliente, p.name as produto, s.quantity, s.total_price, 
               s.salesperson, s.payment_method, s.discount, s.notes, s.product_id,
               pv.variant_name, s.client_id
        FROM sales s
        LEFT JOIN clients c ON s.client_id = c.id
        LEFT JOIN products p ON s.product_id = p.id
        LEFT JOIN product_variants pv ON s.variant_id = pv.id
        WHERE 1=1
    """
    params = []
    
    if filters:
        if filters.get('start_date') and filters.get('end_date'):
            query += " AND s.date BETWEEN ? AND ?"
            params.extend([filters['start_date'], filters['end_date']])
        if filters.get('client_name'):
            query += " AND c.name = ?"
            params.append(filters['client_name'])
        if filters.get('payment_method') and filters['payment_method'] != "Todas":
            query += " AND s.payment_method = ?"
            params.append(filters['payment_method'])
        if filters.get('salesperson') and filters['salesperson'] != "Todas":
            query += " AND s.salesperson = ?"
            params.append(filters['salesperson'])
            
    query += " ORDER BY s.date DESC, s.id DESC"
    
    df = pd.read_sql(query, conn, params=params)
    if not df.empty:
        df['variant_name'] = df['variant_name'].fillna('')
        df['produto_display'] = df.apply(lambda x: f"{x['produto']} ({x['variant_name']})" if x['variant_name'] else x['produto'], axis=1)
        # Fix dates
        df['date'] = pd.to_datetime(df['date'])
        
    return df

def update_sale(conn, sale_id, updates):
    """
    Updates a sale record.
    updates dict: date, salesperson, payment_method, notes
    """
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sales SET date=?, salesperson=?, payment_method=?, notes=?
        WHERE id=?
    """, (updates['date'], updates['salesperson'], updates['payment_method'], updates['notes'], sale_id))
    conn.commit()
    return True

def delete_sale(conn, sale_id, restore_stock=True):
    """
    Deletes a sale and optionally restores stock (including kits).
    Logs audit.
    """
    cursor = conn.cursor()
    
    # 1. Fetch Sale info for Audit/Restore
    sale = pd.read_sql("SELECT quantity, product_id, total_price, variant_id FROM sales WHERE id=?", conn, params=(sale_id,))
    if sale.empty:
        return False
        
    row = sale.iloc[0]
    q_raw = row['quantity']
    p_id = row['product_id']
    v_id = row['variant_id'] # Can be null (float NaN in pandas or None)
    
    # Fix for corrupted/legacy binary data or types
    if isinstance(q_raw, bytes):
        q_restore = int.from_bytes(q_raw, 'little')
    else:
        q_restore = int(q_raw)
        
    # Audit Data
    old_data = {'id': sale_id, 'quantity': q_restore, 'product_id': p_id, 'total_price': row['total_price']}
    
    # 2. Delete
    cursor.execute("DELETE FROM sales WHERE id=?", (sale_id,))
    
    # 3. Restore Stock
    if restore_stock and p_id:
        # Check Variant First
        if pd.notna(v_id):
             cursor.execute("UPDATE product_variants SET stock_quantity = stock_quantity + ? WHERE id=?", (q_restore, int(v_id)))
        else:
            # Check Kit
            kit_restore = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn, params=(p_id,))
            
            if not kit_restore.empty:
                for _, kr in kit_restore.iterrows():
                    restore_qty = q_restore * kr['quantity']
                    cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (int(restore_qty), int(kr['child_product_id'])))
            else:
                cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (q_restore, int(p_id)))
            
    # Audit
    audit.log_action(conn, 'DELETE', 'sales', sale_id, old_data, None)
    conn.commit()
    return True

# ==============================================================================
# COMMISSION ORDERS (Encomendas)
# ==============================================================================

def create_commission_order(cursor, order_data):
    """
    Creates a new commission order header.
    order_data: client_id, date_created, date_due, status, total_price, notes, deposit_amount
    """
    query = """
        INSERT INTO commission_orders (client_id, date_created, date_due, status, total_price, notes, deposit_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(query, (
        order_data['client_id'],
        order_data['date_created'],
        order_data['date_due'],
        order_data['status'],
        order_data['total_price'],
        order_data['notes'],
        order_data['deposit_amount']
    ))
    return cursor.lastrowid

def add_commission_items(cursor, order_id, items):
    """
    Adds items to a commission order.
    items: list of dicts {product_id, qty, qty_from_stock, unit_price}
    """
    total_val = 0
    for item in items:
        val = item['qty'] * item['unit_price']
        total_val += val
        cursor.execute("""
            INSERT INTO commission_items (order_id, product_id, quantity, quantity_from_stock, unit_price, variant_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            order_id, 
            int(item['product_id']), 
            item['qty'], 
            item.get('qty_from_stock', 0), 
            item['unit_price'],
            int(item['variant_id']) if item.get('variant_id') else None
        ))
    
    # Update total price of order
    cursor.execute("UPDATE commission_orders SET total_price = ? WHERE id = ?", (total_val, order_id))
    return total_val

def get_commission_orders(conn, filters=None):
    """
    Fetches commission orders based on filters.
    """
    query = """
        SELECT co.id, co.date_created, c.name as cliente, co.total_price, co.status, co.date_due, co.client_id
        FROM commission_orders co
        LEFT JOIN clients c ON co.client_id = c.id
        WHERE 1=1
    """
    params = []
    
    if filters:
        if filters.get('start_date') and filters.get('end_date'):
            query += " AND co.date_created BETWEEN ? AND ?"
            params.extend([filters['start_date'], filters['end_date']])
        if filters.get('client_name'):
            query += " AND c.name = ?"
            params.append(filters['client_name'])
            
    query += " ORDER BY co.date_created DESC"
    return pd.read_sql(query, conn, params=params)

def get_commission_items(conn, order_ids):
    """
    Fetches items for a list of order IDs.
    Returns DataFrame with product names joined.
    """
    ids_ph = ",".join(["?"] * len(order_ids))
    query = f"""
        SELECT ci.order_id, ci.product_id, ci.quantity, p.name 
        FROM commission_items ci 
        LEFT JOIN products p ON ci.product_id = p.id
        WHERE ci.order_id IN ({ids_ph})
    """
    return pd.read_sql(query, conn, params=order_ids)


# ==============================================================================
# CLIENTS
# ==============================================================================

def get_all_clients(conn):
    """Returns list of client names or dicts"""
    return pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)

def create_client(conn, name, phone, email=None):
    """Creates a new client and returns ID"""
    cursor = conn.cursor()
    cursor.execute("INSERT INTO clients (name, phone, email) VALUES (?, ?, ?)", (name, phone, email))
    conn.commit()
    return cursor.lastrowid


# ==============================================================================
# QUOTES
# ==============================================================================

def create_quote(conn, quote_data, items):
    """
    Creates a quote and its items.
    quote_data: client_id, notes, delivery_terms, payment_terms, valid_days
    items: list of dicts {product_id, qty, price, notes}
    """
    cursor = conn.cursor()
    
    # 1. Header
    valid_until = (date.today() + pd.Timedelta(days=quote_data.get('valid_days', 30))).isoformat()
    cursor.execute("""
       INSERT INTO quotes (client_id, date_created, date_valid_until, status, total_price, notes, delivery_terms, payment_terms)
       VALUES (?, ?, ?, 'Pendente', 0, ?, ?, ?)
    """, (quote_data['client_id'], date.today().isoformat(), valid_until, quote_data['notes'], quote_data['delivery_terms'], quote_data['payment_terms']))
    
    quote_id = cursor.lastrowid
    
    # 2. Items
    total = 0.0
    for item in items:
        # Check variant logic if needed (passed in notes or separate col?)
        # Current schema puts variant info in 'item_notes' for quotes usually
        
        t_item = item['qty'] * item['price']
        total += t_item
        
        cursor.execute("""
            INSERT INTO quote_items (quote_id, product_id, quantity, unit_price, item_notes) 
            VALUES (?, ?, ?, ?, ?)
        """, (quote_id, int(item['product_id']), item['qty'], item['price'], item.get('notes', '')))
        
    # 3. Update Total
    cursor.execute("UPDATE quotes SET total_price=? WHERE id=?", (total, quote_id))
    conn.commit()
    return quote_id

def delete_quote(conn, quote_id):
    """Deletes a quote and its items."""
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quote_items WHERE quote_id=?", (quote_id,))
        cursor.execute("DELETE FROM quotes WHERE id=?", (quote_id,))
        audit.log_action(conn, 'DELETE', 'quotes', quote_id, None, None) # Simple log
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
