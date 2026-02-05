import pandas as pd
from datetime import datetime

def get_unified_revenue(conn, start_date, end_date):
    """
    Combines all revenue sources:
    1. Sales (Vendas Diretas)
    2. Commission Order Deposits (Sinais de Encomendas)
    3. Student Tuitions Paid (Mensalidades Paga)
    4. Student Consumptions Paid (Extras de Alunos Pagos)
    """
    # 1. Sales
    sales_df = pd.read_sql("""
        SELECT date, total_price as amount, 'Venda Direta' as source
        FROM sales
        WHERE date BETWEEN ? AND ?
    """, conn, params=(start_date, end_date))

    # 2. Commission Order Deposits
    deposits_df = pd.read_sql("""
        SELECT date_created as date, deposit_amount as amount, 'Sinal Encomenda' as source
        FROM commission_orders
        WHERE date_created BETWEEN ? AND ? AND deposit_amount > 0
    """, conn, params=(start_date, end_date))

    # 3. Student Tuitions Paid
    # We use payment_date to know WHEN the money entered
    tuitions_df = pd.read_sql("""
        SELECT payment_date as date, amount, 'Mensalidade' as source
        FROM tuitions
        WHERE status = 'Pago' AND payment_date BETWEEN ? AND ?
    """, conn, params=(start_date, end_date))

    # 4. Student Consumptions Paid
    consumptions_df = pd.read_sql("""
        SELECT payment_date as date, total_value as amount, 'Consumo Aluno' as source
        FROM student_consumptions
        WHERE status = 'Pago' AND payment_date BETWEEN ? AND ?
    """, conn, params=(start_date, end_date))

    # Combined DataFrame
    combined = pd.concat([sales_df, deposits_df, tuitions_df, consumptions_df], ignore_index=True)
    if not combined.empty:
        # Use errors='coerce' to safely handle invalid date strings
        combined['date'] = pd.to_datetime(combined['date'], errors='coerce')
        # Drop rows with invalid dates to avoid errors in sorting/display
        combined = combined.dropna(subset=['date']).sort_values('date')
    
    return combined

def get_unified_expenses(conn, start_date, end_date):
    """
    Fetches all expenses from the expenses table.
    """
    expenses_df = pd.read_sql("""
        SELECT date, amount, category, description, 'Despesa' as source
        FROM expenses
        WHERE date BETWEEN ? AND ?
    """, conn, params=(start_date, end_date))
    
    if not expenses_df.empty:
        # Use errors='coerce' to safely handle invalid date strings
        expenses_df['date'] = pd.to_datetime(expenses_df['date'], errors='coerce')
        # Drop rows with invalid dates
        expenses_df = expenses_df.dropna(subset=['date']).sort_values('date')
        
    return expenses_df

def get_financial_summary(conn, start_date, end_date):
    """
    Returns a dictionary with summarized metrics.
    """
    rev_df = get_unified_revenue(conn, start_date, end_date)
    exp_df = get_unified_expenses(conn, start_date, end_date)
    
    gross_revenue = rev_df['amount'].sum() if not rev_df.empty else 0.0
    total_expenses = exp_df['amount'].sum() if not exp_df.empty else 0.0
    net_profit = gross_revenue - total_expenses
    
    # Calculate discounts (from sales table)
    discounts = pd.read_sql("""
        SELECT SUM(discount) as d FROM sales WHERE date BETWEEN ? AND ?
    """, conn, params=(start_date, end_date)).iloc[0]['d'] or 0.0
    
    return {
        'gross_revenue': gross_revenue,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'total_discounts': discounts,
        'revenue_details': rev_df,
        'expense_details': exp_df
    }
