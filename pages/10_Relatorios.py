import streamlit as st
import database
import admin_utils
import auth
import views.report_pages.stock as stock_view
import views.report_pages.financial as financial_view
import views.report_pages.production as production_view
import views.report_pages.stakeholders as stakeholders_view
import views.report_pages.tools as tools_view
import views.report_pages.common as common_view

st.set_page_config(page_title="Relatórios", page_icon="📊", layout="wide")

# Apply Global Styles
import utils.styles as styles
styles.apply_custom_style()

admin_utils.render_sidebar_logo()
with database.db_session() as conn:

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
        "Gargalos de Produção": "bottlenecks",
        "Exportar Agenda (.ics)": "calendar_export"
    }

    selected_report = st.selectbox("Selecione o Relatório", list(report_types.keys()))
    report_key = report_types[selected_report]

    st.divider()

    # Dispatcher
    if report_key == "stock":
        stock_view.render_stock_current(conn)
    elif report_key == "sales":
        financial_view.render_sales_period(conn)
    elif report_key == "top_products":
        financial_view.render_top_products(conn)
    elif report_key == "sales_trend":
        financial_view.render_sales_trend(conn)
    elif report_key == "profitability":
        financial_view.render_profitability(conn)
    elif report_key == "seasonality":
        financial_view.render_seasonality(conn)
    elif report_key == "dead_stock":
        stock_view.render_dead_stock(conn)
    elif report_key == "customer_history":
        stakeholders_view.render_customer_history(conn)
    elif report_key == "cash_flow":
        financial_view.render_cash_flow(conn)
    elif report_key == "stock_forecast":
        stock_view.render_stock_forecast(conn)
    elif report_key == "pending_orders":
        financial_view.render_pending_orders(conn)
    elif report_key == "production_cost":
        production_view.render_production_cost(conn)
    elif report_key == "suppliers":
        stakeholders_view.render_suppliers(conn)
    elif report_key == "expenses":
        financial_view.render_expenses(conn)
    elif report_key == "consumption":
        production_view.render_consumption(conn)
    elif report_key == "production":
        production_view.render_production_history(conn)
    elif report_key == "bottlenecks":
        production_view.render_bottlenecks(conn)
    elif report_key == "calendar_export":
        tools_view.render_calendar_export(conn)

    # Render results
    common_view.render_report_result()
