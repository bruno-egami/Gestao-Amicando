import sys
import os
import sqlite3
import logging

# Ensure we can import from root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_cleanup():
    try:
        logger.info(f"Connecting to database at: {config.DB_PATH}")
        conn = sqlite3.connect(config.DB_PATH)
        cursor = conn.cursor()
        
        # Delete all records from class_cancellations
        logger.info("Deleting all records from class_cancellations table...")
        cursor.execute("DELETE FROM class_cancellations")
        
        conn.commit()
        conn.close()
        logger.info("Cleanup completed successfully.")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

if __name__ == "__main__":
    run_cleanup()
