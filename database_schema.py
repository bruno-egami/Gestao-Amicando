import sqlite3
from utils.logging_config import get_logger

logger = get_logger(__name__)

# --- Migrations ---

def _migrate_v1(cursor):
    """
    Baseline migration: Applies all legacy column additions using try-except.
    This ensures existing databases (Version 0) are brought up to the baseline state.
    """
    # 1. Materials
    for col, dtype in [('type', "TEXT DEFAULT 'Material'"), ('supplier_id', 'INTEGER'), 
                       ('category_id', 'INTEGER'), ('image_path', 'TEXT')]:
        try: cursor.execute(f"ALTER TABLE materials ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError: pass

    # 2. Sales
    try: cursor.execute("ALTER TABLE sales ADD COLUMN client_id INTEGER")
    except sqlite3.OperationalError: pass

    # 3. Commission Orders
    try: cursor.execute("ALTER TABLE commission_orders ADD COLUMN image_paths TEXT")
    except sqlite3.OperationalError: pass

    # 10. Production Losses
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS production_losses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            product_id INTEGER,
            variant_id INTEGER,
            stage TEXT,
            quantity INTEGER,
            reason TEXT,
            order_id INTEGER,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (variant_id) REFERENCES product_variants(id),
            FOREIGN KEY (order_id) REFERENCES commission_orders(id)
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_losses_product ON production_losses(product_id)")

    # 11. Student Consumptions
    for col, dtype in [('payment_date', 'TEXT'), ('material_id', 'INTEGER'), ('amount_paid', 'REAL DEFAULT 0')]:
        try: cursor.execute(f"ALTER TABLE student_consumptions ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError: pass

    # 12. Tuitions
    for col, dtype in [('created_at', 'TEXT'), ('amount_paid', 'REAL DEFAULT 0'), ('class_dates', 'TEXT')]:
        try: cursor.execute(f"ALTER TABLE tuitions ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError: pass

    # 13. Settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('backup_frequency', 'Diário')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('last_backup_timestamp', '2000-01-01T00:00:00')")

# Registry of migrations: {version_int: function_taking_cursor}
def _migrate_v2(cursor):
    """
    Migration v2: Add 'force_password_change' to users.
    """
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN force_password_change INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    
    # Force existing admin to change password
    try:
        cursor.execute("UPDATE users SET force_password_change = 1 WHERE username = 'admin'")
    except Exception: pass

MIGRATIONS = {
    1: _migrate_v1,
    2: _migrate_v2
}

def run_migrations(conn):
    """
    Check current DB version and apply pending migrations sequentially.
    """
    cursor = conn.cursor()
    
    # Get current version
    current_version = cursor.execute("PRAGMA user_version").fetchone()[0]
    logger.info(f"Database Current Version: {current_version}")
    
    # Determine max version
    max_version = max(MIGRATIONS.keys()) if MIGRATIONS else 0
    
    if current_version < max_version:
        for version in range(current_version + 1, max_version + 1):
            if version in MIGRATIONS:
                try:
                    logger.info(f"Applying Migration v{version}...")
                    MIGRATIONS[version](cursor)
                    cursor.execute(f"PRAGMA user_version = {version}")
                    conn.commit()
                    logger.info(f"Migration v{version} applied successfully.")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Migration v{version} Failed: {e}")
                    raise e
    else:
        logger.info("Database is up to date.")

# --- Schema Initialization ---

def init_db_from_conn(conn):
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

    # Settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('backup_frequency', 'Diário')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('last_backup_timestamp', '2000-01-01T00:00:00')")

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

    # Firings (Quemas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS firings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT, -- 'Biscoito', 'Esmaltação'
            kiln_id INTEGER,
            power_consumption_kwh REAL DEFAULT 0,
            cost REAL DEFAULT 0,
            observation TEXT,
            image_path TEXT,
            FOREIGN KEY (kiln_id) REFERENCES kilns(id)
        )
    ''')

    # ... (rest of tables)

    # ... (Seed and Migration blocks moved below)
    pass

    # 10. Commission Items: Add 'notes', 'variant_id'
    try:
        cursor.execute("ALTER TABLE commission_items ADD COLUMN notes TEXT")
    except sqlite3.OperationalError: pass

    # 11. Quote Items: Add 'item_notes', 'variant_id'
    try:
        cursor.execute("ALTER TABLE quote_items ADD COLUMN item_notes TEXT")
    except sqlite3.OperationalError: pass

    try:
        cursor.execute("ALTER TABLE quote_items ADD COLUMN variant_id INTEGER REFERENCES product_variants(id)")
    except sqlite3.OperationalError: pass

    # 12. Quotes: Add 'delivery_terms', 'payment_terms'
    try:
        cursor.execute("ALTER TABLE quotes ADD COLUMN delivery_terms TEXT")
    except sqlite3.OperationalError: pass

    try:
        cursor.execute("ALTER TABLE quotes ADD COLUMN payment_terms TEXT")
    except sqlite3.OperationalError: pass

    # 13. Product Variants: Add 'material_quantity'
    try:
        cursor.execute("ALTER TABLE product_variants ADD COLUMN material_quantity REAL DEFAULT 0.0")
    except sqlite3.OperationalError: pass

    # ... (Refactor blocks moved below)
    pass





    # Security Upgrade: Password reset REMOVED (User request)
    # Admin creation is handled by auth.create_default_admin
    pass

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
            variant_id INTEGER,
            notes TEXT,
            FOREIGN KEY (order_id) REFERENCES commission_orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (variant_id) REFERENCES product_variants(id)
        )
    ''')  
    
    # Quotes (Orçamentos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            date_created TEXT,
            date_valid_until TEXT,
            status TEXT DEFAULT 'Pendente',
            total_price REAL DEFAULT 0,
            discount REAL DEFAULT 0,
            notes TEXT,
            converted_order_id INTEGER,
            delivery_terms TEXT,
            payment_terms TEXT,
            FOREIGN KEY (client_id) REFERENCES clients (id),
            FOREIGN KEY (converted_order_id) REFERENCES commission_orders (id)
        )
    ''')
    
    # Quote Items (Itens do Orçamento)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quote_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            unit_price REAL,
            item_notes TEXT,
            variant_id INTEGER,
            FOREIGN KEY (quote_id) REFERENCES quotes (id),
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (variant_id) REFERENCES product_variants(id)
        )
    ''') 
    
    # Drop old table if exists (during dev phase)
    try:
        cursor.execute("DROP TABLE IF EXISTS commissions")
    except Exception:
        pass

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

    # Product Variants (Esmaltes/Acabamentos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            variant_name TEXT,
            stock_quantity INTEGER DEFAULT 0,
            price_adder REAL DEFAULT 0.0,
            material_quantity REAL DEFAULT 0.0,
            material_id INTEGER,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (material_id) REFERENCES materials(id)
        )
    ''')

    # --- CLASS MANAGEMENT TABLES (Phase 4) ---
    # Students
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            active INTEGER DEFAULT 1,
            class_id INTEGER,
            join_date TEXT
        )
    ''')

    # Class Cancellations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS class_cancellations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER,
            date TEXT NOT NULL,
            reason TEXT,
            created_at TEXT,
            FOREIGN KEY (class_id) REFERENCES classes(id),
            UNIQUE(class_id, date)
        )
    ''')

    # Tuitions (Mensalidades)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tuitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            month_year TEXT, -- MM/AAAA
            amount REAL,
            status TEXT DEFAULT 'Pendente', -- Pendente, Pago
            payment_date TEXT,
            class_count INTEGER,
            unit_price REAL,
            class_dates TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    ''')
    
    # Student Consumptions (Consumo de Aulas/Insumos Extras)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_consumptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            description TEXT,
            quantity REAL,
            unit_price REAL,
            total_value REAL,
            date TEXT,
            status TEXT DEFAULT 'Pendente', -- Pendente, Pago
            payment_date TEXT,
            notes TEXT,
            markup REAL DEFAULT 0.0,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    ''')
    
    # Classes (Turmas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE, -- e.g. "Terça Manhã"
            schedule TEXT, -- e.g. "Terça 09:00 - 12:00"
            notes TEXT
        )
    ''')

    # --- INDEXES for Performance ---
    # Sales indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_client ON sales(client_id)")
    
    # Expenses indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_supplier ON expenses(supplier_id)")
    
    # Production WIP (Work In Progress/Kanban)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS production_wip (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            variant_id INTEGER, 
            order_id INTEGER,
            order_item_id INTEGER,
            stage TEXT CHECK( stage IN ('Fila de Espera', 'Modelagem', 'Secagem', 'Biscoito', 'Esmaltação', 'Queima de Alta') ),
            quantity INTEGER NOT NULL,
            start_date TEXT, -- Data agendada ou real de início
            materials_deducted BOOLEAN DEFAULT 0, -- Controle se a massa/argila já foi baixada
            stage_history TEXT, -- Histórico de datas por etapa (JSON)
            notes TEXT,
            priority INTEGER DEFAULT 0, -- Prioridade para ordenação customizada
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (order_id) REFERENCES commission_orders(id),
            FOREIGN KEY (order_item_id) REFERENCES commission_items(id)
        )
    ''')
    
    # Production Losses (Breakage Tracking) - Handled in run_migrations
    
    # Commission Orders indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON commission_orders(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_date_due ON commission_orders(date_due)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_client ON commission_orders(client_id)")
    
    # Products indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
    
    # Materials indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_materials_name ON materials(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_materials_type ON materials(type)")
    
    # Inventory transactions indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_trans_date ON inventory_transactions(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_trans_material ON inventory_transactions(material_id)")
    
    # Audit log indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_log(table_name)")

    # Product Variants indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_variants_product ON product_variants(product_id)")
    
    conn.commit()

    
    # Ensure default data for categories (Duplicate removed)
    pass
    
    # --- GLOBAL MIGRATIONS (Try-Except for idempotency) ---
    
    # Firings Fix
    for col, dtype in [('kiln_id', 'INTEGER'), ('observation', 'TEXT'), ('image_path', 'TEXT')]:
        try: cursor.execute(f"ALTER TABLE firings ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError: pass

    # Fixed Costs Fix
    for col, dtype in [('due_day', 'INTEGER'), ('periodicity', 'TEXT'), ('category', 'TEXT')]:
        try: cursor.execute(f"ALTER TABLE fixed_costs ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError: pass

    # Sales Fix
    for col, dtype in [('discount', 'REAL DEFAULT 0'), ('payment_method', 'TEXT'), ('notes', 'TEXT'), ('salesperson', 'TEXT'), ('order_id', 'TEXT'), ('variant_id', 'INTEGER')]:
        try: cursor.execute(f"ALTER TABLE sales ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError: pass

    # Student Management Fix
    try: cursor.execute("ALTER TABLE students ADD COLUMN class_id INTEGER")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE classes ADD COLUMN weekday INTEGER")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE students ADD COLUMN price_per_class REAL")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE tuitions ADD COLUMN class_count INTEGER")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE tuitions ADD COLUMN unit_price REAL")
    except sqlite3.OperationalError: pass
    
    # Seed Data
    cursor.execute("SELECT count(*) FROM expense_categories")
    if cursor.fetchone()[0] == 0:
        defaults = ["Gasto Eventual", "Custo Fixo Mensal (Pagamento)", "Compra de Insumo", "Manutenção", "Impostos", "Outros", "Aluguel", "Energia", "Água", "Internet", "Transporte", "Marketing"]
        for d in defaults:
            try: cursor.execute("INSERT OR IGNORE INTO expense_categories (name) VALUES (?)", (d,))
            except Exception: pass
        conn.commit()

    # Run versioned migrations
    run_migrations(conn)

    print(f"Database schema initialized.")
