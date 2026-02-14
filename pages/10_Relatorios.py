import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import database
import admin_utils
import auth
import reports
import io
import services.production_service as production_service
import services.product_service as product_service
import services.report_service as report_service
from datetime import datetime, date, timedelta

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

@st.cache_data(ttl=300, show_spinner=False)
def get_cached_material_consumption(_conn, start_date, end_date, cat_filter):
    """Fetches material consumption."""
    return report_service.get_material_consumption(_conn, start_date, end_date, cat_filter)

st.set_page_config(page_title="Relatórios", page_icon="📊", layout="wide")

# Apply Global Styles
import utils.styles as styles
styles.apply_custom_style()

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
    "Top Produtos Vendidos": "top_products",
    "Análise de Vendas Anual": "sales_trend",
    "Lucratividade por Produto": "profitability",
    "Análise de Sazonalidade": "seasonality",
    "Itens sem Movimentação": "dead_stock",
    "Clientes - Histórico": "customer_history",
    "Fluxo de Caixa": "cash_flow",
    "Previsão de Estoque": "stock_forecast",
    "Encomendas Pendentes": "pending_orders",
    "Custo de Produção": "production_cost",
    "Fornecedores - Compras": "suppliers",
    "Despesas por Categoria": "expenses",
    "Consumo de Insumos": "consumption",
    "Histórico de Produção": "production",
    "Gargalos de Produção": "bottlenecks"
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
            # Use cached service
            df_prod = product_service.get_all_products(conn)
            if not df_prod.empty:
                df_prod = df_prod.copy() # Avoid modifying cache
                df_prod['Valor Total'] = df_prod['stock_quantity'] * df_prod['base_price']
                products_df = df_prod[['name', 'category', 'stock_quantity', 'base_price', 'Valor Total']].rename(
                    columns={'name': 'Nome', 'category': 'Categoria', 'stock_quantity': 'Estoque', 'base_price': 'Preço Unit.'}
                )
                products_df = products_df.sort_values('Nome')
            else:
                products_df = pd.DataFrame(columns=['Nome', 'Categoria', 'Estoque', 'Preço Unit.', 'Valor Total'])
            
            products_df['Tipo'] = 'Produto'
            
            if show_low_only:
                products_df = products_df[products_df['Estoque'] <= 5]
        
        if stock_type in ["Todos", "Insumos"]:
            # Use cached service
            materials_df = product_service.get_all_materials(conn)
            if not materials_df.empty:
                 materials_df = materials_df.copy() # Copy
                 materials_df['Tipo'] = 'Insumo'
                 if show_low_only:
                     materials_df = materials_df[materials_df['Estoque'] <= materials_df['min_stock_alert'].fillna(0)]
            else:
                 materials_df = pd.DataFrame(columns=['Nome', 'Categoria', 'Estoque', 'Unidade', 'Preço Unit.', 'Valor Total', 'Tipo'])
        
        # Calculate WIP Value (Work In Process)
        wip_df = pd.DataFrame()
        if stock_type in ["Todos", "Produtos"]:

            # Use cached service
            wip_df = product_service.get_wip_stock_value(conn)

        # Combine or select
        if stock_type == "Produtos":
            report_df = pd.concat([products_df, wip_df], ignore_index=True) if not wip_df.empty else products_df
            report_df = report_df[['Nome', 'Categoria', 'Estoque', 'Preço Unit.', 'Valor Total']]
            headers = ['Nome', 'Categoria', 'Estoque', 'Preço Unit.', 'Valor Total']
            chart_data = {'type': 'bar', 'df': report_df, 'x': 'Nome', 'y': 'Valor Total', 'title': 'Valor em Estoque (Acabados + WIP)'}
        elif stock_type == "Insumos":
            report_df = materials_df[['Nome', 'Categoria', 'Estoque', 'Unidade', 'Preço Unit.', 'Valor Total']]
            headers = ['Nome', 'Categoria', 'Estoque', 'Unidade', 'Preço Unit.', 'Valor Total']
            chart_data = {'type': 'bar', 'df': materials_df, 'x': 'Nome', 'y': 'Valor Total', 'title': 'Valor em Estoque por Insumo'}
        else:
            products_df = products_df[['Nome', 'Tipo', 'Categoria', 'Estoque', 'Valor Total']]
            materials_df = materials_df[['Nome', 'Tipo', 'Categoria', 'Estoque', 'Valor Total']]
            
            # Prepare WIP for concat
            if not wip_df.empty:
                wip_df = wip_df[['Nome', 'Tipo', 'Categoria', 'Estoque', 'Valor Total']]
            
            report_df = pd.concat([products_df, materials_df, wip_df], ignore_index=True)
            headers = ['Nome', 'Tipo', 'Categoria', 'Estoque', 'Valor Total']
            # Pie chart by type
            chart_data = {'type': 'pie', 'df': report_df.groupby('Tipo')['Valor Total'].sum().reset_index(), 
                         'names': 'Tipo', 'values': 'Valor Total', 'title': 'Distribuição de Valor (Matéria-Prima vs Acabado vs WIP)'}
        
        # Format values
        if 'Valor Total' in report_df.columns:
            total_value = report_df['Valor Total'].sum()
            
            # Totals breakdown
            totals = [("Total Geral Ativos", f"R$ {total_value:,.2f}")]
            
            if 'Tipo' in report_df.columns:
                by_type = report_df.groupby('Tipo')['Valor Total'].sum()
                for t, v in by_type.items():
                    totals.append((f"Total {t}", f"R$ {v:,.2f}"))
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
        
        # Use cached function
        report_df = get_cached_sales_data(conn, start_date, end_date, seller_filter)
        
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
        
        # Use cached function
        report_df = get_cached_expenses(conn, start_date, end_date, cat_filter)
        
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
        
        # Use cached function
        report_df = get_cached_material_consumption(conn, start_date, end_date, cat_filter)
        
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
    c1, c2, c3 = st.columns(3)
    today = date.today()
    start_date = c1.date_input("Data Início", today.replace(day=1), format="DD/MM/YYYY")
    end_date = c2.date_input("Data Fim", today, format="DD/MM/YYYY")
    top_limit = c3.number_input("Top Produtos no Gráfico", min_value=5, value=10, step=5)
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Histórico de Produção"
        info_lines = {
            "Período": f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
        }
        
        # Query production history
        # Use cached service function
        report_df = production_service.get_production_log_report(conn, start_date, end_date)
        totals = []
        charts = []
        
        # 1. Main Production Stats (if any)
        if not report_df.empty:
            total_produced = report_df['Quantidade'].sum()
            unique_products = report_df['Produto'].nunique()
            
            totals.append(("Total Produzido", str(int(total_produced))))
            totals.append(("Produtos Diferentes", str(unique_products)))
            
            # Chart - Production by product
            prod_by_product = report_df.groupby('Produto')['Quantidade'].sum().reset_index()
            prod_by_product = prod_by_product.nlargest(top_limit, 'Quantidade')
            charts.append({'type': 'bar_h', 'df': prod_by_product, 'x': 'Quantidade', 'y': 'Produto', 
                          'title': f'Top {top_limit} Produtos Produzidos'})
            
            # Format date
            report_df['Data'] = pd.to_datetime(report_df['Data']).dt.strftime('%d/%m/%Y')
            headers = ['Data', 'Produto', 'Categoria', 'Quantidade', 'Usuário']
        else:
            headers = []

        # 2. Loss Statistics (Quality) - Independent of main production
        loss_df = production_service.get_loss_statistics(conn, start_date, end_date)
            
        if not loss_df.empty:
            total_losses = loss_df['Quantidade'].sum()
            # Calculate total produced (handle if report_df was empty)
            prod_qty = report_df['Quantidade'].sum() if not report_df.empty else 0
            
            loss_rate = (total_losses / (prod_qty + total_losses) * 100) if (prod_qty + total_losses) > 0 else 0
            totals.append(("Total Perdas (Qtd)", str(int(total_losses))))
            totals.append(("Taxa de Perda Global", f"{loss_rate:.1f}%"))
            
            # Pizza: Motivos
            loss_by_reason = loss_df.groupby('Motivo')['Quantidade'].sum().reset_index()
            charts.append({'type': 'pie', 'df': loss_by_reason, 'names': 'Motivo', 'values': 'Quantidade', 
                             'title': 'Distribuição de Perdas por Motivo'})
            
            # Bar: Stage
            loss_by_stage = loss_df.groupby('Estágio')['Quantidade'].sum().reset_index()
            charts.append({'type': 'bar', 'df': loss_by_stage, 'x': 'Estágio', 'y': 'Quantidade', 
                             'title': 'Perdas por Estágio de Produção'})

        # 3. Productivity History (Trend) - Independent (Last 180 days)
        hist_df = production_service.get_production_history_stats(conn, days=180)
        if not hist_df.empty:
            charts.append({'type': 'line', 'df': hist_df, 'x': 'Mes', 'y': 'Quantidade', 
                          'title': 'Tendência de Produtividade (Últimos 6 Meses)'})

        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'charts': charts 
        }

# ============================================================
# REPORT: GARGALOS DE PRODUÇÃO (LEAD TIME)
# ============================================================
elif report_key == "bottlenecks":
    st.subheader("⏳ Gargalos de Produção (Lead Time)")
    st.info("Analise há quanto tempo os itens estão parados em cada estágio.")
    
    if st.button("🔄 Analisar Gargalos", type="primary"):
        report_title = "Análise de Gargalos e Lead Time"
        info_lines = {
            "Data da Análise": datetime.now().strftime('%d/%m/%Y %H:%M')
        }
        
        # Get stats
        report_df = production_service.get_stage_duration_stats(conn)
        
        if not report_df.empty:
            # Sort by days descending for the table
            report_df = report_df.sort_values('Dias no Estágio', ascending=False)
            
            # Avg days by stage for chart
            avg_days = report_df.groupby('Estágio')['Dias no Estágio'].mean().reset_index()
            avg_days = avg_days.sort_values('Dias no Estágio', ascending=True)
            
            totals = [
                ("Total Itens em WIP", str(len(report_df))),
                ("Média Geral de Dias", f"{report_df['Dias no Estágio'].mean():.1f} dias"),
                ("Maior Gargalo", f"{report_df['Dias no Estágio'].max()} dias")
            ]
            
            # Chart - Horizontal Bar for Avg Days
            chart_bottleneck = {
                'type': 'bar_h', 
                'df': avg_days, 
                'x': 'Dias no Estágio', 
                'y': 'Estágio', 
                'title': 'Tempo Médio de Permanência por Estágio (Dias)'
            }
            
            headers = ['Produto', 'Estágio', 'Quantidade', 'Dias no Estágio', 'Data Entrada']
            charts = [chart_bottleneck]
        else:
            headers = []
            totals = []
            charts = []
            st.success("Nenhum item em produção no momento! 🎉")

        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'charts': charts 
        }

# ============================================================
# REPORT: LUCRATIVIDADE POR PRODUTO (MARGEM DE LUCRO)
# ============================================================
elif report_key == "profitability":
    st.subheader("💰 Relatório de Lucratividade por Produto")
    st.info("Analisa a margem de lucro comparando custos de produção com preços de venda.")
    
    # Filters
    c1, c2 = st.columns(2)
    categories = ["Todas"] + pd.read_sql("SELECT DISTINCT category FROM products WHERE category IS NOT NULL", conn)['category'].tolist()
    cat_filter = c1.selectbox("Categoria", categories)
    
    margin_filter = c2.selectbox("Filtrar por Margem", ["Todas", "Margem Alta (>50%)", "Margem Média (20-50%)", "Margem Baixa (<20%)", "Margem Negativa"])
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Relatório de Lucratividade"
        info_lines = {
            "Data": datetime.now().strftime('%d/%m/%Y %H:%M'),
            "Categoria": cat_filter
        }
        
        # Query products with cost calculation
        # Cost is calculated from product_recipes (materials used)
        report_df = report_service.get_product_profitability(conn, cat_filter)
        
        if not report_df.empty:
            # Calculate margin columns
            report_df['Margem R$'] = report_df['Preço Venda'] - report_df['Custo Produção']
            report_df['Margem %'] = report_df.apply(
                lambda row: (row['Margem R$'] / row['Preço Venda'] * 100) if row['Preço Venda'] > 0 else 0,
                axis=1
            )
            
            # Apply margin filter
            if margin_filter == "Margem Alta (>50%)":
                report_df = report_df[report_df['Margem %'] > 50]
            elif margin_filter == "Margem Média (20-50%)":
                report_df = report_df[(report_df['Margem %'] >= 20) & (report_df['Margem %'] <= 50)]
            elif margin_filter == "Margem Baixa (<20%)":
                report_df = report_df[(report_df['Margem %'] >= 0) & (report_df['Margem %'] < 20)]
            elif margin_filter == "Margem Negativa":
                report_df = report_df[report_df['Margem %'] < 0]
            
            # Totals
            avg_margin = report_df['Margem %'].mean()
            total_products = len(report_df)
            negative_count = len(report_df[report_df['Margem %'] < 0])
            
            totals = [
                ("Total Produtos", str(total_products)),
                ("Margem Média", f"{avg_margin:.1f}%"),
                ("Produtos com Margem Negativa", str(negative_count))
            ]
            
            # Category summary
            if cat_filter == "Todas" and len(report_df['Categoria'].unique()) > 1:
                cat_margins = report_df.groupby('Categoria')['Margem %'].mean().reset_index()
                cat_margins = cat_margins.sort_values('Margem %', ascending=False)
                for _, row in cat_margins.iterrows():
                    totals.append((f"Margem Média - {row['Categoria']}", f"{row['Margem %']:.1f}%"))
            
            # Chart - Top 10 products by margin
            chart_df = report_df.nlargest(10, 'Margem %')[['Produto', 'Margem %']].copy()
            chart_data = {
                'type': 'bar_h', 
                'df': chart_df, 
                'x': 'Margem %', 
                'y': 'Produto', 
                'title': 'Top 10 Produtos por Margem de Lucro (%)'
            }
            
            # Format for display
            report_df['Preço Venda'] = report_df['Preço Venda'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Custo Produção'] = report_df['Custo Produção'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Margem R$'] = report_df['Margem R$'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Margem %'] = report_df['Margem %'].apply(lambda x: f"{x:.1f}%")
            
            # Remove id column for display
            report_df = report_df.drop(columns=['id'])
            
            headers = ['Produto', 'Categoria', 'Preço Venda', 'Custo Produção', 'Margem R$', 'Margem %', 'Estoque']
        else:
            headers = []
            totals = []
            chart_data = None
            
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: ANÁLISE DE VENDAS ANUAL
# ============================================================
elif report_key == "sales_trend":
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
            else:
                report_df = pd.DataFrame()
                headers = []
                totals = []
                chart_data = None
        
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
            else:
                headers = []
                totals = []
                chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: LUCRATIVIDADE POR PRODUTO
# ============================================================
elif report_key == "profitability":
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
        else:
            headers = []
            totals = []
            chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: CLIENTES - HISTÓRICO
# ============================================================
elif report_key == "customer_history":
    st.subheader("🤝 Clientes - Histórico de Compras")
    
    # Filters
    c1, c2 = st.columns(2)
    today = date.today()
    start_date = c1.date_input("Data Início", today.replace(month=1, day=1), format="DD/MM/YYYY")
    end_date = c2.date_input("Data Fim", today, format="DD/MM/YYYY")
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Histórico de Compras por Cliente"
        info_lines = {
            "Período": f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
        }
        
        report_df = report_service.get_customer_history(conn, start_date, end_date)
        
        if not report_df.empty:
            report_df.columns = ['Cliente', 'Nº Compras', 'Qtd Itens', 'Valor Total', 'Ticket Médio', 'Última Compra']
            
            # Totals
            total_clients = len(report_df)
            total_sales = report_df['Nº Compras'].sum()
            total_value = report_df['Valor Total'].sum()
            avg_ticket = report_df['Ticket Médio'].mean()
            
            totals = [
                ("Total Clientes", str(total_clients)),
                ("Total Vendas", str(int(total_sales))),
                ("Valor Total", f"R$ {total_value:,.2f}"),
                ("Ticket Médio", f"R$ {avg_ticket:,.2f}")
            ]
            
            # Chart - Top clients by value
            chart_df = report_df.head(15).copy()
            chart_data = {
                'type': 'bar_h', 
                'df': chart_df, 
                'x': 'Valor Total', 
                'y': 'Cliente',
                'title': 'Top 15 Clientes por Valor'
            }
            
            # Format values
            report_df['Valor Total'] = report_df['Valor Total'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Ticket Médio'] = report_df['Ticket Médio'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Última Compra'] = pd.to_datetime(report_df['Última Compra']).dt.strftime('%d/%m/%Y')
            
            headers = list(report_df.columns)
        else:
            headers = []
            totals = []
            chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: FLUXO DE CAIXA
# ============================================================
elif report_key == "cash_flow":
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
            display_format = '%d/%m/%Y'
        elif view_type == "Semana":
            date_format = '%Y-%W'
            display_format = 'Sem %W/%Y'
        else:  # Mês
            date_format = '%Y-%m'
            display_format = '%m/%Y'
        
        # Get sales (income) and expenses
        flow_data = report_service.get_cash_flow_data(conn, start_date, end_date, date_format)
        sales_df = flow_data['sales']
        expenses_df = flow_data['expenses']
        
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
        else:
            report_df = pd.DataFrame()
            headers = []
            totals = []
            chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: PREVISÃO DE ESTOQUE
# ============================================================
elif report_key == "stock_forecast":
    st.subheader("📦 Previsão de Estoque")
    
    # Filters
    c1, c2 = st.columns(2)
    
    item_type = c1.selectbox("Tipo de Item", ["Produtos", "Insumos"])
    period_days = c2.number_input("Período de Análise (dias)", min_value=30, max_value=365, value=90, step=30)
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Previsão de Estoque"
        cutoff_date = (date.today() - timedelta(days=period_days)).isoformat()
        info_lines = {
            "Tipo": item_type,
            "Período de Análise": f"Últimos {period_days} dias"
        }
        
        if item_type == "Produtos":
            # Products: based on average sales
            report_df = report_service.get_stock_forecast_products(conn, period_days, cutoff_date)
            
            if not report_df.empty:
                # Calculate days until stockout
                report_df['DiasRestantes'] = report_df.apply(
                    lambda x: int(x['EstoqueAtual'] / x['MediaDiaria']) if x['MediaDiaria'] > 0 else 999,
                    axis=1
                )
                report_df['DataPrevista'] = report_df.apply(
                    lambda x: (date.today() + timedelta(days=x['DiasRestantes'])).strftime('%d/%m/%Y') if x['DiasRestantes'] < 999 else 'Sem previsão',
                    axis=1
                )
                
                # Sort by urgency
                report_df = report_df.sort_values('DiasRestantes')
                
                report_df.columns = ['Produto', 'Categoria', 'Estoque', 'Vendido', 'Média/Dia', 'Dias Rest.', 'Data Prev.']
                
        else:  # Insumos
            # Materials: based on average consumption
            report_df = report_service.get_stock_forecast_materials(conn, period_days, cutoff_date)
            
            if not report_df.empty:
                # Calculate days until stockout
                report_df['DiasRestantes'] = report_df.apply(
                    lambda x: int(x['EstoqueAtual'] / x['MediaDiaria']) if x['MediaDiaria'] > 0 else 999,
                    axis=1
                )
                report_df['DataPrevista'] = report_df.apply(
                    lambda x: (date.today() + timedelta(days=x['DiasRestantes'])).strftime('%d/%m/%Y') if x['DiasRestantes'] < 999 else 'Sem previsão',
                    axis=1
                )
                
                # Sort by urgency
                report_df = report_df.sort_values('DiasRestantes')
                
                report_df.columns = ['Insumo', 'Categoria', 'Estoque', 'Unidade', 'Consumido', 'Média/Dia', 'Dias Rest.', 'Data Prev.']
        
        if not report_df.empty:
            # Items at risk (less than 30 days)
            at_risk = len(report_df[report_df['Dias Rest.'] < 30])
            low_stock = len(report_df[report_df['Dias Rest.'] < 7])
            
            totals = [
                ("Total de Itens", str(len(report_df))),
                ("Em Risco (<30 dias)", str(at_risk)),
                ("Críticos (<7 dias)", str(low_stock))
            ]
            
            # Chart - Items by days remaining
            if len(report_df) > 0:
                chart_df = report_df.head(15).copy()
                chart_data = {
                    'type': 'bar_h', 
                    'df': chart_df, 
                    'x': 'Dias Rest.', 
                    'y': report_df.columns[0],  # Produto or Insumo
                    'title': 'Previsão de Esgotamento (dias)'
                }
            else:
                chart_data = None
            
            headers = list(report_df.columns)
        else:
            headers = []
            totals = []
            chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: ITENS SEM MOVIMENTAÇÃO
# ============================================================
elif report_key == "dead_stock":
    st.subheader("⚠️ Itens sem Movimentação")
    
    # Filters
    c1, c2 = st.columns(2)
    
    # Period filter
    period_options = {
        "Último Ano": 365,
        "Últimos 6 Meses": 180,
        "Últimos 3 Meses": 90,
        "Último Mês": 30
    }
    selected_period = c1.selectbox("Período sem Movimento", list(period_options.keys()))
    days = period_options[selected_period]
    
    # Type filter
    item_type = c2.selectbox("Tipo de Item", ["Todos", "Produtos", "Insumos"])
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Itens sem Movimentação"
        cutoff_date = (date.today() - timedelta(days=days)).isoformat()
        info_lines = {
            "Período": selected_period,
            "Data de Corte": (date.today() - timedelta(days=days)).strftime('%d/%m/%Y'),
            "Tipo": item_type
        }
        
        dfs = []
        
        # Products without sales
        if item_type in ["Todos", "Produtos"]:
            products_df = report_service.get_dead_stock_products(conn, cutoff_date)
            if not products_df.empty:
                products_df['Tipo'] = 'Produto'
                products_df['Última Venda'] = products_df['Última Venda'].apply(
                    lambda x: pd.to_datetime(x).strftime('%d/%m/%Y') if pd.notnull(x) and x else 'Nunca'
                )
                dfs.append(products_df)
        
        # Materials without consumption
        if item_type in ["Todos", "Insumos"]:
            materials_df = report_service.get_dead_stock_materials(conn, cutoff_date)
            if not materials_df.empty:
                materials_df['Tipo'] = 'Insumo'
                materials_df['Último Consumo'] = materials_df['Último Consumo'].apply(
                    lambda x: pd.to_datetime(x).strftime('%d/%m/%Y') if pd.notnull(x) and x else 'Nunca'
                )
                # Rename column for consistency
                materials_df = materials_df.rename(columns={'Último Consumo': 'Última Movim.'})
                dfs.append(materials_df)
        
        # Combine results
        if dfs:
            if item_type == "Produtos":
                report_df = dfs[0]
                report_df = report_df.rename(columns={'Última Venda': 'Última Movim.'})
            elif item_type == "Insumos":
                report_df = dfs[0]
            else:
                # Normalize columns for both
                if len(dfs) == 2:
                    dfs[0] = dfs[0].rename(columns={'Última Venda': 'Última Movim.'})
                    report_df = pd.concat(dfs, ignore_index=True)
                else:
                    report_df = dfs[0]
                    if 'Última Venda' in report_df.columns:
                        report_df = report_df.rename(columns={'Última Venda': 'Última Movim.'})
            
            # Sort by value stuck
            report_df = report_df.sort_values('Valor Parado', ascending=False)
            
            # Calculate totals
            total_items = len(report_df)
            total_value = report_df['Valor Parado'].sum()
            
            totals = [
                ("Total de Itens Parados", str(total_items)),
                ("Valor Total Parado", f"R$ {total_value:,.2f}")
            ]
            
            # Chart - Pie by type (if both types)
            if item_type == "Todos" and 'Tipo' in report_df.columns:
                by_type = report_df.groupby('Tipo')['Valor Parado'].sum().reset_index()
                chart_data = {
                    'type': 'pie', 
                    'df': by_type, 
                    'names': 'Tipo', 
                    'values': 'Valor Parado',
                    'title': 'Valor Parado por Tipo'
                }
            else:
                # Bar chart of top items
                chart_df = report_df.head(15).copy()
                chart_data = {
                    'type': 'bar_h', 
                    'df': chart_df, 
                    'x': 'Valor Parado', 
                    'y': 'Nome',
                    'title': 'Maiores Valores Parados'
                }
            
            # Format values
            report_df['Preço'] = report_df['Preço'].apply(lambda x: f"R$ {x:,.2f}" if pd.notnull(x) else "-")
            report_df['Valor Parado'] = report_df['Valor Parado'].apply(lambda x: f"R$ {x:,.2f}" if pd.notnull(x) else "-")
            
            headers = list(report_df.columns)
        else:
            report_df = pd.DataFrame()
            headers = []
            totals = []
            chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: ENCOMENDAS PENDENTES
# ============================================================
elif report_key == "pending_orders":
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
        else:
            headers = []
            totals = []
            chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: CUSTO DE PRODUÇÃO
# ============================================================
elif report_key == "production_cost":
    st.subheader("🏭 Custo de Produção")
    
    st.info("Este relatório mostra o custo de insumos consumidos na produção de cada produto.")
    
    # Filters
    c1, c2 = st.columns(2)
    today = date.today()
    start_date = c1.date_input("Data Início", today.replace(day=1), format="DD/MM/YYYY")
    end_date = c2.date_input("Data Fim", today, format="DD/MM/YYYY")
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Custo de Produção por Produto"
        info_lines = {
            "Período": f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
        }
        
        # Get production with material costs from inventory transactions
        report_df = report_service.get_production_cost_data(conn, start_date, end_date)
        
        if not report_df.empty:
            # Get material consumption in the same period as an estimate
            # Get material consumption in the same period as an estimate
            total_material_cost = report_service.get_period_material_cost(conn, start_date, end_date)
            
            # Distribute material cost proportionally by production quantity
            total_produced = report_df['QtdProduzida'].sum()
            if total_produced > 0:
                report_df['CustoInsumos'] = (report_df['QtdProduzida'] / total_produced) * total_material_cost
                report_df['CustoUnit'] = report_df['CustoInsumos'] / report_df['QtdProduzida']
                report_df['MargemBruta'] = report_df['ReceitaPotencial'] - report_df['CustoInsumos']
                report_df['Margem%'] = ((report_df['MargemBruta'] / report_df['ReceitaPotencial']) * 100).round(1)
            else:
                report_df['CustoInsumos'] = 0
                report_df['CustoUnit'] = 0
                report_df['MargemBruta'] = 0
                report_df['Margem%'] = 0
            
            report_df.columns = ['Produto', 'Categoria', 'Qtd', 'Preço Venda', 'Receita Pot.', 
                                'Custo Insumos', 'Custo Unit.', 'Margem Bruta', 'Margem %']
            
            # Totals
            total_revenue = report_df['Receita Pot.'].sum()
            total_cost = report_df['Custo Insumos'].sum()
            total_margin = report_df['Margem Bruta'].sum()
            
            totals = [
                ("Receita Potencial", f"R$ {total_revenue:,.2f}"),
                ("Custo Insumos", f"R$ {total_cost:,.2f}"),
                ("Margem Bruta Total", f"R$ {total_margin:,.2f}")
            ]
            
            # Chart - Margin by product
            chart_data = {
                'type': 'bar_h', 
                'df': report_df, 
                'x': 'Margem Bruta', 
                'y': 'Produto',
                'title': 'Margem Bruta por Produto'
            }
            
            # Format values
            for col in ['Preço Venda', 'Receita Pot.', 'Custo Insumos', 'Custo Unit.', 'Margem Bruta']:
                report_df[col] = report_df[col].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Margem %'] = report_df['Margem %'].apply(lambda x: f"{x}%")
            
            headers = list(report_df.columns)
        else:
            headers = []
            totals = []
            chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: ANÁLISE DE SAZONALIDADE
# ============================================================
elif report_key == "seasonality":
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
        else:
            headers = []
            totals = []
            chart_data = None
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

# ============================================================
# REPORT: FORNECEDORES - COMPRAS
# ============================================================
elif report_key == "suppliers":
    st.subheader("🏪 Fornecedores - Compras")
    
    # Filters
    c1, c2 = st.columns(2)
    today = date.today()
    start_date = c1.date_input("Data Início", today.replace(month=1, day=1), format="DD/MM/YYYY")
    end_date = c2.date_input("Data Fim", today, format="DD/MM/YYYY")
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Compras por Fornecedor"
        info_lines = {
            "Período": f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
        }
        
        # Get expenses by supplier (purchases are usually in "Compra de Insumo" category)
        report_df = report_service.get_supplier_purchases(conn, start_date, end_date)
        
        if not report_df.empty:
            report_df.columns = ['Fornecedor', 'Nº Compras', 'Valor Total', 'Média/Compra', 'Última Compra']
            
            # Totals
            total_suppliers = len(report_df[report_df['Fornecedor'] != 'Sem Fornecedor'])
            total_purchases = report_df['Nº Compras'].sum()
            total_value = report_df['Valor Total'].sum()
            
            totals = [
                ("Fornecedores Ativos", str(total_suppliers)),
                ("Total Compras", str(int(total_purchases))),
                ("Valor Total", f"R$ {total_value:,.2f}")
            ]
            
            # Chart - Top suppliers by value
            chart_df = report_df.head(10).copy()
            chart_data = {
                'type': 'bar_h', 
                'df': chart_df, 
                'x': 'Valor Total', 
                'y': 'Fornecedor',
                'title': 'Top 10 Fornecedores por Valor'
            }
            
            # Format values
            report_df['Valor Total'] = report_df['Valor Total'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Média/Compra'] = report_df['Média/Compra'].apply(lambda x: f"R$ {x:,.2f}")
            report_df['Última Compra'] = pd.to_datetime(report_df['Última Compra']).dt.strftime('%d/%m/%Y')
            
            headers = list(report_df.columns)
        else:
            # Try broader category
            report_df = report_service.get_supplier_purchases_all(conn, start_date, end_date)
            
            if not report_df.empty:
                report_df.columns = ['Fornecedor', 'Nº Compras', 'Valor Total', 'Média/Compra', 'Última Compra']
                
                total_suppliers = len(report_df)
                total_purchases = report_df['Nº Compras'].sum()
                total_value = report_df['Valor Total'].sum()
                
                totals = [
                    ("Fornecedores Ativos", str(total_suppliers)),
                    ("Total Compras", str(int(total_purchases))),
                    ("Valor Total", f"R$ {total_value:,.2f}")
                ]
                
                chart_df = report_df.head(10).copy()
                chart_data = {
                    'type': 'bar_h', 
                    'df': chart_df, 
                    'x': 'Valor Total', 
                    'y': 'Fornecedor',
                    'title': 'Top 10 Fornecedores por Valor'
                }
                
                report_df['Valor Total'] = report_df['Valor Total'].apply(lambda x: f"R$ {x:,.2f}")
                report_df['Média/Compra'] = report_df['Média/Compra'].apply(lambda x: f"R$ {x:,.2f}")
                report_df['Última Compra'] = pd.to_datetime(report_df['Última Compra']).dt.strftime('%d/%m/%Y')
                
                headers = list(report_df.columns)
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
        
        # Charts
        charts_to_render = []
        if data.get('charts'):
            charts_to_render = data['charts']
        elif data.get('chart'):
            charts_to_render = [data['chart']]
            
        for i, chart in enumerate(charts_to_render):
            st.markdown(f"### 📈 {chart['title']}")
            
            fig = None
            if chart['type'] == 'pie':
                fig = px.pie(chart['df'], names=chart['names'], values=chart['values'], 
                            title=None, hole=0.4)
                fig.update_traces(textposition='inside', textinfo='percent+label')
            
            elif chart['type'] == 'bar':
                fig = px.bar(chart['df'].head(15), x=chart['x'], y=chart['y'], title=None)
                fig.update_layout(xaxis_tickangle=-45)
            
            elif chart['type'] == 'bar_h':
                fig = px.bar(chart['df'], x=chart['x'], y=chart['y'], orientation='h', title=None,
                            text=chart['x'])  # Show values on bars
                fig.update_layout(
                    yaxis={'categoryorder': 'total ascending'},
                    margin=dict(l=200, r=20, t=20, b=40),  # More space for labels
                    height=max(400, len(chart['df']) * 35)  # Dynamic height based on items
                )
                fig.update_traces(textposition='outside', texttemplate='%{text:.0f}')
            
            elif chart['type'] == 'line':
                fig = px.line(chart['df'], x=chart['x'], y=chart['y'], title=None, markers=True)
            
            elif chart['type'] == 'grouped_bar':
                fig = px.bar(chart['df'], x=chart['x'], y=chart['y'], color=chart.get('color'),
                            barmode='group', title=None)
                fig.update_layout(
                    xaxis_tickangle=-45,
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                    height=500
                )
            
            if fig:
                # Style for better readability - white text for dark theme
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',  # Transparent background
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(size=14, color='white'),
                    yaxis=dict(tickfont=dict(size=13, color='white')),
                    xaxis=dict(tickfont=dict(size=12, color='white'))
                )
                # White text on bar labels for visibility
                fig.update_traces(textfont=dict(color='white', size=13))
                st.plotly_chart(fig, use_container_width=True)
                
                # Save chart as image for PDF
                try:
                    # Larger size for better PDF quality
                    chart_height = max(500, len(chart.get('df', [])) * 40) if chart['type'] == 'bar_h' else 500
                    chart_image_bytes = fig.to_image(format="png", width=1000, height=chart_height, scale=2)
                except Exception:
                    # Kaleido might not be installed - PDF will be without chart
                    chart_image_bytes = None
        
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
            # Generate PDF with chart
            pdf_data = df.values.tolist()
            pdf_bytes = reports.generate_report_pdf(
                title=data['title'],
                info_lines=data['info'],
                headers=data['headers'],
                data=pdf_data,
                totals=data['totals'],
                orientation='L' if len(data['headers']) > 5 else 'P',
                chart_image=chart_image_bytes
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
