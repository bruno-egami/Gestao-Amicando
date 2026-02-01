import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import database
import admin_utils
import auth
import reports
import io
from datetime import datetime, date, timedelta

st.set_page_config(page_title="Relatórios", page_icon="📊", layout="wide")

admin_utils.render_sidebar_logo()
conn = database.get_connection()

if not auth.require_login(conn):
    st.stop()

auth.render_custom_sidebar()
st.title("📊 Relatórios")

# --- REPORT TYPE SELECTOR ---
report_types = {
    "Estoque Atual": "stock",
    "Vendas por Período": "sales",
    "Top 10 Produtos Vendidos": "top_products",
    "Despesas por Categoria": "expenses",
    "Consumo de Insumos": "consumption",
    "Histórico de Produção": "production"
}

selected_report = st.selectbox("Selecione o Relatório", list(report_types.keys()))
report_key = report_types[selected_report]

st.divider()

# Initialize report data
report_df = pd.DataFrame()
report_title = ""
info_lines = {}
headers = []
totals = []
chart_data = None  # For storing chart data

# ============================================================
# REPORT: ESTOQUE ATUAL
# ============================================================
if report_key == "stock":
    st.subheader("📦 Relatório de Estoque Atual")
    
    # Filters
    c1, c2 = st.columns(2)
    stock_type = c1.selectbox("Tipo", ["Todos", "Produtos", "Insumos"])
    show_low_only = c2.checkbox("Mostrar apenas estoque baixo")
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Relatório de Estoque Atual"
        info_lines = {"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Tipo": stock_type}
        
        if stock_type in ["Todos", "Produtos"]:
            products_df = pd.read_sql("""
                SELECT name as 'Nome', category as 'Categoria', stock_quantity as 'Estoque', 
                       base_price as 'Preço Unit.', (stock_quantity * base_price) as 'Valor Total'
                FROM products
                ORDER BY name
            """, conn)
            products_df['Tipo'] = 'Produto'
            
            if show_low_only:
                products_df = products_df[products_df['Estoque'] <= 5]
        
        if stock_type in ["Todos", "Insumos"]:
            materials_df = pd.read_sql("""
                SELECT m.name as 'Nome', mc.name as 'Categoria', m.stock_level as 'Estoque',
                       m.unit as 'Unidade', m.price_per_unit as 'Preço Unit.',
                       (m.stock_level * m.price_per_unit) as 'Valor Total'
                FROM materials m
                LEFT JOIN material_categories mc ON m.category_id = mc.id
                WHERE m.type = 'Material'
                ORDER BY m.name
            """, conn)
            materials_df['Tipo'] = 'Insumo'
            
            if show_low_only:
                materials_df = materials_df[materials_df['Estoque'] <= materials_df.get('min_stock_alert', 0)]
        
        # Combine or select
        if stock_type == "Produtos":
            report_df = products_df[['Nome', 'Categoria', 'Estoque', 'Preço Unit.', 'Valor Total']]
            headers = ['Nome', 'Categoria', 'Estoque', 'Preço Unit.', 'Valor Total']
            chart_data = {'type': 'bar', 'df': products_df, 'x': 'Nome', 'y': 'Valor Total', 'title': 'Valor em Estoque por Produto'}
        elif stock_type == "Insumos":
            report_df = materials_df[['Nome', 'Categoria', 'Estoque', 'Unidade', 'Preço Unit.', 'Valor Total']]
            headers = ['Nome', 'Categoria', 'Estoque', 'Unidade', 'Preço Unit.', 'Valor Total']
            chart_data = {'type': 'bar', 'df': materials_df, 'x': 'Nome', 'y': 'Valor Total', 'title': 'Valor em Estoque por Insumo'}
        else:
            products_df = products_df[['Nome', 'Tipo', 'Categoria', 'Estoque', 'Valor Total']]
            materials_df = materials_df[['Nome', 'Tipo', 'Categoria', 'Estoque', 'Valor Total']]
            report_df = pd.concat([products_df, materials_df], ignore_index=True)
            headers = ['Nome', 'Tipo', 'Categoria', 'Estoque', 'Valor Total']
            # Pie chart by type
            chart_data = {'type': 'pie', 'df': report_df.groupby('Tipo')['Valor Total'].sum().reset_index(), 
                         'names': 'Tipo', 'values': 'Valor Total', 'title': 'Distribuição de Valor por Tipo'}
        
        # Format values
        if 'Valor Total' in report_df.columns:
            total_value = report_df['Valor Total'].sum()
            totals = [("Total em Estoque", f"R$ {total_value:,.2f}")]
            report_df['Valor Total'] = report_df['Valor Total'].apply(lambda x: f"R$ {x:,.2f}" if pd.notnull(x) else "-")
        if 'Preço Unit.' in report_df.columns:
            report_df['Preço Unit.'] = report_df['Preço Unit.'].apply(lambda x: f"R$ {x:,.2f}" if pd.notnull(x) else "-")
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines, 
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: VENDAS POR PERÍODO
# ============================================================
elif report_key == "sales":
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
        
        query = """
            SELECT s.date as 'Data', p.name as 'Produto', s.quantity as 'Qtd',
                   s.total_price as 'Valor', s.discount as 'Desconto',
                   s.payment_method as 'Pagamento', s.salesperson as 'Vendedor',
                   COALESCE(c.name, 'Consumidor Final') as 'Cliente'
            FROM sales s
            LEFT JOIN products p ON s.product_id = p.id
            LEFT JOIN clients c ON s.client_id = c.id
            WHERE s.date BETWEEN ? AND ?
        """
        params = [start_date, end_date]
        
        if seller_filter != "Todos":
            query += " AND s.salesperson = ?"
            params.append(seller_filter)
        
        query += " ORDER BY s.date DESC"
        
        report_df = pd.read_sql(query, conn, params=params)
        
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
                
                prev_query = """
                    SELECT SUM(total_price) as total FROM sales
                    WHERE date BETWEEN ? AND ?
                """
                prev_params = [prev_start, prev_end]
                if seller_filter != "Todos":
                    prev_query += " AND salesperson = ?"
                    prev_params.append(seller_filter)
                
                prev_total = pd.read_sql(prev_query, conn, params=prev_params).iloc[0]['total'] or 0
                
                if prev_total > 0:
                    variation = ((total_value - prev_total) / prev_total) * 100
                    totals.append(("Variação vs Anterior", f"{variation:+.1f}%"))
                    info_lines["Período Anterior"] = f"{prev_start.strftime('%d/%m/%Y')} a {prev_end.strftime('%d/%m/%Y')}"
            
            # Chart - Sales by day
            report_df_chart = report_df.copy()
            report_df_chart['Data'] = pd.to_datetime(report_df_chart['Data'])
            daily_sales = report_df_chart.groupby(report_df_chart['Data'].dt.date)['Valor'].sum().reset_index()
            daily_sales.columns = ['Data', 'Valor']
            chart_data = {'type': 'line', 'df': daily_sales, 'x': 'Data', 'y': 'Valor', 'title': 'Vendas por Dia'}
            
            # Format
            report_df['Valor'] = report_df['Valor'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Desconto'] = report_df['Desconto'].apply(lambda x: f"R$ {x:,.2f}" if x > 0 else "-")
            report_df['Data'] = pd.to_datetime(report_df['Data']).dt.strftime('%d/%m/%Y')
            
            headers = ['Data', 'Produto', 'Qtd', 'Valor', 'Desconto', 'Pagamento', 'Vendedor', 'Cliente']
        else:
            headers = []
            totals = []
            chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: TOP 10 PRODUTOS VENDIDOS
# ============================================================
elif report_key == "top_products":
    st.subheader("🏆 Top Produtos Vendidos")
    
    # Filters
    c1, c2, c3, c4 = st.columns(4)
    today = date.today()
    start_date = c1.date_input("Data Início", today.replace(day=1), format="DD/MM/YYYY")
    end_date = c2.date_input("Data Fim", today, format="DD/MM/YYYY")
    order_by = c3.selectbox("Ordenar por", ["Quantidade", "Valor"])
    top_limit = c4.number_input("Quantidade", min_value=5, max_value=50, value=10, step=5)
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = f"Top {top_limit} Produtos Vendidos"
        info_lines = {
            "Período": f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}",
            "Ordenado por": order_by,
            "Limite": str(top_limit)
        }
        
        order_col = "total_qty" if order_by == "Quantidade" else "total_value"
        
        query = f"""
            SELECT p.name as 'Produto', p.category as 'Categoria',
                   SUM(s.quantity) as total_qty,
                   SUM(s.total_price) as total_value,
                   COUNT(*) as num_sales
            FROM sales s
            JOIN products p ON s.product_id = p.id
            WHERE s.date BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY {order_col} DESC
            LIMIT ?
        """
        
        report_df = pd.read_sql(query, conn, params=[start_date, end_date, top_limit])
        
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
        else:
            headers = []
            totals = []
            chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: DESPESAS POR CATEGORIA
