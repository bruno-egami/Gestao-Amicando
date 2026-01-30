import streamlit as st
import database
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import admin_utils

# Page config
st.set_page_config(
    page_title="CeramicAdmin OS",
    page_icon="🏺",
    layout="wide",
    initial_sidebar_state="expanded",
)

database.init_db()

# --- SIDEBAR: Access & Filters ---
with st.sidebar:
    st.title("Acesso")
    mode = st.radio("Modo de Acesso", ["Vendedor", "Administrador"])
    
    if mode == "Administrador":
        if not admin_utils.check_password():
            st.stop()
    
    st.divider()
    st.header("Filtros de Data")
    
    # Date Range
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Início", datetime.now().replace(day=1))
    end_date = col2.date_input("Fim", datetime.now())

# Main Content
st.title("CeramicAdmin OS 🏺")
st.markdown(f"### Visão Geral ({start_date} a {end_date})")

conn = database.get_connection()

try:
    # --- Filtered Queries ---
    
    # 1. Sales in Range
    sales_query = f"SELECT sum(total_price) as total FROM sales WHERE date BETWEEN '{start_date}' AND '{end_date}'"
    sales_total = pd.read_sql(sales_query, conn).iloc[0]['total'] or 0.0
    
    # 2. Expenses in Range
    exp_query = f"SELECT sum(amount) as total FROM expenses WHERE date BETWEEN '{start_date}' AND '{end_date}'"
    expenses_total = pd.read_sql(exp_query, conn).iloc[0]['total'] or 0.0
    
    # 3. Balance
    balance = sales_total - expenses_total
    
    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Faturamento (Período)", f"R$ {sales_total:.2f}")
    c2.metric("Despesas (Período)", f"R$ {expenses_total:.2f}", delta_color="inverse")
    c3.metric("Balanço Financeiro", f"R$ {balance:.2f}", delta_color="normal" if balance >=0 else "inverse")

    st.divider()
    
    # --- Admin View of Charts ---
    if mode == "Administrador":
        # Monthly Chart
        st.subheader("Evolução Mensal (Receita vs Despesas)")
        
        # Monthly Sales
        m_sales = pd.read_sql("""
            SELECT strftime('%Y-%m', date) as month, sum(total_price) as amount 
            FROM sales 
            GROUP BY month ORDER BY month
        """, conn)
        m_sales['Type'] = 'Receita'
        
        # Monthly Expenses
        m_exp = pd.read_sql("""
            SELECT strftime('%Y-%m', date) as month, sum(amount) as amount 
            FROM expenses
            GROUP BY month ORDER BY month
        """, conn)
        m_exp['Type'] = 'Despesa'
        
        combined = pd.concat([m_sales, m_exp])
        
        if not combined.empty:
            fig = px.bar(combined, x='month', y='amount', color='Type', barmode='group',
                         color_discrete_map={'Receita': '#4CAF50', 'Despesa': '#FF5722'})
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.info("Sem dados para gráfico mensal.")

    else:
        st.info("Modo Vendedor: Gráficos administrativos ocultos.")

except Exception as e:
    st.error(f"Erro no dashboard: {e}")
finally:
    conn.close()
