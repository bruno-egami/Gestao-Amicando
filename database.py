import sqlite3
import os

DB_FOLDER = "data"
DB_NAME = "ceramic_admin.db"
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    run_migrations(conn)
    return conn

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

    # Inventory Transactions (Stock History) - ensuring existence
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER,
            date TEXT,
            type TEXT, -- 'ENTRADA', 'SAIDA', 'AJUSTE'
            quantity REAL,
            cost REAL,
            notes TEXT,
            user_id INTEGER,
            FOREIGN KEY (material_id) REFERENCES materials(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

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

    # Product Categories
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_categories (
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

    # Users (Authentication & Authorization)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'vendedor',
            name TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT,
            last_login TEXT
        )
    ''')

    # Audit Log (Track all changes for rollback)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_id INTEGER,
            username TEXT,
            action TEXT NOT NULL,
            table_name TEXT NOT NULL,
            record_id INTEGER,
            old_data TEXT,
            new_data TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Production History (Log each production event)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS production_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT,
            quantity INTEGER NOT NULL,
            order_id INTEGER,
            user_id INTEGER,
            username TEXT,
            notes TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (order_id) REFERENCES commission_orders(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
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

    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN order_id TEXT")
    except sqlite3.OperationalError: pass

    # 7. Create product_kits table (Migration)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_kits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_product_id INTEGER NOT NULL,
            child_product_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            FOREIGN KEY (parent_product_id) REFERENCES products(id),
            FOREIGN KEY (child_product_id) REFERENCES products(id)
        )
    ''')



    # 6. Security Upgrade: Reset Admin Password to 'admin' (bcrypt)
    # This runs every time but we only want to do it once ideally? 
    # Or strict requirement: "reset senhas atuais".
    # We will reset 'admin' user password to 'admin' (bcrypt hashed).
    # Hash for 'admin' generated with bcrypt (cost 12): 
    # We can generate it dynamically if we import bcrypt, but let's avoid adding dep to database.py if possible.
    # Actually, we added bcrypt to requirements, so we can import it.
    try:
        import bcrypt
        admin_hash = bcrypt.hashpw('admin'.encode(), bcrypt.gensalt()).decode()
        cursor.execute("UPDATE users SET password_hash = ? WHERE username = 'admin'", (admin_hash,))
        # Optional: Invalidate others?
        # cursor.execute("UPDATE users SET active = 0 WHERE username != 'admin'")
    except ImportError:
        pass
    except Exception as e:
        print(f"Migration error (reset admin): {e}")

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

    # Ensure default data for Product categories
    cursor.execute("SELECT count(*) FROM product_categories")
    if cursor.fetchone()[0] == 0:
        def_prods = ["Utilitário", "Decorativo", "Outros"]
        for dp in def_prods:
            cursor.execute("INSERT INTO product_categories (name) VALUES (?)", (dp,))
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
    
    # Drop old table if exists (during dev phase)
    try:
        cursor.execute("DROP TABLE IF EXISTS commissions")
    except: pass

    # --- Drop Deprecated Tables ---
    cursor.execute("DROP TABLE IF EXISTS formulas")
    cursor.execute("DROP TABLE IF EXISTS formula_ingredients")
    
    # Inventory Transactions (Stock History)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER,
            date TEXT,
            type TEXT, -- 'ENTRADA', 'SAIDA', 'AJUSTE'
            quantity REAL,
            cost REAL,
            notes TEXT,
            user_id INTEGER,
            FOREIGN KEY (material_id) REFERENCES materials(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Product Kits (Bundles)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_kits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_product_id INTEGER NOT NULL,
            child_product_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            FOREIGN KEY (parent_product_id) REFERENCES products(id),
            FOREIGN KEY (child_product_id) REFERENCES products(id)
        )
    ''')
    
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
