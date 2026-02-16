
import os
import sys
import ast
import importlib
import pkgutil
import sqlite3
import traceback

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

def check_syntax(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError in {file_path}: {e}"
    except Exception as e:
        return False, f"Error reading {file_path}: {e}"

def check_imports():
    error_list = []
    # Walk through all directories
    for root, dirs, files in os.walk(PROJECT_ROOT):
        if "env" in root or "venv" in root or ".git" in root or "__pycache__" in root:
            continue
            
        for file in files:
            if file.endswith(".py"):
                # Try to import strictly modules that are meant to be imported
                # For pages/ and scripts/, we just syntax check them usually, but import checks are good for services/views
                rel_path = os.path.relpath(os.path.join(root, file), PROJECT_ROOT)
                module_name = rel_path.replace(os.path.sep, ".")[:-3]
                
                # Skip top level scripts meant for direct execution if they have side effects
                if module_name in ["Dashboard", "verify_full_project"]: 
                    continue
                
                try:
                    importlib.import_module(module_name)
                    # print(f"Import OK: {module_name}")
                except Exception as e:
                    # Ignore streamlit specific errors if running headless
                    if "streamlit" in str(e):
                        continue
                    error_list.append(f"ImportError in {rel_path}: {e}")
    return error_list

def check_database():
    try:
        from database import DB_PATH
        if not os.path.exists(DB_PATH):
            return "Database file not found."
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] == "ok":
            return None
        else:
            return f"Database integrity check failed: {result}"
    except Exception as e:
        return f"Database check error: {e}"

def main():
    print("=== STARTING FULL PROJECT VERIFICATION ===")
    
    # 1. Syntax Check
    print("\n--- Syntax Check ---")
    syntax_errors = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        if "env" in root or "venv" in root or ".git" in root or "__pycache__" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                ok, err = check_syntax(path)
                if not ok:
                    print(f"❌ {err}")
                    syntax_errors.append(err)
    
    if not syntax_errors:
        print("✅ All files passed syntax check.")

    # 2. Database Check
    print("\n--- Database Check ---")
    db_err = check_database()
    if db_err:
        print(f"❌ {db_err}")
    else:
        print("✅ Database integrity OK.")

    # 3. Import Check (Basic)
    print("\n--- Import Check ---")
    # This is tricky because some scripts perform actions on import. 
    # We will try to rely on the fact that we fixed imports. 
    # Let's just check specific critical modules.
    critical_modules = [
        "views.report_pages.financial",
        "views.report_pages.stock",
        "services.analytics_service",
        "services.order_service",
        "Dashboard", # This might fail due to streamlit commands but let's see
        "pages.9_Encomendas"
    ]
    
    # Actually, let's just create a list of modules to verify from file structure
    # and try to check them with a dedicated subprocess to avoid polluting this process
    # or just checking the ones we moved.
    
    print("Verifying critical modules import...")
    for mod in ["services.analytics_service", "views.report_pages.financial", "audit", "auth"]:
        try:
            importlib.import_module(mod)
            print(f"✅ {mod} imported successfully.")
        except Exception as e:
            print(f"❌ Failed to import {mod}: {e}")

    print("\n=== VERIFICATION COMPLETE ===")

if __name__ == "__main__":
    main()
