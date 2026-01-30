import streamlit as st
import pandas as pd
import database
import admin_utils
import audit
import time

st.set_page_config(page_title="Fornecedores", page_icon="🚚", layout="wide")

admin_utils.render_sidebar_logo()

# Auth Check (Admin only)
if not admin_utils.check_password():
    st.stop()

admin_utils.render_header_logo()
st.title("🚚 Gestão de Fornecedores")

conn = database.get_connection()
cursor = conn.cursor()

# Session State for Edit Mode
if "sup_edit_id" not in st.session_state:
    st.session_state.sup_edit_id = None

# --- LAYOUT: NEW + LIST ---
col_form, col_list = st.columns([1, 2], gap="large")

# === LEFT: NEW SUPPLIER FORM ===
with col_form:
    is_edit = st.session_state.sup_edit_id is not None
    form_title = "✏️ Editar Fornecedor" if is_edit else "➕ Novo Fornecedor"
    st.subheader(form_title)
    
    # Defaults
    def_name, def_contact, def_phone, def_email, def_notes = "", "", "", "", ""
    
    if is_edit:
        try:
            edit_row = pd.read_sql("SELECT * FROM suppliers WHERE id=?", conn, params=(st.session_state.sup_edit_id,)).iloc[0]
            def_name = edit_row['name'] or ""
            def_contact = edit_row['contact'] or ""
            def_phone = edit_row['phone'] or ""
            def_email = edit_row['email'] or ""
            def_notes = edit_row['notes'] or ""
        except:
            st.session_state.sup_edit_id = None
            st.rerun()
    
    if is_edit:
        if st.button("⬅️ Cancelar Edição"):
            st.session_state.sup_edit_id = None
            st.rerun()
    
    with st.form("supplier_form", clear_on_submit=not is_edit):
        f_name = st.text_input("Nome/Empresa *", value=def_name)
        f_contact = st.text_input("Nome do Contato", value=def_contact)
        f_phone = st.text_input("Telefone", value=def_phone)
        f_email = st.text_input("Email", value=def_email)
        f_notes = st.text_area("Observações", value=def_notes)
        
        btn_label = "💾 Salvar Alterações" if is_edit else "💾 Cadastrar"
        if st.form_submit_button(btn_label, type="primary", use_container_width=True):
            if not f_name:
                st.error("Nome é obrigatório.")
            else:
                new_data = {'name': f_name, 'contact': f_contact, 'phone': f_phone, 'email': f_email, 'notes': f_notes}
                
                if is_edit:
                    old_data = {'name': def_name, 'contact': def_contact, 'phone': def_phone, 'email': def_email, 'notes': def_notes}
                    cursor.execute("""
                        UPDATE suppliers SET name=?, contact=?, phone=?, email=?, notes=? WHERE id=?
                    """, (f_name, f_contact, f_phone, f_email, f_notes, st.session_state.sup_edit_id))
                    conn.commit()
                    audit.log_action(conn, 'UPDATE', 'suppliers', st.session_state.sup_edit_id, old_data, new_data)
                    st.success("Fornecedor atualizado!")
                    st.session_state.sup_edit_id = None
                else:
                    cursor.execute("""
                        INSERT INTO suppliers (name, contact, phone, email, notes) VALUES (?, ?, ?, ?, ?)
                    """, (f_name, f_contact, f_phone, f_email, f_notes))
                    conn.commit()
                    new_id = cursor.lastrowid
                    audit.log_action(conn, 'CREATE', 'suppliers', new_id, None, new_data)
                    st.success("Fornecedor cadastrado!")
                time.sleep(0.5)
                st.rerun()

# === RIGHT: LIST WITH SEARCH ===
with col_list:
    st.subheader("📋 Fornecedores Cadastrados")
    
    # Search
    search_term = st.text_input("🔍 Buscar", placeholder="Nome, contato, telefone...")
    
    # Fetch Data
    df = pd.read_sql("SELECT * FROM suppliers ORDER BY name", conn)
    
    # Apply Search Filter
    if search_term and not df.empty:
        mask = df.apply(lambda row: search_term.lower() in str(row).lower(), axis=1)
        df = df[mask]
    
    st.caption(f"{len(df)} fornecedor(es) encontrado(s)")
    
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
                    if st.button("✏️ Editar", key=f"edit_sup_{row['id']}", use_container_width=True):
                        st.session_state.sup_edit_id = row['id']
                        st.rerun()
                
                with c3:
                    if st.button("🗑️ Excluir", key=f"del_sup_{row['id']}", use_container_width=True):
                        try:
                            old_data = {'id': row['id'], 'name': row['name'], 'contact': row['contact'], 
                                       'phone': row['phone'], 'email': row['email'], 'notes': row['notes']}
                            cursor.execute("DELETE FROM suppliers WHERE id=?", (row['id'],))
                            conn.commit()
                            audit.log_action(conn, 'DELETE', 'suppliers', row['id'], old_data, None)
                            st.success(f"'{row['name']}' excluído!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
    else:
        st.info("Nenhum fornecedor cadastrado ou encontrado.")

conn.close()
