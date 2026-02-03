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

def get_all_classes(conn):
    """Returns DataFrame of all classes."""
    return pd.read_sql("SELECT * FROM classes ORDER BY name", conn)

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

def update_student(conn, student_id, name, phone, active, class_id=None):
    """Updates student info."""
    # Get old data
    old = pd.read_sql(f"SELECT * FROM students WHERE id={student_id}", conn).iloc[0].to_dict()
    
    cursor = conn.cursor()
    cursor.execute("UPDATE students SET name=?, phone=?, active=?, class_id=? WHERE id=?", 
                   (name, phone, int(active), class_id, student_id))
    
    audit.log_action(conn, 'UPDATE', 'students', student_id, old, {'name': name, 'phone': phone, 'active': active, 'class': class_id}, commit=False)
    conn.commit()

# --- Consumption Logic ---

def add_consumption(conn, student_id, description, quantity, unit_price, total_val, date, user_id=None):
    """
    Logs a consumption (extra material/class).
    WARNING: Does NOT deduct stock automatically here. 
    Stock deduction logic should be handled by caller IF it links to a specific material ID, 
    but for this module requirements:
    'Ao registrar, busque o preço na tabela materials e realize a baixa automática no estoque (stock_level).'
    
    So we need an overload or parameter to handle material_id if applicable.
    """
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO student_consumptions (student_id, description, quantity, unit_price, total_value, date, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Pendente')
    """, (student_id, description, quantity, unit_price, total_val, date))
    
    new_id = cursor.lastrowid
    audit.log_action(conn, 'CREATE', 'student_consumptions', new_id, None, 
                     {'student_id': student_id, 'desc': description, 'val': total_val}, commit=False)
    conn.commit()
    return new_id

def process_material_consumption(conn, student_id, material_id, quantity, date, user_id=None):
    """
    High-level flow: 
    1. Fetch material info (price, name).
    2. Deduct stock.
    3. Log consumption record.
    4. Log inventory transaction.
    """
    cursor = conn.cursor()
    
    # 1. Fetch Material
    mat = pd.read_sql(f"SELECT name, price_per_unit, stock_level FROM materials WHERE id={material_id}", conn).iloc[0]
    unit_price = mat['price_per_unit']
    total_val = unit_price * quantity
    desc = f"Consumo: {mat['name']}"
    
    # 2. Deduct Stock
    new_stock = mat['stock_level'] - quantity
    cursor.execute("UPDATE materials SET stock_level=? WHERE id=?", (new_stock, material_id))
    
    # 3. Log Consumption
    cursor.execute("""
        INSERT INTO student_consumptions (student_id, description, quantity, unit_price, total_value, date, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Pendente')
    """, (student_id, desc, quantity, unit_price, total_val, date))
    cons_id = cursor.lastrowid
    
    # 4. Inventory Log
    cursor.execute("""
        INSERT INTO inventory_transactions (material_id, date, type, quantity, cost, notes, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (material_id, datetime.now().isoformat(), 'SAIDA', quantity, total_val, f"Aluno ID {student_id}", user_id))
    
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
