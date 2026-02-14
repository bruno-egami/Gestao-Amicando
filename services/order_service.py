"""
Order Service Module
Handles logic for creating sales, commission orders, and managing order items.
Now includes: Clients, Quotes, Sales History Management, and Commission Order Management.
"""
import pandas as pd
import sqlite3
import logging
import json
from datetime import date, datetime
import audit

logger = logging.getLogger(__name__)

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


def get_orders_for_management(conn):
    """
    Fetches all commission orders with client name for the management page.
    Returns DataFrame with all columns needed for display.
    """
    return pd.read_sql("""
        SELECT o.id, c.name as client, o.date_due, o.status, o.total_price, o.notes, o.client_id,
               o.manual_discount, o.deposit_amount, o.date_created, o.image_paths
        FROM commission_orders o
        JOIN clients c ON o.client_id = c.id
        ORDER BY o.date_due ASC
    """, conn)


def get_order_items_detail(conn, order_id):
    """
    Fetches items for a single order with full product/variant detail.
    Returns DataFrame with cleaned numeric columns.
    """
    items = pd.read_sql("""
        SELECT ci.id, p.name, ci.quantity, ci.quantity_from_stock, ci.quantity_produced, ci.product_id, ci.unit_price, ci.notes, p.image_paths,
               ci.variant_id, pv.variant_name
        FROM commission_items ci
        LEFT JOIN products p ON ci.product_id = p.id
        LEFT JOIN product_variants pv ON ci.variant_id = pv.id
        WHERE ci.order_id = ?
    """, conn, params=(order_id,))
    
    # Clean binary data
    def _clean_numeric(val):
        if isinstance(val, bytes): return int.from_bytes(val, 'little')
        return val
    
    for col in ['quantity', 'quantity_from_stock', 'quantity_produced', 'product_id']:
        items[col] = items[col].apply(_clean_numeric)
    
    items['quantity'] = items['quantity'].fillna(0).astype(int)
    items['quantity_from_stock'] = items['quantity_from_stock'].fillna(0).astype(int)
    items['quantity_produced'] = items['quantity_produced'].fillna(0).astype(int)
    items['name'] = items['name'].fillna("Produto Desconhecido")
    items['notes'] = items['notes'].fillna("")
    
    return items


def get_wip_quantity(conn, order_item_id):
    """Returns the total WIP quantity for an order item."""
    wip_res = pd.read_sql(
        "SELECT SUM(quantity) as qty FROM production_wip WHERE order_item_id=?", 
        conn, params=(order_item_id,)
    )
    if not wip_res.empty and pd.notna(wip_res.iloc[0]['qty']):
        return int(wip_res.iloc[0]['qty'])
    return 0


def get_products_for_selection(conn):
    """Fetches products for order item selection dropdowns."""
    return pd.read_sql("SELECT id, name, stock_quantity, base_price FROM products ORDER BY name", conn)


def get_product_variants(conn, product_id):
    """Fetches variants for a product."""
    return pd.read_sql(
        "SELECT id, variant_name, price_adder, stock_quantity FROM product_variants WHERE product_id=?",
        conn, params=(product_id,)
    )


def update_order_details(conn, order_id, date_due, notes, manual_discount, deposit_amount, client_id):
    """Updates editable fields of a commission order."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE commission_orders 
            SET date_due=?, notes=?, manual_discount=?, deposit_amount=?, client_id=? 
            WHERE id=?
        """, (date_due, notes, manual_discount, deposit_amount, int(client_id), order_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao atualizar encomenda {order_id}: {e}")
        raise


def update_order_status(conn, order_id, new_status, old_status=None):
    """Updates order status and logs audit."""
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE commission_orders SET status=? WHERE id=?", (new_status, order_id))
        if old_status and old_status != new_status:
            audit.log_action(conn, 'UPDATE', 'commission_orders', order_id, 
                {'status': old_status}, {'status': new_status})
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao atualizar status da encomenda {order_id}: {e}")
        raise


def update_order_images(conn, order_id, image_paths_list):
    """Updates image_paths for an order."""
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE commission_orders SET image_paths=? WHERE id=?", 
                       (str(image_paths_list), order_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao atualizar imagens da encomenda {order_id}: {e}")
        raise


def delete_commission_order(conn, order_id):
    """
    Deletes a commission order, its items, and restores reserved stock.
    Returns True on success.
    """
    try:
        cursor = conn.cursor()
        
        # 1. Get reserved items to restore
        items = pd.read_sql(
            "SELECT product_id, quantity_from_stock, variant_id FROM commission_items WHERE order_id=?", 
            conn, params=(order_id,)
        )
        
        def _clean_bin(val):
            if isinstance(val, bytes): return int.from_bytes(val, 'little')
            return val
        
        items['quantity_from_stock'] = items['quantity_from_stock'].apply(_clean_bin)
        items['product_id'] = items['product_id'].apply(_clean_bin)
        
        # Get order data for audit
        order_data = pd.read_sql(
            "SELECT client_id, total_price, status FROM commission_orders WHERE id=?", 
            conn, params=(order_id,)
        )
        old_data = order_data.iloc[0].to_dict() if not order_data.empty else {}
        
        # 2. Restore stock
        for _, it in items.iterrows():
            qty_rest = int(it['quantity_from_stock'])
            if qty_rest > 0:
                if pd.notna(it['variant_id']) and it['variant_id'] > 0:
                    cursor.execute(
                        "UPDATE product_variants SET stock_quantity = stock_quantity + ? WHERE id=?", 
                        (qty_rest, int(it['variant_id']))
                    )
                else:
                    cursor.execute(
                        "UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                        (qty_rest, int(it['product_id']))
                    )
        
        # 3. Delete items and order
        cursor.execute("DELETE FROM commission_items WHERE order_id=?", (order_id,))
        cursor.execute("DELETE FROM commission_orders WHERE id=?", (order_id,))
        conn.commit()
        
        audit.log_action(conn, 'DELETE', 'commission_orders', order_id, old_data, None)
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao excluir encomenda {order_id}: {e}")
        raise


def add_commission_item_with_stock(conn, order_id, product_id, quantity, qty_from_stock, 
                                     unit_price, variant_id=None):
    """
    Adds an item to a commission order with stock reservation (handles kits).
    Updates the order total.
    """
    try:
        cursor = conn.cursor()
        
        # Insert item
        cursor.execute("""
            INSERT INTO commission_items (order_id, product_id, quantity, quantity_from_stock, quantity_produced, unit_price, variant_id)
            VALUES (?, ?, ?, ?, 0, ?, ?)
        """, (order_id, int(product_id), quantity, int(qty_from_stock), float(unit_price), 
              int(variant_id) if variant_id else None))
        
        # Reserve stock
        if qty_from_stock > 0:
            if variant_id:
                cursor.execute(
                    "UPDATE product_variants SET stock_quantity = stock_quantity - ? WHERE id=?", 
                    (int(qty_from_stock), int(variant_id))
                )
            else:
                kit_comps = pd.read_sql(
                    "SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", 
                    conn, params=(int(product_id),)
                )
                if not kit_comps.empty:
                    for _, kc in kit_comps.iterrows():
                        deduct_res = qty_from_stock * kc['quantity']
                        cursor.execute(
                            "UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", 
                            (int(deduct_res), int(kc['child_product_id']))
                        )
                else:
                    cursor.execute(
                        "UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", 
                        (int(qty_from_stock), int(product_id))
                    )
        
        # Update order total
        cursor.execute(
            "UPDATE commission_orders SET total_price = total_price + ? WHERE id=?", 
            (unit_price * quantity, order_id)
        )
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao adicionar item à encomenda {order_id}: {e}")
        raise


def delete_commission_item(conn, order_id, item_id, product_id, quantity, 
                            quantity_from_stock, unit_price):
    """
    Removes an item from a commission order, restores stock (including kits), 
    and updates the order total.
    """
    try:
        cursor = conn.cursor()
        rest_qty = quantity_from_stock
        
        if rest_qty > 0:
            old_stock = pd.read_sql(
                "SELECT stock_quantity FROM products WHERE id=?", conn, params=(product_id,)
            ).iloc[0]['stock_quantity']
            
            # Kit restore
            kit_comps = pd.read_sql(
                "SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", 
                conn, params=(product_id,)
            )
            if not kit_comps.empty:
                for _, kc in kit_comps.iterrows():
                    restore_amt = rest_qty * kc['quantity']
                    cursor.execute(
                        "UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                        (int(restore_amt), int(kc['child_product_id']))
                    )
            else:
                cursor.execute(
                    "UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                    (rest_qty, product_id)
                )
            
            audit.log_action(conn, 'UPDATE', 'products', product_id, 
                {'stock_quantity': old_stock}, {'stock_quantity': old_stock + rest_qty})
        
        # Delete item
        cursor.execute("DELETE FROM commission_items WHERE id=?", (item_id,))
        
        # Update order total
        deduction = unit_price * quantity
        cursor.execute(
            "UPDATE commission_orders SET total_price = total_price - ? WHERE id=?", 
            (deduction, order_id)
        )
        
        conn.commit()
        
        # Audit
        old_data = {'id': item_id, 'product_id': product_id, 'quantity': quantity}
        audit.log_action(conn, 'DELETE', 'commission_items', item_id, old_data, None)
        
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao excluir item {item_id} da encomenda {order_id}: {e}")
        raise


def update_item_quantity(conn, order_id, item_id, new_qty, old_qty, 
                          quantity_from_stock, unit_price, product_id):
    """
    Updates item quantity, adjusts order total, and restores stock if quantity decreased below reserved.
    """
    diff = new_qty - old_qty
    if diff == 0:
        return True
    
    try:
        cursor = conn.cursor()
        
        # Update item
        cursor.execute("UPDATE commission_items SET quantity=? WHERE id=?", (new_qty, item_id))
        
        # Update order total
        cost_diff = diff * unit_price
        cursor.execute(
            "UPDATE commission_orders SET total_price = total_price + ? WHERE id=?", 
            (cost_diff, order_id)
        )
        
        # Return excess stock if new qty < reserved
        if new_qty < quantity_from_stock:
            to_return = quantity_from_stock - new_qty
            cursor.execute(
                "UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                (to_return, product_id)
            )
            cursor.execute(
                "UPDATE commission_items SET quantity_from_stock=? WHERE id=?", 
                (new_qty, item_id)
            )
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao atualizar quantidade do item {item_id}: {e}")
        raise


def quick_produce_item(conn, order_id, item_id, product_id, amount, 
                        old_order_status, old_qty_produced, deduct_materials_fn=None,
                        user_id=None, username='system'):
    """
    Registers quick production for an order item.
    Optionally deducts materials, updates item produced count, order status, 
    and logs to production_history.
    
    deduct_materials_fn: callable(cursor, product_id, amount, note_suffix) for material deduction
    """
    try:
        cursor = conn.cursor()
        
        # Deduct materials if function provided
        if deduct_materials_fn:
            deduct_materials_fn(cursor, product_id, amount)
        
        # Update item produced count
        cursor.execute(
            "UPDATE commission_items SET quantity_produced = quantity_produced + ? WHERE id=?", 
            (amount, item_id)
        )
        
        # Check pending items
        cursor.execute("""
            SELECT COUNT(*) FROM commission_items 
            WHERE order_id=? AND quantity_produced < (quantity - quantity_from_stock)
        """, (order_id,))
        pending_count = cursor.fetchone()[0]
        
        new_status = 'Concluída' if pending_count == 0 else 'Em Produção'
        cursor.execute("UPDATE commission_orders SET status=? WHERE id=?", (new_status, order_id))
        
        # Log status change
        if old_order_status != new_status:
            audit.log_action(conn, 'UPDATE', 'commission_orders', order_id, 
                {'status': old_order_status}, {'status': new_status})
        
        # Get product name for history
        prod_name_row = pd.read_sql(
            "SELECT name FROM products WHERE id=?", conn, params=(product_id,)
        )
        prod_name = prod_name_row.iloc[0]['name'] if not prod_name_row.empty else 'Produto'
        
        # Log production history
        cursor.execute("""
            INSERT INTO production_history (timestamp, product_id, product_name, quantity, order_id, user_id, username)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now().isoformat(), product_id, prod_name, amount, order_id, user_id, username))
        new_hist_id = cursor.lastrowid
        
        conn.commit()
        
        # Audit
        audit.log_action(conn, 'CREATE', 'production_history', new_hist_id, None, {
            'product_id': product_id, 'product_name': prod_name, 'quantity': amount, 'order_id': order_id
        })
        audit.log_action(conn, 'UPDATE', 'commission_items', item_id, 
            {'quantity_produced': old_qty_produced}, {'quantity_produced': old_qty_produced + amount})
        
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro na produção rápida do item {item_id}: {e}")
        raise


def start_wip_production(conn, order_id, item_id, product_id, variant_id, 
                          amount, start_date, notes=None, old_order_status='Pendente'):
    """
    Creates a WIP entry for an order item and updates order status if needed.
    """
    try:
        cursor = conn.cursor()
        
        history = {
            "Iniciado": datetime.now().strftime("%d/%m %H:%M"), 
            "Fila de Espera": datetime.now().strftime("%d/%m %H:%M")
        }
        history_json = json.dumps(history)
        
        cursor.execute("""
            INSERT INTO production_wip (product_id, variant_id, order_id, order_item_id, stage, quantity, start_date, materials_deducted, stage_history, notes)
            VALUES (?, ?, ?, ?, 'Fila de Espera', ?, ?, 0, ?, ?)
        """, (product_id, variant_id, order_id, item_id, amount, start_date, history_json, notes))
        
        # Update order status to "Em Produção" if pending
        if old_order_status == 'Pendente':
            cursor.execute("UPDATE commission_orders SET status='Em Produção' WHERE id=?", (order_id,))
            audit.log_action(conn, 'UPDATE', 'commission_orders', order_id, 
                {'status': 'Pendente'}, {'status': 'Em Produção'})
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao iniciar produção WIP para item {item_id}: {e}")
        raise


def deliver_order(conn, order_id, order_data, items_df):
    """
    Delivers a commission order:
    1. Re-injects items to stock (net zero from reservation)
    2. Creates sale records for each item
    3. Deducts stock (as sales)
    4. Marks order as 'Entregue'
    
    order_data: dict with client_id, total_price, deposit_amount, status
    items_df: DataFrame with product_id, quantity, unit_price, variant_name, name, notes, image_paths
    """
    try:
        cursor = conn.cursor()
        
        # 1. Re-inject ALL items to stock momentarily
        for _, it in items_df.iterrows():
            p_row_chk = pd.read_sql(
                "SELECT stock_quantity FROM products WHERE id=?", 
                conn, params=(it['product_id'],)
            )
            if p_row_chk.empty: 
                continue
            
            old_stock = p_row_chk.iloc[0]['stock_quantity']
            kit_comps = pd.read_sql(
                "SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", 
                conn, params=(it['product_id'],)
            )
            
            if not kit_comps.empty:
                for _, kc in kit_comps.iterrows():
                    restore_amt = it['quantity'] * kc['quantity']
                    cursor.execute(
                        "UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                        (int(restore_amt), int(kc['child_product_id']))
                    )
            else:
                cursor.execute(
                    "UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                    (it['quantity'], it['product_id'])
                )
            
            audit.log_action(conn, 'UPDATE', 'products', it['product_id'], 
                {'stock_quantity': old_stock}, {'stock_quantity': old_stock + it['quantity']})
        
        # 2. Create Sale Records
        ord_uuid = f"ENC-{datetime.now().strftime('%y%m%d')}-{order_id}"
        total_ord_price = order_data['total_price']
        deposit_total = order_data.get('deposit_amount') or 0
        deposit_ratio = deposit_total / total_ord_price if total_ord_price > 0 else 0
        
        for _, it in items_df.iterrows():
            item_subtotal = it['unit_price'] * it['quantity']
            discount_share = item_subtotal * deposit_ratio
            final_item_price = item_subtotal - discount_share
            notes_item = f"Encomenda #{order_id}"
            if deposit_total > 0: 
                notes_item += f" (Sinal: R$ {discount_share:.2f})"
            
            cursor.execute("""
                INSERT INTO sales (date, product_id, quantity, total_price, status, client_id, 
                                 discount, payment_method, notes, salesperson, order_id)
                VALUES (?, ?, ?, ?, 'Finalizada', ?, ?, 'Misto', ?, 'Sistema', ?)
            """, (date.today(), it['product_id'], it['quantity'], final_item_price, 
                  order_data['client_id'], discount_share, notes_item, ord_uuid))
            
            # 3. Deduct Stock (Sales Logic)
            p_row_chk = pd.read_sql(
                "SELECT stock_quantity FROM products WHERE id=?", 
                conn, params=(it['product_id'],)
            )
            if not p_row_chk.empty:
                old_stock_after = p_row_chk.iloc[0]['stock_quantity']
                kit_comps_2 = pd.read_sql(
                    "SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", 
                    conn, params=(it['product_id'],)
                )
                if not kit_comps_2.empty:
                    for _, kc in kit_comps_2.iterrows():
                        deduct_amt = it['quantity'] * kc['quantity']
                        cursor.execute(
                            "UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", 
                            (int(deduct_amt), int(kc['child_product_id']))
                        )
                else:
                    cursor.execute(
                        "UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", 
                        (it['quantity'], it['product_id'])
                    )
                
                audit.log_action(conn, 'UPDATE', 'products', it['product_id'], 
                    {'stock_quantity': old_stock_after}, {'stock_quantity': old_stock_after - it['quantity']})
            
            audit.log_action(conn, 'CREATE', 'sales', cursor.lastrowid, None, {
                'order_id': order_id, 'product_id': it['product_id'], 
                'quantity': it['quantity'], 'total_price': it['unit_price'] * it['quantity']
            })
        
        # 4. Finalize Order Status
        old_status = order_data.get('status', '')
        cursor.execute("UPDATE commission_orders SET status='Entregue' WHERE id=?", (order_id,))
        conn.commit()
        
        audit.log_action(conn, 'UPDATE', 'commission_orders', order_id, 
            {'status': old_status}, {'status': 'Entregue'})
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao realizar entrega da encomenda {order_id}: {e}")
        raise


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
    Creates a new quote.
    quote_data: client_id, notes, delivery_terms, payment_terms, valid_days
    items: list of {product_id, qty, price, notes}
    """
    cursor = conn.cursor()
    try:
        # Calculate validity
        valid_until = date.today() + pd.Timedelta(days=int(quote_data.get('valid_days', 30)))
        
        # Calculate total
        total_val = sum(i['qty'] * i['price'] for i in items)
        
        cursor.execute("""
            INSERT INTO quotes (client_id, date_created, date_valid_until, status, total_price, notes, delivery_terms, payment_terms)
            VALUES (?, ?, ?, 'Pendente', ?, ?, ?, ?)
        """, (quote_data['client_id'], date.today(), valid_until, total_val, quote_data['notes'], 
              quote_data.get('delivery_terms'), quote_data.get('payment_terms')))
        
        quote_id = cursor.lastrowid
        
        for item in items:
            cursor.execute("""
                INSERT INTO quote_items (quote_id, product_id, quantity, unit_price, item_notes)
                VALUES (?, ?, ?, ?, ?)
            """, (quote_id, item['product_id'], item['qty'], item['price'], item.get('notes', '')))
            
        conn.commit()
        return quote_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating quote: {e}")
        raise

def get_all_quotes(conn):
    """Fetches all quotes ordered by creation date."""
    return pd.read_sql("SELECT * FROM quotes ORDER BY date_created DESC", conn)

def get_quote_items(conn, quote_id):
    """Fetches items for a specific quote."""
    return pd.read_sql("SELECT * FROM quote_items WHERE quote_id=?", conn, params=(quote_id,))

def get_quote_details_for_pdf(conn, quote_id):
    """Fetches detailed item info for quote PDF."""
    return pd.read_sql("""
        SELECT qi.product_id, p.name, qi.quantity, qi.unit_price, qi.item_notes 
        FROM quote_items qi
        LEFT JOIN products p ON qi.product_id = p.id
        WHERE qi.quote_id=?
    """, conn, params=(quote_id,))

def update_quote_status(conn, quote_id, new_status):
    """Updates the status of a quote."""
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE quotes SET status=? WHERE id=?", (new_status, quote_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating quote status {quote_id}: {e}")
        raise

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
