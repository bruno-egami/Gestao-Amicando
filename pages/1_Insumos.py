import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import database
import admin_utils
import audit

st.set_page_config(page_title="Insumos", page_icon="🧱", layout="wide")

admin_utils.render_sidebar_logo()

if not admin_utils.check_password():
    st.stop()

admin_utils.render_header_logo()
st.title("Gestão de Insumos (Matérias-Primas)")

conn = database.get_connection()
cursor = conn.cursor()

# --- 1. Top Bar: Controls & Filters ---
# Create Categories if needed
cats_df = pd.read_sql("SELECT id, name FROM material_categories ORDER BY name", conn)
cat_map = {row['name']: row['id'] for _, row in cats_df.iterrows()}
cat_options = ["Todas"] + list(cat_map.keys())

# Suppliers
sup_df = pd.read_sql("SELECT id, name FROM suppliers ORDER BY name", conn)
sup_map = {row['name']: row['id'] for _, row in sup_df.iterrows()}
sup_options = ["Todos"] + list(sup_map.keys())

# Filters Row
c_filter1, c_filter2, c_filter3, c_add = st.columns([1, 1, 1, 1])
with c_filter1:
    f_cat = st.selectbox("Filtrar Categoria", cat_options)
with c_filter2:
    f_sup = st.selectbox("Filtrar Fornecedor", sup_options)
with c_filter3:
    f_search = st.text_input("Buscar por Nome", placeholder="Ex: Argila")

# Mode Toggle Session State
if "insumo_edit_id" not in st.session_state:
    st.session_state.insumo_edit_id = None
if "manage_cats" not in st.session_state:
    st.session_state.manage_cats = False

with c_add:
    st.write("") # Spacer
    if st.button("➕ Novo Insumo", use_container_width=True):
        st.session_state.insumo_edit_id = "NEW"
        st.session_state.manage_cats = False # Close other modes
        st.rerun()

# --- 2. Category Management ---
with st.expander("Gerenciar Categorias de Insumos"):
    c1, c2 = st.columns([3, 1])
    new_cat_name = c1.text_input("Nova Categoria")
    if c2.button("Adicionar Categoria"):
        if new_cat_name:
            try:
                cursor.execute("INSERT INTO material_categories (name) VALUES (?)", (new_cat_name,))
                conn.commit()
                st.success(f"Categoria '{new_cat_name}' criada!")
                time.sleep(1)
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Categoria já existe.")
        else:
            st.warning("Digite um nome.")
            
    # List Existing (small editor)
    if not cats_df.empty:
        st.write("Categorias Existentes:")
        # Simple list for now, maybe add delete later if simple
        st.dataframe(cats_df, hide_index=True)

st.divider()

# --- 3. Main Data Fetch ---
query = """
    SELECT m.id, m.name, m.price_per_unit, m.unit, m.stock_level, m.min_stock_alert, m.type, 
           m.image_path, s.name as supplier_name, c.name as category_name, m.category_id, m.supplier_id
    FROM materials m
    LEFT JOIN suppliers s ON m.supplier_id = s.id
    LEFT JOIN material_categories c ON m.category_id = c.id
    WHERE 1=1
"""
params = []

if f_cat != "Todas":
    query += " AND c.name = ?"
    params.append(f_cat)
if f_sup != "Todos":
    query += " AND s.name = ?"
    params.append(f_sup)
if f_search:
    query += " AND m.name LIKE ?"
    params.append(f"%{f_search}%")

query += " ORDER BY m.name"

df_materials = pd.read_sql(query, conn, params=params)

# --- 4. Logic: Detail View OR Grid View ---

