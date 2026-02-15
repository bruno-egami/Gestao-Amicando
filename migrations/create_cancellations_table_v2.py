import sys
import os
import logging

# Ensure we can import from root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    try:
        # Use database.get_connection() to ensure we use the EXACT same DB as the app
        logger.info(f"Connecting to database at: {config.DB_PATH}")
        conn = database.get_connection()
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
