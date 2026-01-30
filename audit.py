"""
Audit Module for CeramicAdmin OS
Handles logging of data changes and rollback capabilities.
"""
import json
from datetime import datetime
import streamlit as st

def get_current_user_info():
    """Get current user ID and username from session state."""
    if 'current_user' in st.session_state and st.session_state.current_user:
        user = st.session_state.current_user
        return user.get('id'), user.get('username', 'unknown')
    return None, 'system'

def log_action(conn, action: str, table_name: str, record_id: int, 
               old_data: dict = None, new_data: dict = None):
    """
    Log a data change action to the audit log.
    
    Args:
        conn: Database connection
        action: 'CREATE', 'UPDATE', 'DELETE'
        table_name: Name of the affected table
        record_id: ID of the affected record
        old_data: Previous state of the record (for UPDATE/DELETE)
        new_data: New state of the record (for CREATE/UPDATE)
    """
    user_id, username = get_current_user_info()
    
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_log (timestamp, user_id, username, action, table_name, record_id, old_data, new_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        user_id,
        username,
        action,
        table_name,
        record_id,
        json.dumps(old_data, default=str) if old_data else None,
        json.dumps(new_data, default=str) if new_data else None
    ))
    conn.commit()

def get_record_history(conn, table_name: str, record_id: int):
    """
    Get the change history for a specific record.
    
    Returns a list of audit log entries for the record.
    """
    import pandas as pd
    
    df = pd.read_sql("""
        SELECT id, timestamp, username, action, old_data, new_data
        FROM audit_log
        WHERE table_name = ? AND record_id = ?
        ORDER BY timestamp DESC
    """, conn, params=(table_name, record_id))
    
    return df

def get_audit_log(conn, filters: dict = None, limit: int = 100):
    """
    Get audit log entries with optional filters.
    
    Filters can include:
        - user_id: Filter by user
        - table_name: Filter by table
        - action: Filter by action type
        - start_date: Filter from date
        - end_date: Filter to date
    """
    import pandas as pd
    
    query = """
        SELECT al.id, al.timestamp, al.username, al.action, al.table_name, 
               al.record_id, al.old_data, al.new_data
        FROM audit_log al
        WHERE 1=1
    """
    params = []
    
    if filters:
        if filters.get('user_id'):
            query += " AND al.user_id = ?"
            params.append(filters['user_id'])
        if filters.get('table_name'):
            query += " AND al.table_name = ?"
            params.append(filters['table_name'])
        if filters.get('action'):
            query += " AND al.action = ?"
            params.append(filters['action'])
        if filters.get('start_date'):
            query += " AND al.timestamp >= ?"
            params.append(filters['start_date'])
        if filters.get('end_date'):
            query += " AND al.timestamp <= ?"
            params.append(filters['end_date'])
    
    query += f" ORDER BY al.timestamp DESC LIMIT {limit}"
    
    return pd.read_sql(query, conn, params=params)

def rollback_record(conn, audit_id: int) -> bool:
    """
    Rollback a record to its previous state based on an audit log entry.
    
    Returns True if successful, False otherwise.
    """
    import pandas as pd
    
    # Get the audit log entry
    entry = pd.read_sql(
        "SELECT * FROM audit_log WHERE id = ?", 
        conn, 
        params=(audit_id,)
    )
    
    if entry.empty:
        return False
    
    entry = entry.iloc[0]
    action = entry['action']
    table_name = entry['table_name']
    record_id = entry['record_id']
    old_data = json.loads(entry['old_data']) if entry['old_data'] else None
    
    cursor = conn.cursor()
    
    try:
        if action == 'DELETE' and old_data:
            # Re-insert the deleted record
            columns = ', '.join(old_data.keys())
            placeholders = ', '.join(['?' for _ in old_data])
            cursor.execute(f"""
                INSERT INTO {table_name} ({columns}) VALUES ({placeholders})
            """, list(old_data.values()))
            
        elif action == 'UPDATE' and old_data:
            # Restore previous values
            set_clause = ', '.join([f"{k} = ?" for k in old_data.keys() if k != 'id'])
            values = [v for k, v in old_data.items() if k != 'id']
            values.append(record_id)
            cursor.execute(f"""
                UPDATE {table_name} SET {set_clause} WHERE id = ?
            """, values)
            
        elif action == 'CREATE':
            # Delete the created record
            cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (record_id,))
        
        else:
            return False
        
        conn.commit()
        
        # Log the rollback action
        log_action(conn, 'ROLLBACK', table_name, record_id, 
                   old_data={'rollback_from_audit_id': audit_id},
                   new_data={'restored_to': old_data} if old_data else None)
        
        return True
        
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao reverter: {e}")
        return False

def format_action(action: str) -> str:
    """Format action for display."""
    actions = {
        'CREATE': '➕ Criação',
        'UPDATE': '✏️ Alteração',
        'DELETE': '🗑️ Exclusão',
        'ROLLBACK': '↩️ Reversão'
    }
    return actions.get(action, action)

def format_table_name(table_name: str) -> str:
    """Format table name for display."""
    tables = {
        'products': '📦 Produtos',
        'sales': '💰 Vendas',
        'expenses': '💸 Despesas',
        'materials': '🧱 Insumos',
        'clients': '👥 Clientes',
        'suppliers': '🚚 Fornecedores',
        'commission_orders': '📋 Encomendas',
        'firings': '🔥 Queimas',
        'users': '👤 Usuários'
    }
    return tables.get(table_name, table_name)
