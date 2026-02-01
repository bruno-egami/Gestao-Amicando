import streamlit as st
import database
import pandas as pd
from datetime import date
import admin_utils
import auth

# Page config
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# Hide default sidebar immediately to prevent flicker
st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {display: none;}
    </style>
""", unsafe_allow_html=True)

database.init_db()
conn = database.get_connection()

# Ensure default admin exists
auth.create_default_admin(conn)

# --- AUTHENTICATION ---
if not auth.require_login(conn):
    st.stop()

# Render custom sidebar
auth.render_custom_sidebar()

# Get current user
current_user = auth.get_current_user()
is_admin = current_user and current_user['role'] == 'admin'

# --- SIDEBAR ---
# --- SIDEBAR (Legacy Admin Tools removed - now in pages/99_Administracao.py) ---
with st.sidebar:
    admin_utils.render_sidebar_logo()
    
    st.info("ℹ️ Dashboard focado em operações (Encomendas e Estoque).")

# --- MAIN CONTENT ---
admin_utils.render_header_logo()
st.title("📊 Dashboard")
st.write(f"Hoje: **{date.today().strftime('%d/%m/%Y')}**")

# --- PRODUCTION SUMMARY ---
st.markdown("### 🔨 Resumo de Produção")

try:
    # Today's production
    today_str = date.today().isoformat()
    today_production = pd.read_sql("""
        SELECT SUM(quantity) as total FROM production_history 
        WHERE timestamp LIKE ?
    """, conn, params=(today_str + '%',))
    today_total = today_production.iloc[0]['total'] or 0
    
    # Week's production
    week_start = (date.today() - pd.Timedelta(days=7)).isoformat()
    week_production = pd.read_sql("""
        SELECT SUM(quantity) as total FROM production_history 
        WHERE timestamp >= ?
    """, conn, params=(week_start,))
    week_total = week_production.iloc[0]['total'] or 0
    
    # Month's production
    month_start = date.today().replace(day=1).isoformat()
    month_production = pd.read_sql("""
        SELECT SUM(quantity) as total FROM production_history 
        WHERE timestamp >= ?
    """, conn, params=(month_start,))
    month_total = month_production.iloc[0]['total'] or 0

    prod_c1, prod_c2, prod_c3 = st.columns(3)
    prod_c1.metric("🔨 Hoje", f"{int(today_total)} peças")
    prod_c2.metric("📅 Últimos 7 dias", f"{int(week_total)} peças")
    prod_c3.metric("📆 Este mês", f"{int(month_total)} peças")
    
    # Recent production history
    recent_prod = pd.read_sql("""
        SELECT timestamp, product_name, quantity, username
        FROM production_history
        ORDER BY timestamp DESC
        LIMIT 5
    """, conn)
    
    if not recent_prod.empty:
        st.caption("**Últimas Produções:**")
        for _, row in recent_prod.iterrows():
            ts = row['timestamp'][:16].replace('T', ' ')
            st.caption(f"🔹 {ts} — **{row['product_name']}** x{row['quantity']} ({row['username']})")
    
    st.divider()
except Exception as e:
    st.caption(f"(Histórico de produção ainda não disponível)")
    st.divider()

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