# ============================================================
elif report_key == "expenses":
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
        
        query = """
            SELECT e.date as 'Data', e.description as 'Descrição', e.category as 'Categoria',
                   COALESCE(s.name, '-') as 'Fornecedor', e.amount as 'Valor'
            FROM expenses e
            LEFT JOIN suppliers s ON e.supplier_id = s.id
            WHERE e.date BETWEEN ? AND ?
        """
        params = [start_date, end_date]
        
        if cat_filter != "Todas":
            query += " AND e.category = ?"
            params.append(cat_filter)
        
        query += " ORDER BY e.date DESC"
        
        report_df = pd.read_sql(query, conn, params=params)
        
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
                
                prev_query = "SELECT SUM(amount) as total FROM expenses WHERE date BETWEEN ? AND ?"
                prev_params = [prev_start, prev_end]
                if cat_filter != "Todas":
                    prev_query += " AND category = ?"
                    prev_params.append(cat_filter)
                
                prev_total = pd.read_sql(prev_query, conn, params=prev_params).iloc[0]['total'] or 0
                
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
        else:
            headers = []
            totals = []
            chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: CONSUMO DE INSUMOS
# ============================================================
elif report_key == "consumption":
    st.subheader("🧪 Relatório de Consumo de Insumos")
    
    # Filters
    c1, c2, c3 = st.columns(3)
    today = date.today()
    start_date = c1.date_input("Data Início", today.replace(day=1), format="DD/MM/YYYY")
    end_date = c2.date_input("Data Fim", today, format="DD/MM/YYYY")
    
    # Get categories for filter
    mat_categories = ["Todas"] + pd.read_sql("SELECT name FROM material_categories ORDER BY name", conn)['name'].tolist()
    cat_filter = c3.selectbox("Categoria", mat_categories)
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Relatório de Consumo de Insumos"
        info_lines = {
            "Período": f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}",
            "Categoria": cat_filter
        }
        
        # Query aggregated consumption (SAIDA = consumption, stored as positive quantity)
        query = """
            SELECT m.name as 'Insumo', 
                   COALESCE(mc.name, 'Geral') as 'Categoria',
                   SUM(it.quantity) as 'Consumido',
                   m.unit as 'Unidade',
                   m.price_per_unit as 'Custo Unit.',
                   SUM(it.quantity) * m.price_per_unit as 'Custo Total'
            FROM inventory_transactions it
            JOIN materials m ON it.material_id = m.id
            LEFT JOIN material_categories mc ON m.category_id = mc.id
            WHERE DATE(it.date) BETWEEN ? AND ?
              AND it.type = 'SAIDA'
        """
        params = [start_date, end_date]
        
        if cat_filter != "Todas":
            query += " AND mc.name = ?"
            params.append(cat_filter)
        
        query += """
            GROUP BY m.id
            HAVING SUM(it.quantity) > 0
            ORDER BY SUM(it.quantity) DESC
        """
        
        report_df = pd.read_sql(query, conn, params=params)
        
        if not report_df.empty:
            total_cost = report_df['Custo Total'].sum()
            total_items = len(report_df)
            
            totals = [
                ("Total de Insumos", str(total_items)),
                ("Custo Total do Período", f"R$ {total_cost:,.2f}")
            ]
            
            # Chart - Bar by consumption
            chart_df = report_df.head(10).copy()  # Top 10
            chart_data = {'type': 'bar_h', 'df': chart_df, 'x': 'Custo Total', 'y': 'Insumo', 
                         'title': 'Top 10 Insumos por Custo'}
            
            # Format
            report_df['Custo Unit.'] = report_df['Custo Unit.'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Custo Total'] = report_df['Custo Total'].apply(lambda x: f"R$ {x:,.2f}")
            
            headers = ['Insumo', 'Categoria', 'Consumido', 'Unidade', 'Custo Unit.', 'Custo Total']
        else:
            headers = []
            totals = []
            chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: HISTÓRICO DE PRODUÇÃO
# ============================================================
elif report_key == "production":
    st.subheader("🔨 Histórico de Produção")
    
    # Filters
    c1, c2 = st.columns(2)
    today = date.today()
    start_date = c1.date_input("Data Início", today.replace(day=1), format="DD/MM/YYYY")
    end_date = c2.date_input("Data Fim", today, format="DD/MM/YYYY")
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Histórico de Produção"
        info_lines = {
            "Período": f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
        }
        
        # Query production history
        query = """
            SELECT DATE(ph.timestamp) as 'Data', 
                   p.name as 'Produto', 
                   p.category as 'Categoria',
                   SUM(ph.quantity) as 'Quantidade',
                   ph.username as 'Usuário'
            FROM production_history ph
            JOIN products p ON ph.product_id = p.id
            WHERE DATE(ph.timestamp) BETWEEN ? AND ?
            GROUP BY DATE(ph.timestamp), ph.product_id, ph.username
            ORDER BY ph.timestamp DESC
        """
        
        report_df = pd.read_sql(query, conn, params=[start_date, end_date])
        
        if not report_df.empty:
            total_produced = report_df['Quantidade'].sum()
            unique_products = report_df['Produto'].nunique()
            
            totals = [
                ("Total Produzido", str(int(total_produced))),
                ("Produtos Diferentes", str(unique_products))
            ]
            
            # Chart - Production by product
            prod_by_product = report_df.groupby('Produto')['Quantidade'].sum().reset_index()
            prod_by_product = prod_by_product.nlargest(10, 'Quantidade')
            chart_data = {'type': 'bar_h', 'df': prod_by_product, 'x': 'Quantidade', 'y': 'Produto', 
                         'title': 'Top 10 Produtos Produzidos'}
            
            # Format date
            report_df['Data'] = pd.to_datetime(report_df['Data']).dt.strftime('%d/%m/%Y')
            
            headers = ['Data', 'Produto', 'Categoria', 'Quantidade', 'Usuário']
        else:
            headers = []
            totals = []
            chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# DISPLAY RESULTS AND EXPORT
# ============================================================
if 'report_data' in st.session_state and st.session_state.report_data:
    data = st.session_state.report_data
    df = data['df']
    
    st.divider()
    
    if not df.empty:
        # Info lines
        for label, value in data['info'].items():
            st.caption(f"**{label}:** {value}")
        
        # Chart (if available)
        if data.get('chart'):
            chart = data['chart']
            st.markdown(f"### 📈 {chart['title']}")
            
            if chart['type'] == 'pie':
                fig = px.pie(chart['df'], names=chart['names'], values=chart['values'], 
                            title=None, hole=0.4)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            
            elif chart['type'] == 'bar':
                fig = px.bar(chart['df'].head(15), x=chart['x'], y=chart['y'], title=None)
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
            
            elif chart['type'] == 'bar_h':
                fig = px.bar(chart['df'], x=chart['x'], y=chart['y'], orientation='h', title=None)
                fig.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
            
            elif chart['type'] == 'line':
                fig = px.line(chart['df'], x=chart['x'], y=chart['y'], title=None, markers=True)
                st.plotly_chart(fig, use_container_width=True)
        
        # Data preview
        st.markdown("### 📋 Dados")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Totals - Display as rows instead of columns to avoid truncation
        if data['totals']:
            st.markdown("### 📊 Resumo")
            total_items = data['totals']
            
            # If many totals (like expenses with subtotals), show as a table
            if len(total_items) > 4:
                totals_df = pd.DataFrame(total_items, columns=['Categoria', 'Valor'])
                st.dataframe(totals_df, use_container_width=True, hide_index=True)
            else:
                # Show as metrics in rows of 2
                for i in range(0, len(total_items), 2):
                    cols = st.columns(2)
                    for j, col in enumerate(cols):
                        if i + j < len(total_items):
                            label, value = total_items[i + j]
                            col.metric(label, value)
        
        st.divider()
        
        # Export buttons
        c_pdf, c_excel = st.columns(2)
        
        with c_pdf:
            # Generate PDF
            pdf_data = df.values.tolist()
            pdf_bytes = reports.generate_report_pdf(
                title=data['title'],
                info_lines=data['info'],
                headers=data['headers'],
                data=pdf_data,
                totals=data['totals'],
                orientation='L' if len(data['headers']) > 5 else 'P'
            )
            
            st.download_button(
                "📄 Exportar PDF",
                data=pdf_bytes,
                file_name=f"{data['title'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        
        with c_excel:
            # Generate Excel
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False, sheet_name='Relatório')
            excel_bytes = excel_buffer.getvalue()
            
            st.download_button(
                "📊 Exportar Excel",
                data=excel_bytes,
                file_name=f"{data['title'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    else:
        st.info("Nenhum dado encontrado para os filtros selecionados.")

conn.close()
