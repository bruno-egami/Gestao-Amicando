import streamlit as st
import pandas as pd
import services.report_service as report_service
from datetime import datetime, date, timedelta

def render_customer_history(conn):
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
        
        headers = []
        totals = []
        chart_data = None

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
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }

def render_suppliers(conn):
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
        
        headers = []
        totals = []
        chart_data = None
        
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
        
        st.session_state.report_data = {
            'df': report_df, 'title': report_title, 'info': info_lines,
            'headers': headers, 'totals': totals, 'chart': chart_data
        }
