import pandas as pd
import sqlite3
from datetime import datetime
import json
import calendar
import audit
from utils.logging_config import get_logger
from database import safe_transaction

logger = get_logger(__name__)

# --- Student CRUD ---

def get_all_active_students(conn, class_id=None):
    """Returns DataFrame of all active students, optionally filtered by class."""
    query = "SELECT s.*, c.name as class_name FROM students s LEFT JOIN classes c ON s.class_id = c.id WHERE s.active=1"
    params = []
    if class_id:
        query += " AND s.class_id=?"
        params.append(class_id)
    query += " ORDER BY s.name"
    return pd.read_sql(query, conn, params=params)

def get_all_inactive_students(conn):
    """Returns DataFrame of all inactive students."""
    query = "SELECT s.*, c.name as class_name FROM students s LEFT JOIN classes c ON s.class_id = c.id WHERE s.active=0 ORDER BY s.name"
    return pd.read_sql(query, conn)

def get_all_classes(conn):
    """Returns DataFrame of all classes with active student count."""
    query = """
        SELECT c.*, 
               (SELECT COUNT(*) FROM students WHERE class_id = c.id AND active = 1) as student_count
        FROM classes c
        ORDER BY c.name
    """
    return pd.read_sql(query, conn)

def create_class(conn, name, schedule, notes, weekday=None):
    """Creates a new class."""
    try:
        with safe_transaction(conn):
            cursor = conn.cursor()
            cursor.execute("INSERT INTO classes (name, schedule, notes, weekday) VALUES (?, ?, ?, ?)", (name, schedule, notes, weekday))
            rid = cursor.lastrowid
            audit.log_action(conn, 'CREATE', 'classes', rid, None, {'name': name}, commit=False)
        return rid
    except Exception as e:
        # safe_transaction rolls back on error
        logger.error(f"Erro ao criar turma '{name}': {e}")
        raise

def update_class(conn, class_id, name, schedule, notes, weekday=None):
    """Updates a class."""
    old = pd.read_sql("SELECT * FROM classes WHERE id=?", conn, params=(class_id,)).iloc[0].to_dict()
    try:
        with safe_transaction(conn):
            cursor = conn.cursor()
            cursor.execute("UPDATE classes SET name=?, schedule=?, notes=?, weekday=? WHERE id=?", (name, schedule, notes, weekday, class_id))
            audit.log_action(conn, 'UPDATE', 'classes', class_id, old, {'name': name}, commit=False)
    except Exception as e:
        logger.error(f"Erro ao atualizar turma {class_id}: {e}")
        raise

def create_student(conn, name, phone, class_id=None, join_date=None):
    """Creates a new student."""
    if not join_date:
        join_date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        with safe_transaction(conn):
            cursor = conn.cursor()
            cursor.execute("INSERT INTO students (name, phone, class_id, join_date, active) VALUES (?, ?, ?, ?, 1)", (name, phone, class_id, join_date))
            new_id = cursor.lastrowid
            audit.log_action(conn, 'CREATE', 'students', new_id, None, {'name': name, 'class_id': class_id}, commit=False)
        return new_id
    except Exception as e:
        logger.error(f"Erro ao criar aluno '{name}': {e}")
        raise

def update_student(conn, student_id, name, phone, active):
    """Updates student info (Name, Phone, Active). Class is handled separately."""
    student_id = int(student_id)
    # Get old data
    old = pd.read_sql("SELECT * FROM students WHERE id=?", conn, params=(student_id,)).iloc[0].to_dict()
    
    try:
        with safe_transaction(conn):
            cursor = conn.cursor()
            cursor.execute("UPDATE students SET name=?, phone=?, active=? WHERE id=?", 
                        (name, phone, int(active), student_id))
            
            audit.log_action(conn, 'UPDATE', 'students', student_id, old, {'name': name, 'phone': phone, 'active': active}, commit=False)
    except Exception as e:
        logger.error(f"Erro ao atualizar aluno {student_id}: {e}")
        raise
    try:
        conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
    except Exception as e:
        logger.warning(f"WAL Checkpoint (PASSIVE) failed: {e}")

# ... (update_student_class remains same) ...

# --- Settings Helpers ---
def get_global_price_per_class(conn):
    """Fetches global price per class from settings."""
    try:
        res = conn.execute("SELECT value FROM settings WHERE key='global_price_per_class'").fetchone()
        return float(res[0]) if res else 87.50 # Default if not set
    except:
        return 87.50

def set_global_price_per_class(conn, price):
    """Updates global price per class."""
    try:
        price = float(price)
        with safe_transaction(conn):
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('global_price_per_class', ?)", (str(price),))
        return True
    except Exception as e:
        logger.error(f"Error setting global price: {e}")
        return False

# --- Class Cancellation Helpers ---
def add_class_cancellation(conn, class_id, date_str, reason=""):
    """Adds a cancellation record."""
    try:
        # Enforce native int
        class_id = int(class_id)
        with safe_transaction(conn):
            conn.execute("INSERT INTO class_cancellations (class_id, date, reason, created_at) VALUES (?, ?, ?, ?)", 
                        (class_id, date_str, reason, datetime.now().isoformat()))
        return True
    except Exception as e:
        logger.error(f"Error adding cancellation: {e}")
        return False

def delete_class_cancellation(conn, cancellation_id):
    """Removes a cancellation record."""
    try:
        with safe_transaction(conn):
            conn.execute("DELETE FROM class_cancellations WHERE id=?", (cancellation_id,))
        return True
    except Exception as e:
        logger.error(f"Error deleting cancellation: {e}")
        return False

def get_class_cancellations(conn, class_id):
    """Returns DataFrame of cancellations for a class."""
    class_id = int(class_id)
    return pd.read_sql("SELECT * FROM class_cancellations WHERE class_id=? ORDER BY date DESC", conn, params=(class_id,))

def calculate_tuition(conn, student_id, month_year):
    """
    Calculates tuition based on student's class weekday and month days.
    Subtracts any class cancellations in that month.
    Returns: (count_of_days, price_per_class, total_amount)
    """
    # 1. Get Student Class Weekday
    student_id = int(student_id)
    row = pd.read_sql("SELECT s.class_id, c.weekday FROM students s LEFT JOIN classes c ON s.class_id = c.id WHERE s.id=?", conn, params=(student_id,)).iloc[0]
    
    if pd.isna(row['class_id']) or row['weekday'] is None or pd.isna(row['weekday']):
        logger.warning(f"Student {student_id} or class data missing: class_id={row['class_id']}, weekday={row['weekday']}")
        return 0, 0.0, 0.0
        
    class_id = int(row['class_id'])
    weekday = int(row['weekday']) # 0=Mon, 6=Sun
    price = get_global_price_per_class(conn)
    
    # 2. Count occurrences of weekday in month_year (MM/YYYY)
    try:
        m, y = map(int, month_year.split('/'))
        import calendar
        # calendar.monthcalendar returns list of weeks (lists of days). 
        # Days outside month are 0.
        cal = calendar.monthcalendar(y, m)
        
        # Get all valid dates for this weekday in the month
        valid_dates = []
        for week in cal:
            d = week[weekday]
            if d != 0:
                valid_dates.append(f"{y:04d}-{m:02d}-{d:02d}")
                
        total_days = len(valid_dates)
        
        # 3. Check for Cancellations
        # We need to query cancellations for this class_id and filter by the valid_dates we found.
        # SQLite 'IN' clause with many dates is okay, or just fetch all for month.
        # Let's fetch all cancellations for this class and filter in python for simplicity with dates.
        cancellations = pd.read_sql("SELECT date FROM class_cancellations WHERE class_id=?", conn, params=(class_id,))
        
        cancelled_count = 0
        if not cancellations.empty:
            # Filter cancellations that match our valid meeting dates
            # Ensure format matches YYYY-MM-DD
            cancelled_dates = cancellations['date'].tolist()
            for d in valid_dates:
                if d in cancelled_dates:
                    cancelled_count += 1
        
        final_count = max(0, total_days - cancelled_count)
        
        # Get purely final dates (removing cancelled ones)
        if cancelled_count > 0:
            final_dates = [d for d in valid_dates if d not in cancelled_dates]
        else:
            final_dates = valid_dates
            
    except Exception as e:
        logger.error(f"Error calculating tuition: {e}")
        final_count = 0
        final_dates = []
        
    total = final_count * price
    return final_count, price, total, final_dates

def generate_tuition_record(conn, student_id, month_year, amount, class_count=None, unit_price=None, class_dates=None):
    """Generates a monthly tuition record if not exists."""
    student_id = int(student_id)
    cursor = conn.cursor()
    # Check dup
    exist = cursor.execute("SELECT id FROM tuitions WHERE student_id=? AND month_year=?", (student_id, month_year)).fetchone()
    if exist:
        return False, "Mensalidade já gerada."
        
    import json
    dates_str = json.dumps(class_dates) if class_dates else None

    try:
        with safe_transaction(conn):
            cursor.execute("""
                INSERT INTO tuitions (student_id, month_year, amount, status, created_at, class_count, unit_price, class_dates) 
                VALUES (?, ?, ?, 'Pendente', ?, ?, ?, ?)
            """, (student_id, month_year, amount, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), class_count, unit_price, dates_str))
        return True, "Gerada com sucesso."
    except Exception as e:
        logger.error(f"Error generating tuition: {e}")
        return False, f"Erro: {e}"
        conn.rollback()
        logger.error(f"Erro ao gerar mensalidade para aluno {student_id}: {e}")
        raise

