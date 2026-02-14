"""
Firing Service Module
Handles business logic related to Kiln Firings and Maintenance.
"""
import pandas as pd
import sqlite3
import audit
import os
from datetime import datetime
from utils.logging_config import get_logger, log_exception

logger = get_logger(__name__)

# ==============================================================================
# QUEMAS (FIRINGS)
# ==============================================================================

def get_kilns(conn):
    """Returns a dictionary of {name: id} for all kilns."""
    df = pd.read_sql("SELECT id, name FROM kilns", conn)
    return {row['name']: row['id'] for _, row in df.iterrows()}

def get_firings(conn, filters=None):
    """
    Fetches firings based on filters.
    filters: dict with kiln_name, type, start_date, end_date
    """
    query = """
        SELECT f.id, f.date, k.name as forno, f.type, f.power_consumption_kwh, f.cost, f.observation, f.image_path, f.kiln_id
        FROM firings f
        LEFT JOIN kilns k ON f.kiln_id = k.id
        WHERE 1=1
    """
    params = []
    
    if filters:
        if filters.get('kiln_name') and filters['kiln_name'] != "Todos":
            query += " AND k.name = ?"
            params.append(filters['kiln_name'])
            
        if filters.get('type') and filters['type'] != "Todos":
            query += " AND f.type = ?"
            params.append(filters['type'])
            
        if filters.get('start_date') and filters.get('end_date'):
            query += " AND f.date BETWEEN ? AND ?"
            params.append(filters['start_date'])
            params.append(filters['end_date'])
            
    query += " ORDER BY f.date DESC"
    return pd.read_sql(query, conn, params=params)

def get_firing_by_id(conn, firing_id):
    """Fetches a single firing record."""
    df = pd.read_sql("SELECT * FROM firings WHERE id = ?", conn, params=(firing_id,))
    return df.iloc[0] if not df.empty else None

def create_firing(conn, firing_data):
    """
    Creates a new firing record.
    firing_data: date, type, power_consumption_kwh, cost, kiln_id, observation, image_path
    """
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO firings (date, type, power_consumption_kwh, cost, kiln_id, observation, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            firing_data['date'], 
            firing_data['type'], 
            firing_data['power_consumption_kwh'], 
            firing_data['cost'], 
            firing_data['kiln_id'], 
            firing_data['observation'], 
            firing_data['image_path']
        ))
        new_id = cursor.lastrowid
        conn.commit()
        
        audit.log_action(conn, 'CREATE', 'firings', new_id, None,
            {'date': str(firing_data['date']), 'type': firing_data['type'], 
             'cost': firing_data['cost'], 'consumption': firing_data['power_consumption_kwh']})
        return new_id
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error creating firing", e)
        raise

def update_firing(conn, firing_id, firing_data):
    """Updates an existing firing record."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE firings 
            SET date=?, type=?, power_consumption_kwh=?, cost=?, kiln_id=?, observation=?, image_path=?
            WHERE id=?
        """, (
            firing_data['date'], 
            firing_data['type'], 
            firing_data['power_consumption_kwh'], 
            firing_data['cost'], 
            firing_data['kiln_id'], 
            firing_data['observation'], 
            firing_data['image_path'],
            firing_id
        ))
        conn.commit()
        
        audit.log_action(conn, 'UPDATE', 'firings', firing_id, None, firing_data) # Simplified audit
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error updating firing {firing_id}", e)
        raise

def delete_firing(conn, firing_id):
    """Deletes a firing record."""
    cursor = conn.cursor()
    try:
        # Get old data for audit
        old = get_firing_by_id(conn, firing_id)
        old_data = old.to_dict() if old is not None else {}
        
        cursor.execute("DELETE FROM firings WHERE id=?", (firing_id,))
        conn.commit()
        
        audit.log_action(conn, 'DELETE', 'firings', firing_id, old_data, None)
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error deleting firing {firing_id}", e)
        raise

# ==============================================================================
# MANUTENÇÃO (MAINTENANCE)
# ==============================================================================

def get_maintenance_records(conn, filters=None):
    """
    Fetches maintenance records based on filters.
    filters: dict with kiln_name, category, start_date, end_date
    """
    query = """
        SELECT m.id, m.date, k.name as forno, m.category, m.description, m.observation, m.image_path, m.kiln_id
        FROM kiln_maintenance m
        JOIN kilns k ON m.kiln_id = k.id
        WHERE 1=1
    """
    params = []
    
    if filters:
        if filters.get('kiln_name') and filters['kiln_name'] != "Todos":
            query += " AND k.name = ?"
            params.append(filters['kiln_name'])
            
        if filters.get('category') and filters['category'] != "Todas":
            query += " AND m.category = ?"
            params.append(filters['category'])
            
        if filters.get('start_date') and filters.get('end_date'):
            query += " AND m.date BETWEEN ? AND ?"
            params.append(filters['start_date'])
            params.append(filters['end_date'])
            
    query += " ORDER BY m.date DESC"
    return pd.read_sql(query, conn, params=params)

def get_maintenance_by_id(conn, maint_id):
    """Fetches a single maintenance record."""
    df = pd.read_sql("SELECT * FROM kiln_maintenance WHERE id = ?", conn, params=(maint_id,))
    return df.iloc[0] if not df.empty else None

def create_maintenance(conn, maint_data):
    """
    Creates a new maintenance record.
    maint_data: kiln_id, date, category, description, observation, image_path
    """
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO kiln_maintenance (kiln_id, date, category, description, observation, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            maint_data['kiln_id'],
            maint_data['date'],
            maint_data['category'],
            maint_data['description'],
            maint_data['observation'],
            maint_data['image_path']
        ))
        new_id = cursor.lastrowid
        conn.commit()
        
        audit.log_action(conn, 'CREATE', 'kiln_maintenance', new_id, None,
            {'date': str(maint_data['date']), 'category': maint_data['category'], 'description': maint_data['description']})
        return new_id
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error creating maintenance", e)
        raise

def update_maintenance(conn, maint_id, maint_data):
    """Updates an existing maintenance record."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE kiln_maintenance 
            SET kiln_id=?, date=?, category=?, description=?, observation=?, image_path=?
            WHERE id=?
        """, (
            maint_data['kiln_id'],
            maint_data['date'],
            maint_data['category'],
            maint_data['description'],
            maint_data['observation'],
            maint_data['image_path'],
            maint_id
        ))
        conn.commit()
        
        audit.log_action(conn, 'UPDATE', 'kiln_maintenance', maint_id, None, maint_data)
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error updating maintenance {maint_id}", e)
        raise

def delete_maintenance(conn, maint_id):
    """Deletes a maintenance record."""
    cursor = conn.cursor()
    try:
        old = get_maintenance_by_id(conn, maint_id)
        old_data = old.to_dict() if old is not None else {}
        
        cursor.execute("DELETE FROM kiln_maintenance WHERE id=?", (maint_id,))
        conn.commit()
        
        audit.log_action(conn, 'DELETE', 'kiln_maintenance', maint_id, old_data, None)
        return True
    except Exception as e:
        conn.rollback()
        log_exception(logger, f"Error deleting maintenance {maint_id}", e)
        raise
