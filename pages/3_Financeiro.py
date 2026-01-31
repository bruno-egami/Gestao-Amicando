import streamlit as st
import pandas as pd
import database
import admin_utils
import auth
from datetime import date, timedelta
import plotly.express as px

st.set_page_config(page_title="Financeiro", page_icon="💰", layout="wide")

admin_utils.render_sidebar_logo()

conn = database.get_connection()

# Authentication
if not auth.require_login(conn):
    st.stop()

auth.render_custom_sidebar()

# Role check - admin only
if not auth.check_page_access('Financeiro'):
    st.stop()

admin_utils.render_header_logo()
st.title("💰 Relatórios Financeiros")

# --- SIDEBAR FILTERS ---
with st.sidebar:
    st.subheader("📅 Período do Relatório")
    
    # Quick selectors
    quick_period = st.radio("Período Rápido", 
                            ["Mês Atual", "Mês Anterior", "Último Trimestre", "Ano Atual", "Personalizado"],
                            index=0)
    
    today = date.today()
    
    if quick_period == "Mês Atual":
        start_date = today.replace(day=1)
        end_date = today
    elif quick_period == "Mês Anterior":
        first_this_month = today.replace(day=1)
        end_date = first_this_month - timedelta(days=1)
        start_date = end_date.replace(day=1)
    elif quick_period == "Último Trimestre":
        start_date = today - timedelta(days=90)
        end_date = today
    elif quick_period == "Ano Atual":
        start_date = today.replace(month=1, day=1)
        end_date = today
    else:  # Personalizado
        start_date = st.date_input("Data Início", today.replace(day=1))
        end_date = st.date_input("Data Fim", today)
    
    st.caption(f"De **{start_date.strftime('%d/%m/%Y')}** até **{end_date.strftime('%d/%m/%Y')}**")

# --- DATA QUERIES ---
# Sales
sales_df = pd.read_sql("""
    SELECT s.id, s.date, s.total_price, s.discount, s.payment_method, s.salesperson,
           p.name as product_name, p.category as product_category, c.name as client_name
    FROM sales s
    JOIN products p ON s.product_id = p.id
    LEFT JOIN clients c ON s.client_id = c.id
    WHERE s.date BETWEEN ? AND ?
""", conn, params=(start_date, end_date))

# Expenses
expenses_df = pd.read_sql("""
    SELECT e.id, e.date, e.description, e.amount, e.category, s.name as supplier_name
    FROM expenses e
    LEFT JOIN suppliers s ON e.supplier_id = s.id
    WHERE e.date BETWEEN ? AND ?
""", conn, params=(start_date, end_date))

# Commission Orders (Deposits)
orders_df = pd.read_sql("""
    SELECT co.id, co.date_created, co.deposit_amount, co.total_price, co.status, c.name as client_name
    FROM commission_orders co
    LEFT JOIN clients c ON co.client_id = c.id
    WHERE co.date_created BETWEEN ? AND ?
""", conn, params=(start_date, end_date))

# --- CALCULATIONS ---
total_sales = sales_df['total_price'].sum() if not sales_df.empty else 0.0
total_discounts = sales_df['discount'].sum() if not sales_df.empty else 0.0
total_expenses = expenses_df['amount'].sum() if not expenses_df.empty else 0.0
total_deposits = orders_df['deposit_amount'].sum() if not orders_df.empty else 0.0

gross_revenue = total_sales + total_deposits
net_profit = gross_revenue - total_expenses

# --- MAIN METRICS ---
st.subheader("📊 Resumo do Período")

c1, c2, c3, c4 = st.columns(4)
c1.metric("💵 Faturamento Bruto", f"R$ {gross_revenue:,.2f}", 
          help="Vendas finalizadas + Sinais de encomendas")
c2.metric("📤 Despesas", f"R$ {total_expenses:,.2f}")
c3.metric("📉 Descontos Concedidos", f"R$ {total_discounts:,.2f}")
c4.metric("💰 Lucro Líquido", f"R$ {net_profit:,.2f}", 
          delta=f"R$ {net_profit:,.2f}", delta_color="normal" if net_profit >= 0 else "inverse")

st.divider()

# --- EXCEL EXPORT ---
import io
from datetime import datetime as dt

exp_col1, exp_col2, exp_col3 = st.columns(3)