def update_student_class(conn, student_id, class_id):
    """Updates only the student's class."""
    student_id = int(student_id)
    class_id = int(class_id)
    # Get old data for audit
    try:
        old = pd.read_sql("SELECT class_id FROM students WHERE id=?", conn, params=(student_id,)).iloc[0].to_dict()
    except Exception:
        old = {}
        
    try:
        with safe_transaction(conn):
            cursor = conn.cursor()
            cursor.execute("UPDATE students SET class_id=? WHERE id=?", (class_id, student_id))
            
            if cursor.rowcount == 0:
                logger.warning(f"Update failed for student {student_id} (Row not found?)")
            
            audit.log_action(conn, 'UPDATE_CLASS', 'students', student_id, old, {'class_id': class_id}, commit=False)
    except Exception as e:
        logger.error(f"Erro ao atualizar turma do aluno {student_id}: {e}")
        raise
    
    # Force Checkpoint to ensure visibility
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception as e:
        logger.warning(f"WAL Checkpoint (TRUNCATE) failed: {e}")
    
    return True

# --- Consumption Logic ---

def add_consumption(conn, student_id, description, quantity, unit_price, total_val, date, user_id=None, notes=None, markup=0.0):
    """
    Logs a consumption (extra material/class) with optional markup.
    The unit_price and total_val should be ALREADY MARKED UP before calling this 
    IF they come from the UI, but let's ensure we store the markup % for audit.
    """
    try:
        student_id = int(student_id)
        
        with safe_transaction(conn):
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO student_consumptions (student_id, description, quantity, unit_price, total_value, date, status, notes, markup)
                VALUES (?, ?, ?, ?, ?, ?, 'Pendente', ?, ?)
            """, (student_id, description, quantity, unit_price, total_val, date, notes, markup))
            
            new_id = cursor.lastrowid
            audit.log_action(conn, 'CREATE', 'student_consumptions', new_id, None, 
                            {'student_id': student_id, 'desc': description, 'val': total_val, 'markup': markup}, commit=False)
        return new_id
    except Exception as e:
        logger.error(f"Erro ao adicionar consumo para aluno {student_id}: {e}")
        raise

def process_material_consumption(conn, student_id, material_id, quantity, date, user_id=None, notes=None, markup=0.0):
    """
    High-level flow: 
    1. Fetch material info (price, name).
    2. Deduct stock.
    3. Log consumption record with markup applied.
    4. Log inventory transaction.
    """
    student_id = int(student_id)
    material_id = int(material_id)
    cursor = conn.cursor()
    
    # 1. Fetch Material
    mat = pd.read_sql("SELECT name, price_per_unit, stock_level FROM materials WHERE id=?", conn, params=(material_id,)).iloc[0]
    base_price = mat['price_per_unit']
    
    # Calculate Marked-up price (Markup 50 = 50% more)
    unit_price = base_price * (1 + (markup / 100.0))
    total_val = unit_price * quantity
    desc = f"Consumo: {mat['name']}"
    
    try:
        with safe_transaction(conn):
            # 2. Deduct Stock
            new_stock = mat['stock_level'] - quantity
            cursor.execute("UPDATE materials SET stock_level=? WHERE id=?", (new_stock, material_id))
            
            # 3. Log Consumption
            cursor.execute("""
                INSERT INTO student_consumptions (student_id, description, quantity, unit_price, total_value, date, status, notes, markup, material_id)
                VALUES (?, ?, ?, ?, ?, ?, 'Pendente', ?, ?, ?)
            """, (student_id, desc, quantity, unit_price, total_val, date, notes, markup, material_id))
            cons_id = cursor.lastrowid
            
            # 4. Inventory Log (We log the base cost for inventory purposes? Or the total val?)
            # Usually inventory SAIDA is at cost. But for student revenue tracking, we use the sale price.
            # Let's log at base cost for inventory and noted as student consumption.
            base_total = base_price * quantity
            cursor.execute("""
                INSERT INTO inventory_transactions (material_id, date, type, quantity, cost, notes, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (material_id, datetime.now().isoformat(), 'SAIDA', quantity, base_total, f"Aluno ID {student_id} (Markup: {markup}%)", user_id))
            
            # Audit
            audit.log_action(conn, 'CONSUME_MAT', 'student_consumptions', cons_id, None, 
                            {'mat_id': material_id, 'qty': quantity}, commit=False)
        
        return cons_id
    except Exception as e:
        logger.error(f"Erro ao processar consumo de material para aluno {student_id}: {e}")
        raise


# --- Financials ---

def get_student_financial_summary(conn, student_id, month_year_filter=None):
    """
    Returns tuple: (tuitions_df, consumptions_df, total_due)
    """
    # 1. Tuitions (Pending)
    tuitions = get_student_tuitions(conn, int(student_id), status='Pendente', month_year=month_year_filter)
    
    # 2. Consumptions (Pending)
    # Note: month_year_filter is currently not applied to consumptions in the old logic, preserving that.
    consumptions = get_student_consumptions(conn, int(student_id), status='Pendente')
    
    # Calculate Total
    tuitions['amount_paid'] = tuitions['amount_paid'].fillna(0)
    consumptions['amount_paid'] = consumptions['amount_paid'].fillna(0)
    
    total = (tuitions['amount'] - tuitions['amount_paid']).sum() + (consumptions['total_value'] - consumptions['amount_paid']).sum()
    
    return tuitions, consumptions, total

def get_student_payment_history(conn, student_id):
    """
    Returns tuple: (tuitions_df, consumptions_df) of paid items.
    """
    student_id = int(student_id)
    tuitions = pd.read_sql("SELECT * FROM tuitions WHERE student_id=? AND status='Pago' ORDER BY payment_date DESC", conn, params=(student_id,))
    consumptions = pd.read_sql("SELECT * FROM student_consumptions WHERE student_id=? AND status='Pago' ORDER BY payment_date DESC", conn, params=(student_id,))
    return tuitions, consumptions

def get_payment_history(conn, start_date=None, end_date=None, student_id=None, payment_type=None, class_id=None, status_filter='Pago'):
    """
    Returns a combined DataFrame of payments/debits from students with filters.
    """
    t_where_pago = ["t.status = 'Pago'"]
    c_where_pago = ["sc.status = 'Pago'"]
    t_where_pend = ["t.status = 'Pendente'"]
    c_where_pend = ["sc.status = 'Pendente'"]
    
    # We need separate params for each query because they are executed independently
    params_t_pago, params_c_pago = [], []
    params_t_pend, params_c_pend = [], []

    def get_common_filters(date_col, student_id, class_id):
        where = []
        params = []
        if start_date:
            where.append(f"{date_col} >= ?")
            params.append(start_date)
        if end_date:
            where.append(f"{date_col} <= ?")
            params.append(end_date)
        if student_id and student_id != "Todos":
            where.append("s.id = ?")
            params.append(int(student_id))
        if class_id and class_id != "Todas":
            where.append("s.class_id = ?")
            params.append(int(class_id))
        return where, params

    # DATE FALLBACK FOR TUITIONS: 
    # Try created_at, then payment_date, then month_year (mapped to YYYY-MM-01)
    # SQLite logic: SUBSTR(month_year, 4, 4) || '-' || SUBSTR(month_year, 1, 2) || '-01'
    t_date_sql = "COALESCE(t.created_at, t.payment_date, SUBSTR(t.month_year, 4, 4) || '-' || SUBSTR(t.month_year, 1, 2) || '-01')"

    # Build filters and params for each case
    w, p = get_common_filters("t.payment_date", student_id, class_id); t_where_pago += w; params_t_pago = p
    w, p = get_common_filters("sc.payment_date", student_id, class_id); c_where_pago += w; params_c_pago = p
    w, p = get_common_filters(t_date_sql, student_id, class_id); t_where_pend += w; params_t_pend = p
    w, p = get_common_filters("sc.date", student_id, class_id); c_where_pend += w; params_c_pend = p
    
    t_query_pago = f"SELECT t.payment_date as date, t.amount, s.name as student_name, t.student_id, 'Mensalidade ' || t.month_year as description, 'Mensalidade' as cat, 'Recebimento' as movement_type, 'Pago' as status, t.class_count, t.class_dates, c.name as class_name FROM tuitions t JOIN students s ON t.student_id = s.id LEFT JOIN classes c ON s.class_id = c.id WHERE {' AND '.join(t_where_pago)}"
    c_query_pago = f"SELECT sc.payment_date as date, sc.total_value as amount, s.name as student_name, sc.student_id, sc.description, 'Consumo' as cat, 'Recebimento' as movement_type, 'Pago' as status, NULL as class_count, NULL as class_dates, NULL as class_name FROM student_consumptions sc JOIN students s ON sc.student_id = s.id WHERE {' AND '.join(c_where_pago)}"
    t_query_pend = f"SELECT {t_date_sql} as date, t.amount, s.name as student_name, t.student_id, 'Mensalidade ' || t.month_year as description, 'Mensalidade' as cat, 'Lançamento de Débito' as movement_type, 'Pendente' as status, t.class_count, t.class_dates, c.name as class_name FROM tuitions t JOIN students s ON t.student_id = s.id LEFT JOIN classes c ON s.class_id = c.id WHERE {' AND '.join(t_where_pend)}"
    c_query_pend = f"SELECT sc.date as date, sc.total_value as amount, s.name as student_name, sc.student_id, sc.description, 'Consumo' as cat, 'Lançamento de Débito' as movement_type, 'Pendente' as status, NULL as class_dates, NULL as class_name FROM student_consumptions sc JOIN students s ON sc.student_id = s.id WHERE {' AND '.join(c_where_pend)}"
    
    dfs = []
    if status_filter in ['Todos', 'Pago']:
        if payment_type in [None, 'Todos', 'Mensalidade']:
            dfs.append(pd.read_sql(t_query_pago, conn, params=params_t_pago))
        if payment_type in [None, 'Todos', 'Consumo']:
            dfs.append(pd.read_sql(c_query_pago, conn, params=params_c_pago))

    if status_filter in ['Todos', 'Pendente']:
        if payment_type in [None, 'Todos', 'Mensalidade']:
            dfs.append(pd.read_sql(t_query_pend, conn, params=params_t_pend))
        if payment_type in [None, 'Todos', 'Consumo']:
            dfs.append(pd.read_sql(c_query_pend, conn, params=params_c_pend))
            
    if not dfs:
        return pd.DataFrame()
        
    combined = pd.concat(dfs, ignore_index=True)
    if not combined.empty:
        # Sort and ensure date format
        combined['date'] = pd.to_datetime(combined['date'], errors='coerce')
        combined = combined.sort_values(['date', 'movement_type'], ascending=[False, False])
    
    return combined



