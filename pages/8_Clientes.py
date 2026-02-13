import streamlit as st
import pandas as pd
import auth
import database
import admin_utils
import audit
import time

st.set_page_config(page_title="Clientes", page_icon="👥", layout="wide")

# Apply Global Styles
import utils.styles as styles
styles.apply_custom_style()

conn = database.get_connection()

if not auth.require_login(conn):
    st.stop()

if not auth.check_page_access("Clientes"):
    st.stop()

auth.render_custom_sidebar()
admin_utils.render_header_logo()
st.title("👥 Gestão de Clientes")

cursor = conn.cursor()

# Session State for Edit Mode
if "cli_edit_id" not in st.session_state:
    st.session_state.cli_edit_id = None

# --- LAYOUT: NEW + LIST ---
col_form, col_list = st.columns([1, 2], gap="large")

# === LEFT: NEW CLIENT FORM ===
with col_form:
    is_edit = st.session_state.cli_edit_id is not None
    form_title = "✏️ Editar Cliente" if is_edit else "➕ Novo Cliente"
    st.subheader(form_title)
    
    # Defaults
    def_name, def_contact, def_phone, def_email, def_notes = "", "", "", "", ""
    
    if is_edit:
        try:
            edit_row = pd.read_sql("SELECT * FROM clients WHERE id=?", conn, params=(st.session_state.cli_edit_id,)).iloc[0]
            def_name = edit_row['name'] or ""
            def_contact = edit_row['contact'] or ""
            def_phone = edit_row['phone'] or ""
            def_email = edit_row['email'] or ""
            def_notes = edit_row['notes'] or ""
        except Exception:
            st.session_state.cli_edit_id = None
            st.rerun()
    
    if is_edit:
        if st.button("⬅️ Cancelar Edição"):
            st.session_state.cli_edit_id = None
            st.rerun()
    
    with st.form("client_form", clear_on_submit=not is_edit):
        f_name = st.text_input("Nome *", value=def_name)
        f_contact = st.text_input("Contato", value=def_contact)
        f_phone = st.text_input("Telefone", value=def_phone)
        f_email = st.text_input("Email", value=def_email)
        f_notes = st.text_area("Observações", value=def_notes)
        
        btn_label = "💾 Salvar Alterações" if is_edit else "💾 Cadastrar"
        if st.form_submit_button(btn_label, type="primary", use_container_width=True):
            if not f_name:
                admin_utils.show_feedback_dialog("Nome é obrigatório.", level="warning")
            else:
                new_data = {'name': f_name, 'contact': f_contact, 'phone': f_phone, 'email': f_email, 'notes': f_notes}
                
                if is_edit:
                    # Capture old data for audit
                    old_data = {'name': def_name, 'contact': def_contact, 'phone': def_phone, 'email': def_email, 'notes': def_notes}
                    
                    cursor.execute("""
                        UPDATE clients SET name=?, contact=?, phone=?, email=?, notes=? WHERE id=?
                    """, (f_name, f_contact, f_phone, f_email, f_notes, st.session_state.cli_edit_id))
                    conn.commit()
                    
                    # Log UPDATE
                    audit.log_action(conn, 'UPDATE', 'clients', st.session_state.cli_edit_id, old_data, new_data)
                    
                    admin_utils.show_feedback_dialog("Cliente atualizado!", level="success")
                    st.session_state.cli_edit_id = None
                else:
                    cursor.execute("""
                        INSERT INTO clients (name, contact, phone, email, notes) VALUES (?, ?, ?, ?, ?)
                    """, (f_name, f_contact, f_phone, f_email, f_notes))
                    conn.commit()
                    new_id = cursor.lastrowid
                    
                    # Log CREATE
                    audit.log_action(conn, 'CREATE', 'clients', new_id, None, new_data)
                    
                    admin_utils.show_feedback_dialog("Cliente cadastrado!", level="success")

# === RIGHT: LIST WITH SEARCH ===
with col_list:
    st.subheader("📋 Clientes Cadastrados")
    
    # Search
    search_term = st.text_input("🔍 Buscar", placeholder="Nome, contato, telefone...")
    
    # Fetch Data
    df = pd.read_sql("SELECT * FROM clients ORDER BY name", conn)
    
    # Apply Search Filter
    if search_term and not df.empty:
        mask = df.apply(lambda row: search_term.lower() in str(row).lower(), axis=1)
        df = df[mask]
    
    st.caption(f"{len(df)} cliente(s) encontrado(s)")
    
    if not df.empty:
        for _, row in df.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                
                with c1:
                    st.markdown(f"### {row['name']}")
                    if row['contact']:
                        st.write(f"👤 **Contato:** {row['contact']}")
                    if row['phone']:
                        st.write(f"📞 {row['phone']}")
                    if row['email']:
                        st.write(f"📧 {row['email']}")
                    if row['notes']:
                        st.caption(f"📝 {row['notes']}")
                
                with c2:
                    if st.button("✏️ Editar", key=f"edit_cli_{row['id']}", use_container_width=True):
                        st.session_state.cli_edit_id = row['id']
                        st.rerun()
                
                with c3:
                    if st.button("🗑️ Excluir", key=f"del_cli_{row['id']}", use_container_width=True):
                        def do_delete(cid=row['id'], cname=row['name'], r=row):
                            try:
                                old_data = {'id': cid, 'name': cname, 'contact': r['contact'], 
                                           'phone': r['phone'], 'email': r['email'], 'notes': r['notes']}
                                cursor.execute("DELETE FROM clients WHERE id=?", (cid,))
                                conn.commit()
                                audit.log_action(conn, 'DELETE', 'clients', cid, old_data, None)
                            except Exception as e:
                                st.error(f"Erro: {e}")

                        admin_utils.show_confirmation_dialog(
                            f"Tem certeza que deseja excluir o cliente '{row['name']}'?",
                            on_confirm=do_delete
                        )
    else:
        st.info("Nenhum cliente cadastrado ou encontrado.")

conn.close()
