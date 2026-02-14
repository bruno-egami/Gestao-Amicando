import pandas as pd
import sqlite3
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
import calendar

# Configure logger
logger = logging.getLogger(__name__)

# --- EXPENSE CATEGORIES ---

def get_expense_categories(conn: sqlite3.Connection) -> List[str]:
    """Fetches all expense category names."""
    df = pd.read_sql("SELECT name FROM expense_categories ORDER BY name", conn)
    return df['name'].tolist()

def create_expense_category(conn: sqlite3.Connection, name: str) -> None:
    """Creates a new expense category."""
    cursor = conn.cursor()
    cursor.execute("INSERT INTO expense_categories (name) VALUES (?)", (name,))
    conn.commit()

def delete_expense_category(conn: sqlite3.Connection, name: str) -> None:
    """Deletes an expense category by name."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expense_categories WHERE name=?", (name,))
    conn.commit()

# --- EXPENSES ---

def get_expenses(conn: sqlite3.Connection, filters: Dict[str, Any] = None) -> pd.DataFrame:
    """
    Fetches expenses based on filters.
    filters: 
        'category': str
        'start_date': date
        'end_date': date
        'supplier_name': str
        'search_term': str (for description/supplier)
    """
    query = """
        SELECT e.id, e.date, e.description, e.amount, e.category, s.name as supplier_name, e.supplier_id, e.linked_material_id
        FROM expenses e
        LEFT JOIN suppliers s ON e.supplier_id = s.id
        WHERE 1=1
    """
    params = []
    
    if filters:
        if filters.get('category') and filters['category'] != "Todas":
            query += " AND e.category = ?"
            params.append(filters['category'])
            
        if filters.get('start_date') and filters.get('end_date'):
            query += " AND e.date BETWEEN ? AND ?"
            params.append(filters['start_date'])
            params.append(filters['end_date'])
            
        if filters.get('supplier_name') and filters['supplier_name'] != "Todos":
            query += " AND s.name = ?"
            params.append(filters['supplier_name'])
            
    query += " ORDER BY e.date DESC"
    
    df = pd.read_sql(query, conn, params=params)
    
    # In-memory search for flexibility
    if filters and filters.get('search_term') and not df.empty:
        term = filters['search_term'].lower()
        mask = df.apply(lambda row: term in str(row['description']).lower() or 
                                    term in str(row['supplier_name']).lower(), axis=1)
        df = df[mask]
        
    return df

def get_expense_by_id(conn: sqlite3.Connection, expense_id: int) -> Dict[str, Any]:
    """Fetches a single expense by ID."""
    df = pd.read_sql("SELECT * FROM expenses WHERE id=?", conn, params=(expense_id,))
    return df.iloc[0].to_dict() if not df.empty else {}

def create_expense(conn: sqlite3.Connection, date_obj: date, description: str, amount: float, category: str, 
                  supplier_id: Optional[int], linked_material_id: Optional[int] = None, 
                  qty_bought: float = 0.0) -> int:
    """Creates a new expense and optionally updates material stock."""
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO expenses (date, description, amount, category, supplier_id, linked_material_id) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (date_obj, description, amount, category, supplier_id, linked_material_id))
        
        new_id = cursor.lastrowid
        
        # Simple Stock Update Logic (mirrors original UI logic)
        if linked_material_id and qty_bought > 0:
            cursor.execute("UPDATE materials SET stock_level = stock_level + ? WHERE id = ?", (qty_bought, linked_material_id))
            
        conn.commit()
        return new_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao criar despesa '{description}': {e}")
        raise

def update_expense(conn: sqlite3.Connection, expense_id: int, date_obj: date, description: str, 
                  amount: float, category: str, supplier_id: Optional[int]) -> Dict[str, Any]:
    """Updates an existing expense and returns the old data for audit."""
    # Get old data first
    old_data = get_expense_by_id(conn, expense_id)
    
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE expenses 
        SET date=?, description=?, amount=?, category=?, supplier_id=? 
        WHERE id=?
    """, (date_obj, description, amount, category, supplier_id, expense_id))
    conn.commit()
    return old_data

def delete_expense(conn: sqlite3.Connection, expense_id: int) -> Dict[str, Any]:
    """Deletes an expense and returns the deleted data for audit."""
    old_data = get_expense_by_id(conn, expense_id)
    
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    return old_data

# --- FIXED COSTS ---

def get_fixed_costs(conn: sqlite3.Connection, filters: Dict[str, Any] = None) -> pd.DataFrame:
    """Fetches fixed cost definitions."""
    query = "SELECT * FROM fixed_costs WHERE 1=1"
    params = []
    
    if filters:
        if filters.get('category') and filters['category'] != "Todas":
            query += " AND category = ?"
            params.append(filters['category'])
        if filters.get('periodicity') and filters['periodicity'] != "Todas":
            query += " AND periodicity = ?"
            params.append(filters['periodicity'])
            
    query += " ORDER BY due_day"
    return pd.read_sql(query, conn, params=params)

def get_fixed_cost_by_id(conn: sqlite3.Connection, fc_id: int) -> Dict[str, Any]:
    df = pd.read_sql("SELECT * FROM fixed_costs WHERE id=?", conn, params=(fc_id,))
    return df.iloc[0].to_dict() if not df.empty else {}