def confirm_payment_all_pending(conn, student_id):
    """Marks all pending items as Paid for a student."""
    try:
        student_id = int(student_id)
        
        with safe_transaction(conn):
            cursor = conn.cursor()
            now_str = datetime.now().strftime('%Y-%m-%d')
            
            # Tuitions
            cursor.execute("UPDATE tuitions SET status='Pago', payment_date=? WHERE student_id=? AND status='Pendente'", (now_str, student_id))
            
            # Consumptions
            cursor.execute("UPDATE student_consumptions SET status='Pago', payment_date=? WHERE student_id=? AND status='Pendente'", (now_str, student_id))
            
            audit.log_action(conn, 'PAYMENT', 'finance', student_id, None, {'type': 'ALL_PENDING'}, commit=False)
    except Exception as e:
        logger.error(f"Erro ao confirmar pagamento total para aluno {student_id}: {e}")
        raise

def process_partial_payment(conn, student_id, payment_amount):
    """
    Allocates a payment amount to the oldest pending debts first.
    """
    try:
        student_id = int(student_id)
        cursor = conn.cursor()
        
        # 1. Fetch all pending debts
        tuitions = pd.read_sql("SELECT id, amount, amount_paid, month_year as date, 'tuition' as type FROM tuitions WHERE student_id=? AND status='Pendente'", conn, params=(student_id,))
        consumptions = pd.read_sql("SELECT id, total_value as amount, amount_paid, date, 'consumption' as type FROM student_consumptions WHERE student_id=? AND status='Pendente'", conn, params=(student_id,))
        
        # Combine
        pending = pd.concat([tuitions, consumptions])
        if pending.empty:
            return True, "Nenhuma dívida pendente encontrada."
            
        # Add 'due' column and handle NaNs in amount_paid
        pending['amount_paid'] = pending['amount_paid'].fillna(0.0)
        pending['due'] = pending['amount'] - pending['amount_paid']
        
        # Sort by date (oldest first). For month_year, we might need a better sort, but simple string sort works for same year.
        pending = pending.sort_values('date')
        
        remaining_payment = float(payment_amount)
        items_paid = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with safe_transaction(conn):
            for _, item in pending.iterrows():
                if remaining_payment <= 0.009:
                    break
                    
                pay_this_item = min(remaining_payment, item['due'])
                
                if item['type'] == 'tuition':
                    cursor.execute("UPDATE tuitions SET amount_paid = COALESCE(amount_paid, 0) + ? WHERE id=?", (pay_this_item, item['id']))
                    if abs((item['amount_paid'] + pay_this_item) - item['amount']) < 0.01:
                        cursor.execute("UPDATE tuitions SET status='Pago', payment_date=? WHERE id=?", (now_str, item['id']))
                else:
                    cursor.execute("UPDATE student_consumptions SET amount_paid = COALESCE(amount_paid, 0) + ? WHERE id=?", (pay_this_item, item['id']))
                    if abs((item['amount_paid'] + pay_this_item) - item['amount']) < 0.01:
                        cursor.execute("UPDATE student_consumptions SET status='Pago', payment_date=? WHERE id=?", (now_str, item['id']))
                
                remaining_payment -= pay_this_item
                items_paid.append(f"{item['type']} {item['id']} ({pay_this_item:.2f})")
                
            audit.log_action(conn, 'PARTIAL_PAYMENT', 'finance', student_id, None, {'amount': payment_amount, 'items': items_paid}, commit=False)
        
        return True, f"Pagamento registrado! {len(items_paid)} itens afetados."
    except Exception as e:
        logger.error(f"Erro ao processar pagamento parcial para aluno {student_id}: {e}")
        raise

