import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import database  # Use centralized DB connection

st.set_page_config(page_title="Gestão de Produtos", layout="wide")

# Database Connection
conn = database.get_connection()
cursor = conn.cursor()

st.title("📦 Produtos e Fichas Técnicas")

tab1, tab2 = st.tabs(["Configuração (Cadastro/Receita)", "Produção"])

# --- Tab 1: Configuração ---
with tab1:
    with st.expander("Cadastrar Novo Produto", expanded=False):
        with st.form("new_prod"):
            name = st.text_input("Nome do Produto")
            desc = st.text_area("Descrição")
            category = st.selectbox("Categoria", ["Utilitário", "Decorativo", "Outros"])
            markup = st.number_input("Markup Padrão", value=2.0, step=0.1)
            image_paths = "[]"
             
            if st.form_submit_button("Cadastrar"):
                if name:
                    try:
                        cursor.execute("""
                            INSERT INTO products (name, description, category, markup, image_paths, stock_quantity, base_price)
                            VALUES (?, ?, ?, ?, ?, 0, 0)
                        """, (name, desc, category, markup, image_paths))
                        conn.commit()
                        
                        # Get ID of new product
                        new_id = cursor.lastrowid
                        
                        # Auto-select for editing
                        st.session_state.editing_product_id = new_id
                        
                        st.success(f"Produto '{name}' criado! Configure a receita abaixo.")
                        time.sleep(1) 
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar: {e}")

    st.divider()

    # --- SHARED DATA FETCH (For Catalog and Production Tab) ---
    try:
        products = pd.read_sql("SELECT * FROM products", conn)
    except Exception as e:
        st.error(f"Erro ao ler banco de dados: {e}")
        products = pd.DataFrame()

    prod_dict = {}
    if not products.empty:
        prod_dict = {f"{row['name']} (Est: {row['stock_quantity']})": row['id'] for _, row in products.iterrows()}

    if "editing_product_id" not in st.session_state:
        st.session_state.editing_product_id = None

    # --- LOGIC: CATALOG OR EDIT ---
    if st.session_state.editing_product_id is None:
        # VISUAL CATALOG
        st.subheader("Catálogo de Produtos")
        if not products.empty:
            for i, row in products.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
                    
                    # Image
                    imgs = eval(row['image_paths']) if row['image_paths'] else []
                    with c1:
                        if imgs:
                             st.image(imgs[0], width=80)
                        else:
                            st.write("🖼️")
                    
                    # Info
                    with c2:
                        st.write(f"**{row['name']}**")
                        st.caption(f"{row['category']} | Est: {row['stock_quantity']}")
                    
                    # Price
                    with c3:
                        price = float(row['base_price']) if row['base_price'] else 0.0
                        st.write(f"R$ {price:.2f}")

                    # Edit Button
                    with c4:
                        if st.button("EDITAR", key=f"sel_prod_{row['id']}"):
                            st.session_state.editing_product_id = row['id']
                            st.rerun()
        else:
            st.info("Nenhum produto cadastrado. Use o formulário acima para adicionar.")

    else:
        # EDITING INTERFACE
        selected_prod_id = st.session_state.editing_product_id
        
        # Ensure product exists (fetch fresh data)
        try:
            curr_prod = pd.read_sql(f"SELECT * FROM products WHERE id={selected_prod_id}", conn).iloc[0]
        except IndexError:
            st.warning("Produto não encontrado (talvez excluído).")
            st.session_state.editing_product_id = None
            st.rerun()

        # Header with Back button
        c_back, c_title = st.columns([1, 5])
        with c_back:
            if st.button("⬅️ Voltar"):
                st.session_state.editing_product_id = None
                st.rerun()
        with c_title:
             st.markdown(f"### ✏️ Editando: {curr_prod['name']}")
        
        # --- 0. DETAILS EDIT (New) ---
        with st.expander("Editar Detalhes do Produto", expanded=False):
            with st.form("edit_details"):
                new_name = st.text_input("Nome", value=curr_prod['name'])
                
                # Safe category index logic
                cats = ["Utilitário", "Decorativo", "Outros"]
                curr_cat = curr_prod['category']
                cat_idx = cats.index(curr_cat) if curr_cat in cats else 0
                
                new_cat = st.selectbox("Categoria", cats, index=cat_idx)
                new_desc = st.text_area("Descrição", value=curr_prod['description'] or "")
                
                if st.form_submit_button("Salvar Detalhes"):
                    cursor.execute("UPDATE products SET name=?, category=?, description=? WHERE id=?", (new_name, new_cat, new_desc, selected_prod_id))
                    conn.commit()
                    st.success("Detalhes atualizados!")
                    # Just update local var to avoid full rerun jump if possible, but rerun easiest to sync UI title
                    st.rerun()

        # 0.1 IMAGE MANAGEMENT
        with st.expander("Gerenciar Imagens", expanded=True):
            curr_imgs = eval(curr_prod['image_paths']) if curr_prod['image_paths'] else []
            
            # Show current
            if curr_imgs:
                st.write("Imagens Atuais:")
                cols = st.columns(4)
                for i, img_path in enumerate(curr_imgs):
                    with cols[i % 4]:
                        try:
                            st.image(img_path, width=150)
                            if st.button("🗑️", key=f"del_img_{i}"):
                                curr_imgs.pop(i)
                                cursor.execute("UPDATE products SET image_paths=? WHERE id=?", (str(curr_imgs), selected_prod_id))
                                conn.commit()
                                st.rerun()
                        except:
                            st.error("Erro Imagem")
            
            # Upload new
            new_imgs = st.file_uploader("Adicionar Novas Imagens", accept_multiple_files=True)
            if new_imgs:
                if st.button("Salvar Novas Imagens"):
                    save_dir = "assets/product_images"
                    if not os.path.exists(save_dir): os.makedirs(save_dir)
                    for uf in new_imgs:
                         path = os.path.join(save_dir, uf.name)
                         with open(path, "wb") as f: f.write(uf.getbuffer())
                         curr_imgs.append(path)
                    
                    cursor.execute("UPDATE products SET image_paths=? WHERE id=?", (str(curr_imgs), selected_prod_id))
                    conn.commit()
                    st.success("Imagens adicionadas!")
                    st.rerun()

        # 1. RECIPE (Composição)
        st.subheader("1. Composição (Receita)")
        
        # Add Ingredient Form
        with st.expander("Adicionar Insumo à Receita"):
            with st.form("add_ingredient"):
                c1, c2 = st.columns([3, 1])
                materials = pd.read_sql("SELECT id, name, unit, price_per_unit FROM materials", conn)
                mat_dict = {f"{row['name']} ({row['unit']}) - R$ {row['price_per_unit']:.2f}": row['id'] for _, row in materials.iterrows()}
                
                mat_choice = c1.selectbox("Material/Mão de Obra", list(mat_dict.keys()))
                qty_needed = c2.number_input("Qtd", min_value=0.0, step=0.001, format="%.3f")
                
                if st.form_submit_button("Adicionar"):
                    if qty_needed > 0 and mat_choice:
                        mat_id = mat_dict[mat_choice]
                        cursor.execute("INSERT INTO product_recipes (product_id, material_id, quantity) VALUES (?, ?, ?)",
                                       (selected_prod_id, mat_id, qty_needed))
                        conn.commit()
                        st.rerun()

        # List/Edit Ingredients
        recipe_df = pd.read_sql(f"""
            SELECT pr.id, m.name, pr.quantity, m.unit, m.price_per_unit, (pr.quantity * m.price_per_unit) as cost
            FROM product_recipes pr
            JOIN materials m ON pr.material_id = m.id
            WHERE pr.product_id = {selected_prod_id}
        """, conn)
        
        cost_base = 0.0
        if not recipe_df.empty:
            # ADD REMOVE COLUMN for explicit deletion
            recipe_df['remove'] = False # Default False
            
            edited_recipe = st.data_editor(
                recipe_df,
                column_config={
                    "id": st.column_config.NumberColumn(disabled=True),
                    "name": st.column_config.TextColumn(label="Insumo", disabled=True),
                    "quantity": st.column_config.NumberColumn(label="Quantidade", min_value=0.0, step=0.001, required=True),
                    "unit": st.column_config.TextColumn(label="Unid.", disabled=True),
                    "price_per_unit": st.column_config.NumberColumn(label="Preço/Unid", disabled=True, format="R$ %.2f"),
                    "cost": st.column_config.NumberColumn(label="Custo", disabled=True, format="R$ %.2f"),
                    "remove": st.column_config.CheckboxColumn(label="Excluir?", help="Marque para remover este item")
                },
                hide_index=True,
                num_rows="dynamic",
                key=f"editor_recipe_{selected_prod_id}"
            )
            
            cost_base = (edited_recipe['quantity'] * edited_recipe['price_per_unit']).sum()

            if st.button("Salvar Alterações da Receita"):
                # Logic to handle updates and deletions (both implicit via UI delete and explicit check)
                
                # Rows present in editor
                current_rows = edited_recipe[edited_recipe['id'].notna()]
                
                # ID set logic
                ids_to_keep = set()
                ids_to_delete = set()
                
                # 1. Identify rows user requested to delete via Checkbox
                for i, row in current_rows.iterrows():
                    if row['remove']:
                        ids_to_delete.add(row['id'])
                    else:
                        ids_to_keep.add(row['id'])
                
                # 2. Identify rows deleted via UI (missing IDs)
                orig_ids = set(recipe_df['id'])
                # IDs that are in original but NOT in kept (because they were either removed via checkbox OR removed via UI X button)
                # Note: if removed via UI, they won't be in current_rows at all.
                # If removed via Checkbox, they ARE in current_rows but marked.
                
                # Effectively: Delete if ID is NOT in ids_to_keep.
                # Wait, ids_to_keep only tracks rows currently present and unchecked.
                
                # Let's simplify:
                # Any ID in orig_ids that is NOT in ids_to_keep should be deleted.
                
                final_delete_set = orig_ids - ids_to_keep
                
                # Execute deletes
                for did in final_delete_set:
                    cursor.execute("DELETE FROM product_recipes WHERE id=?", (did,))
                
                # Execute updates (for those kept)
                for i, row in current_rows.iterrows():
                    if row['id'] in ids_to_keep:
                         cursor.execute("UPDATE product_recipes SET quantity=? WHERE id=?", (row['quantity'], row['id']))
                
                conn.commit()
                st.success("Receita atualizada!")
                st.rerun()

        else:
            st.warning("Produto sem receita definida.")

        st.metric("Custo Base (Materiais + Mão de Obra)", f"R$ {cost_base:.2f}")
        
        # 2. PRICING & CALC UPDATE
        st.subheader("2. Precificação & Atualização")
        
        new_markup = st.number_input("Markup Padrão", value=float(curr_prod['markup']) if curr_prod['markup'] is not None else 2.0, step=0.1)
        suggested_price = cost_base * new_markup
        st.write(f"Preço Sugerido (Custo * Markup): **R$ {suggested_price:.2f}**")
        
        current_base = float(curr_prod['base_price']) if (curr_prod['base_price'] is not None and curr_prod['base_price'] != '') else 0.0
        default_val = current_base if current_base > 0 else suggested_price
        
        final_price = st.number_input("Preço Final de Venda", value=float(default_val), step=1.0)
        
        # --- NEW: EFFECTIVE MARKUP FEEDBACK ---
        if final_price > 0 and cost_base > 0:
            effective_markup = final_price / cost_base
            # Show if different from target markup
            if abs(effective_markup - new_markup) > 0.01:
                st.info(f"💡 Obs: O Markup efetivo para o preço de R$ {final_price:.2f} é **{effective_markup:.2f}** (Padrão: {new_markup})")
        
        if st.button("Salvar Preço e Markup"):
             cursor.execute("UPDATE products SET base_price=?, markup=? WHERE id=?", (final_price, new_markup, selected_prod_id))
             conn.commit()
             st.success("Atualizado!")
             time.sleep(1)
             st.rerun()

        if st.button("EXCLUIR PRODUTO", type="primary"):
            cursor.execute("DELETE FROM product_recipes WHERE product_id=?", (selected_prod_id,))
            cursor.execute("DELETE FROM products WHERE id=?", (selected_prod_id,))
            conn.commit()
            st.success("Produto excluído.")
            st.session_state.editing_product_id = None
            st.rerun()

# --- Tab 2: Production ---
with tab2:
    st.subheader("Registrar Produção")
    st.info("Produzir itens aumentará o estoque do Produto e descontará dos Insumos (conforme Receita).")
    
    prod_select = st.selectbox("Produto para Produzir", list(prod_dict.keys()), key="prod_select_prod")
    
    if prod_select:
        prod_id_prod = prod_dict[prod_select]
        
        qty_to_make = st.number_input("Quantidade a Produzir", min_value=1, step=1, value=1)
        
        # Preview Materials
        # Use try/except just in case
        try:
            # We fetch 'type' and 'unit' to filter out Labor
            recipe = pd.read_sql(f"""
                SELECT m.name, m.stock_level, (pr.quantity * {qty_to_make}) as needed, m.unit, m.type
                FROM product_recipes pr
                JOIN materials m ON pr.material_id = m.id
                WHERE pr.product_id = {prod_id_prod}
            """, conn)
            
            st.write("Impacto no Estoque de Insumos:")
            st.dataframe(recipe)
            
            # Check sufficient stock (Skip Labor)
            # Labor items: type='Mão de Obra' OR unit='hora (mão de obra)'
            # We create a mask for physical items
            is_physical = (recipe['type'] != 'Mão de Obra') & (recipe['unit'] != 'hora (mão de obra)')
            
            insufficient = recipe[is_physical & (recipe['stock_level'] < recipe['needed'])]
            
            if not insufficient.empty:
                st.error("Estoque insuficiente de insumos físicos:")
                st.dataframe(insufficient)
                disable_prod = True
            else:
                disable_prod = False
                
            if st.button("Confirmar Produção", disabled=disable_prod):
                
                # Re-fetch with ID for safe updates
                recipe_w_id = pd.read_sql(f"""
                    SELECT m.id, (pr.quantity * {qty_to_make}) as needed, m.type, m.unit
                    FROM product_recipes pr
                    JOIN materials m ON pr.material_id = m.id
                    WHERE pr.product_id = {prod_id_prod}
                """, conn)
                
                for _, row in recipe_w_id.iterrows():
                    # Only deduct if physical
                    if row['type'] != 'Mão de Obra' and row['unit'] != 'hora (mão de obra)':
                         cursor.execute("UPDATE materials SET stock_level = stock_level - ? WHERE id = ?", (row['needed'], row['id']))
                
                # Add Product Stock
                cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (qty_to_make, prod_id_prod))
                
                conn.commit()
                st.success(f"Adicionado {qty_to_make} ao estoque de produtos!")
                time.sleep(1)
                st.rerun()
        except Exception as e:
                st.error(f"Erro na produção: {e}")

conn.close()
