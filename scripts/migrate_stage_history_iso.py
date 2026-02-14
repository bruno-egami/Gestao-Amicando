
import sqlite3
import json
import logging
from datetime import datetime
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection

def migrate_stage_history():
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        logger.info("Starting migration of stage_history to ISO format...")
        
        # Get all records with stage_history
        cursor.execute("SELECT id, stage_history FROM production_wip WHERE stage_history IS NOT NULL")
        rows = cursor.fetchall()
        
        updated_count = 0
        today = datetime.now()
        current_year = today.year
        
        for row in rows:
            item_id = row[0]
            history_str = row[1]
            
            try:
                history = json.loads(history_str)
            except json.JSONDecodeError:
                logger.warning(f"Skipping Invalid JSON for item {item_id}")
                continue
                
            changed = False
            new_history = {}
            
            for stage, date_str in history.items():
                # Check format
                # ISO usually has 'T' or looks YYYY-MM-DD...
                # Old format is DD/MM HH:MM
                
                # Check if already ISO (try parsing)
                is_iso = False
                try:
                    datetime.fromisoformat(date_str)
                    is_iso = True
                except ValueError:
                    pass
                
                if not is_iso:
                    # Try to parse old format
                    try:
                        # Handle potential " - " or other noise if any, but code says "%d/%m %H:%M"
                        # The code also had a logic for breakages: "-5 pcs | 14/02 10:00"
                        if "|" in date_str:
                            # It's a breakage record, leave it or parse the date part?
                            # production_service.py logic mostly ignores these in get_stage_duration_stats
                            # But let's leave them as string for now if they are complex
                            # production_service L314 only uses history[stage]
                            pass
                        else:
                            dt = datetime.strptime(date_str, "%d/%m %H:%M")
                            # Add year logic
                            dt = dt.replace(year=current_year)
                            if dt > today:
                                dt = dt.replace(year=current_year - 1)
                                
                            new_date_str = dt.isoformat(timespec='minutes')
                            new_history[stage] = new_date_str
                            changed = True
                            continue
                            
                    except ValueError:
                        # Might be some other format or garbage
                        logger.warning(f"Could not parse date '{date_str}' for item {item_id}, stage '{stage}'")
                
                # Copy as is if not changed
                new_history[stage] = date_str
            
            if changed:
                new_json = json.dumps(new_history)
                cursor.execute("UPDATE production_wip SET stage_history=? WHERE id=?", (new_json, item_id))
                updated_count += 1
                
        conn.commit()
        logger.info(f"Migration completed. Updated {updated_count} records.")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_stage_history()
