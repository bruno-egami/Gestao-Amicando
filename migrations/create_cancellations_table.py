import sqlite3
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = 'data/ceramic_admin.db'

def run_migration():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create class_cancellations table
        logger.info("Creating table: class_cancellations")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS class_cancellations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                reason TEXT,
                created_at TEXT,
                FOREIGN KEY (class_id) REFERENCES classes (id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Migration completed successfully.")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    run_migration()
