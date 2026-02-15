import streamlit as st
import database
import pandas as pd
from datetime import date
import admin_utils
import auth
import utils.ui_components as ui_components
import utils.backup_utils as backup_utils


# Initialize Database (Runs once)
@st.cache_resource
def init_app():
    database.initialize()

init_app()

# Page config
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# Hide default sidebar immediately to prevent flicker
import utils.styles as styles

# Apply Global Styles (Premium/Glassmorphism)
styles.apply_custom_style()





def get_db_connection():
    return database.get_connection()

# Ensure default admin exists
with database.db_session() as conn_init:
    auth.create_default_admin(conn_init)

# --- AUTHENTICATION ---
conn = get_db_connection()
try:
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

    # --- QUERIES & DATA LOADING ---
    today_str = date.today().isoformat()
    
    # 1. Encomendas (Orders)
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
    
    # 2. Alunos e Aulas (Classes)
    from services import student_service
    class_stats = student_service.get_module_summary_stats(conn)
    debts_df = student_service.get_debts_summary(conn)
    
    # 3. Estoque (Inventory)
    materials_df = pd.read_sql("""
        SELECT name, stock_level, min_stock_alert, unit 
        FROM materials 
        WHERE type = 'Material'
        ORDER BY stock_level ASC
    """, conn)
    low_stock_materials = materials_df[materials_df['stock_level'] <= materials_df['min_stock_alert']].copy()
    products_df = pd.read_sql("SELECT name, stock_quantity, base_price FROM products ORDER BY name", conn)
    inventory_val = (products_df['stock_quantity'] * products_df['base_price']).sum()
    
    # 4. Produção (Production)
    # Today's production
    today_production = pd.read_sql("SELECT SUM(quantity) as total FROM production_history WHERE timestamp LIKE ?", conn, params=(today_str + '%',))
    today_total = today_production.iloc[0]['total'] or 0
    # Week's production
    week_start = (date.today() - pd.Timedelta(days=7)).isoformat()
    week_production = pd.read_sql("SELECT SUM(quantity) as total FROM production_history WHERE timestamp >= ?", conn, params=(week_start,))
    week_total = week_production.iloc[0]['total'] or 0
    # Month's production
    month_start = date.today().replace(day=1).isoformat()
    month_production = pd.read_sql("SELECT SUM(quantity) as total FROM production_history WHERE timestamp >= ?", conn, params=(month_start,))
    month_total = month_production.iloc[0]['total'] or 0
    # Yield
    month_losses = pd.read_sql("SELECT SUM(quantity) as total FROM production_losses WHERE timestamp >= ?", conn, params=(month_start,))
    month_broken = month_losses.iloc[0]['total'] or 0
    month_yield = (month_total / (month_total + month_broken) * 100) if (month_total + month_broken) > 0 else 100
    
    today_losses = pd.read_sql("SELECT SUM(quantity) as total FROM production_losses WHERE timestamp LIKE ?", conn, params=(today_str + '%',))
    broken_today = today_losses.iloc[0]['total'] or 0

    # ==============================================================================
    # SECTION 1: ENCOMENDAS (ORDERS)
    # ==============================================================================
    st.markdown("### 📦 Encomendas Pendentes")
    with st.container(border=True):
        c_ord1, c_ord2 = st.columns([1, 3])
        c_ord1.metric("📦 Total de Pedidos", len(orders_df))
        
        if not orders_df.empty:
            # Format Date for display
            display_orders = orders_df.copy()
            display_orders['DueDate'] = pd.to_datetime(display_orders['DueDate']).dt.strftime('%d/%m/%Y')
            
            c_ord2.dataframe(
                display_orders[['Client', 'Items', 'DueDate', 'status']],
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
            delayed = orders_df[pd.to_datetime(orders_df['DueDate']).dt.date < date.today()]
            if not delayed.empty:
                st.error(f"⚠️ **{len(delayed)} Encomenda(s) Atrasada(s)!**")
        else:
            c_ord2.success("Incrível! Nenhuma encomenda pendente no momento. 🎉")
    
    st.divider()

    # ==============================================================================
    # SECTION 2: ALUNOS E AULAS (CLASSES)
    # ==============================================================================
    st.markdown("### 🎓 Gestão de Aulas e Alunos")
    with st.container(border=True):
        c_al1, c_al2 = st.columns([1, 3])
        with c_al1:
            st.metric("👥 Alunos Ativos", class_stats.get('total_students', 0))
            st.metric("💸 Valor Pendente", f"R$ {class_stats.get('pending_revenue', 0):.2f}")
        
        with c_al2:
            if not debts_df.empty:
                st.write("**Mensalidades/Consumos Pendentes:**")
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
                st.success("Tudo em dia! Nenhum aluno com pendência financeira. ✅")

    st.divider()

    # ==============================================================================
    # SECTION 3: ESTOQUE (INVENTORY)
    # ==============================================================================
    st.markdown("### 🏺 Estoque e Insumos")
    
    # Inventory Metrics
    with st.container(border=True):
        m1, m2, m3 = st.columns(3)
        m1.metric("⚠️ Insumos em Alerta", len(low_stock_materials), delta_color="inverse")
        m2.metric("🏺 Peças em Estoque", int(products_df['stock_quantity'].sum()))
        m3.metric("💰 Valor em Estoque", f"R$ {inventory_val:,.2f}")
    
    # Stock Details
    c_st1, c_st2 = st.columns(2, gap="large")
    with c_st1:
        st.caption("**⚠️ Alerta de Insumos:**")
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

    with c_st2:
        st.caption("**🏺 Resumo de Estoque (Peças):**")
        st.dataframe(
            products_df[['name', 'stock_quantity']],
            hide_index=True,
            use_container_width=True,
            column_config={
                "name": "Peça",
                "stock_quantity": st.column_config.NumberColumn("Qtd Atual", format="%d")
            }
        )

    st.divider()

    # ==============================================================================
    # SECTION 4: PRODUÇÃO (PRODUCTION)
    # ==============================================================================
    st.markdown("### 🔨 Resumo de Produção")
    
    if broken_today > 0:
        st.warning(f"💔 **Alerta de Perdas**: {int(broken_today)} peças foram registradas como quebra hoje.")

    with st.container(border=True):
        p_c1, p_c2, p_c3, p_c4 = st.columns(4)
        p_c1.metric("🔨 Hoje", f"{int(today_total)} un")
        p_c2.metric("📅 Últimos 7 dias", f"{int(week_total)} un")
        p_c3.metric("📆 Este mês", f"{int(month_total)} un")
        p_c4.metric("📈 Rendimento", f"{month_yield:.1f}%")

    # WIP Status Bar
    st.write("📍 **Status Atual da Produção (Kanban):**")
    with st.container(border=True):
        wip_data = pd.read_sql("SELECT stage, SUM(quantity) as total FROM production_wip GROUP BY stage", conn)
        stage_order = ["Fila de Espera", "Modelagem", "Secagem", "Biscoito", "Esmaltação", "Queima de Alta"]
        
        if not wip_data.empty:
            wip_counts = wip_data.set_index('stage')['total'].reindex(stage_order).fillna(0)
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

except Exception as e:
    st.error(f"Erro no dashboard: {e}")
    logger.exception("Dashboard error")
finally:
    conn.close()
