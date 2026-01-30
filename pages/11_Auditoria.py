import streamlit as st
import pandas as pd
import database
import admin_utils
import auth
import audit
import json

st.set_page_config(page_title="Auditoria", page_icon="📜", layout="wide")

admin_utils.render_sidebar_logo()

conn = database.get_connection()

# Authentication
if not auth.require_login(conn):
    st.stop()

auth.render_user_info()

# Admin only
if not auth.check_page_access('Usuarios'):  # Reuse admin-only access
    st.stop()

admin_utils.render_header_logo()
st.title("📜 Log de Auditoria")

# --- FILTERS ---
st.subheader("🔍 Filtros")

f1, f2, f3, f4 = st.columns(4)

with f1:
    tables = ["Todas", "products", "sales", "expenses", "materials", "clients", "suppliers", "commission_orders", "firings", "users"]
    sel_table = st.selectbox("Tabela", tables, format_func=lambda x: audit.format_table_name(x) if x != "Todas" else "Todas")

with f2:
    actions = ["Todas", "CREATE", "UPDATE", "DELETE", "ROLLBACK"]
    sel_action = st.selectbox("Ação", actions, format_func=lambda x: audit.format_action(x) if x != "Todas" else "Todas")

with f3:
    users_df = pd.read_sql("SELECT DISTINCT username FROM audit_log ORDER BY username", conn)
    user_opts = ["Todos"] + users_df['username'].tolist()
    sel_user = st.selectbox("Usuário", user_opts)

with f4:
    limit = st.number_input("Limite", min_value=10, max_value=500, value=100, step=50)

# Date filters
d1, d2 = st.columns(2)
with d1:
    start_date = st.date_input("De", value=None)
with d2:
    end_date = st.date_input("Até", value=None)

# Build filters
filters = {}
if sel_table != "Todas":
    filters['table_name'] = sel_table
if sel_action != "Todas":
    filters['action'] = sel_action
if sel_user != "Todos":
    filters['username'] = sel_user
if start_date:
    filters['start_date'] = start_date.isoformat()
if end_date:
    filters['end_date'] = end_date.isoformat() + "T23:59:59"

st.divider()

# --- AUDIT LOG TABLE ---
log_df = audit.get_audit_log(conn, filters if filters else None, limit=limit)

st.subheader(f"📋 Registros ({len(log_df)})")

if log_df.empty:
    st.info("Nenhum registro encontrado com os filtros selecionados.")
else:
    for _, row in log_df.iterrows():
        action_icon = audit.format_action(row['action'])
        table_icon = audit.format_table_name(row['table_name'])
        
        timestamp = row['timestamp'][:16].replace('T', ' ')
        
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 1, 1])
            
            with c1:
                st.markdown(f"**{action_icon}** em {table_icon} (ID: {row['record_id']})")
                st.caption(f"🕐 {timestamp} | 👤 {row['username']}")
            
            with c2:
                # Show details
                with st.popover("📋 Detalhes"):
                    st.markdown("**Dados Anteriores:**")
                    if row['old_data']:
                        try:
                            old = json.loads(row['old_data'])
                            st.json(old)
                        except:
                            st.code(row['old_data'])
                    else:
                        st.caption("N/A")
                    
                    st.markdown("**Dados Novos:**")
                    if row['new_data']:
                        try:
                            new = json.loads(row['new_data'])
                            st.json(new)
                        except:
                            st.code(row['new_data'])
                    else:
                        st.caption("N/A")
            
            with c3:
                # Rollback button (only for UPDATE and DELETE)
                if row['action'] in ['UPDATE', 'DELETE'] and row['old_data']:
                    if st.button("↩️ Reverter", key=f"rb_{row['id']}", help="Restaurar dados anteriores"):
                        if audit.rollback_record(conn, row['id']):
                            st.success("Dados restaurados com sucesso!")
                            st.rerun()
                        else:
                            st.error("Erro ao restaurar dados.")

st.divider()

# --- STATISTICS ---
st.subheader("📊 Estatísticas")

stats_col1, stats_col2 = st.columns(2)

with stats_col1:
    st.markdown("**Por Ação**")
    action_stats = pd.read_sql("""
        SELECT action, count(*) as total
        FROM audit_log
        GROUP BY action
        ORDER BY total DESC
    """, conn)
    if not action_stats.empty:
        action_stats['label'] = action_stats['action'].apply(audit.format_action)
        st.bar_chart(action_stats.set_index('label')['total'])

with stats_col2:
    st.markdown("**Por Tabela**")
    table_stats = pd.read_sql("""
        SELECT table_name, count(*) as total
        FROM audit_log
        GROUP BY table_name
        ORDER BY total DESC
        LIMIT 10
    """, conn)
    if not table_stats.empty:
        table_stats['label'] = table_stats['table_name'].apply(audit.format_table_name)
        st.bar_chart(table_stats.set_index('label')['total'])

conn.close()
