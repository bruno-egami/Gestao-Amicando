import streamlit as st
import pandas as pd
import database
import admin_utils

st.set_page_config(page_title="Insumos", page_icon="🧱")

if not admin_utils.check_password():
    st.stop()

st.title("Gestão de Insumos (Matérias-Primas)")

conn = database.get_connection()

# --- Form for new material ---
with st.expander("Cadastrar Novo Insumo", expanded=False):
    with st.form("new_material_form"):
        col1, col2 = st.columns(2)
        name = col1.text_input("Nome do Material")
        
        # Suppliers
        suppliers = pd.read_sql("SELECT id, name FROM suppliers", conn)
        sup_dict = {row['name']: row['id'] for _, row in suppliers.iterrows()}
        supplier_name = col2.selectbox("Fornecedor", [""] + list(sup_dict.keys()))
        
        col3, col4, col5 = st.columns(3)
        price = col3.number_input("Preço por Unidade (R$)", min_value=0.0, step=0.01, format="%.2f")
        unit = col4.selectbox("Unidade", ["kg", "L", "unidade", "hora (mão de obra)"])
        m_type = col5.selectbox("Tipo", ["Material", "Mão de Obra"])
        
        col6, col7 = st.columns(2)
        stock = col6.number_input("Estoque Inicial", min_value=0.0, step=0.1)
        min_alert = col7.number_input("Alerta de Estoque Mínimo", min_value=0.0, step=0.1)
        
        submitted = st.form_submit_button("Salvar Insumo")
        
        if submitted:
            if name:
                sup_id = sup_dict.get(supplier_name) if supplier_name else None
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO materials (name, supplier_id, price_per_unit, unit, stock_level, min_stock_alert, type)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (name, sup_id, price, unit, stock, min_alert, m_type))
                    conn.commit()
                    st.success(f"'{name}' cadastrado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
            else:
                st.warning("Nome obrigatório.")

# --- List Materials ---
st.divider()
st.subheader("Estoque Atual")

try:
    df = pd.read_sql("""
        SELECT m.id, m.name, s.name as supplier, m.price_per_unit, m.unit, m.stock_level, m.min_stock_alert, m.type
        FROM materials m
        LEFT JOIN suppliers s ON m.supplier_id = s.id
        ORDER BY m.name
    """, conn)
    
    if not df.empty:
        # Add 'remove' column for explicit deletion
        df['remove'] = False
        
        # Use data_editor for Edit/Delete capability
        edited_df = st.data_editor(
            df,
            column_config={
                "id": st.column_config.NumberColumn(disabled=True),
                "price_per_unit": st.column_config.NumberColumn(format="R$ %.2f"),
                "stock_level": st.column_config.NumberColumn(label="Estoque"),
                "min_stock_alert": st.column_config.NumberColumn(label="Mínimo"),
                "unit": st.column_config.SelectboxColumn(
                    label="Unidade",
                    options=["kg", "L", "unidade", "hora (mão de obra)"],
                    required=True
                ),
                "remove": st.column_config.CheckboxColumn(label="Excluir?", help="Marque para excluir este insumo")
            },
            hide_index=True,
            num_rows="dynamic",
            key="materials_editor",
            use_container_width=True
        )
        
        if st.button("Salvar Alterações de Estoque/Preço"):
             cursor = conn.cursor()
             
             # Identify explicit deletes (Checkbox)
             to_delete_ids = set(edited_df[edited_df['remove'] == True]['id'])
             
             # Identify implicit deletes (Removed row in UI)
             orig_ids = set(df['id'])
             present_ids = set(edited_df[edited_df['id'].notna()]['id'])
             missing_ids = orig_ids - present_ids
             
             all_deletes = to_delete_ids.union(missing_ids)
             
             if all_deletes:
                 for did in all_deletes:
                     cursor.execute("DELETE FROM materials WHERE id=?", (did,))
             
             # Updates (Skip deleted)
             for index, row in edited_df.iterrows():
                 if row['id'] and row['id'] not in all_deletes:
                     cursor.execute("""
                        UPDATE materials 
                        SET name=?, price_per_unit=?, unit=?, stock_level=?, min_stock_alert=?, type=?
                        WHERE id=?
                     """, (row['name'], row['price_per_unit'], row['unit'], row['stock_level'], row['min_stock_alert'], row['type'], row['id']))
             
             conn.commit()
             st.success("Dados atualizados! (Obs: Estoque de 'Mão de Obra' é ignorado na produção)")
             st.rerun()

    else:
        st.info("Nenhum material cadastrado.")

except Exception as e:
    st.error(f"Erro ao carregar materiais: {e}")
finally:
    conn.close()
