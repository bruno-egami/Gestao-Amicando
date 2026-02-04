import sqlite3
import pandas as pd
import database

def migrate():
    conn = database.get_connection()
    cursor = conn.cursor()
    print("Starting WIP Table Migration V2 (Adding 'Queima de Alta')...")
    
    try:
        # 1. Rename old table
        print("Renaming old table...")
        cursor.execute("ALTER TABLE production_wip RENAME TO production_wip_old")
        
        # 2. Create new table with updated CHECK
        print("Creating new table...")
        cursor.execute('''
            CREATE TABLE production_wip (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                variant_id INTEGER, 
                order_id INTEGER,
                order_item_id INTEGER,
                stage TEXT CHECK( stage IN ('Modelagem', 'Secagem', 'Biscoito', 'Esmaltação', 'Queima de Alta') ),
                quantity INTEGER NOT NULL,
                start_date TEXT, 
                materials_deducted BOOLEAN DEFAULT 0,
                notes TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (order_id) REFERENCES commission_orders(id),
                FOREIGN KEY (order_item_id) REFERENCES commission_items(id)
            )
        ''')
        
        # 3. Copy data
        print("Copying data...")
        cursor.execute("""
            INSERT INTO production_wip 
            SELECT id, product_id, variant_id, order_id, order_item_id, stage, quantity, start_date, materials_deducted, notes 
            FROM production_wip_old
        """)
        
        # 4. Verification
        count_old = cursor.execute("SELECT COUNT(*) FROM production_wip_old").fetchone()[0]
        count_new = cursor.execute("SELECT COUNT(*) FROM production_wip").fetchone()[0]
        print(f"Old Rows: {count_old}, New Rows: {count_new}")
        
        if count_old == count_new:
            # 5. Drop old
            print("Dropping old table...")
            cursor.execute("DROP TABLE production_wip_old")
            conn.commit()
            print("Migration Success!")
        else:
            print("Row count mismatch! Rolling back...")
            conn.rollback()
            
    except Exception as e:
        print(f"Migration Failed: {e}")
        conn.rollback()
    
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
