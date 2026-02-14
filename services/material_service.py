import sqlite3
import pandas as pd
import logging
from typing import List, Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

def get_all_materials(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Fetches all materials with their supplier and category names.
    """
    query = """
        SELECT m.id, m.name, m.price_per_unit, m.unit, m.stock_level, m.min_stock_alert, m.type, 
               m.image_path, s.name as supplier_name, c.name as category_name, m.category_id, m.supplier_id
        FROM materials m
        LEFT JOIN suppliers s ON m.supplier_id = s.id
        LEFT JOIN material_categories c ON m.category_id = c.id
        ORDER BY m.name
    """
    return pd.read_sql(query, conn)

def get_material_by_id(conn: sqlite3.Connection, material_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetches a single material by ID.
    """
    query = "SELECT * FROM materials WHERE id = ?"
    df = pd.read_sql(query, conn, params=(material_id,))
    if not df.empty:
        return df.iloc[0].to_dict()
    return None

def create_material(conn: sqlite3.Connection, name: str, category_id: Optional[int], supplier_id: Optional[int],
                   price: float, unit: str, stock_level: float, min_stock: float, 
                   material_type: str, image_path: Optional[str] = None) -> int:
    """
    Creates a new material. Returns the new material ID.
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO materials (name, category_id, supplier_id, price_per_unit, unit, stock_level, min_stock_alert, type, image_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, category_id, supplier_id, price, unit, stock_level, min_stock, material_type, image_path))
    conn.commit()
    return cursor.lastrowid

def update_material(conn: sqlite3.Connection, material_id: int, name: str, category_id: Optional[int], 
                   supplier_id: Optional[int], price: float, unit: str, stock_level: float, 
                   min_stock: float, material_type: str, image_path: Optional[str] = None) -> None:
    """
    Updates an existing material.
    """
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE materials
        SET name = ?, category_id = ?, supplier_id = ?, price_per_unit = ?, unit = ?, 
            stock_level = ?, min_stock_alert = ?, type = ?, image_path = ?
        WHERE id = ?
    """, (name, category_id, supplier_id, price, unit, stock_level, min_stock, material_type, image_path, material_id))
    conn.commit()

def delete_material(conn: sqlite3.Connection, material_id: int) -> None:
    """
    Deletes a material.
    """
    cursor = conn.cursor()
    cursor.execute("DELETE FROM materials WHERE id = ?", (material_id,))
    conn.commit()

def update_stock(conn: sqlite3.Connection, material_id: int, quantity_change: float, reason: str) -> None:
    """
    Updates stock level and logs the movement.
    Positive quantity_change adds to stock, negative removes.
    """
    try:
        cursor = conn.cursor()
        
        # Get current stock
        current_stock = cursor.execute("SELECT stock_level FROM materials WHERE id = ?", (material_id,)).fetchone()[0]
        new_stock = current_stock + quantity_change
        
        # Update stock
        cursor.execute("UPDATE materials SET stock_level = ? WHERE id = ?", (new_stock, material_id))
        
        # Log movement
        movement_type = "Entrada" if quantity_change > 0 else "Saída"
        cursor.execute("""
            INSERT INTO stock_movements (material_id, quantity, movement_type, date, reason)
            VALUES (?, ?, ?, DATE('now'), ?)
        """, (material_id, abs(quantity_change), movement_type, reason))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao atualizar estoque (material_id={material_id}): {e}")
        raise

# --- Categories ---

