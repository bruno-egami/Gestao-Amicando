import os
import shutil
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import database
import config
from utils.logging_config import get_logger, log_exception

logger = get_logger(__name__)

BACKUP_FOLDER = config.BACKUP_DIR

def get_backup_settings(conn):
    """Fetch backup frequency and last run timestamp."""
    try:
        settings = pd.read_sql("SELECT key, value FROM settings WHERE key IN ('backup_frequency', 'last_backup_timestamp')", conn)
        settings_dict = dict(zip(settings['key'], settings['value']))
        return {
            'frequency': settings_dict.get('backup_frequency', 'Diário'),
            'last_run': settings_dict.get('last_backup_timestamp', '2000-01-01T00:00:00')
        }
    except (sqlite3.Error, pd.io.sql.DatabaseError, KeyError):
        return {'frequency': 'Diário', 'last_run': '2000-01-01T00:00:00'}

def save_backup_settings(conn, frequency):
    """Update backup frequency setting."""
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value = ? WHERE key = 'backup_frequency'", (frequency,))
    conn.commit()

def run_backup_if_needed(conn):
    """Check if a backup is due and run it if so."""
    settings = get_backup_settings(conn)
    freq = settings['frequency']
    
    if freq == 'Manual':
        return False

    last_run = datetime.fromisoformat(settings['last_run'])
    now = datetime.now()
    
    needed = False
    if freq == 'Diário' and (now - last_run) >= timedelta(days=1):
        needed = True
    elif freq == 'Semanal' and (now - last_run) >= timedelta(weeks=1):
        needed = True
    elif freq == 'Mensal' and (now - last_run) >= timedelta(days=30):
        needed = True
        
    if needed:
        return perform_backup(conn)
    return False

def perform_backup(conn):
    """Execute the database backup."""
    if not os.path.exists(BACKUP_FOLDER):
        os.makedirs(BACKUP_FOLDER)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_FOLDER, backup_filename)
    
    try:
        # Validate path is within the expected backup folder
        safe_path = os.path.abspath(backup_path)
        expected_folder = os.path.abspath(BACKUP_FOLDER)
        if not safe_path.startswith(expected_folder + os.sep) and safe_path != expected_folder:
            raise ValueError(f"Caminho de backup fora do diretório permitido: {safe_path}")
        
        # VACUUM INTO is a safe way to create a backup of a live DB
        # Note: SQLite does not support parameterized queries for VACUUM INTO,
        # so we use f-string after validating the path above
        cursor = conn.cursor()
        escaped_path = safe_path.replace("'", "''")
        cursor.execute(f"VACUUM INTO '{escaped_path}'")
        
        # Update last run
        cursor.execute("UPDATE settings SET value = ? WHERE key = 'last_backup_timestamp'", (datetime.now().isoformat(),))
        conn.commit()
        logger.info(f"Backup created successfully: {backup_filename}")
        return True
    except sqlite3.Error as e:
        log_exception(logger, "Backup failed", e)
        return False

def list_backups():
    """List last 5 backups in the backup folder."""
    if not os.path.exists(BACKUP_FOLDER):
        return []
    
    files = [f for f in os.listdir(BACKUP_FOLDER) if f.endswith('.db')]
    # Sort by name (which has timestamp) descending
    files.sort(reverse=True)
    return files[:10] # Return up to 10 for better visibility

def delete_backup(filename):
    """Delete a specific backup file."""
    path = os.path.join(BACKUP_FOLDER, filename)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
