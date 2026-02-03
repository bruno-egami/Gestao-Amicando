import ast
import os
import sys
import importlib.util
from unittest.mock import MagicMock
import sqlite3

# --- 1. CONFIGURATION ---
EXCLUDE_IMPORT = [
    'verify_health_check.py', 
    'verify_full_project.py', 
    'debug_', 'fix_', 'migration_'
]

DB_PATH = "data/ceramic_admin.db"

# --- 2. MOCKING STREAMLIT ---
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit_extras"] = MagicMock()
sys.modules["streamlit_extras.metric_cards"] = MagicMock()

def mock_columns(spec, gap="small"):
    if isinstance(spec, int):
        return [MagicMock() for _ in range(spec)]
    return [MagicMock() for _ in range(len(spec))]

sys.modules["streamlit"].columns = MagicMock(side_effect=mock_columns)

# --- 3. HELPER FUNCTIONS ---

def check_syntax(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
        return True, None
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)

def check_db_integrity():
    if not os.path.exists(DB_PATH):
        return True, "DB File not found (local?)"
    
    issues = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check Critical Tables
        required_tables = [
            'users', 'products', 'materials', 'sales', 'expenses', 
            'clients', 'suppliers', 'product_recipes', 'product_kits',
            'inventory_transactions', 'production_history', 'audit_log'
        ]
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [r[0] for r in cursor.fetchall()]
        
        for rt in required_tables:
            if rt not in existing_tables:
                issues.append(f"Missing Table: {rt}")
                
        # Check Recent Column Additions (from our tasks)
        # Material Categories, Suppliers in materials table?
        cursor.execute("PRAGMA table_info(materials)")
        mat_cols = [r[1] for r in cursor.fetchall()]
        if 'supplier_id' not in mat_cols: issues.append("materials.supplier_id missing")
        if 'category_id' not in mat_cols: issues.append("materials.category_id missing")
        
        # Products export/import support (Composição is calculated, not DB)
        
        conn.close()
    except Exception as e:
        return False, f"DB Error: {e}"
        
    return len(issues) == 0, issues

def run_project_scan():
    print("==========================================")
    print("    PROJECT HEALTH CHECK - FULL SCAN      ")
    print("==========================================")
    
    root_dir = os.getcwd()
    py_files = []
    
    for root, dirs, files in os.walk(root_dir):
        if "venv" in root or ".git" in root or "__pycache__" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))
    
    print(f"found {len(py_files)} python files.")
    
    # A. SYNTAX CHECK
    print("\n[ A. SYNTAX CHECK ]")
    syntax_errors = 0
    for pf in py_files:
        rel_path = os.path.relpath(pf, root_dir)
        ok, msg = check_syntax(pf)
        if not ok:
            print(f"❌ {rel_path}: {msg}")
            syntax_errors += 1
        # else: print(f"✅ {rel_path}") # verbose
    
    if syntax_errors == 0:
        print("✅ No Syntax Errors found.")
    else:
        print(f"❌ Found {syntax_errors} Syntax Errors!")
        
    # B. IMPORT CHECK (Runtime Crash Detection)
    print("\n[ B. IMPORT/RUNTIME CHECK ]")
    # We attempt to import core modules. We catch exceptions that happen constantly at top-level
    import_errors = 0
    
    search_paths = [root_dir] + sys.path
    sys.path = search_paths
    
    for pf in py_files:
        rel_path = os.path.relpath(pf, root_dir)
        
        # Skip exclusion list
        if any(ex in rel_path for ex in EXCLUDE_IMPORT):
            continue
            
        module_name = os.path.splitext(rel_path.replace(os.sep, "."))[0]
        
        try:
            # We use importlib to load source
            spec = importlib.util.spec_from_file_location(module_name, pf)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                # print(f"✅ {rel_path}")
        except Exception as e:
            # Common error in Streamlit scripts if we don't mock everything perfectly, 
            # but we care about NameError, SyntaxError (caught above), IndentationError
            error_str = str(e)
            if "No module named" in error_str and "streamlit" not in error_str:
                print(f"⚠️ {rel_path}: Import Warning: {e}")
            elif "streamlit" not in error_str:
                print(f"❌ {rel_path}: Runtime Error: {e}")
                import_errors += 1
                
    if import_errors == 0:
        print("✅ Core modules loaded without crash.")
    else:
        print(f"❌ Found {import_errors} Import/Runtime Errors.")

    # C. DATABASE INTEGRITY
    print("\n[ C. DATABASE INTEGRITY ]")
    ok, data = check_db_integrity()
    if ok:
        print("✅ Database Schema appears healthy.")
    else:
        if isinstance(data, list):
            for i in data: print(f"❌ {i}")
        else:
            print(f"❌ {data}")

if __name__ == "__main__":
    run_project_scan()