def create_fixed_cost(conn: sqlite3.Connection, description: str, value: float, due_day: int, 
                     periodicity: str, category: str) -> int:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO fixed_costs (description, value, due_day, periodicity, category) 
        VALUES (?, ?, ?, ?, ?)
    """, (description, value, due_day, periodicity, category))
    conn.commit()
    return cursor.lastrowid

def update_fixed_cost(conn: sqlite3.Connection, fc_id: int, description: str, value: float, 
                     due_day: int, periodicity: str, category: str) -> Dict[str, Any]:
    old_data = get_fixed_cost_by_id(conn, fc_id)
    
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE fixed_costs 
        SET description=?, value=?, due_day=?, periodicity=?, category=? 
        WHERE id=?
    """, (description, value, due_day, periodicity, category, fc_id))
    conn.commit()
    return old_data

def delete_fixed_cost(conn: sqlite3.Connection, fc_id: int) -> Dict[str, Any]:
    old_data = get_fixed_cost_by_id(conn, fc_id)
    
    cursor = conn.cursor()
    cursor.execute("DELETE FROM fixed_costs WHERE id=?", (fc_id,))
    conn.commit()
    return old_data

def auto_process_monthly_fixed_costs(conn: sqlite3.Connection) -> int:
    """
    Checks and inserts pending fixed costs for the current month.
    Returns the number of created expenses.
    """
    today = date.today()
    curr_m = today.month
    curr_y = today.year
    
    start_m_date = date(curr_y, curr_m, 1)
    if curr_m == 12: end_m_date = date(curr_y + 1, 1, 1)
    else: end_m_date = date(curr_y, curr_m + 1, 1)

    # 1. Get all Fixed Cost Definitions
    fcs = pd.read_sql("SELECT * FROM fixed_costs", conn)
    if fcs.empty:
        return 0
        
    # 2. Get expenses already created this month (to prevent duplicates)
    ex_month = pd.read_sql("""
        SELECT description FROM expenses 
        WHERE date >= ? AND date < ?
    """, conn, params=(start_m_date, end_m_date))
    existing_set = set(ex_month['description'].tolist())
    
    added_count = 0
    cursor = conn.cursor()
    
    try:
        for _, fc in fcs.iterrows():
            if fc['description'] in existing_set:
                continue
                
            try:
                d_day = int(fc['due_day']) if fc['due_day'] else 1
                last_day = calendar.monthrange(curr_y, curr_m)[1]
                eff_day = min(d_day, last_day) 
                due_date_obj = date(curr_y, curr_m, eff_day)
                
                # Auto-insert if due date has passed or is today
                if today >= due_date_obj:
                    cursor.execute("""
                        INSERT INTO expenses (date, description, amount, category)
                        VALUES (?, ?, ?, ?)
                    """, (due_date_obj, fc['description'], fc['value'], fc['category']))
                    added_count += 1
            except Exception as e:
                logger.error(f"Error processing fixed cost {fc['description']}: {e}")
                
        if added_count > 0:
            conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao processar custos fixos: {e}")
        raise
        
    return added_count

# --- FINANCIAL REPORTING ---

def get_financial_summary(conn: sqlite3.Connection, start_date: date, end_date: date) -> Dict[str, Any]:
    """
    Generates a full financial summary for a period (Revenue, Expenses, Profit).
    Returns a dictionary of metrics and DataFrames.
    """
    
    # 1. Sales Revenue (From Sales Table)
    # Note: Includes Payment Method and Client info
    sales_query = """
        SELECT s.id, s.date, s.total_price, s.discount, s.payment_method, s.salesperson,
               p.name as product_name, p.category as product_category, c.name as client_name, 'Venda' as source
        FROM sales s
        LEFT JOIN products p ON s.product_id = p.id
        LEFT JOIN clients c ON s.client_id = c.id
        WHERE s.date BETWEEN ? AND ?
    """
    sales_df = pd.read_sql(sales_query, conn, params=(start_date, end_date))
    
    # 2. Expenses (From Expenses Table)
    expenses_query = """
        SELECT e.id, e.date, e.description, e.amount, e.category, s.name as supplier_name, 'Despesa' as source
        FROM expenses e
        LEFT JOIN suppliers s ON e.supplier_id = s.id
        WHERE e.date BETWEEN ? AND ?
    """
    expenses_df = pd.read_sql(expenses_query, conn, params=(start_date, end_date))
    
    # 3. Create 'amount' column for sales unified view (total_price)
    if not sales_df.empty:
        sales_df['amount'] = sales_df['total_price']
        sales_df['date'] = pd.to_datetime(sales_df['date'])
        
    if not expenses_df.empty:
        expenses_df['date'] = pd.to_datetime(expenses_df['date'])

    # Calculations
    gross_revenue = sales_df['total_price'].sum() if not sales_df.empty else 0.0
    total_expenses = expenses_df['amount'].sum() if not expenses_df.empty else 0.0
    total_discounts = sales_df['discount'].sum() if not sales_df.empty else 0.0
    
    net_profit = gross_revenue - total_expenses
    
    return {
        'gross_revenue': gross_revenue,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'total_discounts': total_discounts,
        'revenue_details': sales_df, # Detailed DF for charts/tables
        'expense_details': expenses_df # Detailed DF for charts/tables
    }
