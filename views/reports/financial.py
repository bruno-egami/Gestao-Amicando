import streamlit as st
import pandas as pd
import services.analytics_service as report_service
from datetime import datetime, date, timedelta

# --- Caching Helpers ---
@st.cache_data(ttl=300, show_spinner=False)
def get_cached_sales_data(_conn, start_date, end_date, seller_filter):
    """Fetches sales data for reports."""
    return report_service.get_sales_data(_conn, start_date, end_date, seller_filter)

@st.cache_data(ttl=300, show_spinner=False)
def get_cached_top_products(_conn, start_date, end_date, top_limit, order_by):
    """Fetches top items for report."""
    return report_service.get_top_products(_conn, start_date, end_date, top_limit, order_by)

@st.cache_data(ttl=300, show_spinner=False)
def get_cached_expenses(_conn, start_date, end_date, cat_filter):
    """Fetches expenses for report."""
    return report_service.get_expenses_data(_conn, start_date, end_date, cat_filter)

# --- Render Functions ---

def render_sales_period(conn):
    st.subheader("💰 Relatório de Vendas por Período")
    
    # Filters
    c1, c2, c3 = st.columns(3)
    today = date.today()
    start_date = c1.date_input("Data Início", today.replace(day=1), format="DD/MM/YYYY")
    end_date = c2.date_input("Data Fim", today, format="DD/MM/YYYY")
    
    # Get sellers
    sellers = ["Todos"] + pd.read_sql("SELECT DISTINCT salesperson FROM sales WHERE salesperson IS NOT NULL", conn)['salesperson'].tolist()
    seller_filter = c3.selectbox("Vendedor(a)", sellers)
    
    # Comparison toggle
    show_comparison = st.checkbox("📈 Comparar com período anterior")
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Relatório de Vendas"
        info_lines = {
            "Período": f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}",
            "Vendedor(a)": seller_filter
        }
        
        # Use cached function
        report_df = get_cached_sales_data(conn, start_date, end_date, seller_filter)
        
        headers = []
        totals = []
        chart_data = None
        
        if not report_df.empty:
            # Calculate totals
            total_sales = len(report_df)
            total_value = report_df['Valor'].sum()
            total_discount = report_df['Desconto'].sum()
            
            totals = [
                ("Total de Vendas", str(total_sales)),
                ("Valor Bruto", f"R$ {total_value + total_discount:,.2f}"),
                ("Descontos", f"R$ {total_discount:,.2f}"),
                ("Valor Líquido", f"R$ {total_value:,.2f}")
            ]
            
            # Comparison with previous period
            if show_comparison:
                period_days = (end_date - start_date).days + 1
                prev_start = start_date - timedelta(days=period_days)
                prev_end = start_date - timedelta(days=1)
                
                prev_total = report_service.get_sales_total_period(conn, prev_start, prev_end, seller_filter)
                
                if prev_total > 0:
                    variation = ((total_value - prev_total) / prev_total) * 100
                    totals.append(("Variação vs Anterior", f"{variation:+.1f}%"))
                    info_lines["Período Anterior"] = f"{prev_start.strftime('%d/%m/%Y')} a {prev_end.strftime('%d/%m/%Y')}"
            
            # Chart - Sales by day
            report_df_chart = report_df.copy()
            report_df_chart['Data'] = pd.to_datetime(report_df_chart['Data'])
            daily_sales = report_df_chart.groupby(report_df_chart['Data'].dt.date)['Valor'].sum().reset_index()
            daily_sales.columns = ['Data', 'Valor']
            daily_sales['Data'] = pd.to_datetime(daily_sales['Data']).dt.strftime('%d/%m/%Y')
            chart_data = {'type': 'line', 'df': daily_sales, 'x': 'Data', 'y': 'Valor', 'title': 'Vendas por Dia'}
            
            # Format
            report_df['Valor'] = report_df['Valor'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Desconto'] = report_df['Desconto'].apply(lambda x: f"R$ {x:,.2f}" if x > 0 else "-")
            report_df['Data'] = pd.to_datetime(report_df['Data']).dt.strftime('%d/%m/%Y')
            
            headers = ['Data', 'Produto', 'Qtd', 'Valor', 'Desconto', 'Pagamento', 'Vendedor', 'Cliente']
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

def render_top_products(conn):
    st.subheader("🏆 Top Produtos Vendidos")
    
    # Filters
    c1, c2, c3, c4 = st.columns(4)
    today = date.today()
    start_date = c1.date_input("Data Início", today.replace(day=1), format="DD/MM/YYYY")
    end_date = c2.date_input("Data Fim", today, format="DD/MM/YYYY")
    order_by = c3.selectbox("Ordenar por", ["Quantidade", "Valor"])
    top_limit = c4.number_input("Quantidade", min_value=5, value=10, step=5)
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = f"Top {top_limit} Produtos Vendidos"
        info_lines = {
            "Período": f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}",
            "Ordenado por": order_by,
            "Limite": str(top_limit)
        }
        
        # Use cached function
        report_df = get_cached_top_products(conn, start_date, end_date, top_limit, order_by)
        
        headers = []
        totals = []
        chart_data = None

        if not report_df.empty:
            # Rename columns
            report_df.columns = ['Produto', 'Categoria', 'Qtd Vendida', 'Valor Total', 'Nº Vendas']
            
            total_qty = report_df['Qtd Vendida'].sum()
            total_value = report_df['Valor Total'].sum()
            
            totals = [
                ("Total Quantidade", str(int(total_qty))),
                ("Total Valor", f"R$ {total_value:,.2f}")
            ]
            
            # Chart - Horizontal bar
            chart_data = {'type': 'bar_h', 'df': report_df, 'x': 'Qtd Vendida' if order_by == "Quantidade" else 'Valor Total', 
                         'y': 'Produto', 'title': f'Top 10 por {order_by}'}
            
            # Format
            report_df['Valor Total'] = report_df['Valor Total'].apply(lambda x: f"R$ {x:,.2f}")
            
            headers = ['Produto', 'Categoria', 'Qtd Vendida', 'Valor Total', 'Nº Vendas']
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

