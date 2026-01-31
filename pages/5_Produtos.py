import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import database  # Use centralized DB connection
import admin_utils
import auth
import audit

st.set_page_config(page_title="Produtos", page_icon="🏺", layout="wide")
admin_utils.render_sidebar_logo()

# Database Connection
conn = database.get_connection()
cursor = conn.cursor()

auth.render_custom_sidebar()
st.title("📦 Produtos e Fichas Técnicas")

tab1, tab2 = st.tabs(["Catálogo & Produção", "Histórico de Produção"])

# --- Tab 1: Catálogo & Produção ---
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

    # --- SHARED DATA FETCH ---
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

    # --- TOP BAR: FILTERS & CONTROLS ---
    # Layout: [Filter Cat] [Spacer] [Search] [New Button]
    c_filter1, c_space, c_filter2, c_add = st.columns([1.5, 0.5, 1.5, 1.2])
    
    # Filter Category
    sel_cat_filt = c_filter1.selectbox("Filtrar Categoria", ["Todas"] + cat_opts)
    
    # Search
    search_term = c_filter2.text_input("Buscar Produto", placeholder="Nome...")
    
    # New Button
    with c_add:
        st.write("") # Align
        if st.button("➕ Novo Produto", type="primary", use_container_width=True):
             st.session_state.editing_product_id = "NEW"
             st.rerun()

    st.divider()

    # --- LOGIC: CATALOG, NEW, OR EDIT ---
    if st.session_state.editing_product_id is None:
        # VISUAL CATALOG
        
        # Apply Filters (Global now)
        filtered_products = products.copy()
        if search_term:
            filtered_products = filtered_products[filtered_products['name'].str.contains(search_term, case=False, na=False)]
        
        if sel_cat_filt != "Todas":
            filtered_products = filtered_products[filtered_products['category'] == sel_cat_filt]

        if not filtered_products.empty:
            for i, row in filtered_products.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4, c5 = st.columns([1, 2, 1, 0.5, 0.5])
                    
                    # Image
                    imgs = eval(row['image_paths']) if row['image_paths'] else []
                    
                    # Logic: If no direct images, check if it is a Kit and fetch component images
                    if not imgs:
                        kit_children = pd.read_sql("SELECT child_product_id FROM product_kits WHERE parent_product_id=?", conn, params=(row['id'],))
                        if not kit_children.empty:
                            c_ids = ",".join(map(str, kit_children['child_product_id'].tolist()))
                            c_imgs_df = pd.read_sql(f"SELECT image_paths FROM products WHERE id IN ({c_ids})", conn)
                            for _, ci_row in c_imgs_df.iterrows():
                                ci_list = eval(ci_row['image_paths']) if ci_row['image_paths'] else []
                                if ci_list:
                                    imgs.extend(ci_list)
                    
                    with c1:
                        if imgs:
                            # Show up to 2 images for kits if available to give a "composite" feel? 
                            # Or just the first one. User asked "not just 1 image" maybe implying seeing the set.
                            # Carousel-like or just static? St.image handles lists by stacking.
                            # Let's show first 2 side-by-side if multiple, or just main.
                            # Since column is small (width 1), better to show just one main or a small gallery.
                            # "aparece só 1 imagem e não duas" -> implies they want to see the 2 components.
                            
                            if len(imgs) > 1:
                                cols_img = st.columns(2)
                                with cols_img[0]:
                                    st.image(imgs[0], use_container_width=True)
                                with cols_img[1]:
                                    st.image(imgs[1], use_container_width=True)
                            else:
                                st.image(imgs[0], use_container_width=True)
                        else:
                            # Try to check if it's a kit to show a "Kit" icon reference
                            # Optimized: we already checked for kit above and found no images.
                            st.write("🖼️")
                    
                    # Info
                    with c2:
                        # DYNAMIC STOCK FOR KITS
                        display_stock = row['stock_quantity']
                        is_kit = False
                        
                        # Check kit components to min-max stock
                        # Optimization: We already checked product_kits above for images, but let's re-query specifically for qty
                        # Or safer: just query valid components
                        kit_stock_df = pd.read_sql("""
                            SELECT pk.quantity, p.stock_quantity as child_stock, p.name
                            FROM product_kits pk
                            JOIN products p ON pk.child_product_id = p.id
                            WHERE pk.parent_product_id = ?
                        """, conn, params=(row['id'],))
                        
                        breakdown_str = ""
                        if not kit_stock_df.empty:
                            is_kit = True
                            # Calculate max producible kits
                            kit_stock_df['max_possible'] = kit_stock_df['child_stock'] // kit_stock_df['quantity']
                            display_stock = int(kit_stock_df['max_possible'].min())
                            if display_stock < 0: display_stock = 0
                            
                            # Construct breakdown
                            items = []
                            for _, kr in kit_stock_df.iterrows():
                                items.append(f"{kr['name']}: {kr['child_stock']}")
                            breakdown_str = " | ".join(items)

                        st.write(f"**{row['name']}**")
                        stock_label = f"📦 Kit: {display_stock} (Calc)" if is_kit else f"Est: {row['stock_quantity']}"
                        st.caption(f"ID: {row['id']} | {row['category']} | {stock_label}")
                        if breakdown_str:
                            st.caption(f"🔎 {breakdown_str}")
                    
                    # Price
                    with c3:
                        price = float(row['base_price']) if row['base_price'] else 0.0
                        st.write(f"R$ {price:.2f}")

                    # PRODUCE Button (Popover)
                    with c4:
                        with st.popover("🔨", help="Registrar Produção"):
                            st.markdown(f"**Produzir: {row['name']}**")
                            qty_make = st.number_input("Qtd", min_value=1, value=1, key=f"make_qty_{row['id']}")
                            
                            # Validation: cannot produce more than dynamic stock if kit?
                            # Actually production of kit consumes components, so as long as we have components...
                            # But wait, 'Produce' button on Kit usually means 'Assemble'.
                            # If we assemble, we consume stock. That logic is fine.
                            
                            if st.button("Confirmar", key=f"btn_make_{row['id']}", type="primary"):
                                try:
                                    # Fetch Recipe
                                    recipe = pd.read_sql(f"""
                                        SELECT m.id, m.name, m.stock_level, (pr.quantity * {qty_make}) as needed, m.unit, m.type
                                        FROM product_recipes pr
                                        JOIN materials m ON pr.material_id = m.id
                                        WHERE pr.product_id = {row['id']}
                                    """, conn)
                                    
                                    # Check Stock (Physical only)
                                    is_burning = (recipe['unit'] == 'fornada') | (recipe['name'].str.startswith('Queima')) | (recipe['type'] == 'Queima')
                                    is_labor = (recipe['type'] == 'Mão de Obra') | (recipe['unit'] == 'hora (mão de obra)')
                                    is_physical = ~(is_burning | is_labor)
                                    
                                    insufficient = recipe[is_physical & (recipe['stock_level'] < recipe['needed'])]
                                    
                                    if not insufficient.empty:
                                        st.error("Estoque insuficiente!")
                                        st.dataframe(insufficient[['name', 'stock_level', 'needed']])
                                    else:
                                        # Execute Production
                                        from datetime import datetime as dt
                                        user_id, username = None, 'system'
                                        if 'current_user' in st.session_state and st.session_state.current_user:
                                            user_id = int(st.session_state.current_user.get('id'))
                                            username = st.session_state.current_user.get('username', 'unknown')
                                            
                                    # LOGIC: Check if it's a KIT (has entries in product_kits)
                                    kits = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn, params=(row['id'],))
                                    
                                    if not kits.empty:
                                        # === IT IS A KIT ===
                                        # Check sufficiency of Child Products
                                        can_make_kit = True
                                        miss_msg = []
                                        
                                        for _, kit_item in kits.iterrows():
                                            needed_total = kit_item['quantity'] * qty_make
                                            # Check stock of child
                                            child_stock = pd.read_sql("SELECT stock_quantity, name FROM products WHERE id=?", conn, params=(kit_item['child_product_id'],)).iloc[0]
                                            
                                            if child_stock['stock_quantity'] < needed_total:
                                                can_make_kit = False
                                                miss_msg.append(f"{child_stock['name']}: Precisa {needed_total}, Tem {child_stock['stock_quantity']}")
                                        
                                        if not can_make_kit:
                                            st.error(f"Estoque insuficiente de componentes: {', '.join(miss_msg)}")
                                        else:
                                            # Deduct Child Products
                                            for _, kit_item in kits.iterrows():
                                                 needed_total = kit_item['quantity'] * qty_make
                                                 child_id = kit_item['child_product_id']
                                                 
                                                 cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?", (needed_total, child_id))
                                                 # Log Usage? Optional, maybe internal transfer log.
                                            
                                            # Add Kit Stock
                                            cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (qty_make, row['id']))
                                            
                                            # Log Production
                                            cursor.execute("INSERT INTO production_history (timestamp, product_id, product_name, quantity, user_id, username, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                                           (dt.now().isoformat(), row['id'], row['name'], qty_make, user_id, username, 'Produção de Kit'))
                                            
                                            audit.log_action(conn, 'CREATE', 'production_history', cursor.lastrowid, None, {'product_id': row['id'], 'quantity': qty_make, 'type': 'KIT'})
                                            conn.commit()
                                            st.toast(f"Kit Montado: {qty_make}x {row['name']}!", icon="📦")
                                            time.sleep(1)
                                            st.rerun()

                                    else:
                                        # === REGULAR PRODUCTION (Raw Materials) ===
                                        # 1. Fetch Recipe
                                        recipe = pd.read_sql("""
                                            SELECT m.id, m.name, m.stock_level, pr.quantity as needed_per_unit, m.unit, m.type
                                            FROM product_recipes pr
                                            JOIN materials m ON pr.material_id = m.id
                                            WHERE pr.product_id = ?
                                        """, conn, params=(row['id'],))
                                        
                                        if recipe.empty:
                                            st.warning("Produto sem receita cadastrada! Apenas o estoque do produto será ajustado.")
                                            # Just Update Stock
                                            cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (qty_make, row['id']))
                                            cursor.execute("INSERT INTO production_history (timestamp, product_id, product_name, quantity, user_id, username, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                                           (dt.now().isoformat(), row['id'], row['name'], qty_make, user_id, username, 'Produção Sem Receita'))
                                            conn.commit()
                                            st.rerun()
                                        else:
                                            # Calculate total needed
                                            recipe['needed'] = recipe['needed_per_unit'] * qty_make
                                            
                                            # Check sufficient stock (Skip Labor & Firing)
                                            # Labor items: type='Mão de Obra' OR unit='hora (mão de obra)'
                                            # Firing items: type='Queima' OR unit='fornada' OR name starts with 'Queima'
                                            # We create a mask for physical items
                                            is_burning = (recipe['unit'] == 'fornada') | (recipe['name'].str.startswith('Queima')) | (recipe['type'] == 'Queima')
                                            is_labor = (recipe['type'] == 'Mão de Obra') | (recipe['unit'] == 'hora (mão de obra)')

                                            is_physical = ~(is_burning | is_labor)

                                            insufficient = recipe[is_physical & (recipe['stock_level'] < recipe['needed'])]
                                            
                                            if not insufficient.empty:
                                                st.error(f"Falta insumo: {', '.join(insufficient['name'].tolist())}")
                                            else:
                                                # Deduct Stock
                                                for _, mat in recipe.iterrows():
                                                    if not ((mat['unit'] == 'fornada') or (str(mat['name']).startswith('Queima')) or (mat['type'] == 'Queima') or (mat['type'] == 'Mão de Obra') or (mat['unit'] == 'hora (mão de obra)')):
                                                         # Explicit Type Casting
                                                         needed_py = float(mat['needed'])
                                                         mat_id_py = int(mat['id'])
                                                         
                                                         cursor.execute("UPDATE materials SET stock_level = stock_level - ? WHERE id = ?", (needed_py, mat_id_py))
                                                         # Log Consumption
                                                         cursor.execute("""
                                                            INSERT INTO inventory_transactions (material_id, date, type, quantity, notes, user_id)
                                                            VALUES (?, ?, ?, ?, ?, ?)
                                                        """, (mat_id_py, dt.now().isoformat(), 'SAIDA', needed_py, f"Prod: {qty_make}x {row['name']}", user_id))
                                                         st.toast(f"Baixado {needed_py} de {mat['name']}")
                                                    else:
                                                         st.toast(f"Ignorado (Não-físico): {mat['name']}")
                                                
                                                # Update Product Stock
                                                cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (qty_make, row['id']))
                                                cursor.execute("INSERT INTO production_history (timestamp, product_id, product_name, quantity, user_id, username, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                                               (dt.now().isoformat(), row['id'], row['name'], qty_make, user_id, username, 'Produção Rápida'))
                                                
                                                audit.log_action(conn, 'CREATE', 'production_history', cursor.lastrowid, None, {'product_id': row['id'], 'quantity': qty_make})
                                                conn.commit()
                                                st.toast(f"Produzido: {qty_make}x {row['name']}!", icon="✅")
                                                time.sleep(1)
                                                st.rerun()
 
                                except Exception as e:
                                    st.error(f"Erro: {e}")

                    # Edit Button
                    with c5:
                        if st.button("✏️", key=f"sel_prod_{row['id']}", help="Editar Produto"):
                            st.session_state.editing_product_id = row['id']
                            st.rerun()
        else:
            st.info("Nenhum produto encontrado.")

    elif st.session_state.editing_product_id == "NEW":
        # === CREATE MODE ===
        c_back, c_tit = st.columns([1, 5])
        if c_back.button("⬅️ Cancelar"):
            st.session_state.editing_product_id = None
            st.rerun()
        c_tit.subheader("✨ Novo Produto")
        
        st.info("Preencha os dados básicos para criar o produto. Receita e Imagens poderão ser adicionadas em seguida.")
        
        with st.form("create_prod_form"):
            new_name = st.text_input("Nome do Produto")
            new_cat = st.selectbox("Categoria", cat_opts)
            new_markup = st.number_input("Markup Sugerido", value=2.0, step=0.1)
            new_desc = st.text_area("Descrição")
            
            if st.form_submit_button("Criar Produto"):
                if new_name:
                    try:
                        cursor.execute("""
                            INSERT INTO products (name, description, category, markup, image_paths, stock_quantity, base_price)
                            VALUES (?, ?, ?, ?, ?, 0, 0)
                        """, (new_name, new_desc, new_cat, new_markup, "[]"))
                        conn.commit()
                        new_id = cursor.lastrowid
                        
                        st.success(f"Produto '{new_name}' criado!")
                        st.session_state.editing_product_id = new_id # Switch to Edit Mode
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
                else:
                    st.warning("Nome é obrigatório.")

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
                
                # --- NEW: Manual Stock Adjustment ---
                
                # Check if it is a KIT
                is_kit_edit = False
                kit_stock_calc = 0
                check_kit = pd.read_sql("""
                    SELECT pk.quantity, p.stock_quantity as child_stock, p.name 
                    FROM product_kits pk
                    JOIN products p ON pk.child_product_id = p.id
                    WHERE pk.parent_product_id = ?
                """, conn, params=(selected_prod_id,))
                
                kit_info_text = ""
                if not check_kit.empty:
                    is_kit_edit = True
                    check_kit['max'] = check_kit['child_stock'] // check_kit['quantity']
                    kit_stock_calc = int(check_kit['max'].min())
                    if kit_stock_calc < 0: kit_stock_calc = 0
                    
                    # Debug info
                    kit_info_text = "Estoque calculado pelos componentes: " + ", ".join([f"{r['name']}: {int(r['child_stock'])} (Precisa {r['quantity']})" for _, r in check_kit.iterrows()])

                if is_kit_edit:
                    st.info(f"📦 Este produto é um Kit. Estoque calculado: **{kit_stock_calc}**")
                    st.caption(kit_info_text)
                    new_stock = st.number_input("Estoque (Calculado Auto)", value=kit_stock_calc, disabled=True, help="O estoque de kits é baseado na disponibilidade dos seus componentes.")
                else:
                    curr_stock = int(curr_prod['stock_quantity']) if curr_prod['stock_quantity'] else 0
                    new_stock = st.number_input("Estoque Atual", value=curr_stock, step=1, help="Alterar este valor registrará um ajuste manual no histórico.")
                
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
                    # Check stock diff (ONLY IF NOT KIT, or if we decide to store cached stock for kit? 
                    # If kit, we usually don't update stock_quantity column manually, just let it be cached or ignore.
                    # Best practice: Update stock_quantity column with filtered calc value so simplistic queries work?
                    # Let's save the calculated value to DB for performance in other simple queries, even if read-only here.
                    
                    if not is_kit_edit:
                         if new_stock != (int(curr_prod['stock_quantity']) if curr_prod['stock_quantity'] else 0):
                            diff = new_stock - (int(curr_prod['stock_quantity']) if curr_prod['stock_quantity'] else 0)
                            # Log adjustment
                            from datetime import datetime as dt
                            # Get user
                            user_id, username = None, 'system'
                            if 'current_user' in st.session_state and st.session_state.current_user:
                                user_id = int(st.session_state.current_user.get('id'))
                                username = st.session_state.current_user.get('username', 'unknown')
                                
                            cursor.execute("""
                                INSERT INTO production_history (timestamp, product_id, product_name, quantity, user_id, username, notes)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (dt.now().isoformat(), selected_prod_id, new_name, diff, user_id, username, "Ajuste Manual"))

                    cursor.execute("UPDATE products SET name=?, category=?, description=?, stock_quantity=? WHERE id=?", (new_name, new_cat, new_desc, new_stock, selected_prod_id))
                    conn.commit()
                    st.success("Detalhes atualizados!")
                    # Just update local var to avoid full rerun jump if possible, but rerun easiest to sync UI title
                    st.rerun()

        # TABS INTERFACE
        tab_recipe, tab_comp, tab_pricing, tab_images = st.tabs(["📜 Receita", "📦 Composição (Kit)", "💰 Precificação", "📷 Imagens"])

        # --- TAB 1: RECEITA (INSUMOS) ---
        with tab_recipe:
            st.caption("Adicione matérias-primas (argila, esmaltes) usadas para criar este produto.")
            with st.form("add_ingredient"):
                c1, c2 = st.columns([3, 1])
                materials = pd.read_sql("SELECT id, name, unit, price_per_unit FROM materials ORDER BY name", conn)
                mat_dict = {f"{row['name']} ({row['unit']}) - R$ {row['price_per_unit']:.2f}": row['id'] for _, row in materials.iterrows()}
                
                mat_choice = c1.selectbox("Material/Mão de Obra", [""] + list(mat_dict.keys()))
                qty_needed = c2.number_input("Qtd", min_value=0.0, step=0.001, format="%.3f")
                
                if st.form_submit_button("➕ Adicionar Insumo"):
                    if qty_needed > 0 and mat_choice:
                        mat_id = mat_dict[mat_choice]
                        cursor.execute("INSERT INTO product_recipes (product_id, material_id, quantity) VALUES (?, ?, ?)",
                                       (selected_prod_id, mat_id, qty_needed))
                        conn.commit()
                        st.rerun()

            # List Ingredients
            current_recipe = pd.read_sql("""
                SELECT pr.id, m.name, pr.quantity, m.unit, m.price_per_unit
                FROM product_recipes pr
                JOIN materials m ON pr.material_id = m.id
                WHERE pr.product_id = ?
            """, conn, params=(selected_prod_id,))
            
            if not current_recipe.empty:
                st.dataframe(current_recipe, hide_index=True, use_container_width=True)
                # Remove
                del_id = st.selectbox("Remover Insumo ID", [""] + current_recipe['id'].astype(str).tolist())
                if st.button("🗑️ Remover Insumo selecionado"):
                    if del_id:
                        cursor.execute("DELETE FROM product_recipes WHERE id=?", (del_id,))
                        conn.commit()
                        st.rerun()
            else:
                st.info("Nenhuma receita definida.")

        # --- TAB 2: COMPOSIÇÃO (KITS) ---
        with tab_comp:
            st.caption("Use esta aba se este produto for um CONJUNTO formado por outros produtos prontos (Ex: Kit Xícara + Pires).")
            
            with st.form("add_kit_item"):
                c1, c2 = st.columns([3, 1])
                # Filter out self
                prods = pd.read_sql("SELECT id, name FROM products WHERE id != ? ORDER BY name", conn, params=(selected_prod_id,))
                prod_dict = {row['name']: row['id'] for _, row in prods.iterrows()}
                
                prod_choice = c1.selectbox("Produto Componente", [""] + list(prod_dict.keys()))
                k_qty = c2.number_input("Qtd", min_value=1, value=1)
                
                if st.form_submit_button("➕ Adicionar Componente"):
                    if prod_choice:
                        child_id = prod_dict[prod_choice]
                        cursor.execute("INSERT INTO product_kits (parent_product_id, child_product_id, quantity) VALUES (?, ?, ?)",
                                       (selected_prod_id, child_id, k_qty))
                        conn.commit()
                        st.toast("Componente adicionado!")
                        time.sleep(1)
                        st.rerun()
            
            # List Kit Items
            kit_items = pd.read_sql("""
                SELECT pk.id, p.name as component_name, pk.quantity
                FROM product_kits pk
                JOIN products p ON pk.child_product_id = p.id
                WHERE pk.parent_product_id = ?
            """, conn, params=(selected_prod_id,))
            
            if not kit_items.empty:
                st.warning("⚠️ Nota: Ao produzir este KIT, o estoque dos componentes abaixo será descontado.")
                st.dataframe(kit_items, hide_index=True, use_container_width=True)
                
                del_kit_id = st.selectbox("Remover Componente ID", [""] + kit_items['id'].astype(str).tolist())
                if st.button("🗑️ Remover Componente selecionado"):
                     cursor.execute("DELETE FROM product_kits WHERE id=?", (del_kit_id,))
                     conn.commit()
                     st.rerun()

        # --- TAB 3: IMAGENS ---
        with tab_images:
            st.caption("Gerencie as fotos do produto.")
            # Reuse logic from expanding section
            curr_imgs = eval(curr_prod['image_paths']) if curr_prod['image_paths'] else []
            
            if curr_imgs:
                cols = st.columns(4)
                for i, img_path in enumerate(curr_imgs):
                    with cols[i % 4]:
                        try:
                            st.image(img_path, width=150)
                            if st.button("🗑️", key=f"del_img_t_{i}"):
                                curr_imgs.pop(i)
                                cursor.execute("UPDATE products SET image_paths=? WHERE id=?", (str(curr_imgs), selected_prod_id))
                                conn.commit()
                                st.rerun()
                        except: pass
            
            new_imgs = st.file_uploader("Upload Novas Imagens", accept_multiple_files=True, key="new_imgs_tab")
            if new_imgs:
                if st.button("Salvar Imagens"):
                    save_dir = "assets/product_images"
                    if not os.path.exists(save_dir): os.makedirs(save_dir)
                    for uf in new_imgs:
                         path = os.path.join(save_dir, uf.name)
                         with open(path, "wb") as f: f.write(uf.getbuffer())
                         curr_imgs.append(path)
                    cursor.execute("UPDATE products SET image_paths=? WHERE id=?", (str(curr_imgs), selected_prod_id))
                    conn.commit()
                    st.success("Salvo!")
                    st.rerun()

            # --- NEW: Auto-Display Component Images (Kits) ---
            comps = pd.read_sql("SELECT child_product_id FROM product_kits WHERE parent_product_id=?", conn, params=(selected_prod_id,))
            if not comps.empty:
                st.markdown("---")
                st.info("ℹ️ Abaixo são exibidas automaticamente as imagens dos produtos que compõem este kit.")
                
                comp_ids = comps['child_product_id'].tolist()
                id_list = ",".join(map(str, comp_ids))
                
                comp_prods = pd.read_sql(f"SELECT name, image_paths FROM products WHERE id IN ({id_list})", conn)
                
                for _, cp in comp_prods.iterrows():
                    cp_imgs = eval(cp['image_paths']) if cp['image_paths'] else []
                    if cp_imgs:
                        st.caption(f"De: **{cp['name']}**")
                        c_imgs = st.columns(6)
                        for idx, p_img in enumerate(cp_imgs):
                            with c_imgs[idx % 6]:
                                try:
                                    st.image(p_img, width=100)
                                except: pass

        # --- TAB 4: PRECIFICAÇÃO ---
        with tab_pricing:
            st.subheader("💰 Cálculo de Preço")
            
            # 1. Calculate Cost (Recipe vs Kit)
            total_cost = 0.0
            cost_breakdown = []
            
            # Check Kit
            kit_components = pd.read_sql("""
                SELECT pk.quantity, p.name, p.base_price 
                FROM product_kits pk
                JOIN products p ON pk.child_product_id = p.id
                WHERE pk.parent_product_id = ?
            """, conn, params=(selected_prod_id,))
            
            if not kit_components.empty:
                st.info("ℹ️ Custo baseado na soma dos produtos componentes (Kit).")
                for _, row in kit_components.iterrows():
                    subtotal = row['quantity'] * row['base_price']
                    total_cost += subtotal
                    cost_breakdown.append({"Item": row['name'], "Qtd": row['quantity'], "Unit": f"R$ {row['base_price']:.2f}", "Total": f"R$ {subtotal:.2f}"})
            else:
                # Check Recipe
                recipe_items = pd.read_sql("""
                    SELECT m.name, pr.quantity, m.price_per_unit, m.unit
                    FROM product_recipes pr
                    JOIN materials m ON pr.material_id = m.id
                    WHERE pr.product_id = ?
                """, conn, params=(selected_prod_id,))
                
                if not recipe_items.empty:
                    st.info("ℹ️ Custo baseado na receita de insumos.")
                    for _, row in recipe_items.iterrows():
                        # Simple calc (assuming price is per unit matching recipe unit)
                        subtotal = row['quantity'] * row['price_per_unit']
                        total_cost += subtotal
                        cost_breakdown.append({"Item": row['name'], "Qtd": f"{row['quantity']} {row['unit']}", "Unit": f"R$ {row['price_per_unit']:.2f}", "Total": f"R$ {subtotal:.2f}"})
                else:
                    st.warning("⚠️ Sem receita ou composição definida. Custo calculado é zero.")
            
            # Show Breakdown
            if cost_breakdown:
                with st.expander("Ver Detalhes do Custo"):
                    st.dataframe(pd.DataFrame(cost_breakdown))
            
            col_cost, col_markup, col_sug, col_final = st.columns(4)
            
            col_cost.metric("Custo Total", f"R$ {total_cost:.2f}")
            
            # Markup
            curr_markup = curr_prod['markup'] if curr_prod['markup'] else 2.0
            new_markup = col_markup.number_input("Markup (Mult.)", value=float(curr_markup), step=0.1)
            
            # Suggested
            suggested = total_cost * new_markup
            col_sug.metric("Preço Sugerido", f"R$ {suggested:.2f}")
            
            # Helper to apply suggestion
            if col_sug.button("⬇️ Usar Sugerido", help="Preenche o Preço Final com o valor sugerido"):
                st.session_state[f"final_price_{selected_prod_id}"] = float(suggested)
                st.rerun()

            # Final Price Input
            curr_price = float(curr_prod['base_price']) if (curr_prod['base_price'] is not None and curr_prod['base_price'] != '') else 0.0
            
            # Logic: Default to DB value. If 0, default to Suggested.
            # If manually updated via button above, session_state will handle the value via key.
            default_val = curr_price if curr_price > 0.01 else suggested
            
            # Use 'key' to allow programmatic setting
            if f"final_price_{selected_prod_id}" not in st.session_state:
                st.session_state[f"final_price_{selected_prod_id}"] = float(default_val)
            
            new_price = col_final.number_input("Preço Final (Venda)", step=1.0, key=f"final_price_{selected_prod_id}")
            
            # Update Button
            if st.button("💾 Salvar Preço Definido", type="primary", use_container_width=True):
                cursor.execute("UPDATE products SET markup = ?, base_price = ? WHERE id = ?", (new_markup, new_price, selected_prod_id))
                conn.commit()
                st.success("Preço e Markup salvos com sucesso!")
                time.sleep(1)
                st.rerun()

        st.markdown("---")
        with st.expander("🚫 Zona de Perigo"):
            if st.button("EXCLUIR PRODUTO", type="primary"):
                cursor.execute("DELETE FROM product_recipes WHERE product_id=?", (selected_prod_id,))
                cursor.execute("DELETE FROM product_kits WHERE parent_product_id=?", (selected_prod_id,))
                cursor.execute("DELETE FROM products WHERE id=?", (selected_prod_id,))
                conn.commit()
                st.success("Produto excluído.")
                st.session_state.editing_product_id = None
                st.rerun()

# --- Tab 2: History (Moved content) ---
with tab2:
    st.subheader("📜 Histórico de Produção")
    
    # Filters
    fh1, fh2, fh3 = st.columns(3)
    
    with fh1:
        # Date filter
        from datetime import timedelta
        # Check if timedelta imported? Safe to re-import
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
                        new_qty = st.number_input("Nova Quantidade", value=int(row['quantity']), step=1, key=f"edit_qty_{row['id']}")
                        
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
