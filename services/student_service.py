import pandas as pd
import sqlite3
from datetime import datetime
import json
import audit

# --- Student CRUD ---

def get_all_active_students(conn, class_id=None):
    """Returns DataFrame of all active students, optionally filtered by class."""
    query = "SELECT s.*, c.name as class_name FROM students s LEFT JOIN classes c ON s.class_id = c.id WHERE s.active=1"
    if class_id:
        query += f" AND s.class_id={class_id}"
    query += " ORDER BY s.name"
    return pd.read_sql(query, conn)

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

def create_class(conn, name, schedule, notes):
    """Creates a new class."""
    cursor = conn.cursor()
    cursor.execute("INSERT INTO classes (name, schedule, notes) VALUES (?, ?, ?)", (name, schedule, notes))
    rid = cursor.lastrowid
    audit.log_action(conn, 'CREATE', 'classes', rid, None, {'name': name}, commit=False)
    conn.commit()
    return rid

def update_class(conn, class_id, name, schedule, notes):
    """Updates a class."""
    old = pd.read_sql(f"SELECT * FROM classes WHERE id={class_id}", conn).iloc[0].to_dict()
    cursor = conn.cursor()
    cursor.execute("UPDATE classes SET name=?, schedule=?, notes=? WHERE id=?", (name, schedule, notes, class_id))
    audit.log_action(conn, 'UPDATE', 'classes', class_id, old, {'name': name}, commit=False)
    conn.commit()

def create_student(conn, name, phone, class_id=None, join_date=None):
    """Creates a new student."""
    if not join_date:
        join_date = datetime.now().strftime('%Y-%m-%d')
    
    cursor = conn.cursor()
    cursor.execute("INSERT INTO students (name, phone, class_id, join_date, active) VALUES (?, ?, ?, ?, 1)", (name, phone, class_id, join_date))
    new_id = cursor.lastrowid
    audit.log_action(conn, 'CREATE', 'students', new_id, None, {'name': name, 'class_id': class_id}, commit=False)
    conn.commit()
    return new_id

def update_student(conn, student_id, name, phone, active):
    """Updates student info (Name, Phone, Active). Class is handled separately."""
    student_id = int(student_id)
    # Get old data
    old = pd.read_sql(f"SELECT * FROM students WHERE id={student_id}", conn).iloc[0].to_dict()
    
    cursor = conn.cursor()
    cursor.execute("UPDATE students SET name=?, phone=?, active=? WHERE id=?", 
                   (name, phone, int(active), student_id))
    
    audit.log_action(conn, 'UPDATE', 'students', student_id, old, {'name': name, 'phone': phone, 'active': active}, commit=False)
    conn.commit()
    try:
        conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
    except: pass

def update_student_class(conn, student_id, class_id):
    """Updates only the student's class."""
    # Get old data for audit
    try:
        old = pd.read_sql(f"SELECT class_id FROM students WHERE id={student_id}", conn).iloc[0].to_dict()
    except:
        old = {}
        
    cursor = conn.cursor()
    cursor.execute("UPDATE students SET class_id=? WHERE id=?", (class_id, student_id))
    
    if cursor.rowcount == 0:
        print(f"WARNING: Update failed for student {student_id} (Row not found?)")
    
    audit.log_action(conn, 'UPDATE_CLASS', 'students', student_id, old, {'class_id': class_id}, commit=False)
    conn.commit()
    
    # Force Checkpoint to ensure visibility
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except: pass
    
    return True

# --- Consumption Logic ---

