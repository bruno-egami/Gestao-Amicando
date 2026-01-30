import sqlite3
import os

DB_FOLDER = "data"
DB_NAME = "ceramic_admin.db"
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def get_connection():
    return sqlite3.connect(DB_PATH)

def run_migrations(conn):
    cursor = conn.cursor()
    
    # --- Migrations for Existing Tables ---
    
    # 1. Materials: Add 'type' and 'supplier_id'
    try:
        cursor.execute("ALTER TABLE materials ADD COLUMN type TEXT DEFAULT 'Material'")
    except sqlite3.OperationalError:
        pass # Already exists
        
    try:
        cursor.execute("ALTER TABLE materials ADD COLUMN supplier_id INTEGER")
    except sqlite3.OperationalError:
        pass

    # 2. Sales: Add 'client_id'
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN client_id INTEGER")
    except sqlite3.OperationalError:
        pass

    conn.commit()

def init_db():
    if not os.path.exists(DB_FOLDER):
        os.makedirs(DB_FOLDER)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- New Tables ---

    # Suppliers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT,
            phone TEXT,
            email TEXT,
            notes TEXT
        )
    ''')

    # Clients
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT,
            phone TEXT,
            email TEXT,
            notes TEXT
        )
    ''')

    # Product Recipes (Ingredients for Products)
    # Replaces 'formula_ingredients' but linked directly to products now (custom recipes per product)
    # Or we can keep 'formulas' as templates. 
    # User asked for: "incremental product items... addition of items from insumos... reflect in consumption"
    # So each product has a recipe.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            material_id INTEGER,
            quantity REAL, -- Amount needed for 1 unit of product
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (material_id) REFERENCES materials (id)
        )
    ''')
    
    # Expenses (Recurring & Eventual)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            description TEXT,
            amount REAL,
            category TEXT, -- 'Fixo', 'Eventual'
            supplier_id INTEGER,
            linked_material_id INTEGER, -- If stocking up material
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id),
            FOREIGN KEY (linked_material_id) REFERENCES materials (id)
        )
    ''')

    # --- Existing Tables (Ensure they exist) ---
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            supplier TEXT, 
            price_per_unit REAL NOT NULL,
            unit TEXT NOT NULL,
            stock_level REAL DEFAULT 0,
            min_stock_alert REAL DEFAULT 0,
            type TEXT DEFAULT 'Material',
            supplier_id INTEGER
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fixed_costs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            value REAL NOT NULL
        )
    ''')

    # Firings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS firings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            type TEXT,
            power_consumption_kwh REAL,
            cost REAL
        )
    ''')

    # Products
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            weight_g REAL,
            labor_time_h REAL,
            base_price REAL,
            markup REAL DEFAULT 0,
            image_paths TEXT,
            stock_quantity INTEGER DEFAULT 0
        )
    ''')

    # Sales
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            product_id INTEGER,
            quantity INTEGER,
            total_price REAL,
            status TEXT,
            client_id INTEGER,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')

    # --- Drop Deprecated Tables ---
    cursor.execute("DROP TABLE IF EXISTS formulas")
    cursor.execute("DROP TABLE IF EXISTS formula_ingredients")
    
    conn.commit()
    
    # Run migrations for columns in existing tables
    run_migrations(conn)
    
    conn.close()
    print(f"Database initialized and migrated at {DB_PATH}")

if __name__ == "__main__":
    init_db()