def get_all_categories(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Fetches all material categories.
    """
    return pd.read_sql("SELECT id, name FROM material_categories ORDER BY name", conn)

def create_category(conn: sqlite3.Connection, name: str) -> int:
    """
    Creates a new category.
    """
    cursor = conn.cursor()
    cursor.execute("INSERT INTO material_categories (name) VALUES (?)", (name,))
    conn.commit()
    return cursor.lastrowid

# --- Suppliers ---

def get_all_suppliers(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Fetches all suppliers.
    """
    return pd.read_sql("SELECT id, name FROM suppliers ORDER BY name", conn)

def get_material_history(conn: sqlite3.Connection, material_id: int) -> pd.DataFrame:
    """
    Fetches transaction history for a specific material.
    """
    query = """
        SELECT t.date, t.type, t.quantity, t.notes, u.username 
        FROM inventory_transactions t
        LEFT JOIN users u ON t.user_id = u.id
        WHERE t.material_id = ?
        ORDER BY t.id DESC
    """
    return pd.read_sql(query, conn, params=(material_id,))

def get_global_history(conn: sqlite3.Connection, filters: Dict[str, Any]) -> pd.DataFrame:
    """
    Fetches global transaction history with filters.
    filters: {
        'period': 'Hoje' | '7d' | '30d' | 'all',
        'material_id': int (optional),
        'type': str (optional),
        'user_name': str (optional)
    }
    """
    from datetime import date, timedelta
    
    query = """
        SELECT 
            t.id, t.date, m.name as material_name, t.type, t.quantity, m.unit, t.cost, t.notes, u.username
        FROM inventory_transactions t
        JOIN materials m ON t.material_id = m.id
        LEFT JOIN users u ON t.user_id = u.id
        WHERE 1=1
    """
    params = []
    
    period = filters.get('period', '7d')
    today = date.today()
    
    if period == 'Hoje':
        query += " AND t.date LIKE ?"
        params.append(today.isoformat() + '%')
    elif period == '7d':
        start = (today - timedelta(days=7)).isoformat()
        query += " AND t.date >= ?"
        params.append(start)
    elif period == '30d':
        start = (today - timedelta(days=30)).isoformat()
        query += " AND t.date >= ?"
        params.append(start)
        
    if filters.get('material_name') and filters['material_name'] != "Todos":
        query += " AND m.name = ?"
        params.append(filters['material_name'])
        
    if filters.get('type') and filters['type'] != "Todos":
        query += " AND t.type = ?"
        params.append(filters['type'])
        
    if filters.get('user_name') and filters['user_name'] != "Todos":
        query += " AND u.username = ?"
        params.append(filters['user_name'])
        
    query += " ORDER BY t.date DESC LIMIT 200"
    
    return pd.read_sql(query, conn, params=params)

def log_transaction(conn: sqlite3.Connection, material_id: int, date_str: str, trans_type: str, 
                   quantity: float, cost: float, notes: str, user_id: int) -> None:
    """
    Logs a manual inventory transaction.
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO inventory_transactions (material_id, date, type, quantity, cost, notes, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (material_id, date_str, trans_type, quantity, cost, notes, user_id))
    conn.commit()

def register_entry(conn: sqlite3.Connection, material_id: int, quantity: float, total_cost: float, 
                   notes: str, user_id: int) -> Tuple[float, float]:
    """
    Registers a material entry, updates stock, and recalculates weighted average price.
    Returns (new_stock, new_avg_price).
    """
    try:
        cursor = conn.cursor()
        
        # Get current state
        mat = get_material_by_id(conn, material_id)
        if not mat:
            raise ValueError("Material not found")
            
        current_stock = mat['stock_level']
        current_price = mat['price_per_unit']
        
        # Calculate new weighted average price
        purchase_price_per_unit = total_cost / quantity if quantity > 0 else 0
        
        if current_stock > 0:
            new_avg_price = ((current_stock * current_price) + total_cost) / (current_stock + quantity)
        else:
            new_avg_price = purchase_price_per_unit
            
        new_stock = current_stock + quantity
        
        # Log Transaction
        log_transaction(conn, material_id, pd.Timestamp.now().isoformat(), 'ENTRADA', quantity, total_cost, notes, user_id)
        
        # Update Material
        cursor.execute("""
            UPDATE materials 
            SET stock_level = ?, price_per_unit = ? 
            WHERE id = ?
        """, (new_stock, new_avg_price, material_id))
        conn.commit()
        
        return new_stock, new_avg_price
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao registrar entrada (material_id={material_id}): {e}")
        raise

def register_exit(conn: sqlite3.Connection, material_id: int, quantity: float, notes: str, user_id: int) -> float:
    """
    Registers a material exit (usage/loss) and updates stock.
    Returns new_stock.
    """
    try:
        cursor = conn.cursor()
        
        mat = get_material_by_id(conn, material_id)
        if not mat:
            raise ValueError("Material not found")
            
        current_stock = mat['stock_level']
        new_stock = current_stock - quantity
        
        # Log Transaction
        log_transaction(conn, material_id, pd.Timestamp.now().isoformat(), 'SAIDA', quantity, 0.0, notes, user_id)
        
        # Update Material
        cursor.execute("UPDATE materials SET stock_level = ? WHERE id = ?", (new_stock, material_id))
        conn.commit()
        
        return new_stock
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao registrar saída (material_id={material_id}): {e}")
        raise