with exp_col1:
    if not sales_df.empty:
        output_sales = io.BytesIO()
        sales_df.to_excel(output_sales, index=False, engine='openpyxl')
        st.download_button(
            "📥 Exportar Vendas (Excel)",
            output_sales.getvalue(),
            file_name=f"vendas_{start_date}_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

with exp_col2:
    if not expenses_df.empty:
        output_exp = io.BytesIO()
        expenses_df.to_excel(output_exp, index=False, engine='openpyxl')
        st.download_button(
            "📥 Exportar Despesas (Excel)",
            output_exp.getvalue(),
            file_name=f"despesas_{start_date}_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

with exp_col3:
    # Combined Report
    if not sales_df.empty or not expenses_df.empty:
        output_all = io.BytesIO()
        with pd.ExcelWriter(output_all, engine='openpyxl') as writer:
            if not sales_df.empty:
                sales_df.to_excel(writer, sheet_name='Vendas', index=False)
            if not expenses_df.empty:
                expenses_df.to_excel(writer, sheet_name='Despesas', index=False)
            if not orders_df.empty:
                orders_df.to_excel(writer, sheet_name='Encomendas', index=False)
        st.download_button(
            "📥 Relatório Completo (Excel)",
            output_all.getvalue(),
            file_name=f"relatorio_financeiro_{start_date}_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

st.divider()

# --- TABS FOR DETAILS ---
tab_sales, tab_expenses, tab_charts = st.tabs(["📈 Vendas", "📉 Despesas", "📊 Gráficos"])

# ======================
# TAB: VENDAS
# ======================
with tab_sales:
    st.subheader("📈 Detalhamento de Vendas")
    
    if not sales_df.empty:
        # Filters
        f1, f2, f3 = st.columns(3)
        
        payment_opts = ["Todos"] + sales_df['payment_method'].dropna().unique().tolist()
        sel_payment = f1.selectbox("Forma de Pagamento", payment_opts)
        
        seller_opts = ["Todos"] + sales_df['salesperson'].dropna().unique().tolist()
        sel_seller = f2.selectbox("Vendedora", seller_opts)
        
        cat_opts = ["Todos"] + sales_df['product_category'].dropna().unique().tolist()
        sel_cat = f3.selectbox("Categoria do Produto", cat_opts)
        
        # Apply Filters
        filtered_sales = sales_df.copy()
        if sel_payment != "Todos":
            filtered_sales = filtered_sales[filtered_sales['payment_method'] == sel_payment]
        if sel_seller != "Todos":
            filtered_sales = filtered_sales[filtered_sales['salesperson'] == sel_seller]
        if sel_cat != "Todos":
            filtered_sales = filtered_sales[filtered_sales['product_category'] == sel_cat]
        
        # Summary
        st.metric("Total Filtrado", f"R$ {filtered_sales['total_price'].sum():,.2f}")
        
        # Table
        st.dataframe(
            filtered_sales[['date', 'product_name', 'client_name', 'total_price', 'discount', 'payment_method', 'salesperson']],
            hide_index=True,
            use_container_width=True,
            column_config={
                "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "product_name": "Produto",
                "client_name": "Cliente",
                "total_price": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                "discount": st.column_config.NumberColumn("Desconto", format="R$ %.2f"),
                "payment_method": "Pagamento",
                "salesperson": "Vendedora"
            }
        )
        
        # Breakdown by Payment Method
        st.subheader("Por Forma de Pagamento")
        pay_breakdown = filtered_sales.groupby('payment_method')['total_price'].sum().reset_index()
        st.bar_chart(pay_breakdown, x='payment_method', y='total_price', color='payment_method')
        
        # Breakdown by Salesperson
        st.subheader("Por Vendedora")
        seller_breakdown = filtered_sales.groupby('salesperson')['total_price'].sum().reset_index()
        st.bar_chart(seller_breakdown, x='salesperson', y='total_price', color='salesperson')
        
    else:
        st.info("Nenhuma venda registrada no período.")

# ======================
# TAB: DESPESAS
# ======================
with tab_expenses:
    st.subheader("📉 Detalhamento de Despesas")
    
    if not expenses_df.empty:
        # Filters
        e1, e2 = st.columns(2)
        
        exp_cat_opts = ["Todos"] + expenses_df['category'].dropna().unique().tolist()
        sel_exp_cat = e1.selectbox("Categoria", exp_cat_opts)
        
        sup_opts = ["Todos"] + expenses_df['supplier_name'].dropna().unique().tolist()
        sel_sup = e2.selectbox("Fornecedor", sup_opts)
        
        # Apply Filters
        filtered_expenses = expenses_df.copy()
        if sel_exp_cat != "Todos":
            filtered_expenses = filtered_expenses[filtered_expenses['category'] == sel_exp_cat]
        if sel_sup != "Todos":
            filtered_expenses = filtered_expenses[filtered_expenses['supplier_name'] == sel_sup]
        
        # Summary
        st.metric("Total Filtrado", f"R$ {filtered_expenses['amount'].sum():,.2f}")
        
        # Table
        st.dataframe(
            filtered_expenses[['date', 'description', 'amount', 'category', 'supplier_name']],
            hide_index=True,
            use_container_width=True,
            column_config={
                "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "description": "Descrição",
                "amount": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                "category": "Categoria",
                "supplier_name": "Fornecedor"
            }
        )
        
        # Breakdown by Category
        st.subheader("Por Categoria")
        cat_breakdown = filtered_expenses.groupby('category')['amount'].sum().reset_index()
        st.bar_chart(cat_breakdown, x='category', y='amount', color='category')
        
    else:
        st.info("Nenhuma despesa registrada no período.")

# ======================
# TAB: GRÁFICOS
# ======================
with tab_charts:
    st.subheader("📊 Visualizações")
    
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.markdown("### Receita vs Despesa")
        
        summary_data = pd.DataFrame({
            'Tipo': ['Receita', 'Despesas'],
            'Valor': [gross_revenue, total_expenses]
        })
        
        fig_pie = px.pie(summary_data, values='Valor', names='Tipo', 
                         color_discrete_sequence=['#2ecc71', '#e74c3c'],
                         hole=0.4)
        fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with chart_col2:
        st.markdown("### Evolução Diária")
        
        if not sales_df.empty:
            sales_df['date'] = pd.to_datetime(sales_df['date'])
            daily_sales = sales_df.groupby(sales_df['date'].dt.date)['total_price'].sum().reset_index()
            daily_sales.columns = ['Data', 'Vendas']
        else:
            daily_sales = pd.DataFrame({'Data': [], 'Vendas': []})
        
        if not expenses_df.empty:
            expenses_df['date'] = pd.to_datetime(expenses_df['date'])
            daily_expenses = expenses_df.groupby(expenses_df['date'].dt.date)['amount'].sum().reset_index()
            daily_expenses.columns = ['Data', 'Despesas']
        else:
            daily_expenses = pd.DataFrame({'Data': [], 'Despesas': []})
        
        # Merge
        if not daily_sales.empty or not daily_expenses.empty:
            daily_all = pd.merge(daily_sales, daily_expenses, on='Data', how='outer').fillna(0)
            daily_all = daily_all.sort_values('Data')
            
            fig_line = px.line(daily_all, x='Data', y=['Vendas', 'Despesas'],
                               labels={'value': 'Valor (R$)', 'variable': 'Tipo'},
                               color_discrete_sequence=['#2ecc71', '#e74c3c'])
            fig_line.update_layout(margin=dict(t=20, b=0, l=0, r=0))
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("Sem dados para o gráfico de evolução.")
    
    # Monthly Trend (if enough data)
    st.markdown("### Tendência Mensal")
    
    # Sales Monthly
    if not sales_df.empty:
        sales_df['month'] = sales_df['date'].dt.to_period('M').astype(str)
        monthly_sales = sales_df.groupby('month')['total_price'].sum().reset_index()
        monthly_sales.columns = ['Mês', 'Vendas']
    else:
        monthly_sales = pd.DataFrame({'Mês': [], 'Vendas': []})
    
    # Expenses Monthly
    if not expenses_df.empty:
        expenses_df['month'] = expenses_df['date'].dt.to_period('M').astype(str)
        monthly_expenses = expenses_df.groupby('month')['amount'].sum().reset_index()
        monthly_expenses.columns = ['Mês', 'Despesas']
    else:
        monthly_expenses = pd.DataFrame({'Mês': [], 'Despesas': []})
    
    if not monthly_sales.empty or not monthly_expenses.empty:
        monthly_all = pd.merge(monthly_sales, monthly_expenses, on='Mês', how='outer').fillna(0)
        monthly_all = monthly_all.sort_values('Mês')
        monthly_all['Lucro'] = monthly_all['Vendas'] - monthly_all['Despesas']
        
        fig_bar = px.bar(monthly_all, x='Mês', y=['Vendas', 'Despesas', 'Lucro'],
                         barmode='group',
                         color_discrete_sequence=['#2ecc71', '#e74c3c', '#3498db'])
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Sem dados para a tendência mensal.")

conn.close()