def cancel_consumption(conn, consumption_id):
    """Cancels a consumption and restores stock if it was a material."""
    consumption_id = int(consumption_id)
    cursor = conn.cursor()
    # Get record
    res = cursor.execute("SELECT material_id, quantity, student_id, total_value, status FROM student_consumptions WHERE id=?", (consumption_id,)).fetchone()
    if not res: return False, "Registro não encontrado."
    mat_id, qty, sid, val, status = res
    
    if status == 'Cancelado': return False, "Já está cancelado."

    try:
        with safe_transaction(conn):
            # Restore stock if material
            if mat_id and qty:
                cursor.execute("UPDATE materials SET stock_level = stock_level + ? WHERE id=?", (qty, mat_id))
                # Log restoration in inventory transactions
                cursor.execute("""
                    INSERT INTO inventory_transactions (material_id, date, type, quantity, cost, notes)
                    VALUES (?, ?, ?, ?, 0, ?)
                """, (mat_id, datetime.now().isoformat(), 'ENTRADA', qty, f"Estorno Cancelamento Aluno ID {sid}"))

            # Update status
            cursor.execute("UPDATE student_consumptions SET status='Cancelado' WHERE id=?", (consumption_id,))
            
            audit.log_action(conn, 'CANCEL_CONSUMPTION', 'student_consumptions', consumption_id, {'old_status': status}, {'new_status': 'Cancelado'}, commit=False)
    except Exception as e:
        logger.error(f"Erro ao cancelar consumo {consumption_id}: {e}")
        raise
    return True, "Cancelado com sucesso."

def cancel_tuition(conn, tuition_id):
    """Cancels a tuition record."""
    tuition_id = int(tuition_id)
    cursor = conn.cursor()
    res = cursor.execute("SELECT status FROM tuitions WHERE id=?", (tuition_id,)).fetchone()
    if not res: return False, "Registro não encontrado."
    status = res[0]
    
    if status == 'Cancelado': return False, "Já está cancelado."
    
    try:
        with safe_transaction(conn):
            cursor.execute("UPDATE tuitions SET status='Cancelado' WHERE id=?", (tuition_id,))
            audit.log_action(conn, 'CANCEL_TUITION', 'tuitions', tuition_id, {'old_status': status}, {'new_status': 'Cancelado'}, commit=False)
    except Exception as e:
        logger.error(f"Erro ao cancelar mensalidade {tuition_id}: {e}")
        raise
    return True, "Cancelado com sucesso."

def update_tuition(conn, tuition_id, amount):
    """Updates tuition amount."""
    tuition_id = int(tuition_id)
    cursor = conn.cursor()
    old = pd.read_sql("SELECT amount FROM tuitions WHERE id=?", conn, params=(tuition_id,)).iloc[0].to_dict()
    try:
        with safe_transaction(conn):
            cursor.execute("UPDATE tuitions SET amount=? WHERE id=?", (amount, tuition_id))
            audit.log_action(conn, 'UPDATE', 'tuitions', tuition_id, old, {'amount': amount}, commit=False)
    except Exception as e:
        logger.error(f"Erro ao atualizar mensalidade {tuition_id}: {e}")
        raise
    return True

def update_consumption(conn, consumption_id, description, total_value):
    """Updates consumption description or value."""
    # Note: Quantity/Unit Price changes are complex for materials due to stock. 
    # For now, we allow description and total value adjustments.
    consumption_id = int(consumption_id)
    cursor = conn.cursor()
    old = pd.read_sql("SELECT description, total_value FROM student_consumptions WHERE id=?", conn, params=(consumption_id,)).iloc[0].to_dict()
    try:
        with safe_transaction(conn):
            cursor.execute("UPDATE student_consumptions SET description=?, total_value=? WHERE id=?", (description, total_value, consumption_id))
            audit.log_action(conn, 'UPDATE', 'student_consumptions', consumption_id, old, {'description': description, 'total_value': total_value}, commit=False)
    except Exception as e:
        logger.error(f"Erro ao atualizar consumo {consumption_id}: {e}")
        raise
    return True

def get_module_summary_stats(conn):
    """
    Returns dictionary with summary statistics for the module.
    - total_students
    - total_pending_revenue (Tuition + Consumption)
    - total_paid_revenue_current_month (Tuition + Consumption)
    """
    stats = {}
    
    # 1. Total Active Students
    stats['total_students'] = pd.read_sql("SELECT count(*) as c FROM students WHERE active=1", conn).iloc[0]['c']
    
    # 2. Revenue Pending (All time)
    t_pend = pd.read_sql("SELECT sum(amount) as s FROM tuitions WHERE status='Pendente'", conn).iloc[0]['s'] or 0
    c_pend = pd.read_sql("SELECT sum(total_value) as s FROM student_consumptions WHERE status='Pendente'", conn).iloc[0]['s'] or 0
    stats['pending_revenue'] = t_pend + c_pend
    
    # 3. Revenue Paid (Current Month)
    today = datetime.now().strftime('%Y-%m')
    # Filter by payment_date roughly or by month_year for tuitions? 
    # payment_date is better if it exists. We set it in confirm_payment_all_pending.
    # Note: payment_date stores YYYY-MM-DD
    
    # Tuitions Paid this month
    t_paid = pd.read_sql("SELECT sum(amount) as s FROM tuitions WHERE status='Pago' AND payment_date LIKE ?", conn, params=(f"{today}%",)).iloc[0]['s'] or 0
    
    # Consumption Paid this month (We need to ensure consumption query filters by something relevant, 
    # but schema didn't enforce payment_date on consumption update. 
    # In confirm_payment_all_pending we didn't set payment_date for consumption, let's fix that assumption or just query status.
    # Wait, consumption table has 'date', but that's consumption date. The payment date is not strictly in schema.
    # Let's use 'date' for approximation if payment_date missing, OR just rely on what we have.
    # Actually, let's check if we can add payment_date tracking, but for now purely 'Pago' status might be too broad.
    # Let's just return Total Paid (All Time) for simplicity or try to match month.
    # Let's stick to Total Pending vs Total Paid (All Time) for the summary to be robust.
    
    t_paid_all = pd.read_sql("SELECT sum(amount) as s FROM tuitions WHERE status='Pago'", conn).iloc[0]['s'] or 0
    c_paid_all = pd.read_sql("SELECT sum(total_value) as s FROM student_consumptions WHERE status='Pago'", conn).iloc[0]['s'] or 0
    stats['total_revenue_paid'] = t_paid_all + c_paid_all
    
    return stats

def get_debts_summary(conn):
    """Returns a DataFrame of students with total pending balance > 0, showing the oldest month of debt."""
    query = """
        SELECT id, name, total_due, oldest_month as months FROM (
            SELECT s.id, s.name, 
                   COALESCE((SELECT SUM(amount - COALESCE(amount_paid, 0)) FROM tuitions WHERE student_id = s.id AND status = 'Pendente'), 0) +
                   COALESCE((SELECT SUM(total_value - COALESCE(amount_paid, 0)) FROM student_consumptions WHERE student_id = s.id AND status = 'Pendente'), 0) as total_due,
                   COALESCE(
                       (SELECT strftime('%m/%Y', MIN(d)) FROM (
                           SELECT SUBSTR(month_year, 4, 4) || '-' || SUBSTR(month_year, 1, 2) || '-01' as d FROM tuitions WHERE student_id = s.id AND status = 'Pendente'
                           UNION ALL
                           SELECT date as d FROM student_consumptions WHERE student_id = s.id AND status = 'Pendente'
                       )), 
                       '---'
                   ) as oldest_month
            FROM students s
            WHERE s.active = 1
        ) WHERE total_due > 0
        ORDER BY total_due DESC
    """
    return pd.read_sql(query, conn)

def get_student_tuitions(conn, student_id, status=None, month_year=None):
    """
    Get tuitions for a student.
    status: 'Pendente', 'Pago', 'Cancelado' (optional)
    month_year: 'MM/YYYY' (optional)
    """
    query = """
        SELECT t.*, c.name as class_name 
        FROM tuitions t 
        LEFT JOIN students s ON t.student_id = s.id 
        LEFT JOIN classes c ON s.class_id = c.id 
        WHERE t.student_id=?
    """
    params = [student_id]
    
    if status:
        query += " AND t.status=?"
        params.append(status)
        
    if month_year:
        query += " AND t.month_year=?"
        params.append(month_year)
        
    query += " ORDER BY substr(t.month_year, 4, 4) || substr(t.month_year, 1, 2) DESC" # Order by date desc
    
    return pd.read_sql(query, conn, params=params)

def get_student_consumptions(conn, student_id, status=None):
    """
    Get consumptions for a student.
    status: 'Pendente', 'Pago', 'Cancelado' (optional)
    """
    query = "SELECT * FROM student_consumptions WHERE student_id=?"
    params = [student_id]
    
    if status:
        query += " AND status=?"
        params.append(status)
        
    query += " ORDER BY date DESC"
    return pd.read_sql(query, conn, params=params)

def calculate_class_monthly_metrics(conn, class_id, month_year_str):
    """
    Calculates metrics for a class in a given month.
    Returns dict with keys: total_days, canc_count, net_days, estimated_tuition
    """
    try:
        # Get Class Info
        # Ensure native int for sqlite
        c_row = pd.read_sql("SELECT * FROM classes WHERE id=?", conn, params=(int(class_id),)).iloc[0]
        if pd.isnull(c_row['weekday']):
            return None
            
        wd = int(c_row['weekday'])
        m, y = map(int, month_year_str.split('/'))
        
        # Count Days
        cal = calendar.monthcalendar(y, m)
        valid_dates = []
        for week in cal:
            if week[wd] != 0: valid_dates.append(f"{y:04d}-{m:02d}-{week[wd]:02d}")
        total_days = len(valid_dates)
        
        # Cancellations
        cancs = get_class_cancellations(conn, class_id)
        canc_count = 0
        if not cancs.empty:
            canc_dates = cancs['date'].tolist()
            for d in valid_dates:
                if d in canc_dates: canc_count += 1
        
        net = max(0, total_days - canc_count)
        val_global = get_global_price_per_class(conn)
        estimated_tuition = net * val_global
        
        return {
            "total_days": total_days,
            "canc_count": canc_count,
            "net_days": net,
            "estimated_tuition": float(estimated_tuition),
            "weekday_idx": wd
        }
    except Exception as e:
        logger.error(f"Error calculating metrics for class {class_id}: {e}")
        return None

def get_student_statement_items(conn, student_id):
    """
    Generates the list of financial items (Tuitions + Consumptions) and Cancellations
    formatted for the PDF report.
    Returns: (items_list, cancellations_list, total_due, class_name)
    """
    # 1. Fetch Data
    tuit, cons, total = get_student_financial_summary(conn, student_id)
    
    items = []
    involved_months = set()
    st_class_name = "---"
    
    # 2. Process Tuitions
    for _, t in tuit.iterrows():
        if t.get('class_name'): st_class_name = t['class_name']
        
        desc = f"Mensalidade {t['month_year']}"
        if 'class_count' in t and pd.notnull(t['class_count']):
            try: desc += f" ({int(t['class_count'])} aulas)"
            except: pass
        
        paid = t.get('amount_paid', 0) or 0
        items.append({
            "date": t['month_year'], 
            "description": desc, 
            "quantity": 1, 
            "value": float(t['amount']), 
            "paid": float(paid), 
            "status": t['status'],
            "class_dates": t.get('class_dates')
        })
        involved_months.add(t['month_year'])
        
    # 3. Process Consumptions
    for _, c in cons.iterrows():
        desc = c['description']
        if c.get('notes'): desc += f" ({c['notes']})"
        paid = c.get('amount_paid', 0) or 0
        items.append({
            "date": c['date'], 
            "description": desc, 
            "quantity": c['quantity'], 
            "value": float(c['total_value']), 
            "paid": float(paid), 
            "status": c['status']
        })

    # 4. Process Cancellations
    cancellations = []
    if involved_months:
        try:
            s_row = pd.read_sql("SELECT class_id FROM students WHERE id=?", conn, params=(int(student_id),))
            if not s_row.empty and s_row.iloc[0]['class_id']:
                cid = s_row.iloc[0]['class_id']
                all_cancs = get_class_cancellations(conn, cid)
                if not all_cancs.empty:
                    all_cancs['mm_yyyy'] = pd.to_datetime(all_cancs['date']).dt.strftime('%m/%Y')
                    filtered = all_cancs[all_cancs['mm_yyyy'].isin(involved_months)]
                    
                    for _, cr in filtered.iterrows():
                        cancellations.append({
                            'date': cr['date'],
                            'reason': cr['reason']
                        })
        except Exception as e:
            logger.error(f"Error fetching cancellations for statement: {e}")
            
    return items, cancellations, total, st_class_name