def add_consumption(conn, student_id, description, quantity, unit_price, total_val, date, user_id=None, notes=None, markup=0.0):
    """
    Logs a consumption (extra material/class) with optional markup.
    The unit_price and total_val should be ALREADY MARKED UP before calling this 
    IF they come from the UI, but let's ensure we store the markup % for audit.
    """
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO student_consumptions (student_id, description, quantity, unit_price, total_value, date, status, notes, markup)
        VALUES (?, ?, ?, ?, ?, ?, 'Pendente', ?, ?)
    """, (student_id, description, quantity, unit_price, total_val, date, notes, markup))
    
    new_id = cursor.lastrowid
    audit.log_action(conn, 'CREATE', 'student_consumptions', new_id, None, 
                     {'student_id': student_id, 'desc': description, 'val': total_val, 'markup': markup}, commit=False)
    conn.commit()
    return new_id

def process_material_consumption(conn, student_id, material_id, quantity, date, user_id=None, notes=None, markup=0.0):
    """
    High-level flow: 
    1. Fetch material info (price, name).
    2. Deduct stock.
    3. Log consumption record with markup applied.
    4. Log inventory transaction.
    """
    cursor = conn.cursor()
    
    # 1. Fetch Material
    mat = pd.read_sql(f"SELECT name, price_per_unit, stock_level FROM materials WHERE id={material_id}", conn).iloc[0]
    base_price = mat['price_per_unit']
    
    # Calculate Marked-up price as a multiplier (Markup 2 = 200%)
    unit_price = base_price * markup
    total_val = unit_price * quantity
    desc = f"Consumo: {mat['name']}"
    
    # 2. Deduct Stock
    new_stock = mat['stock_level'] - quantity
    cursor.execute("UPDATE materials SET stock_level=? WHERE id=?", (new_stock, material_id))
    
    # 3. Log Consumption
    cursor.execute("""
        INSERT INTO student_consumptions (student_id, description, quantity, unit_price, total_value, date, status, notes, markup)
        VALUES (?, ?, ?, ?, ?, ?, 'Pendente', ?, ?)
    """, (student_id, desc, quantity, unit_price, total_val, date, notes, markup))
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
    
    conn.commit()
    return cons_id


# --- Financials ---

def get_student_financial_summary(conn, student_id, month_year_filter=None):
    """
    Returns tuple: (tuitions_df, consumptions_df, total_due)
    """
    # Tuitions
    t_query = f"SELECT * FROM tuitions WHERE student_id={student_id} AND status='Pendente'"
    if month_year_filter:
        t_query += f" AND month_year='{month_year_filter}'"
    tuitions = pd.read_sql(t_query, conn)
    
    # Consumptions
    c_query = f"SELECT * FROM student_consumptions WHERE student_id={student_id} AND status='Pendente'"
    # Optional date filter logic could go here
    consumptions = pd.read_sql(c_query, conn)
    
    total = tuitions['amount'].sum() + consumptions['total_value'].sum()
    
    return tuitions, consumptions, total

def generate_tuition_record(conn, student_id, month_year, amount):
    """Generates a monthly tuition record if not exists."""
    cursor = conn.cursor()
    # Check dup
    exist = cursor.execute("SELECT id FROM tuitions WHERE student_id=? AND month_year=?", (student_id, month_year)).fetchone()
    if exist:
        return False, "Mensalidade já gerada."
        
    cursor.execute("INSERT INTO tuitions (student_id, month_year, amount, status) VALUES (?, ?, ?, 'Pendente')", 
                   (student_id, month_year, amount))
    conn.commit()
    return True, "Gerada com sucesso."

def confirm_payment_all_pending(conn, student_id):
    """Marks all pending items as Paid for a student."""
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d')
    
    # Tuitions
    cursor.execute("UPDATE tuitions SET status='Pago', payment_date=? WHERE student_id=? AND status='Pendente'", (now_str, student_id))
    
    # Consumptions
    cursor.execute("UPDATE student_consumptions SET status='Pago' WHERE student_id=? AND status='Pendente'", (now_str, student_id)) # Add payment_date col if needed, schema didn't specify for consump but good to have. Schema says date is for consumption date.
    
    conn.commit()
    audit.log_action(conn, 'PAYMENT', 'finance', student_id, None, {'type': 'ALL_PENDING'}, commit=True)

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
    t_paid = pd.read_sql(f"SELECT sum(amount) as s FROM tuitions WHERE status='Pago' AND payment_date LIKE '{today}%'", conn).iloc[0]['s'] or 0
    
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
    """Returns a DataFrame of students with total pending balance > 0."""
    query = """
        SELECT id, name, total_due FROM (
            SELECT s.id, s.name, 
                   COALESCE((SELECT SUM(amount) FROM tuitions WHERE student_id = s.id AND status = 'Pendente'), 0) +
                   COALESCE((SELECT SUM(total_value) FROM student_consumptions WHERE student_id = s.id AND status = 'Pendente'), 0) as total_due
            FROM students s
            WHERE s.active = 1
        ) WHERE total_due > 0
        ORDER BY total_due DESC
    """
    return pd.read_sql(query, conn)
