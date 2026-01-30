import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import database  # Use centralized DB connection
import admin_utils
import audit

st.set_page_config(page_title="Produtos", page_icon="🏺", layout="wide")
admin_utils.render_sidebar_logo()

# Database Connection
conn = database.get_connection()
cursor = conn.cursor()

admin_utils.render_header_logo()
st.title("📦 Produtos e Fichas Técnicas")

tab1, tab2 = st.tabs(["Configuração (Cadastro/Receita)", "Produção"])

# --- Tab 1: Configuração ---
with tab1:
    # Load Categories
    try:
        cat_df = pd.read_sql("SELECT name FROM product_categories", conn)
        cat_opts = cat_df['name'].tolist()
    except:
        cat_opts = ["Utilitário", "Decorativo", "Outros"]

    with st.expander("Gerenciar Categorias", expanded=False):
        c_cat1, c_cat2 = st.columns([2, 1])
        new_cat_name = c_cat1.text_input("Nova Categoria", placeholder="Nome da categoria...")
        if c_cat2.button("Adicionar Categoria"):
            if new_cat_name and new_cat_name not in cat_opts:
                try:
                    cursor.execute("INSERT INTO product_categories (name) VALUES (?)", (new_cat_name,))
                    conn.commit()
                    st.success(f"Categoria '{new_cat_name}' adicionada!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
            elif new_cat_name in cat_opts:
                st.warning("Categoria já existe.")
        
        # List to delete
        if cat_opts:
            st.divider()
            st.write("Categorias Existentes:")
            st.write(", ".join(cat_opts))
            
            del_cat = st.selectbox("Apagar Categoria", [""] + cat_opts)
            if st.button("Excluir Categoria Selecionada"):
                 if del_cat:
                    cursor.execute("DELETE FROM product_categories WHERE name=?", (del_cat,))
                    conn.commit()
                    st.success(f"Categoria '{del_cat}' removida!")
                    st.rerun()

    # --- SHARED DATA FETCH (For Catalog and Production Tab) ---
    try:
        products = pd.read_sql("SELECT * FROM products", conn)
    except Exception as e:
        st.error(f"Erro ao ler banco de dados: {e}")
        products = pd.DataFrame()

    prod_dict = {}
    if not products.empty:
        prod_dict = {f"[{row['id']}] {row['name']} (Est: {row['stock_quantity']})": row['id'] for _, row in products.iterrows()}

    if "editing_product_id" not in st.session_state:
        st.session_state.editing_product_id = None

    with st.expander("Cadastrar Novo Produto", expanded=False):
        # COPY SOURCE LOGIC
        copy_source_id = None
        base_name = ""
        base_desc = ""
        base_cat_idx = 0
        base_markup = 2.0
        
        # Selectbox for copy
        copy_choice = st.selectbox("Copiar dados de (opcional):", ["(Nenhum)"] + list(prod_dict.keys()))
        
        if copy_choice != "(Nenhum)":
            copy_source_id = prod_dict[copy_choice]
            # Fetch base data
            base_row = products[products['id'] == copy_source_id].iloc[0]
            base_name = f"{base_row['name']} (Cópia)"
            base_desc = base_row['description'] or ""
            base_markup = float(base_row['markup']) if base_row['markup'] else 2.0
            
            # Cat index
            if base_row['category'] in cat_opts:
                base_cat_idx = cat_opts.index(base_row['category'])

        with st.form("new_prod"):
            name = st.text_input("Nome do Produto", value=base_name)
            desc = st.text_area("Descrição", value=base_desc)
            
            # Use dynamic options
            category = st.selectbox("Categoria", cat_opts, index=base_cat_idx)
            
            markup = st.number_input("Markup Padrão", value=base_markup, step=0.1)
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
                        
                        # IF COPYING: Copy Recipe
                        if copy_source_id:
                            # Fetch recipe logic
                            base_recipe = pd.read_sql(f"SELECT material_id, quantity FROM product_recipes WHERE product_id={copy_source_id}", conn)
                            if not base_recipe.empty:
                                for _, br in base_recipe.iterrows():
                                    cursor.execute("INSERT INTO product_recipes (product_id, material_id, quantity) VALUES (?, ?, ?)",
                                                   (new_id, br['material_id'], br['quantity']))
                                conn.commit()
                                st.success("Receita copiada com sucesso!")

                        # Auto-select for editing
                        st.session_state.editing_product_id = new_id
                        
                        st.success(f"Produto '{name}' criado! Configure a receita abaixo.")
                        time.sleep(1) 
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao cadastrar: {e}")

    st.divider()



    if "editing_product_id" not in st.session_state:
        st.session_state.editing_product_id = None

    # --- LOGIC: CATALOG OR EDIT ---
    if st.session_state.editing_product_id is None:
        # VISUAL CATALOG
        st.subheader("Catálogo de Produtos")
        
        # --- Filters ---
        c_filt1, c_filt2 = st.columns([2, 1])
        search_term = c_filt1.text_input("🔍 Buscar", placeholder="Nome...")
        
        # Load Categories
        try:
            cat_opts = pd.read_sql("SELECT name FROM product_categories", conn)['name'].tolist()
        except: 
            cat_opts = [] # Fallback
            
        sel_cat_filt = c_filt2.selectbox("Filtrar Categoria", ["Todas"] + cat_opts)
        
        # Apply Filters
        filtered_products = products.copy()
        if search_term:
            filtered_products = filtered_products[filtered_products['name'].str.contains(search_term, case=False, na=False)]
        
        if sel_cat_filt != "Todas":
            filtered_products = filtered_products[filtered_products['category'] == sel_cat_filt]

        if not filtered_products.empty:
            for i, row in filtered_products.iterrows():
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
                        st.caption(f"ID: {row['id']} | {row['category']} | Est: {row['stock_quantity']}")
                    
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
            st.info("Nenhum produto encontrado.")

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
                # Ensure cat_opts available (fetched at top of tab)
                if 'cat_opts' not in locals():
                     try: cat_opts = pd.read_sql("SELECT name FROM product_categories", conn)['name'].tolist()
                     except: cat_opts = ["Utilitário", "Decorativo", "Outros"]

                curr_cat = curr_prod['category']
                cat_idx = cat_opts.index(curr_cat) if curr_cat in cat_opts else 0
                
                new_cat = st.selectbox("Categoria", cat_opts, index=cat_idx)
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
            
            # Check sufficient stock (Skip Labor & Firing)
            # Labor items: type='Mão de Obra' OR unit='hora (mão de obra)'
            # Firing items: type='Queima' OR unit='fornada' OR name starts with 'Queima'
            # We create a mask for physical items
            is_burning = (recipe['unit'] == 'fornada') | (recipe['name'].str.startswith('Queima')) | (recipe['type'] == 'Queima')
            is_labor = (recipe['type'] == 'Mão de Obra') | (recipe['unit'] == 'hora (mão de obra)')
            
            is_physical = ~(is_burning | is_labor)
            
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
                    SELECT m.id, m.name, (pr.quantity * {qty_to_make}) as needed, m.type, m.unit
                    FROM product_recipes pr
                    JOIN materials m ON pr.material_id = m.id
                    WHERE pr.product_id = {prod_id_prod}
                """, conn)
                
                for _, row in recipe_w_id.iterrows():
                    # Only deduct if physical
                    # Same logic as above
                    is_burning = (row['unit'] == 'fornada') or (str(row['name']).startswith('Queima')) or (row['type'] == 'Queima')
                    is_labor = (row['type'] == 'Mão de Obra') or (row['unit'] == 'hora (mão de obra)')
                    
                    if not (is_burning or is_labor):
                         cursor.execute("UPDATE materials SET stock_level = stock_level - ? WHERE id = ?", (row['needed'], row['id']))
                
                # Add Product Stock
                cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (qty_to_make, prod_id_prod))
                
                # Log production history
                from datetime import datetime as dt
                user_id, username = None, 'system'
                if 'current_user' in st.session_state and st.session_state.current_user:
                    user_id = st.session_state.current_user.get('id')
                    username = st.session_state.current_user.get('username', 'unknown')
                
                # Get product name
                prod_name_row = pd.read_sql("SELECT name FROM products WHERE id=?", conn, params=(prod_id_prod,))
                prod_name = prod_name_row.iloc[0]['name'] if not prod_name_row.empty else 'Produto'
                
                cursor.execute("""
                    INSERT INTO production_history (timestamp, product_id, product_name, quantity, order_id, user_id, username, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (dt.now().isoformat(), prod_id_prod, prod_name, qty_to_make, None, user_id, username, 'Produção avulsa'))
                
                # Get the inserted ID for audit
                new_prod_hist_id = cursor.lastrowid
                
                conn.commit()
                
                # Audit log
                audit.log_action(conn, 'CREATE', 'production_history', new_prod_hist_id, None, {
                    'product_id': prod_id_prod, 'product_name': prod_name, 'quantity': qty_to_make, 'notes': 'Produção avulsa'
                })
                
                st.success(f"Adicionado {qty_to_make} ao estoque de produtos!")
                time.sleep(1)
                st.rerun()
        except Exception as e:
                st.error(f"Erro na produção: {e}")
    
    # --- PRODUCTION HISTORY ---
    st.divider()
    st.subheader("📜 Histórico de Produção")
    
    # Filters
    fh1, fh2, fh3 = st.columns(3)
    
    with fh1:
        # Date filter
        from datetime import timedelta
        filter_days = st.selectbox("Período", ["Hoje", "Últimos 7 dias", "Últimos 30 dias", "Todo"], index=1)
    
    with fh2:
        # Product filter
        prod_names = pd.read_sql("SELECT DISTINCT product_name FROM production_history ORDER BY product_name", conn)
        prod_filter_opts = ["Todos"] + (prod_names['product_name'].tolist() if not prod_names.empty else [])
        filter_prod = st.selectbox("Produto", prod_filter_opts)
    
    with fh3:
        # User filter
        user_names = pd.read_sql("SELECT DISTINCT username FROM production_history ORDER BY username", conn)
        user_filter_opts = ["Todos"] + (user_names['username'].tolist() if not user_names.empty else [])
        filter_user = st.selectbox("Usuário", user_filter_opts)
    
    # Build query
    from datetime import datetime as dt, date as dt_date
    query_parts = ["SELECT * FROM production_history WHERE 1=1"]
    params = []
    
    if filter_days == "Hoje":
        query_parts.append("AND timestamp LIKE ?")
        params.append(dt_date.today().isoformat() + '%')
    elif filter_days == "Últimos 7 dias":
        start = (dt_date.today() - timedelta(days=7)).isoformat()
        query_parts.append("AND timestamp >= ?")
        params.append(start)
    elif filter_days == "Últimos 30 dias":
        start = (dt_date.today() - timedelta(days=30)).isoformat()
        query_parts.append("AND timestamp >= ?")
        params.append(start)
    
    if filter_prod != "Todos":
        query_parts.append("AND product_name = ?")
        params.append(filter_prod)
    
    if filter_user != "Todos":
        query_parts.append("AND username = ?")
        params.append(filter_user)
    
    query_parts.append("ORDER BY timestamp DESC LIMIT 100")
    
    history_df = pd.read_sql(" ".join(query_parts), conn, params=params)
    
    # Statistics
    if not history_df.empty:
        total_items = history_df['quantity'].sum()
        unique_products = history_df['product_name'].nunique()
        st.caption(f"**{len(history_df)}** registros | **{int(total_items)}** peças | **{unique_products}** produtos diferentes")
    
    # Display
    if not history_df.empty:
        for _, row in history_df.iterrows():
            ts = row['timestamp'][:16].replace('T', ' ')
            order_info = f" (Encomenda #{row['order_id']})" if row['order_id'] else ""
            notes_info = f" — {row['notes']}" if row['notes'] else ""
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                
                with c1:
                    st.markdown(f"**{row['product_name']}** x{row['quantity']}")
                    st.caption(f"🕐 {ts} | 👤 {row['username']}{order_info}{notes_info}")
                
                with c2:
                    # Edit popover
                    with st.popover("✏️"):
                        st.caption(f"Editar: {row['product_name']}")
                        new_qty = st.number_input("Nova Quantidade", min_value=1, value=int(row['quantity']), key=f"edit_qty_{row['id']}")
                        
                        if st.button("💾 Salvar", key=f"save_qty_{row['id']}"):
                            diff = new_qty - row['quantity']
                            
                            # Update production history
                            cursor.execute("UPDATE production_history SET quantity = ? WHERE id = ?", (new_qty, row['id']))
                            
                            # Adjust product stock accordingly
                            cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (diff, row['product_id']))
                            
                            conn.commit()
                            
                            # Audit log
                            audit.log_action(conn, 'UPDATE', 'production_history', row['id'], 
                                {'quantity': row['quantity']}, {'quantity': new_qty})
                            
                            st.success("Atualizado!")
                            time.sleep(0.5)
                            st.rerun()
                
                with c3:
                    # Delete button
                    if st.button("🗑️", key=f"del_prod_{row['id']}", help="Excluir registro"):
                        # Capture for audit
                        old_data = {'product_id': row['product_id'], 'product_name': row['product_name'], 'quantity': row['quantity']}
                        
                        # Revert stock: subtract the quantity that was recorded
                        cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?", (row['quantity'], row['product_id']))
                        cursor.execute("DELETE FROM production_history WHERE id = ?", (row['id'],))
                        conn.commit()
                        
                        # Audit log
                        audit.log_action(conn, 'DELETE', 'production_history', row['id'], old_data, None)
                        
                        st.success("Registro excluído e estoque revertido!")
                        time.sleep(0.5)
                        st.rerun()
    else:
        st.info("Nenhum registro de produção encontrado para os filtros selecionados.")

conn.close()
