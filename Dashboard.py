import streamlit as st
import database
import pandas as pd
from datetime import date
import admin_utils
import auth
import utils.ui_components as ui_components
import utils.backup_utils as backup_utils

# Page config
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# Hide default sidebar immediately to prevent flicker
st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {display: none;}
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def startup_db():
    database.init_db()

startup_db()

# Run automatic backup check (utility handles frequency logic)
with database.db_session() as conn_bkp:
    backup_utils.run_backup_if_needed(conn_bkp)

def get_db_connection():
    return database.get_connection()

# Ensure default admin exists
with database.db_session() as conn_init:
    auth.create_default_admin(conn_init)

# --- AUTHENTICATION ---
if not auth.require_login(conn):
    st.stop()

# Render custom sidebar
auth.render_custom_sidebar()

# Get current user
current_user = auth.get_current_user()
is_admin = current_user and current_user['role'] == 'admin'

# --- SIDEBAR ---
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
    today_str = date.today().isoformat()
    
    # New: Breaking Alert
    today_losses = pd.read_sql("SELECT SUM(quantity) as total FROM production_losses WHERE timestamp LIKE ?", conn, params=(today_str + '%',))
    broken_today = today_losses.iloc[0]['total'] or 0
    if broken_today > 0:
        st.warning(f"💔 **Alerta de Perdas**: {int(broken_today)} peças foram registradas como quebra hoje.")

    # Today's production
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

    prod_c1, prod_c2, prod_c3, prod_c4 = st.columns(4)
    prod_c1.metric("🔨 Hoje", f"{int(today_total)} un")
    prod_c2.metric("📅 Últimos 7 dias", f"{int(week_total)} un")
    prod_c3.metric("📆 Este mês", f"{int(month_total)} un")
    
    # Calculate Yield (Month)
    month_losses = pd.read_sql("SELECT SUM(quantity) as total FROM production_losses WHERE timestamp >= ?", conn, params=(month_start,))
    month_broken = month_losses.iloc[0]['total'] or 0
    month_yield = (month_total / (month_total + month_broken) * 100) if (month_total + month_broken) > 0 else 100
    prod_c4.metric("📈 Rendimento (Mês)", f"{month_yield:.1f}%")

    # WIP Status Bar
    st.write("📍 **Status Atual da Produção (Kanban):**")
    wip_data = pd.read_sql("SELECT stage, SUM(quantity) as total FROM production_wip GROUP BY stage", conn)
    stage_order = ["Fila de Espera", "Modelagem", "Secagem", "Biscoito", "Esmaltação", "Queima de Alta"]
    
    if not wip_data.empty:
        wip_counts = wip_data.set_index('stage')['total'].reindex(stage_order).fillna(0)
        # Display as a small bar chart or colorful columns
        w_cols = st.columns(len(stage_order))
        for i, s in enumerate(stage_order):
            w_cols[i].caption(f"**{s}**")
            w_cols[i].write(f"{int(wip_counts[s])} un")
    else:
        st.info("Nenhum item em produção no momento.")
    
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

    # 4. Inventory Value
    inventory_val = (products_df['stock_quantity'] * products_df['base_price']).sum()
    
    # 5. Class Highlights
    from services import student_service
    class_stats = student_service.get_module_summary_stats(conn)
    debts_df = student_service.get_debts_summary(conn)

    # --- METRICS ROW ---
    c1, c2, c3, c4 = st.columns(4)
    
    pending_count = len(orders_df)
    low_stock_count = len(low_stock_materials)
    total_products = products_df['stock_quantity'].sum()
    
    c1.metric("📦 Encomendas Pendentes", pending_count)
    c2.metric("⚠️ Insumos em Alerta", low_stock_count, delta_color="inverse")
    c3.metric("🏺 Peças em Estoque", int(total_products))
    c4.metric("💰 Valor em Estoque", f"R$ {inventory_val:,.2f}")

    # Second Metrics Row: Classes
    st.markdown("#### 🎓 Gestão de Aulas")
    cl1, cl2, cl3, cl4 = st.columns(4)
    cl1.metric("👥 Alunos Ativos", class_stats.get('total_students', 0))
    cl2.metric("💸 Valor Pendente (Aulas)", f"R$ {class_stats.get('pending_revenue', 0):.2f}")
    
    if not debts_df.empty:
        st.info(f"🎓 Existem **{len(debts_df)}** alunos com mensalidades ou consumos pendentes. [Ver Gestão de Aulas](Gestao_Aulas)")

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
        st.subheader("🎓 Mensalidades Pendentes")
        if not debts_df.empty:
             st.dataframe(
                debts_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "name": "Aluno",
                    "months": "Mês(es)",
                    "total_due": st.column_config.NumberColumn("Valor em Aberto", format="R$ %.2f")
                }
            )
        else:
            st.success("Todas as mensalidades estão em dia! 🎉")

    st.divider()

    # Lower Row: Stock & Low Stock
    col_st_1, col_st_2 = st.columns([1, 1], gap="large")
    
    with col_st_1:
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

    with col_st_2:
        st.subheader("🏺 Resumo de Estoque (Peças)")
        # Small search and preview
        st.dataframe(
            products_df[['name', 'stock_quantity']],
            hide_index=True,
            use_container_width=True,
            column_config={
                "name": "Peça",
                "stock_quantity": st.column_config.NumberColumn("Qtd Atual", format="%d")
            }
        )

except Exception as e:
    st.error(f"Erro no dashboard: {e}")
finally:
    conn.close()
