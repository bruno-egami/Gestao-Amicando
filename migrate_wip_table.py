import sqlite3
import os

DB_PATH = os.path.join("data", "ceramic_admin.db")

def migrate_wip():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Creating production_wip table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS production_wip (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            variant_id INTEGER, 
            order_id INTEGER,
            order_item_id INTEGER,
            stage TEXT CHECK( stage IN ('Modelagem', 'Secagem', 'Biscoito', 'Esmaltação') ),
            quantity INTEGER NOT NULL,
            start_date TEXT, -- Data agendada ou real de início
            materials_deducted BOOLEAN DEFAULT 0, -- Controle se a massa/argila já foi baixada
            notes TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (order_id) REFERENCES commission_orders(id),
            FOREIGN KEY (order_item_id) REFERENCES commission_items(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate_wip()
