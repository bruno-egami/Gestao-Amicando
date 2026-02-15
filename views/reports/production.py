import streamlit as st
import pandas as pd
import services.production_service as production_service
import services.report_service as report_service
from datetime import datetime, date, timedelta

# --- Caching Helpers ---
@st.cache_data(ttl=300, show_spinner=False)
def get_cached_material_consumption(_conn, start_date, end_date, cat_filter):
    """Fetches material consumption."""
    return report_service.get_material_consumption(_conn, start_date, end_date, cat_filter)

# --- Render Functions ---

def render_consumption(conn):
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
        
        headers = []
        totals = []
        chart_data = None

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
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

def render_production_history(conn):
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
        headers = []

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

def render_bottlenecks(conn):
    st.subheader("⏳ Gargalos de Produção (Lead Time)")
    st.info("Analise há quanto tempo os itens estão parados em cada estágio.")
    
    if st.button("🔄 Analisar Gargalos", type="primary"):
        report_title = "Análise de Gargalos e Lead Time"
        info_lines = {
            "Data da Análise": datetime.now().strftime('%d/%m/%Y %H:%M')
        }
        
        # Get stats
        report_df = production_service.get_stage_duration_stats(conn)
        
        headers = []
        totals = []
        charts = []

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
            st.success("Nenhum item em produção no momento! 🎉")

        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'charts': charts 
        }

def render_production_cost(conn):
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
        
        headers = []
        totals = []
        chart_data = None

        if not report_df.empty:
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
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }
