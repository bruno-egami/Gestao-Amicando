import sqlite3
import os
import contextlib
import config
from utils.logging_config import get_logger
import database_schema

logger = get_logger(__name__)

DB_FOLDER = config.DB_FOLDER
DB_NAME = config.DB_NAME
DB_PATH = config.DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    database_schema.run_migrations(conn) # Ensure DB is always up to date
    return conn

@contextlib.contextmanager
def db_session():
    """Context manager for database connections."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    if not os.path.exists(DB_FOLDER):
        os.makedirs(DB_FOLDER)

    conn = sqlite3.connect(DB_PATH)
    database_schema.init_db_from_conn(conn)
    conn.close()

if __name__ == "__main__":
    init_db()
