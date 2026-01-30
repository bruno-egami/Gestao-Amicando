import streamlit as st
import pandas as pd
import database
import admin_utils
import auth
import audit
from datetime import datetime

st.set_page_config(page_title="Usuários", page_icon="👥", layout="wide")

admin_utils.render_sidebar_logo()

conn = database.get_connection()

# Ensure default admin exists
auth.create_default_admin(conn)

# Require login first
if not auth.require_login(conn):
    st.stop()

# Render user info in sidebar
auth.render_user_info()

# Check admin access
if not auth.check_page_access('Usuarios'):
    st.stop()

admin_utils.render_header_logo()
st.title("👥 Gerenciamento de Usuários")

cursor = conn.cursor()

# Session state for editing
if "user_edit_id" not in st.session_state:
    st.session_state.user_edit_id = None

# --- LAYOUT ---
col_form, col_list = st.columns([1, 2], gap="large")

# === LEFT: NEW/EDIT USER FORM ===
with col_form:
    is_edit = st.session_state.user_edit_id is not None
    form_title = "✏️ Editar Usuário" if is_edit else "➕ Novo Usuário"
    st.subheader(form_title)
    
    # Defaults
    def_username, def_name, def_role = "", "", "vendedor"
    def_active = True
    
    if is_edit:
        try:
            edit_row = pd.read_sql("SELECT * FROM users WHERE id=?", conn, params=(st.session_state.user_edit_id,)).iloc[0]
            def_username = edit_row['username'] or ""
            def_name = edit_row['name'] or ""
            def_role = edit_row['role'] or "vendedor"
            def_active = bool(edit_row['active'])
        except:
            st.session_state.user_edit_id = None
            st.rerun()
    
    if is_edit:
        if st.button("⬅️ Cancelar Edição"):
            st.session_state.user_edit_id = None
            st.rerun()
    
    with st.form("user_form", clear_on_submit=not is_edit):
        f_username = st.text_input("Usuário *", value=def_username, disabled=is_edit)
        f_name = st.text_input("Nome Completo", value=def_name)
        f_role = st.selectbox("Perfil", list(auth.ROLES.keys()), 
                              format_func=lambda x: auth.ROLES[x],
                              index=list(auth.ROLES.keys()).index(def_role) if def_role in auth.ROLES else 0)
        f_active = st.checkbox("Ativo", value=def_active)
        
        st.divider()
        st.caption("Senha" if not is_edit else "Nova Senha (deixe em branco para manter)")
        f_password = st.text_input("Senha", type="password")
        f_password_confirm = st.text_input("Confirmar Senha", type="password")
        
        btn_label = "💾 Salvar Alterações" if is_edit else "💾 Cadastrar"
        if st.form_submit_button(btn_label, type="primary", use_container_width=True):
            # Validation
            error = None
            
            if not is_edit and not f_username:
                error = "Usuário é obrigatório."
            elif not is_edit and not f_password:
                error = "Senha é obrigatória para novo usuário."
            elif f_password and f_password != f_password_confirm:
                error = "As senhas não conferem."
            elif not is_edit:
                # Check if username exists
                existing = pd.read_sql("SELECT id FROM users WHERE username=?", conn, params=(f_username,))
                if not existing.empty:
                    error = "Este usuário já existe."
            
            if error:
                st.error(error)
            else:
                if is_edit:
                    # Get old data for audit
                    old_user = pd.read_sql("SELECT username, name, role, active FROM users WHERE id=?", conn, params=(st.session_state.user_edit_id,))
                    old_data = old_user.iloc[0].to_dict() if not old_user.empty else {}
                    
                    # Update user
                    if f_password:
                        cursor.execute("""
                            UPDATE users SET name=?, role=?, active=?, password_hash=? WHERE id=?
                        """, (f_name, f_role, int(f_active), auth.hash_password(f_password), st.session_state.user_edit_id))
                    else:
                        cursor.execute("""
                            UPDATE users SET name=?, role=?, active=? WHERE id=?
                        """, (f_name, f_role, int(f_active), st.session_state.user_edit_id))
                    conn.commit()
                    audit.log_action(conn, 'UPDATE', 'users', st.session_state.user_edit_id, old_data,
                        {'name': f_name, 'role': f_role, 'active': f_active})
                    st.success("Usuário atualizado!")
                    st.session_state.user_edit_id = None
                else:
                    # Create user
                    cursor.execute("""
                        INSERT INTO users (username, password_hash, role, name, active, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (f_username, auth.hash_password(f_password), f_role, f_name, int(f_active), datetime.now().isoformat()))
                    new_id = cursor.lastrowid
                    conn.commit()
                    audit.log_action(conn, 'CREATE', 'users', new_id, None,
                        {'username': f_username, 'name': f_name, 'role': f_role})
                    st.success("Usuário cadastrado!")
                st.rerun()

# === RIGHT: USER LIST ===
with col_list:
    st.subheader("📋 Usuários Cadastrados")
    
    # Search
    search_user = st.text_input("🔍 Buscar", placeholder="Nome, usuário...")
    
    # Fetch Users
    users_df = pd.read_sql("SELECT id, username, name, role, active, created_at, last_login FROM users ORDER BY name", conn)
    
    # Apply filter
    if search_user and not users_df.empty:
        mask = users_df.apply(lambda row: search_user.lower() in str(row).lower(), axis=1)
        users_df = users_df[mask]
    
    st.caption(f"{len(users_df)} usuário(s)")
    
    if not users_df.empty:
        for _, row in users_df.iterrows():
            status_icon = "✅" if row['active'] else "❌"
            role_name = auth.ROLES.get(row['role'], row['role'])
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                
                with c1:
                    st.markdown(f"### {status_icon} {row['name'] or row['username']}")
                    st.write(f"👤 @{row['username']} | 📋 {role_name}")
                    if row['last_login']:
                        st.caption(f"🕐 Último acesso: {row['last_login'][:16]}")
                
                with c2:
                    if st.button("✏️ Editar", key=f"edit_user_{row['id']}", use_container_width=True):
                        st.session_state.user_edit_id = row['id']
                        st.rerun()
                
                with c3:
                    # Prevent deleting yourself or last admin
                    current_user = auth.get_current_user()
                    is_self = current_user and current_user['id'] == row['id']
                    
                    if not is_self:
                        if st.button("🗑️", key=f"del_user_{row['id']}", use_container_width=True, help="Excluir"):
                            old_data = {'username': row['username'], 'name': row['name'], 'role': row['role']}
                            cursor.execute("DELETE FROM users WHERE id=?", (row['id'],))
                            conn.commit()
                            audit.log_action(conn, 'DELETE', 'users', row['id'], old_data, None)
                            st.success(f"Usuário '{row['username']}' removido!")
                            st.rerun()
                    else:
                        st.caption("(você)")
    else:
        st.info("Nenhum usuário encontrado.")

conn.close()
