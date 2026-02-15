import streamlit as st
import pandas as pd
import services.product_service as product_service
import services.report_service as report_service
from datetime import datetime, date, timedelta

def render_stock_current(conn):
    st.subheader("📦 Relatório de Estoque Atual")
    
    # Filters
    c1, c2 = st.columns(2)
    stock_type = c1.selectbox("Tipo", ["Todos", "Produtos", "Insumos"])
    show_low_only = c2.checkbox("Mostrar apenas estoque baixo")
    
    if st.button("🔄 Gerar Relatório", type="primary"):
        report_title = "Relatório de Estoque Atual"
        info_lines = {"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Tipo": stock_type}
        
        products_df = pd.DataFrame()
        materials_df = pd.DataFrame()
        
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
            df_mat = product_service.get_all_materials(conn)
            if not df_mat.empty:
                 materials_df = df_mat.copy() # Copy
                 # Columns are already: Nome, Categoria, Estoque, Unidade, Preço Unit., Valor Total
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
        report_df = pd.DataFrame()
        headers = []
        chart_data = None
        totals = []

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
            p_sel = products_df[['Nome', 'Tipo', 'Categoria', 'Estoque', 'Valor Total']] if not products_df.empty else pd.DataFrame()
            m_sel = materials_df[['Nome', 'Tipo', 'Categoria', 'Estoque', 'Valor Total']] if not materials_df.empty else pd.DataFrame()
            
            # Prepare WIP for concat
            w_sel = pd.DataFrame()
            if not wip_df.empty:
                w_sel = wip_df[['Nome', 'Tipo', 'Categoria', 'Estoque', 'Valor Total']]
            
            report_df = pd.concat([p_sel, m_sel, w_sel], ignore_index=True)
            headers = ['Nome', 'Tipo', 'Categoria', 'Estoque', 'Valor Total']
            # Pie chart by type
            if not report_df.empty:
                chart_data = {'type': 'pie', 'df': report_df.groupby('Tipo')['Valor Total'].sum().reset_index(), 
                             'names': 'Tipo', 'values': 'Valor Total', 'title': 'Distribuição de Valor (Matéria-Prima vs Acabado vs WIP)'}
        
        # Format values
        if not report_df.empty:
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

def render_stock_forecast(conn):
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
        
        report_df = pd.DataFrame()
        headers = []
        totals = []
        chart_data = None

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
            
            headers = list(report_df.columns)
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

def render_dead_stock(conn):
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
        report_df = pd.DataFrame()
        headers = []
        totals = []
        chart_data = None

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
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }
