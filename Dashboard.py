import streamlit as st
import database
import pandas as pd
from datetime import date
import admin_utils

# Page config
st.set_page_config(
    page_title="Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

database.init_db()

# --- SIDEBAR ---
with st.sidebar:
    admin_utils.render_sidebar_logo()
    st.title("Acesso")
    mode = st.radio("Modo de Visão", ["Operacional", "Administrador"])
    
    if mode == "Administrador":
        if not admin_utils.check_password():
            st.stop()
            
        st.divider()
        st.caption("Filtros Financeiros")
        ini_date = st.date_input("Início", date.today().replace(day=1))
        end_date = st.date_input("Fim", date.today())
            
        if st.checkbox("Sair (Logout)"):
            del st.session_state["password_correct"]
            st.rerun()

    st.info("ℹ️ Dashboard focado em operações (Encomendas e Estoque).")

# --- MAIN CONTENT ---
admin_utils.render_header_logo()
st.title("📊 Dashboard")
st.write(f"Hoje: **{date.today().strftime('%d/%m/%Y')}**")

conn = database.get_connection()

if mode == "Administrador":
    st.markdown("### 💰 Resumo Financeiro")
    try:
        # Sales
        sales_val = pd.read_sql(f"SELECT sum(total_price) as val FROM sales WHERE date BETWEEN '{ini_date}' AND '{end_date}'", conn).iloc[0]['val'] or 0.0
        # Expenses
        exps_val = pd.read_sql(f"SELECT sum(amount) as val FROM expenses WHERE date BETWEEN '{ini_date}' AND '{end_date}'", conn).iloc[0]['val'] or 0.0
        balance = sales_val - exps_val
        
        c_fin1, c_fin2, c_fin3 = st.columns(3)
        c_fin1.metric("Faturamento", f"R$ {sales_val:.2f}")
        c_fin2.metric("Despesas", f"R$ {exps_val:.2f}")
        c_fin3.metric("Balanço", f"R$ {balance:.2f}", delta=f"{balance:.2f}")
        
        st.divider()
    except Exception as e:
        st.error(f"Erro no financeiro: {e}")


try:
    # --- QUERIES ---
    
    # 1. Pending Orders (with items concatenation)
    # We need to process in Python or use GROUP_CONCAT if SQLite supports it (it does).
    orders_df = pd.read_sql("""
        SELECT co.id, c.name as Client, co.date_due as DueDate, co.status,
               GROUP_CONCAT(ci.quantity || 'x ' || p.name, ', ') as Items
        FROM commission_orders co
        JOIN clients c ON co.client_id = c.id
        LEFT JOIN commission_items ci ON co.id = ci.order_id
        LEFT JOIN products p ON ci.product_id = p.id
        WHERE co.status != 'Entregue'
        GROUP BY co.id
        ORDER BY co.date_due ASC
    """, conn)
    
    # 2. Low Stock Materials (Filter out 'Mão de Obra', 'Queima', etc.)
    # Assuming 'type' column exists and we want only 'Material'
    materials_df = pd.read_sql("""
        SELECT name, stock_level, min_stock_alert, unit 
        FROM materials 
        WHERE type = 'Material'
        ORDER BY stock_level ASC
    """, conn)
    
    # Filter Low Stock
    low_stock_materials = materials_df[materials_df['stock_level'] <= materials_df['min_stock_alert']].copy()
    
    # 3. Products Stock
    products_df = pd.read_sql("SELECT name, stock_quantity, base_price FROM products ORDER BY name", conn)

    # --- METRICS ROW ---
    c1, c2, c3 = st.columns(3)
    
    pending_count = len(orders_df)
    low_stock_count = len(low_stock_materials)
    total_products = products_df['stock_quantity'].sum()
    
    c1.metric("📦 Encomendas Pendentes", pending_count)
    c2.metric("⚠️ Insumos em Alerta", low_stock_count, delta_color="inverse")
    c3.metric("🏺 Peças em Estoque", int(total_products))

    st.divider()

    # --- DETAIL COLUMNS ---
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.subheader("📋 Encomendas em Aberto")
        if not orders_df.empty:
            # Format Date
            orders_df['DueDate'] = pd.to_datetime(orders_df['DueDate']).dt.strftime('%d/%m/%Y')
            
            # Simple Table
            st.dataframe(
                orders_df[['Client', 'Items', 'DueDate', 'status']],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Client": "Cliente",
                    "Items": "Resumo do Pedido",
                    "DueDate": "Prazo",
                    "status": "Status"
                }
            )
            
            # Warn about delayed
            delayed = orders_df[pd.to_datetime(orders_df['DueDate'], format='%d/%m/%Y').dt.date < date.today()]
            if not delayed.empty:
                st.error(f"⚠️ {len(delayed)} Encomenda(s) Atrasada(s)!")
        else:
            st.success("Nenhuma encomenda pendente! 🎉")

    with col_right:
        st.subheader("⚠️ Alerta de Insumos")
        if not low_stock_materials.empty:
            st.dataframe(
                low_stock_materials,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "name": "Insumo",
                    "stock_level": st.column_config.NumberColumn("Estoque", format="%.2f"),
                    "min_stock_alert": st.column_config.NumberColumn("Mínimo", format="%.2f"),
                    "unit": "Unid."
                }
            )
        else:
            st.success("Estoque de insumos saudável. ✅")

    st.divider()

    # --- PRODUCTS STOCK ---
    st.subheader("🏺 Estoque de Peças")
    
    # Search Filter
    search = st.text_input("🔍 Buscar Peça", placeholder="Digite o nome...")
    if search:
        products_df = products_df[products_df['name'].str.contains(search, case=False)]
    
    st.dataframe(
        products_df,
        hide_index=True, 
        use_container_width=True,
        column_config={
            "name": "Peça",
            "stock_quantity": st.column_config.NumberColumn("Qtd Atual", format="%d"),
            "base_price": st.column_config.NumberColumn("Preço Base", format="R$ %.2f")
        }
    )

except Exception as e:
    st.error(f"Erro no dashboard: {e}")
finally:
    conn.close()
