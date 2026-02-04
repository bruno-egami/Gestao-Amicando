"""
Order Service Module
Handles logic for creating sales, commission orders, and managing order items.
"""
import pandas as pd
from datetime import date

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