def render_expenses(conn):
    st.subheader("💸 Relatório de Despesas por Categoria")
    
    # Filters
    c1, c2, c3 = st.columns(3)
    today = date.today()
    start_date = c1.date_input("Data Início", today.replace(day=1), format="DD/MM/YYYY")
    end_date = c2.date_input("Data Fim", today, format="DD/MM/YYYY")
    
    # Get categories
    categories = ["Todas"] + pd.read_sql("SELECT DISTINCT category FROM expenses WHERE category IS NOT NULL", conn)['category'].tolist()
    cat_filter = c3.selectbox("Categoria", categories)
    
    # Comparison toggle
    show_comparison = st.checkbox("📈 Comparar com período anterior")
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Relatório de Despesas"
        info_lines = {
            "Período": f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}",
            "Categoria": cat_filter
        }
        
        # Use cached function
        report_df = get_cached_expenses(conn, start_date, end_date, cat_filter)
        
        headers = []
        totals = []
        chart_data = None

        if not report_df.empty:
            # Calculate totals by category
            cat_totals = report_df.groupby('Categoria')['Valor'].sum()
            total_expenses = report_df['Valor'].sum()
            
            totals = [(f"Subtotal - {cat}", f"R$ {val:,.2f}") for cat, val in cat_totals.items()]
            totals.append(("TOTAL GERAL", f"R$ {total_expenses:,.2f}"))
            
            # Comparison with previous period
            if show_comparison:
                period_days = (end_date - start_date).days + 1
                prev_start = start_date - timedelta(days=period_days)
                prev_end = start_date - timedelta(days=1)
                
                prev_total = report_service.get_expenses_total_period(conn, prev_start, prev_end, cat_filter)
                
                if prev_total > 0:
                    variation = ((total_expenses - prev_total) / prev_total) * 100
                    totals.append(("Variação vs Anterior", f"{variation:+.1f}%"))
                    info_lines["Período Anterior"] = f"{prev_start.strftime('%d/%m/%Y')} a {prev_end.strftime('%d/%m/%Y')}"
            
            # Chart - Pie by category
            pie_df = report_df.groupby('Categoria')['Valor'].sum().reset_index()
            chart_data = {'type': 'pie', 'df': pie_df, 'names': 'Categoria', 'values': 'Valor', 
                         'title': 'Despesas por Categoria'}
            
            # Format
            report_df['Valor'] = report_df['Valor'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Data'] = pd.to_datetime(report_df['Data']).dt.strftime('%d/%m/%Y')
            
            headers = ['Data', 'Descrição', 'Categoria', 'Fornecedor', 'Valor']
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

def render_profitability(conn):
    st.subheader("💰 Lucratividade por Produto")
    
    # Filters
    c1, c2, c3 = st.columns(3)
    today = date.today()
    start_date = c1.date_input("Data Início", today.replace(day=1), format="DD/MM/YYYY")
    end_date = c2.date_input("Data Fim", today, format="DD/MM/YYYY")
    top_limit = c3.number_input("Quantidade", min_value=5, value=10, step=5)
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Lucratividade por Produto"
        info_lines = {
            "Período": f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
        }
        
        # Get realized profitability
        report_df = report_service.get_realized_profitability(conn, start_date, end_date, top_limit)
        
        headers = []
        totals = []
        chart_data = None

        if not report_df.empty:
            # Calculate profit margin
            report_df['Lucro'] = report_df['Receita'] - report_df['CustoTotal']
            report_df['Margem %'] = (report_df['Lucro'] / report_df['Receita'] * 100).round(1)
            
            # Reorder columns
            report_df = report_df[['Produto', 'Categoria', 'QtdVendida', 'CustoTotal', 'Receita', 'Lucro', 'Margem %']]
            report_df.columns = ['Produto', 'Categoria', 'Qtd', 'Custo', 'Receita', 'Lucro', 'Margem %']
            
            # Totals
            total_revenue = report_df['Receita'].sum()
            total_cost = report_df['Custo'].sum()
            total_profit = report_df['Lucro'].sum()
            avg_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
            
            totals = [
                ("Receita Total", f"R$ {total_revenue:,.2f}"),
                ("Custo Total", f"R$ {total_cost:,.2f}"),
                ("Lucro Total", f"R$ {total_profit:,.2f}"),
                ("Margem Média", f"{avg_margin:.1f}%")
            ]
            
            # Chart - Profit by product
            chart_data = {
                'type': 'bar_h', 
                'df': report_df, 
                'x': 'Lucro', 
                'y': 'Produto',
                'title': 'Lucro por Produto'
            }
            
            # Format values
            report_df['Custo'] = report_df['Custo'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Receita'] = report_df['Receita'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Lucro'] = report_df['Lucro'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Margem %'] = report_df['Margem %'].apply(lambda x: f"{x:.1f}%")
            
            headers = list(report_df.columns)
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

def render_sales_trend(conn):
    st.subheader("📈 Análise de Vendas Anual")
    
    # Filters
    c1, c2, c3 = st.columns(3)
    current_year = date.today().year
    years = list(range(current_year, current_year - 5, -1))  # Last 5 years
    selected_year = c1.selectbox("Ano", years)
    
    # View options
    view_type = c2.selectbox("Visualização", ["Por Produto", "Geral"])
    top_limit = c3.number_input("Top Produtos", min_value=5, value=10, step=5)
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = f"Análise de Vendas {selected_year}"
        info_lines = {
            "Ano": str(selected_year),
            "Visualização": view_type
        }
        
        headers = []
        totals = []
        chart_data = None
        report_df = pd.DataFrame()

        if view_type == "Por Produto":
            # Monthly sales by product - pivot table
            raw_df = report_service.get_sales_trend(conn, selected_year)
            
            if not raw_df.empty:
                # Get top products by total sales
                top_products = raw_df.groupby('Produto')['Quantidade'].sum().nlargest(top_limit).index.tolist()
                raw_df = raw_df[raw_df['Produto'].isin(top_products)]
                
                # Create pivot table for quantities
                pivot_qty = raw_df.pivot_table(
                    index='Produto', 
                    columns='Mes', 
                    values='Quantidade', 
                    aggfunc='sum',
                    fill_value=0
                )
                
                # Rename columns to month names
                month_names = {
                    '01': 'Jan', '02': 'Fev', '03': 'Mar', '04': 'Abr',
                    '05': 'Mai', '06': 'Jun', '07': 'Jul', '08': 'Ago',
                    '09': 'Set', '10': 'Out', '11': 'Nov', '12': 'Dez'
                }
                pivot_qty.columns = [month_names.get(c, c) for c in pivot_qty.columns]
                
                # Add total column
                pivot_qty['Total'] = pivot_qty.sum(axis=1)
                pivot_qty = pivot_qty.sort_values('Total', ascending=False)
                
                # Reset index for display
                report_df = pivot_qty.reset_index()
                
                # Totals
                grand_total = report_df['Total'].sum()
                totals = [("Total Vendido", str(int(grand_total)))]
                
                # Chart - Grouped bar chart
                chart_df = raw_df.copy()
                chart_df['Mes'] = chart_df['Mes'].map(month_names)
                chart_data = {
                    'type': 'grouped_bar', 
                    'df': chart_df, 
                    'x': 'Mes', 
                    'y': 'Quantidade',
                    'color': 'Produto',
                    'title': f'Vendas Mensais - Top {top_limit} Produtos'
                }
                
                headers = list(report_df.columns)
        
        else:  # Geral - Total monthly sales
            query = (
                "SELECT strftime('%m', s.date) as Mes, COUNT(*) as NumVendas, SUM(s.quantity) as Quantidade, SUM(s.total_price) as Valor "
                "FROM sales s WHERE strftime('%Y', s.date) = ? GROUP BY strftime('%m', s.date) ORDER BY Mes"
            )
            
            report_df = pd.read_sql(query, conn, params=[str(selected_year)])
            
            if not report_df.empty:
                # Rename months
                month_names = {
                    '01': 'Janeiro', '02': 'Fevereiro', '03': 'Março', '04': 'Abril',
                    '05': 'Maio', '06': 'Junho', '07': 'Julho', '08': 'Agosto',
                    '09': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
                }
                report_df['Mes'] = report_df['Mes'].map(month_names)
                report_df.columns = ['Mês', 'Nº Vendas', 'Quantidade', 'Valor']
                
                # Totals
                total_sales = report_df['Nº Vendas'].sum()
                total_qty = report_df['Quantidade'].sum()
                total_value = report_df['Valor'].sum()
                
                totals = [
                    ("Total Vendas", str(int(total_sales))),
                    ("Total Unidades", str(int(total_qty))),
                    ("Valor Total", f"R$ {total_value:,.2f}")
                ]
                
                # Chart - Line chart
                chart_data = {
                    'type': 'line', 
                    'df': report_df, 
                    'x': 'Mês', 
                    'y': 'Valor',
                    'title': f'Evolução de Vendas - {selected_year}'
                }
                
                # Format value
                report_df['Valor'] = report_df['Valor'].apply(lambda x: f"R$ {x:,.2f}")
                
                headers = ['Mês', 'Nº Vendas', 'Quantidade', 'Valor']
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

def render_cash_flow(conn):
    st.subheader("💵 Fluxo de Caixa")
    
    # Filters
    c1, c2, c3 = st.columns(3)
    today = date.today()
    start_date = c1.date_input("Data Início", today.replace(day=1), format="DD/MM/YYYY")
    end_date = c2.date_input("Data Fim", today, format="DD/MM/YYYY")
    view_type = c3.selectbox("Agrupar por", ["Dia", "Semana", "Mês"])
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Fluxo de Caixa"
        info_lines = {
            "Período": f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}",
            "Agrupamento": view_type
        }
        
        # Date grouping
        if view_type == "Dia":
            date_format = '%Y-%m-%d'
        elif view_type == "Semana":
            date_format = '%Y-%W'
        else:  # Mês
            date_format = '%Y-%m'
        
        # Get sales (income) and expenses
        flow_data = report_service.get_cash_flow_data(conn, start_date, end_date, date_format)
        sales_df = flow_data['sales']
        expenses_df = flow_data['expenses']
        
        headers = []
        totals = []
        chart_data = None
        report_df = pd.DataFrame()
        
        # Merge
        if not sales_df.empty or not expenses_df.empty:
            report_df = pd.merge(sales_df, expenses_df, on='Periodo', how='outer').fillna(0)
            report_df = report_df.sort_values('Periodo')
            
            # Calculate balance
            report_df['Saldo'] = report_df['Entradas'] - report_df['Saidas']
            report_df['Saldo Acum.'] = report_df['Saldo'].cumsum()
            
            # Totals
            total_income = report_df['Entradas'].sum()
            total_expenses = report_df['Saidas'].sum()
            final_balance = report_df['Saldo'].sum()
            
            totals = [
                ("Total Entradas", f"R$ {total_income:,.2f}"),
                ("Total Saídas", f"R$ {total_expenses:,.2f}"),
                ("Saldo Final", f"R$ {final_balance:,.2f}")
            ]
            
            # Chart - Line chart of cumulative balance
            chart_data = {
                'type': 'line', 
                'df': report_df, 
                'x': 'Periodo', 
                'y': 'Saldo Acum.',
                'title': 'Evolução do Saldo Acumulado'
            }
            
            # Format values
            report_df['Entradas'] = report_df['Entradas'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Saidas'] = report_df['Saidas'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Saldo'] = report_df['Saldo'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Saldo Acum.'] = report_df['Saldo Acum.'].apply(lambda x: f"R$ {x:,.2f}")
            
            report_df.columns = ['Período', 'Entradas', 'Saídas', 'Saldo', 'Saldo Acum.']
            headers = list(report_df.columns)
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

def render_pending_orders(conn):
    st.subheader("📦 Encomendas Pendentes")
    
    # Filters
    c1, c2 = st.columns(2)
    
    status_options = ["Todas", "Pendente", "Em Produção"]
    selected_status = c1.selectbox("Status", status_options)
    
    sort_options = {"Prazo (Mais Urgente)": "date_due ASC", "Prazo (Mais Novo)": "date_due DESC", 
                   "Valor (Maior)": "total_price DESC", "Valor (Menor)": "total_price ASC"}
    selected_sort = c2.selectbox("Ordenar por", list(sort_options.keys()))
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Encomendas Pendentes"
        info_lines = {
            "Status": selected_status,
            "Ordenação": selected_sort
        }
        
        # Build query
        status_filter = ""
        if selected_status != "Todas":
            status_filter = f"AND co.status = '{selected_status}'"
        
        query_sort = sort_options[selected_sort]
        report_df = report_service.get_pending_orders(conn, status_filter, query_sort)
        
        headers = []
        totals = []
        chart_data = None

        if not report_df.empty:
            # Calculate days until due
            report_df['Dias p/ Prazo'] = (pd.to_datetime(report_df['Prazo']) - pd.Timestamp.today()).dt.days
            
            # Totals
            total_orders = len(report_df)
            total_value = report_df['Valor Total'].sum()
            total_pending = report_df['Saldo'].sum()
            
            totals = [
                ("Total de Encomendas", str(total_orders)),
                ("Valor Total", f"R$ {total_value:,.2f}"),
                ("Saldo a Receber", f"R$ {total_pending:,.2f}")
            ]
            
            # Chart - Orders by status
            by_status = report_df.groupby('Status')['Valor Total'].sum().reset_index()
            chart_data = {
                'type': 'pie', 
                'df': by_status, 
                'names': 'Status', 
                'values': 'Valor Total',
                'title': 'Valor por Status'
            }
            
            # Format dates and values
            report_df['Dt Criação'] = pd.to_datetime(report_df['Dt Criação']).dt.strftime('%d/%m/%Y')
            report_df['Prazo'] = pd.to_datetime(report_df['Prazo']).dt.strftime('%d/%m/%Y')
            report_df['Valor Total'] = report_df['Valor Total'].apply(lambda x: f"R$ {x:,.2f}" if pd.notnull(x) else "-")
            report_df['Sinal'] = report_df['Sinal'].apply(lambda x: f"R$ {x:,.2f}" if pd.notnull(x) and x > 0 else "-")
            report_df['Saldo'] = report_df['Saldo'].apply(lambda x: f"R$ {x:,.2f}" if pd.notnull(x) else "-")
            
            headers = list(report_df.columns)
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

def render_seasonality(conn):
    st.subheader("📊 Análise de Sazonalidade")
    
    st.info("Compare as vendas do mesmo mês em diferentes anos para identificar padrões sazonais.")
    
    # Filters
    c1, c2 = st.columns(2)
    
    month_names = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                   "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    selected_month = c1.selectbox("Mês para Análise", month_names, index=date.today().month - 1)
    month_num = month_names.index(selected_month) + 1
    
    years_back = c2.number_input("Quantos Anos Comparar", min_value=2, max_value=10, value=3, step=1)
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = f"Sazonalidade - {selected_month}"
        info_lines = {
            "Mês Analisado": selected_month,
            "Anos Comparados": str(years_back)
        }
        
        current_year = date.today().year
        years = [str(current_year - i) for i in range(years_back)]
        
        # Get sales for the selected month across years
        report_df = report_service.get_seasonality_data(conn, month_num, years)
        
        headers = []
        totals = []
        chart_data = None

        if not report_df.empty:
            report_df.columns = ['Ano', 'Nº Vendas', 'Qtd Vendida', 'Valor Total', 'Ticket Médio']
            
            # Calculate year-over-year growth
            report_df['Crescimento'] = report_df['Valor Total'].pct_change() * 100
            report_df['Crescimento'] = report_df['Crescimento'].fillna(0)
            
            # Totals
            avg_value = report_df['Valor Total'].mean()
            max_year = report_df.loc[report_df['Valor Total'].idxmax(), 'Ano']
            min_year = report_df.loc[report_df['Valor Total'].idxmin(), 'Ano']
            
            totals = [
                ("Média do Mês", f"R$ {avg_value:,.2f}"),
                ("Melhor Ano", max_year),
                ("Pior Ano", min_year)
            ]
            
            # Chart - Bar by year
            chart_data = {
                'type': 'bar', 
                'df': report_df, 
                'x': 'Ano', 
                'y': 'Valor Total',
                'title': f'Vendas de {selected_month} por Ano'
            }
            
            # Format values
            report_df['Valor Total'] = report_df['Valor Total'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Ticket Médio'] = report_df['Ticket Médio'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Crescimento'] = report_df['Crescimento'].apply(lambda x: f"{x:+.1f}%" if x != 0 else "-")
            
            headers = list(report_df.columns)
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }
