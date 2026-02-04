import database
import sqlite3

def run_migration():
    conn = database.get_connection()
    cursor = conn.cursor()
    
    print("Migrating product_variants to add material_quantity...")
    
    try:
        cursor.execute("ALTER TABLE product_variants ADD COLUMN material_quantity REAL DEFAULT 0.0")
        print("  Added material_quantity to product_variants")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("  material_quantity already exists in product_variants")
        else:
            print(f"  Error altering product_variants: {e}")
                
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    run_migration()
