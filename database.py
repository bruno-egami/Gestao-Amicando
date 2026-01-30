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
    
    # 1. Materials: Add 'type', 'supplier_id', 'category_id', 'image_path'
    try:
        cursor.execute("ALTER TABLE materials ADD COLUMN type TEXT DEFAULT 'Material'")
    except sqlite3.OperationalError: pass
        
    try:
        cursor.execute("ALTER TABLE materials ADD COLUMN supplier_id INTEGER")
    except sqlite3.OperationalError: pass

    try:
        cursor.execute("ALTER TABLE materials ADD COLUMN category_id INTEGER")
    except sqlite3.OperationalError: pass

    try:
        cursor.execute("ALTER TABLE materials ADD COLUMN image_path TEXT")
    except sqlite3.OperationalError: pass

    # 2. Sales: Add 'client_id'
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN client_id INTEGER")
    except sqlite3.OperationalError: pass

    conn.commit()

def init_db():
    if not os.path.exists(DB_FOLDER):
        os.makedirs(DB_FOLDER)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Table Creations ---

    # Material Categories
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS material_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

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

    # Materials
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
            supplier_id INTEGER,
            category_id INTEGER,
            image_path TEXT
        )
    ''')

    # Fixed Costs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fixed_costs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL UNIQUE,
            value REAL NOT NULL,
            due_day INTEGER,
            periodicity TEXT, -- 'Mensal', 'Anual', 'Semanal'
            category TEXT
        )
    ''')

    # Kilns
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kilns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    # Kiln Maintenance
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kiln_maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kiln_id INTEGER,
            date TEXT,
            category TEXT, -- 'Resistência', 'Termopar', 'Estrutura'
            description TEXT,
            observation TEXT,
            image_path TEXT,
            FOREIGN KEY (kiln_id) REFERENCES kilns (id)
        )
    ''')

    # Expense Categories
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expense_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    # ... (rest of tables)

    # Seed Categories
    cursor.execute("SELECT count(*) FROM expense_categories")
    if cursor.fetchone()[0] == 0:
        defaults = ["Gasto Eventual", "Custo Fixo Mensal (Pagamento)", "Compra de Insumo", "Manutenção", "Impostos", "Outros", "Aluguel", "Energia", "Água", "Internet", "Transporte", "Marketing"]
        for d in defaults:
            try:
                cursor.execute("INSERT INTO expense_categories (name) VALUES (?)", (d,))
            except: pass
        conn.commit()

    # Firings (Update existing if needed, else created above)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS firings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            type TEXT,
            power_consumption_kwh REAL,
            cost REAL,
            kiln_id INTEGER,
            observation TEXT,
            image_path TEXT,
            FOREIGN KEY (kiln_id) REFERENCES kilns (id)
        )
    ''')
    
    # ...

    # --- Migrations for Existing Tables ---
    
    # ... (previous materials migrations)

    # 3. Firings: Add 'kiln_id', 'observation', 'image_path'
    try:
        cursor.execute("ALTER TABLE firings ADD COLUMN kiln_id INTEGER")
    except sqlite3.OperationalError: pass

    try:
        cursor.execute("ALTER TABLE firings ADD COLUMN observation TEXT")
    except sqlite3.OperationalError: pass

    try:
        cursor.execute("ALTER TABLE firings ADD COLUMN image_path TEXT")
    except sqlite3.OperationalError: pass

    # 4. Fixed Costs: Add 'due_day', 'periodicity', 'category'
    try:
        cursor.execute("ALTER TABLE fixed_costs ADD COLUMN due_day INTEGER")
    except sqlite3.OperationalError: pass
    
    try:
        cursor.execute("ALTER TABLE fixed_costs ADD COLUMN periodicity TEXT")
    except sqlite3.OperationalError: pass
    
    try:
        cursor.execute("ALTER TABLE fixed_costs ADD COLUMN category TEXT")
    except sqlite3.OperationalError: pass

    # 5. Sales: Add 'discount', 'payment_method', 'notes', 'salesperson'
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN discount REAL DEFAULT 0")
    except sqlite3.OperationalError: pass

    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN payment_method TEXT")
    except sqlite3.OperationalError: pass

    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN notes TEXT")
    except sqlite3.OperationalError: pass
    
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN salesperson TEXT")
    except sqlite3.OperationalError: pass

    conn.commit()
    
    # Seed Kilns
    cursor.execute("SELECT count(*) FROM kilns")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO kilns (name) VALUES ('Jung (Pequeno)')")
        cursor.execute("INSERT INTO kilns (name) VALUES ('Arimbá (Grande)')")
        conn.commit()

    # Ensure default data for categories (previous)
    cursor.execute("SELECT count(*) FROM material_categories")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO material_categories (name) VALUES ('Geral')")
        conn.commit()

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

    # Product Recipes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            material_id INTEGER,
            quantity REAL,
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (material_id) REFERENCES materials (id)
        )
    ''')
    
    # Expenses
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            description TEXT,
            amount REAL,
            category TEXT,
            supplier_id INTEGER,
            linked_material_id INTEGER,
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id),
            FOREIGN KEY (linked_material_id) REFERENCES materials (id)
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
    
    # Run migrations for existing databases that might miss new columns
    run_migrations(conn)
    
    # Ensure default data for categories
    cursor.execute("SELECT count(*) FROM material_categories")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO material_categories (name) VALUES ('Geral')")
        conn.commit()

    conn.close()
    print(f"Database initialized and migrated at {DB_PATH}")

if __name__ == "__main__":
    init_db()