if st.session_state.insumo_edit_id is not None:
    # === DETAIL / EDIT MODE ===
    
    # Check if creating NEW or EDITING existing
    is_new = st.session_state.insumo_edit_id == "NEW"
    
    target_data = {}
    if not is_new:
        # Get fresh data
        try:
            target_data = df_materials[df_materials['id'] == st.session_state.insumo_edit_id].iloc[0]
        except IndexError:
            st.error("Insumo não encontrado.")
            st.session_state.insumo_edit_id = None
            st.rerun()
    
    # Header
    c_back, c_tit = st.columns([1, 5])
    if c_back.button("⬅️ Voltar ao Catálogo"):
        st.session_state.insumo_edit_id = None
        st.rerun()
    
    c_tit.subheader("Cadastrar Novo Insumo" if is_new else f"Editar: {target_data.get('name')}")
    
    with st.form("insumo_form"):
        col1, col2 = st.columns(2)
        
        # Basic Fields
        name = col1.text_input("Nome", value=target_data.get('name', ''))
        
        # Foreign Keys drop downs
        # Category
        curr_cat_idx = 0
        if not is_new and target_data.get('category_name'):
             if target_data['category_name'] in list(cat_map.keys()):
                 curr_cat_idx = list(cat_map.keys()).index(target_data['category_name'])
        
        sel_cat = col2.selectbox("Categoria", list(cat_map.keys()), index=curr_cat_idx)
        
        col3, col4 = st.columns(2)
        
        # Supplier
        curr_sup_idx = 0
        if not is_new and target_data.get('supplier_name'):
            if target_data['supplier_name'] in list(sup_map.keys()):
                 curr_sup_idx = list(sup_map.keys()).index(target_data['supplier_name'])
        
        sel_sup = col3.selectbox("Fornecedor", [""] + list(sup_map.keys()), index=curr_sup_idx + 1 if not is_new and target_data.get('supplier_name') else 0)
        
        m_type = col4.selectbox("Tipo", ["Material", "Mão de Obra", "Queima"], index=["Material", "Mão de Obra", "Queima"].index(target_data.get('type', 'Material')) if target_data.get('type') in ["Material", "Mão de Obra", "Queima"] else 0)
        
        st.markdown("---")
        # Calc Fields
        c5, c6, c7 = st.columns(3)
        price = c5.number_input("Preço Unit. (R$)", value=float(target_data.get('price_per_unit', 0.0)), step=0.01)
        unit = c6.selectbox("Unidade", ["kg", "L", "unidade", "hora (mão de obra)", "fornada"], index=["kg", "L", "unidade", "hora (mão de obra)", "fornada"].index(target_data.get('unit', 'kg')) if not is_new else 0)
        
        stock = c7.number_input("Estoque Atual", value=float(target_data.get('stock_level', 0.0)), step=0.1)
        min_alert = st.number_input("Alerta Mínimo", value=float(target_data.get('min_stock_alert', 0.0)), step=0.1)
        
        # Image Upload
        st.markdown("---")
        st.write("Imagem do Insumo")
        curr_img = target_data.get('image_path')
        if curr_img and os.path.exists(curr_img):
            st.image(curr_img, width=150, caption="Imagem Atual")
            
        new_img_file = st.file_uploader("Carregar nova imagem", type=["png", "jpg", "jpeg"])
        
        # Buttons
        submitted = st.form_submit_button("Salvar Insumo")
        
        if submitted:
            if not name:
                st.error("Nome é obrigatório.")
            else:
                cat_id = cat_map.get(sel_cat)
                sup_id = sup_map.get(sel_sup)
                
                # Handle Image
                final_img_path = curr_img # keep old if no new
                if new_img_file:
                    save_dir = "assets/material_images"
                    if not os.path.exists(save_dir): os.makedirs(save_dir)
                    # Unique name logic could be better, simplified here
                    file_path = os.path.join(save_dir, new_img_file.name)
                    with open(file_path, "wb") as f:
                        f.write(new_img_file.getbuffer())
                    final_img_path = file_path
                
                if is_new:
                    cursor.execute("""
                        INSERT INTO materials (name, price_per_unit, unit, stock_level, min_stock_alert, type, supplier_id, category_id, image_path)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (name, price, unit, stock, min_alert, m_type, sup_id, cat_id, final_img_path))
                    new_id = cursor.lastrowid
                    conn.commit()
                    audit.log_action(conn, 'CREATE', 'materials', new_id, None, {
                        'name': name, 'price_per_unit': price, 'unit': unit, 'stock_level': stock, 'type': m_type
                    })
                    st.success("Criado com sucesso!")
                    st.session_state.insumo_edit_id = None
                    time.sleep(1)
                    st.rerun()
                else:
                    target_id = st.session_state.insumo_edit_id
                    # Get old data for audit
                    old_mat = pd.read_sql("SELECT name, price_per_unit, unit, stock_level, type FROM materials WHERE id=?", conn, params=(target_id,))
                    old_data = old_mat.iloc[0].to_dict() if not old_mat.empty else {}
                    
                    cursor.execute("""
                        UPDATE materials 
                        SET name=?, price_per_unit=?, unit=?, stock_level=?, min_stock_alert=?, type=?, supplier_id=?, category_id=?, image_path=?
                        WHERE id=?
                    """, (name, price, unit, stock, min_alert, m_type, sup_id, cat_id, final_img_path, target_id))
                    conn.commit()
                    audit.log_action(conn, 'UPDATE', 'materials', target_id, old_data, {
                        'name': name, 'price_per_unit': price, 'unit': unit, 'stock_level': stock, 'type': m_type
                    })
                    st.success("Atualizado com sucesso!")
                    time.sleep(1)
                    st.rerun()

    # Delete Option (Only for Edit)
    if not is_new:
        st.markdown("---")
        with st.expander("Zona de Perigo"):
            if st.button("EXCLUIR INSUMO", type="primary"):
                # Get old data for audit
                old_mat = pd.read_sql("SELECT name, price_per_unit, unit, stock_level, type FROM materials WHERE id=?", conn, params=(st.session_state.insumo_edit_id,))
                old_data = old_mat.iloc[0].to_dict() if not old_mat.empty else {}
                
                cursor.execute("DELETE FROM materials WHERE id=?", (st.session_state.insumo_edit_id,))
                conn.commit()
                audit.log_action(conn, 'DELETE', 'materials', st.session_state.insumo_edit_id, old_data, None)
                st.success("Insumo excluído.")
                st.session_state.insumo_edit_id = None
                time.sleep(1)
                st.rerun()

else:
    # === CATALOG / GRID VIEW ===
    if df_materials.empty:
        st.info("Nenhum insumo encontrado com os filtros atuais.")
    else:
        # Display as cards/grid
        # We can iterate and use columns
        # Let's use 3 columns per row
        cols = st.columns(3)
        for i, row in df_materials.iterrows():
            with cols[i % 3]:
                # Card Container
                with st.container(border=True):
                    c_img, c_info = st.columns([1, 2])
                    
                    # Image
                    with c_img:
                        if row['image_path'] and os.path.exists(row['image_path']):
                            st.image(row['image_path'], use_container_width=True)
                        else:
                            st.write("🧱") # Placeholder icon
                    
                    # Info
                    with c_info:
                        st.markdown(f"**{row['name']}**")
                        cat_lbl = row['category_name'] if row['category_name'] else "Geral"
                        st.caption(f"{cat_lbl} | {row['type']}")
                        
                        # Stock Highlight
                        stock_val = row['stock_level']
                        if row['type'] == 'Mão de Obra' or row['unit'] == 'hora (mão de obra)':
                            st.write("Estoque: N/A")
                        else:
                            color = "red" if stock_val <= row['min_stock_alert'] else "green"
                            st.markdown(f"Estoque: :{color}[{stock_val} {row['unit']}]")

                        st.write(f"**R$ {row['price_per_unit']:.2f}** / {row['unit']}")
                    
                    # Edit Button (Full Width)
                    if st.button("✏️ Editar", key=f"edit_{row['id']}", use_container_width=True):
                        st.session_state.insumo_edit_id = row['id']
                        st.rerun()

conn.close()
