import sqlite3
import os

DB_PATH = "data/ceramic_admin.db"

def fix_tables():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Creating tables...")
    
    # Commission Orders (Headers)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commission_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            total_price REAL,
            deposit_amount REAL DEFAULT 0,
            manual_discount REAL DEFAULT 0,
            date_created TEXT,
            date_due TEXT,
            status TEXT, -- 'Pendente', 'Em Produção', 'Concluída', 'Entregue'
            notes TEXT,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
    ''')

    # Commission Items (Details)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commission_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            quantity_from_stock INTEGER DEFAULT 0,
            quantity_produced INTEGER DEFAULT 0,
            unit_price REAL,
            FOREIGN KEY (order_id) REFERENCES commission_orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''') 
    
    # Drop old table if exists
    try:
        cursor.execute("DROP TABLE IF EXISTS commissions")
        print("Dropped old 'commissions' table.")
    except Exception as e:
        print(f"Drop error (ignore): {e}")
        
    conn.commit()
    conn.close()
    print("Tables created successfully.")

if __name__ == "__main__":
    fix_tables()
