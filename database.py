import sqlite3
import os
import contextlib
import config
from utils.logging_config import get_logger
import database_schema
from datetime import date

# Fix for Python 3.12+ SQLite deprecation warning
sqlite3.register_adapter(date, lambda d: d.isoformat())

logger = get_logger(__name__)

DB_FOLDER = config.DB_FOLDER
DB_NAME = config.DB_NAME
DB_PATH = config.DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def initialize():
    """Initializes the database and runs migrations."""
    logger.info("Initializing database...")
    if not os.path.exists(DB_FOLDER):
        os.makedirs(DB_FOLDER)
    
    conn = sqlite3.connect(DB_PATH)
    try:
        database_schema.init_db_from_conn(conn)
        # database_schema.run_migrations(conn) # init_db_from_conn already calls run_migrations
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise e
    finally:
        conn.close()


@contextlib.contextmanager
def db_session():
    """Context manager for database connections."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

if __name__ == "__main__":
    initialize()
