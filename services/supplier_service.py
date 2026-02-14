import sqlite3
import pandas as pd
import logging
from typing import Optional, Dict, Any, List
import audit

logger = logging.getLogger(__name__)

def get_all_suppliers(conn: sqlite3.Connection) -> pd.DataFrame:
    """Fetches all suppliers ordered by name."""
    return pd.read_sql("SELECT * FROM suppliers ORDER BY name", conn)

def get_supplier_by_id(conn: sqlite3.Connection, supplier_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single supplier by ID."""
    df = pd.read_sql("SELECT * FROM suppliers WHERE id = ?", conn, params=(supplier_id,))
    return df.iloc[0].to_dict() if not df.empty else None

def create_supplier(conn: sqlite3.Connection, name: str, contact: str, phone: str, email: str, notes: str) -> int:
    """Creates a new supplier."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO suppliers (name, contact, phone, email, notes) 
            VALUES (?, ?, ?, ?, ?)
        """, (name, contact, phone, email, notes))
        conn.commit()
        supplier_id = cursor.lastrowid
        
        # Log action
        audit.log_action(conn, 'CREATE', 'suppliers', supplier_id, None, 
                         {'name': name, 'contact': contact, 'phone': phone, 'email': email, 'notes': notes})
        
        return supplier_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating supplier '{name}': {e}")
        raise

def update_supplier(conn: sqlite3.Connection, supplier_id: int, name: str, contact: str, phone: str, email: str, notes: str) -> None:
    """Updates an existing supplier."""
    try:
        # Fetch old data for audit
        old_data = get_supplier_by_id(conn, supplier_id)
        if not old_data:
            raise ValueError(f"Supplier {supplier_id} not found")
            
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE suppliers 
            SET name=?, contact=?, phone=?, email=?, notes=? 
            WHERE id=?
        """, (name, contact, phone, email, notes, supplier_id))
        conn.commit()
        
        # Log action
        new_data = {'name': name, 'contact': contact, 'phone': phone, 'email': email, 'notes': notes}
        audit.log_action(conn, 'UPDATE', 'suppliers', supplier_id, old_data, new_data)
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating supplier {supplier_id}: {e}")
        raise

def delete_supplier(conn: sqlite3.Connection, supplier_id: int) -> None:
    """Deletes a supplier."""
    try:
        # Fetch old data for audit
        old_data = get_supplier_by_id(conn, supplier_id)
        if not old_data:
            raise ValueError(f"Supplier {supplier_id} not found")
            
        cursor = conn.cursor()
        cursor.execute("DELETE FROM suppliers WHERE id=?", (supplier_id,))
        conn.commit()
        
        # Log action
        audit.log_action(conn, 'DELETE', 'suppliers', supplier_id, old_data, None)
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting supplier {supplier_id}: {e}")
        raise
