import sqlite3
import pandas as pd
import logging
from typing import Optional, Dict, Any, List
import audit

logger = logging.getLogger(__name__)

def get_all_clients(conn: sqlite3.Connection) -> pd.DataFrame:
    """Fetches all clients ordered by name."""
    return pd.read_sql("SELECT * FROM clients ORDER BY name", conn)

def get_client_by_id(conn: sqlite3.Connection, client_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single client by ID."""
    df = pd.read_sql("SELECT * FROM clients WHERE id = ?", conn, params=(client_id,))
    return df.iloc[0].to_dict() if not df.empty else None

def create_client(conn: sqlite3.Connection, name: str, contact: str, phone: str, email: str, notes: str) -> int:
    """Creates a new client."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO clients (name, contact, phone, email, notes) 
            VALUES (?, ?, ?, ?, ?)
        """, (name, contact, phone, email, notes))
        conn.commit()
        client_id = cursor.lastrowid
        
        # Log action
        audit.log_action(conn, 'CREATE', 'clients', client_id, None, 
                         {'name': name, 'contact': contact, 'phone': phone, 'email': email, 'notes': notes})
        
        return client_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating client '{name}': {e}")
        raise

def update_client(conn: sqlite3.Connection, client_id: int, name: str, contact: str, phone: str, email: str, notes: str) -> None:
    """Updates an existing client."""
    try:
        # Fetch old data for audit
        old_data = get_client_by_id(conn, client_id)
        if not old_data:
            raise ValueError(f"Client {client_id} not found")
            
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE clients 
            SET name=?, contact=?, phone=?, email=?, notes=? 
            WHERE id=?
        """, (name, contact, phone, email, notes, client_id))
        conn.commit()
        
        # Log action
        new_data = {'name': name, 'contact': contact, 'phone': phone, 'email': email, 'notes': notes}
        audit.log_action(conn, 'UPDATE', 'clients', client_id, old_data, new_data)
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating client {client_id}: {e}")
        raise

def delete_client(conn: sqlite3.Connection, client_id: int) -> None:
    """Deletes a client."""
    try:
        # Fetch old data for audit
        old_data = get_client_by_id(conn, client_id)
        if not old_data:
            raise ValueError(f"Client {client_id} not found")
            
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clients WHERE id=?", (client_id,))
        conn.commit()
        
        # Log action
        audit.log_action(conn, 'DELETE', 'clients', client_id, old_data, None)
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting client {client_id}: {e}")
        raise
