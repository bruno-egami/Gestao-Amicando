import streamlit as st
import pandas as pd
import database
import admin_utils

st.set_page_config(page_title="Clientes", page_icon="👥")

admin_utils.render_sidebar_logo()

# Auth Check (Admin or Sales view? Sales needs to SELECT clients, but maybe creating them is okay?
# User said "create 2 distinct accesses... when registering a sale... not view general data".
# So Sales person needs to SEE clients. But maybe this page is for full management.
# Let's allow access but maybe restrict deleting? For now, assume Admin needed for full management, 
# but Sales module will have a "Create Client" shortcut possibly.
# Let's keep this as Admin Management for now.

if not admin_utils.check_password():
    st.stop()

st.title("Gestão de Clientes")

conn = database.get_connection()

# --- Form ---
with st.expander("Novo Cliente", expanded=False):
    with st.form("new_client"):
        name = st.text_input("Nome")
        contact = st.text_input("Contato")
        phone = st.text_input("Telefone")
        email = st.text_input("Email")
        notes = st.text_area("Observações")
        
        if st.form_submit_button("Salvar"):
            if name:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO clients (name, contact, phone, email, notes) VALUES (?, ?, ?, ?, ?)",
                               (name, contact, phone, email, notes))
                conn.commit()
                st.success("Cliente cadastrado!")
                st.rerun()
            else:
                st.error("Nome é obrigatório")

# --- List ---
st.divider()

df = pd.read_sql("SELECT * FROM clients", conn)

if not df.empty:
    st.subheader("Lista de Clientes")
    edited = st.data_editor(df, num_rows="dynamic", key="editor_clients", hide_index=True)
    
    if st.button("Salvar Alterações"):
        cursor = conn.cursor()
        for i, row in edited.iterrows():
            if row['id']:
                 cursor.execute("""
                    UPDATE clients SET name=?, contact=?, phone=?, email=?, notes=? WHERE id=?
                """, (row['name'], row['contact'], row['phone'], row['email'], row['notes'], row['id']))
        conn.commit()
        st.success("Atualizado!")
        st.rerun()
else:
    st.info("Nenhum cliente.")

conn.close()
