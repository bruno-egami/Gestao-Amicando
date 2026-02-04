import database
import sqlite3

def run_migration():
    conn = database.get_connection()
    cursor = conn.cursor()
    
    tables = ['sales', 'commission_items', 'quote_items']
    
    print("Migrating tables to add variant_id...")
    
    for table in tables:
        try:
            print(f"Checking {table}...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN variant_id INTEGER")
            print(f"  Added variant_id to {table}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"  variant_id already exists in {table}")
            else:
                print(f"  Error altering {table}: {e}")
                
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    run_migration()
