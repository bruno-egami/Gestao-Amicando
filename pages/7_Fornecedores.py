import streamlit as st
import pandas as pd
import database
import admin_utils

st.set_page_config(page_title="Fornecedores", page_icon="🚚")

admin_utils.render_sidebar_logo()

# Auth Check (Admin only)
if not admin_utils.check_password():
    st.stop()

st.title("Gestão de Fornecedores")

conn = database.get_connection()

# --- Form ---
with st.expander("Novo Fornecedor", expanded=False):
    with st.form("new_supplier"):
        name = st.text_input("Nome/Empresa")
        contact = st.text_input("Nome do Contato")
        phone = st.text_input("Telefone")
        email = st.text_input("Email")
        notes = st.text_area("Observações")
        
        if st.form_submit_button("Salvar"):
            if name:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO suppliers (name, contact, phone, email, notes) VALUES (?, ?, ?, ?, ?)",
                               (name, contact, phone, email, notes))
                conn.commit()
                st.success("Fornecedor cadastrado!")
                st.rerun()
            else:
                st.error("Nome é obrigatório")

# --- List ---
st.divider()

df = pd.read_sql("SELECT * FROM suppliers", conn)

if not df.empty:
    for i, row in df.iterrows():
        with st.expander(f"{row['name']} ({row['contact'] or 'Sem contato'})"):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.write(f"**Tel:** {row['phone']}")
                st.write(f"**Email:** {row['email']}")
                st.write(f"**Obs:** {row['notes']}")
            with c2:
                if st.button("Excluir", key=f"del_sup_{row['id']}"):
                    cursor = conn.cursor()
                    try:
                        cursor.execute("DELETE FROM suppliers WHERE id=?", (row['id'],))
                        conn.commit()
                        st.success("Excluído!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
                        
                # Edit functionality could be a modal or inline form. 
                # For simplicity, keeping it simple delete/re-add for now or simple updates via form?
                # User asked for Edit/Delete specifically.
                # Let's add a simple Edit Form below the details if "Editar" is clicked?
                # Keeping state for edit is tricky in loop. Pushing simple Delete for now.
                # Actually, let's implement Edit properly via st.data_editor or a form.
                
                # Let's use data_editor for the whole table below instead of expanders for density?
                # Expanders are good for details. 
                pass

    st.subheader("Lista Completa (Edição Rápida)")
    edited = st.data_editor(df, num_rows="dynamic", key="editor_suppliers", hide_index=True)
    
    if st.button("Salvar Alterações em Lote"):
        cursor = conn.cursor()
        # Naive update loop
        for i, row in edited.iterrows():
            if row['id']: # Update
                cursor.execute("""
                    UPDATE suppliers SET name=?, contact=?, phone=?, email=?, notes=? WHERE id=?
                """, (row['name'], row['contact'], row['phone'], row['email'], row['notes'], row['id']))
        conn.commit()
        st.success("Dados atualizados!")
        st.rerun()

else:
    st.info("Nenhum fornecedor.")

conn.close()
