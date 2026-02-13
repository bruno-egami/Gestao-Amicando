import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import database  # Use centralized DB connection
import admin_utils
import auth
import audit
from services import product_service
from utils.logging_config import get_logger, log_exception
import utils.styles as styles

logger = get_logger(__name__)

st.set_page_config(page_title="Produtos", page_icon="🏺", layout="wide")

# Apply Global Styles
styles.apply_custom_style()

admin_utils.render_sidebar_logo()

# Database Connection
conn = database.get_connection()

if not auth.require_login(conn):
    st.stop()

if not auth.check_page_access("Produtos"):
    st.stop()

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
    except (sqlite3.Error, pd.io.sql.DatabaseError):
        cat_opts = ["Utilitário", "Decorativo", "Outros"]

    with st.expander("Gerenciar Categorias", expanded=False):
        c_cat1, c_cat2 = st.columns([2, 1])
        new_cat_name = c_cat1.text_input("Nova Categoria", placeholder="Nome da categoria...")
        if c_cat2.button("Adicionar Categoria"):
            if new_cat_name and new_cat_name not in cat_opts:
                try:
                    cursor.execute("INSERT INTO product_categories (name) VALUES (?)", (new_cat_name,))
                    conn.commit()
                    product_service.get_categories.clear()
                    admin_utils.show_feedback_dialog(f"Categoria '{new_cat_name}' adicionada!", level="success")
                except sqlite3.Error as e:
                    log_exception(logger, "Error adding category", e)
                    admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")
            elif new_cat_name in cat_opts:
                admin_utils.show_feedback_dialog("Categoria já existe.", level="warning")
        
        # List to delete
        if cat_opts:
            st.divider()
            st.write("Categorias Existentes:")
            st.write(", ".join(cat_opts))
            
            del_cat = st.selectbox("Apagar Categoria", [""] + cat_opts)
            if st.button("Excluir Categoria Selecionada", use_container_width=True):
                 if del_cat:
                    def do_del_cat(name=del_cat):
                        cursor.execute("DELETE FROM product_categories WHERE name=?", (name,))
                        conn.commit()
                        product_service.get_categories.clear()
                    
                    admin_utils.show_confirmation_dialog(
                        f"Deseja excluir a categoria '{del_cat}'? Isso não excluirá os produtos, mas eles ficarão sem categoria vinculada.",
                        on_confirm=do_del_cat
                    )

    # --- SHARED DATA FETCH ---
    try:
        products = pd.read_sql("SELECT * FROM products", conn)
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        logger.error(f"Database read error: {e}")
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
                    import ast
                    try:
                        imgs = ast.literal_eval(row['image_paths']) if row['image_paths'] else []
                    except Exception: imgs = []
                    
                    # Logic: Always fetch component images for Kits to ensure freshness
                    kit_children = pd.read_sql("SELECT child_product_id FROM product_kits WHERE parent_product_id=?", conn, params=(row['id'],))
                    if not kit_children.empty:
                        c_ids = ",".join(map(str, kit_children['child_product_id'].tolist()))
                        c_imgs_df = pd.read_sql(f"SELECT image_paths FROM products WHERE id IN ({c_ids})", conn)
                        comp_imgs = []
                        for _, ci_row in c_imgs_df.iterrows():
                            try:
                                import ast
                                ci_list = ast.literal_eval(ci_row['image_paths']) if ci_row['image_paths'] else []
                            except Exception: ci_list = []
                            if ci_list:
                                comp_imgs.extend(ci_list)
                        
                        # Prepend component images (Dynamic) to static images
                        imgs = comp_imgs + imgs
                    
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
                        
                        # Variant Logic - Fetch and Show
                        vars_df = product_service.get_product_variants(conn, row['id'])
                        has_variants = not vars_df.empty
                        
                        stock_label = f"📦 Kit: {display_stock} (Calc)" if is_kit else f"Est. Base: {row['stock_quantity']}"
                        st.caption(f"ID: {row['id']} | {row['category']} | {stock_label}")
                        
                        if breakdown_str:
                            st.caption(f"🔎 Kit: {breakdown_str}")
                            
                        # --- NEW: Product Recipe Summary ---
                        recipe_df = pd.read_sql("""
                            SELECT m.name, pr.quantity, m.unit
                            FROM product_recipes pr
                            JOIN materials m ON pr.material_id = m.id
                            WHERE pr.product_id = ?
                            ORDER BY pr.id ASC
                        """, conn, params=(row['id'],))
                        
                        if not recipe_df.empty:
                            mats = []
                            for _, mr in recipe_df.iterrows():
                                # Format quantity: if it's a small float, show 3 decimals, else 1
                                q_fmt = f"{mr['quantity']:.3f}" if mr['quantity'] < 1 else f"{mr['quantity']:.1f}"
                                mats.append(f"{mr['name']}: {q_fmt}{mr['unit']}")
                            recipe_str = " | ".join(mats)
                            st.caption(f"📜 Formulação: {recipe_str}")
                            
                        # Show Variants Stock
                        if has_variants:
                            st.markdown("<div style='margin-top: 5px; margin-bottom: 5px; font-size: 0.8em; color: #aaa;'>Variações & Estoque:</div>", unsafe_allow_html=True)
                            badges = ""
                            for _, vr in vars_df.iterrows():
                                s_qty = vr['stock_quantity']
                                s_color = "#66ff66" if s_qty > 0 else "#ff6666" # Light Green / Light Red for Dark Mode
                                badges += f"""
                                <div style="
                                    display: flex; 
                                    justify-content: space-between; 
                                    background-color: rgba(255,255,255,0.08); 
                                    padding: 2px 8px; 
                                    border-radius: 4px; 
                                    margin-bottom: 2px;
                                    align-items: center;">
                                    <span style="color: #e0e0e0;">{vr['variant_name']}</span>
                                    <span style="font-weight: bold; color: {s_color}; font-family: monospace;">{s_qty}</span>
                                </div>
                                """
                            st.markdown(badges, unsafe_allow_html=True)
                    
                    # Price
                    with c3:
                        price = float(row['base_price']) if row['base_price'] else 0.0
                        st.write(f"R$ {price:.2f}")

                    # PRODUCE Button (Popover)
                    with c4:
                        with st.popover("🔨", help="Registrar Produção"):
                            st.markdown(f"**Produzir: {row['name']}**")
                            
                            # Variant Selection for Production
                            prod_target = "Produto Base (Padrão)"
                            target_variant_id = None
                            
                            if has_variants:
                                v_opts = {f"{v['variant_name']} (Est: {v['stock_quantity']})": v['id'] for _, v in vars_df.iterrows()}
                                v_keys = ["Produto Base (Padrão)"] + list(v_opts.keys())
                                sel_v_label = st.selectbox("Variação", v_keys)
                                if sel_v_label != "Produto Base (Padrão)":
                                    prod_target = sel_v_label
                                    target_variant_id = v_opts[sel_v_label]
                            
                            qty_make = st.number_input("Qtd", min_value=1, value=1, key=f"make_qty_{row['id']}")
                            
                            if st.button("Confirmar", key=f"btn_make_{row['id']}", type="primary"):
                                try:
                                    # Fetch Recipe (Base)
                                    recipe = pd.read_sql(f"""
                                        SELECT m.id, m.name, m.stock_level, (pr.quantity * {qty_make}) as needed, m.unit, m.type
                                        FROM product_recipes pr
                                        JOIN materials m ON pr.material_id = m.id
                                        WHERE pr.product_id = {row['id']}
                                    """, conn)
                                    
                                    # Variation specific material?
                                    extra_mat_needed = []
                                    if target_variant_id:
                                        # Get variant info specific
                                        # Optimization: We have vars_df but need to be sure.
                                        var_info = vars_df[vars_df['id'] == target_variant_id].iloc[0]
                                        if var_info['material_id'] and var_info['material_quantity'] > 0:
                                             # Fetch that material current stock
                                             try:
                                                 vm = pd.read_sql("SELECT id, name, stock_level, unit, type FROM materials WHERE id=?", conn, params=(var_info['material_id'],)).iloc[0]
                                                 needed_vm = var_info['material_quantity'] * qty_make
                                                 
                                                 # Add to recipe dataframe or handle separately?
                                                 # Let's add to a separate list to check check logic
                                                 extra_mat_needed.append({
                                                     'id': vm['id'], 'name': vm['name'], 'stock_level': vm['stock_level'], 
                                                     'needed': needed_vm, 'unit': vm['unit'], 'type': vm['type']
                                                 })
                                             except Exception: pass # Material not found?

                                    # Check Stock (Physical only)
                                    # Base Recipe
                                    is_burning = (recipe['unit'] == 'fornada') | (recipe['name'].str.startswith('Queima')) | (recipe['type'] == 'Queima')
                                    is_labor = (recipe['type'] == 'Mão de Obra') | (recipe['unit'] == 'hora (mão de obra)')
                                    is_physical = ~(is_burning | is_labor)
                                    
                                    insufficient = recipe[is_physical & (recipe['stock_level'] < recipe['needed'])]
                                    
                                    # Check Extra Materials
                                    missing_extras = []
                                    for em in extra_mat_needed:
                                        # Skip labor/firing checks for extra (usually glaze which is physical)
                                        if em['stock_level'] < em['needed']:
                                            missing_extras.append(em['name'])
                                    
                                    if not insufficient.empty or missing_extras:
                                        admin_utils.show_feedback_dialog(f"Estoque insuficiente! {', '.join(insufficient['name'].tolist() + missing_extras)}", level="error")
                                    else:
                                        # Execute Production
                                        from datetime import datetime as dt
                                        user_id, username = None, 'system'
                                        if 'current_user' in st.session_state and st.session_state.current_user:
                                            user_id = int(st.session_state.current_user.get('id'))
                                            username = st.session_state.current_user.get('username', 'unknown')
                                            
                                        # LOGIC: Check if it's a KIT (has entries in product_kits)
                                        # Note: Kits usually don't have variants in this model yet. If they do, logic is complex.
                                        # We proceed with Kit logic if it's a kit, ignoring variants for now unless user selected one?
                                        # User request implies specific variation production.
                                        
                                        kits = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn, params=(row['id'],))
                                        
                                        if not kits.empty:
                                            # ... Existing Kit Logic (Assumed no variants for kits for now) ...
                                            # Same as before
                                            can_make_kit = True
                                            miss_msg = []
                                            for _, kit_item in kits.iterrows():
                                                needed_total = kit_item['quantity'] * qty_make
                                                child_stock = pd.read_sql("SELECT stock_quantity, name FROM products WHERE id=?", conn, params=(kit_item['child_product_id'],)).iloc[0]
                                                if child_stock['stock_quantity'] < needed_total:
                                                    can_make_kit = False
                                                    miss_msg.append(f"{child_stock['name']}: Precisa {needed_total}, Tem {child_stock['stock_quantity']}")
                                            
                                            if not can_make_kit:
                                                admin_utils.show_feedback_dialog(f"Estoque insuficiente de componentes: {', '.join(miss_msg)}", level="error")
                                            else:
                                                # Deduct
                                                for _, kit_item in kits.iterrows():
                                                     needed_total = kit_item['quantity'] * qty_make
                                                     cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?", (needed_total, kit_item['child_product_id']))
                                                
                                                # Add Stock
                                                if target_variant_id:
                                                    cursor.execute("UPDATE product_variants SET stock_quantity = stock_quantity + ? WHERE id = ?", (qty_make, int(target_variant_id)))
                                                else:
                                                    cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (qty_make, row['id']))
                                                
                                                # Log
                                                cursor.execute("INSERT INTO production_history (timestamp, product_id, product_name, quantity, user_id, username, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                                               (dt.now().isoformat(), row['id'], f"{row['name']} ({prod_target})", qty_make, user_id, username, 'Produção de Kit (Variação)' if target_variant_id else 'Produção de Kit'))
                                                conn.commit()
                                                admin_utils.show_feedback_dialog(f"Kit Montado: {qty_make}x {row['name']}!", level="success")
                                                st.rerun()

                                        else:
                                            # === REGULAR PRODUCTION ===
                                            
                                            # 1. Deduct Base Recipe
                                            if recipe.empty and not extra_mat_needed:
                                                admin_utils.show_feedback_dialog("Sem receita. Ajustando apenas estoque.", level="warning", title="Aviso de Receita")
                                            
                                            # Deduct Base
                                            for _, mat in recipe.iterrows():
                                                if not ((mat['unit'] == 'fornada') or (str(mat['name']).startswith('Queima')) or (mat['type'] == 'Queima') or (mat['type'] == 'Mão de Obra') or (mat['unit'] == 'hora (mão de obra)')):
                                                     needed_py = float(mat['needed'])
                                                     cursor.execute("UPDATE materials SET stock_level = stock_level - ? WHERE id = ?", (needed_py, int(mat['id'])))
                                                     # Log
                                                     cursor.execute("INSERT INTO inventory_transactions (material_id, date, type, quantity, notes, user_id) VALUES (?, ?, ?, ?, ?, ?)", 
                                                                    (int(mat['id']), dt.now().isoformat(), 'SAIDA', needed_py, f"Prod: {qty_make}x {row['name']}", user_id))

                                            # Deduct Extras (Variant specific)
                                            for em in extra_mat_needed:
                                                needed_py = float(em['needed'])
                                                cursor.execute("UPDATE materials SET stock_level = stock_level - ? WHERE id = ?", (needed_py, int(em['id'])))
                                                cursor.execute("INSERT INTO inventory_transactions (material_id, date, type, quantity, notes, user_id) VALUES (?, ?, ?, ?, ?, ?)", 
                                                               (int(em['id']), dt.now().isoformat(), 'SAIDA', needed_py, f"Prod Var: {qty_make}x {row['name']}", user_id))

                                            # Update Stock (Target)
                                            if target_variant_id:
                                                cursor.execute("UPDATE product_variants SET stock_quantity = stock_quantity + ? WHERE id = ?", (qty_make, int(target_variant_id)))
                                            else:
                                                cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?", (qty_make, row['id']))
                                                
                                            cursor.execute("INSERT INTO production_history (timestamp, product_id, product_name, quantity, user_id, username, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                                           (dt.now().isoformat(), row['id'], f"{row['name']} ({prod_target})", qty_make, user_id, username, 'Produção Geral'))
                                            
                                            audit.log_action(conn, 'CREATE', 'production_history', cursor.lastrowid, None, {'product_id': row['id'], 'quantity': qty_make, 'variant_id': target_variant_id})
                                            conn.commit()
                                            admin_utils.show_feedback_dialog(f"Produzido: {qty_make}x {row['name']} ({prod_target})!", level="success")
                                            st.rerun()
 
                                except Exception as e:
                                    admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")

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
                        new_id = cursor.lastrowid
                        audit.log_action(conn, 'CREATE', 'products', new_id, None, {'name': new_name}, commit=False)
                        conn.commit()
                        
                        st.session_state.editing_product_id = new_id # Switch to Edit Mode
                        product_service.get_all_products.clear()
                        admin_utils.show_feedback_dialog(f"Produto '{new_name}' criado!", level="success")
                    except Exception as e:
                        admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")
                else:
                    admin_utils.show_feedback_dialog("Nome é obrigatório.", level="warning")

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

        # Header with Back button and Duplicate
        c_back, c_title, c_dup = st.columns([1, 4, 1])
        with c_back:
            if st.button("⬅️ Voltar"):
                st.session_state.editing_product_id = None
                st.rerun()
        with c_title:
             st.markdown(f"### ✏️ Editando: {curr_prod['name']}")
        with c_dup:
            if st.button("📋 Duplicar", help="Criar cópia deste produto com receitas e componentes"):
                try:
                    # 1. Create new product with copied data
                    new_name = f"{curr_prod['name']} (Cópia)"
                    cursor.execute("""
                        INSERT INTO products (name, description, category, markup, image_paths, stock_quantity, base_price)
                        VALUES (?, ?, ?, ?, '[]', 0, 0)
                    """, (new_name, curr_prod['description'], curr_prod['category'], curr_prod['markup']))
                    conn.commit()
                    new_prod_id = cursor.lastrowid
                    
                    # 2. Copy recipes (product_recipes)
                    recipes = pd.read_sql("""
                        SELECT material_id, quantity FROM product_recipes WHERE product_id = ?
                    """, conn, params=(selected_prod_id,))
                    for _, rec in recipes.iterrows():
                        cursor.execute("""
                            INSERT INTO product_recipes (product_id, material_id, quantity)
                            VALUES (?, ?, ?)
                        """, (new_prod_id, rec['material_id'], rec['quantity']))
                    
                    # 3. Copy kit components (product_kits)
                    kits = pd.read_sql("""
                        SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id = ?
                    """, conn, params=(selected_prod_id,))
                    for _, kit in kits.iterrows():
                        cursor.execute("""
                            INSERT INTO product_kits (parent_product_id, child_product_id, quantity)
                            VALUES (?, ?, ?)
                        """, (new_prod_id, kit['child_product_id'], kit['quantity']))
                    
                    conn.commit()
                    
                    # Log audit
                    audit.log_action(conn, 'CREATE', 'products', new_prod_id, None, {
                        'name': new_name, 'duplicated_from': selected_prod_id
                    })
                    
                    st.session_state.editing_product_id = new_prod_id
                    product_service.get_all_products.clear()
                    admin_utils.show_feedback_dialog(f"Produto '{new_name}' criado com sucesso!", level="success")
                except Exception as e:
                    admin_utils.show_feedback_dialog(f"Erro ao duplicar: {e}", level="error")
        
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
                     except Exception:
                         cat_opts = ["Utilitário", "Decorativo", "Outros"]

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

                    if not is_kit_edit:
                         if new_stock != (int(curr_prod['stock_quantity']) if curr_prod['stock_quantity'] else 0):
                            pass # History log already handles this differently above

                    cursor.execute("UPDATE products SET name=?, category=?, description=?, stock_quantity=? WHERE id=?", (new_name, new_cat, new_desc, new_stock, selected_prod_id))
                    audit.log_action(conn, 'UPDATE', 'products', selected_prod_id, 
                        {'name': curr_prod['name'], 'stock': curr_prod['stock_quantity']},
                        {'name': new_name, 'stock': new_stock}, commit=False)
                    conn.commit()
                    product_service.get_all_products.clear()
                    product_service.get_categories.clear()
                    admin_utils.show_feedback_dialog("Detalhes atualizados!", level="success")

        # TABS INTERFACE
        tab_recipe, tab_variants, tab_comp, tab_pricing, tab_images = st.tabs(["📜 Receita", "🎨 Variações", "📦 Composição (Kit)", "💰 Precificação", "📷 Imagens"])

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
                if st.button("🗑️ Remover Insumo selecionado", use_container_width=True):
                    if del_id:
                        def do_del_rec(rid=del_id):
                            cursor.execute("DELETE FROM product_recipes WHERE id=?", (rid,))
                            conn.commit()
                        
                        admin_utils.show_confirmation_dialog(
                            "Remover este insumo da receita do produto?",
                            on_confirm=do_del_rec
                        )
            else:
                st.info("Nenhuma receita definida.")

        # --- TAB VARIANTS: VARIAÇÕES ---
        with tab_variants:
            st.caption("Gerencie variações deste produto (Ex: Cores, Acabamentos/Esmaltes). O estoque pode ser controlado por variação.")
            
            # Form to Add Variant (Dynamic - No st.form to allow calc)
            st.markdown("##### ➕ Nova Variação")
            
            # Container for inputs
            vc_add = st.container(border=True)
            with vc_add:
                v_c1, v_c2, v_c3 = st.columns([3, 2, 2])
                # Name input moved down to be dynamic
                
                # Material Link (Optional) - Glazes
                materials_df = pd.read_sql("SELECT id, name, unit, price_per_unit FROM materials WHERE type != 'Mão de Obra' ORDER BY name", conn)
                mat_opts = {f"{row['name']} ({row['unit']})": row['id'] for _, row in materials_df.iterrows()}
                v_mat_keys = [""] + list(mat_opts.keys())
                
                # Helper to find key by ID if needed, but here we pick by label
                v_mat = v_c2.selectbox("Esmalte Vinculado (Opcional)", v_mat_keys)
                
                # Material Quantity
                v_mat_qty = v_c2.number_input("Qtd Material (Ex: Esmalte)", min_value=0.0, step=0.001, format="%.3f", help="Quantidade de material consumida por unidade desta variação")
                
                # Dynamic Price & Name Calculation
                suggested_adder = 0.0
                curr_markup = curr_prod['markup'] if curr_prod['markup'] else 2.0
                mat_cost_preview = 0.0
                mat_unit_price = 0.0
                suggested_name = ""
                
                if v_mat:
                    try:
                        sel_mat_id = mat_opts[v_mat]
                        # Find price in df
                        m_row = materials_df[materials_df['id'] == sel_mat_id].iloc[0]
                        mat_unit_price = m_row['price_per_unit']
                        suggested_name = m_row['name']
                        
                        if v_mat_qty > 0:
                            mat_cost_preview = mat_unit_price * v_mat_qty
                            suggested_adder = mat_cost_preview * curr_markup
                    except Exception:
                        pass
                
                # Name Input (Auto-fill if empty and suggested avail)
                # We use key trick or session state? Simple value approach:
                # If we want it to update when v_mat changes, we need to handle it.
                # Simplest: Just use the suggested name if user input is empty. But 'text_input' holds state.
                # Let's rely on user overriding it, but default value set to sugg if provided.
                # Actually, standard Streamlit text_input `value` is only used on first render or if key changes.
                # We can key it to the material selection to force refresh, but that clears user input if they change material?
                # "gostaria também que o nome da variação fosse pré preenchido"
                # Let's try keying name to mat_id roughly or just leave standard.
                # A good compromise: Show suggestion in placeholder or help?
                # User asked for pre-filled.
                
                # Force update name if material changes?
                if "last_v_mat" not in st.session_state: st.session_state.last_v_mat = None
                
                default_v_name = ""
                if v_mat != st.session_state.last_v_mat:
                    default_v_name = suggested_name
                    st.session_state.last_v_mat = v_mat
                    # Reset name input?? We can't easily reset a widget value without rerunning/key hack.
                    # We will use a dynamic key for name input based on material? No, that breaks UI flow.
                    # We will simply not pre-fill dynamically aggressively to avoid overriding.
                    # But wait, user SAID "pre-filled".
                    # Let's set value only if it matches checks.
                    
                # We will use a key that updates when material changes to "reset" the name field to the new material?
                # That might be annoying if they typed something.
                # Let's just use `value` and hope for best or stick to manual?
                # Let's change the key of text_input effectively resetting it when material changes.
                
                v_name = v_c1.text_input("Nome da Variação (Ex: Azul Reativo)", value=suggested_name if v_mat else "", key=f"vn_{v_mat if v_mat else 'none'}")
                
                if mat_unit_price > 0:
                     v_c2.caption(f"💲 Custo Unitário: R$ {mat_unit_price:.2f}/{getattr(m_row, 'unit', 'un') if 'm_row' in locals() else 'un'}")

                if mat_cost_preview > 0:
                    v_c2.caption(f"💰 Custo Est.: R$ {mat_cost_preview:.2f} (Markup {curr_markup}x -> R$ {suggested_adder:.2f})")

                v_stock = v_c3.number_input("Estoque Inicial", min_value=0, step=1)
                
                # Price Input - Default to suggestion if available and distinct
                v_price = v_c3.number_input("Add. Preço (R$)", min_value=0.0, step=0.01, value=float(suggested_adder), help="Valor a somar ao preço base. Sugestão = Custo Material x Markup")
                
                if st.button("Salvar Variação", type="primary"):
                    if v_name:
                        mat_id = mat_opts[v_mat] if v_mat else None
                        success = product_service.create_variant(conn, selected_prod_id, v_name, v_stock, v_price, mat_id, v_mat_qty)
                        if success:
                            admin_utils.show_feedback_dialog("Variação adicionada!", level="success")
                        else:
                            admin_utils.show_feedback_dialog("Erro ao adicionar variação.", level="error")
                    else:
                        admin_utils.show_feedback_dialog("Nome obrigatório.", level="warning")

            # List Variants
            variants_df = product_service.get_product_variants(conn, selected_prod_id)
            if not variants_df.empty:
                st.write("📋 Variações Cadastradas:")
                
                # Custom Table display
                for _, var_row in variants_df.iterrows():
                    with st.container(border=True):
                        vc1, vc2, vc3, vc4, vc5 = st.columns([3, 2, 2, 2, 1])
                        vc1.write(f"**{var_row['variant_name']}**")
                        if var_row['material_name']:
                            qty_display = f" ({var_row['material_quantity']:.3f})" if var_row.get('material_quantity') else ""
                            vc1.caption(f"🎨 {var_row['material_name']}{qty_display}")
                        
                        # Update Stock
                        new_v_stock = vc2.number_input(f"Estoque", value=int(var_row['stock_quantity']), key=f"v_stk_{var_row['id']}")
                        if new_v_stock != int(var_row['stock_quantity']):
                             product_service.update_variant_stock(conn, var_row['id'], new_v_stock)
                             st.rerun()
                             
                        # Display Price
                        vc3.write(f"+ R$ {var_row['price_adder']:.2f}")
                        
                        # Delete
                        if vc5.button("🗑️", key=f"del_var_{var_row['id']}"):
                            def do_del_var(vid=var_row['id'], vname=var_row['variant_name']):
                                product_service.delete_variant(conn, vid)
                            
                            admin_utils.show_confirmation_dialog(
                                f"Excluir a variação '{var_row['variant_name']}'?",
                                on_confirm=do_del_var
                            )
            else:
                st.info("Nenhuma variação cadastrada.")

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
                if st.button("🗑️ Remover Componente selecionado", use_container_width=True):
                     if del_kit_id:
                        def do_del_kit(kid=del_kit_id):
                            cursor.execute("DELETE FROM product_kits WHERE id=?", (kid,))
                            conn.commit()

                        admin_utils.show_confirmation_dialog(
                            "Remover este componente do kit?",
                            on_confirm=do_del_kit
                        )

        # --- TAB 3: IMAGENS ---
        with tab_images:
            st.caption("Gerencie as fotos do produto.")
            # Reuse logic from expanding section
            try:
                import ast
                curr_imgs = ast.literal_eval(curr_prod['image_paths']) if curr_prod['image_paths'] else []
            except Exception: curr_imgs = []
            
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
                                product_service.get_all_products.clear()
                                st.rerun()
                        except Exception:
                            pass
            
            new_imgs = st.file_uploader("Upload Novas Imagens", accept_multiple_files=True, type=["png", "jpg", "jpeg", "webp"], key="new_imgs_tab")
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
                    product_service.get_all_products.clear()
                    admin_utils.show_feedback_dialog("Salvo!", level="success")
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
                    try:
                        import ast
                        cp_imgs = ast.literal_eval(cp['image_paths']) if cp['image_paths'] else []
                    except Exception: cp_imgs = []
                    if cp_imgs:
                        st.caption(f"De: **{cp['name']}**")
                        c_imgs = st.columns(6)
                        for idx, p_img in enumerate(cp_imgs):
                            with c_imgs[idx % 6]:
                                try:
                                    st.image(p_img, width=100)
                                except Exception:
                                    pass

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

            # Helper to apply suggestion (Top)
            if col_sug.button("⬇️ Usar Sugerido", help="Preenche o Preço Final com o valor sugerido"):
                st.session_state[f"final_price_{selected_prod_id}"] = float(suggested)
                st.rerun()

            # Final Price Input (Top)
            curr_price = float(curr_prod['base_price']) if (curr_prod['base_price'] is not None and curr_prod['base_price'] != '') else 0.0
            
            # Logic: Default to DB value. If 0, default to Suggested.
            default_val = curr_price if curr_price > 0.01 else suggested
            
            # Use 'key' to allow programmatic setting
            if f"final_price_{selected_prod_id}" not in st.session_state:
                st.session_state[f"final_price_{selected_prod_id}"] = float(default_val)
            
            new_price = col_final.number_input("Preço Final (Venda)", step=1.0, key=f"final_price_{selected_prod_id}")
            
            # Save Button (Top)
            if col_final.button("💾 Salvar", type="primary", use_container_width=True, help="Salvar Preço Base e Markup"):
                cursor.execute("UPDATE products SET markup = ?, base_price = ? WHERE id = ?", (new_markup, new_price, selected_prod_id))
                conn.commit()
                product_service.get_all_products.clear()
                admin_utils.show_feedback_dialog("Preço Base Salvo!", level="success")
            
            # 2. Variation Cost Analysis (NEW)
            st.divider()
            st.markdown("#### 📊 Análise de Custos por Variação")
            
            # Fetch variants
            vars_analysis = product_service.get_product_variants(conn, selected_prod_id)
            
            if not vars_analysis.empty:
                analysis_data = []
                for _, v_row in vars_analysis.iterrows():
                    # Calculate Extra Cost
                    extra_cost = 0.0
                    mat_info = ""
                    
                    if v_row['material_id'] and v_row['material_quantity']:
                        # Fetch material price
                        try:
                            # Optimization: Could cache materials price, but single query per row is acceptable for small scale
                            mat_p = pd.read_sql("SELECT price_per_unit, unit FROM materials WHERE id=?", conn, params=(v_row['material_id'],)).iloc[0]
                            extra_cost = v_row['material_quantity'] * mat_p['price_per_unit']
                            mat_info = f"{v_row['material_name']} ({v_row['material_quantity']} {mat_p['unit']})"
                        except Exception:
                            pass
                            
                    total_var_cost = total_cost + extra_cost
                    
                    # Ideal Price (Cost * Markup)
                    curr_markup = curr_prod['markup'] if curr_prod['markup'] else 2.0
                    ideal_price = total_var_cost * curr_markup
                    
                    # Current Price (Base Price + Adder)
                    base_p = float(curr_prod['base_price']) if curr_prod['base_price'] else 0.0
                    current_final_price = base_p + v_row['price_adder']
                    
                    diff = current_final_price - ideal_price
                    
                    analysis_data.append({
                        "id": v_row['id'], # For updates
                        "Variação": v_row['variant_name'],
                        "Custo Extra": extra_cost,
                        "Custo Total": total_var_cost,
                        "Preço Ideal (Markup)": ideal_price,
                        "Preço Atual": current_final_price,
                        "Diferença": diff
                    })
                
                df_analysis = pd.DataFrame(analysis_data)
                
                st.dataframe(
                    df_analysis,
                    column_config={
                        "id": None, # Hide ID
                        "Variação": st.column_config.TextColumn(disabled=True),
                        "Custo Extra": st.column_config.NumberColumn(format="R$ %.2f", disabled=True),
                        "Custo Total": st.column_config.NumberColumn(format="R$ %.2f", disabled=True),
                        "Preço Ideal (Markup)": st.column_config.NumberColumn(format="R$ %.2f", disabled=True, help="Custo Total x Markup do Produto"),
                        "Preço Atual": st.column_config.NumberColumn(format="R$ %.2f", disabled=True),
                        "Diferença": st.column_config.NumberColumn(format="R$ %.2f", disabled=True)
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                st.divider()
                st.markdown("#### 🛠️ Personalizar Preço por Variação")
                
                # Select Variant to Edit
                var_opts = {r['variant_name']: r for _, r in vars_analysis.iterrows()}
                sel_var_name = st.selectbox("Selecione a Variação", list(var_opts.keys()))
                
                if sel_var_name:
                    sel_var = var_opts[sel_var_name]
                    
                    # Calculate Metrics
                    v_mat_price = 0.0
                    if sel_var['material_id']:
                         try:
                             mp = pd.read_sql("SELECT price_per_unit FROM materials WHERE id=?", conn, params=(sel_var['material_id'],)).iloc[0]['price_per_unit']
                             v_mat_price = mp * sel_var['material_quantity']
                         except Exception: pass
                    
                    v_total_cost = total_cost + v_mat_price
                    v_curr_price = (float(curr_prod['base_price']) if curr_prod['base_price'] else 0) + sel_var['price_adder']
                    
                    # Layout similar to Base Cost
                    svc1, svc2, svc3, svc4 = st.columns(4)
                    
                    svc1.metric("Custo Total (Base + Var)", f"R$ {v_total_cost:.2f}")
                    
                    # Infer current markup logic
                    v_current_markup = v_curr_price / v_total_cost if v_total_cost > 0 else 0
                    
                    # Markup Input
                    v_new_markup = svc2.number_input("Markup Variação", value=float(v_current_markup) if v_current_markup > 0 else float(curr_markup), step=0.1, key=f"vm_{sel_var['id']}")
                    
                    # Suggested
                    v_suggested = v_total_cost * v_new_markup
                    svc3.metric("Preço Sugerido", f"R$ {v_suggested:.2f}")
                    
                    # Final Price Input
                    v_final_price = svc4.number_input("Preço Final (Venda)", value=float(v_curr_price), step=1.0, key=f"vp_{sel_var['id']}")
                    
                    # Helper button for suggested
                    if svc3.button("⬇️ Usar Sugerido", key=f"vus_{sel_var['id']}"):
                         pass

                    # Save Button moved to col 4
                    if svc4.button("💾 Salvar", key=f"vsave_{sel_var['id']}", type="primary", use_container_width=True):
                         # Calculate new Adder
                         base_p = float(curr_prod['base_price']) if curr_prod['base_price'] else 0.0
                         new_adder = v_final_price - base_p
                         if new_adder < 0: new_adder = 0
                         
                         product_service.update_variant_price(conn, sel_var['id'], new_adder)
                         admin_utils.show_feedback_dialog(f"Preço de '{sel_var_name}' atualizado!", level="success")
            else:
                st.info("Nenhuma variação para analisar.")

        st.markdown("---")
        with st.expander("🚫 Zona de Perigo"):
            if st.button("EXCLUIR PRODUTO", type="primary", use_container_width=True):
                def do_delete_prod(pid=selected_prod_id, pname=curr_prod['name']):
                    cursor.execute("DELETE FROM product_recipes WHERE product_id=?", (pid,))
                    cursor.execute("DELETE FROM product_kits WHERE parent_product_id=?", (pid,))
                    cursor.execute("DELETE FROM products WHERE id=?", (pid,))
                    audit.log_action(conn, 'DELETE', 'products', pid, {'name': pname}, commit=False)
                    conn.commit()
                    product_service.get_all_products.clear()
                    st.session_state.editing_product_id = None

                admin_utils.show_confirmation_dialog(
                    f"Tem certeza que deseja EXCLUIR PERMANENTEMENTE o produto '{curr_prod['name']}'? Todos os vínculos de receita e kit serão removidos.",
                    on_confirm=do_delete_prod
                )

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
                            
                            product_service.get_all_products.clear()
                            admin_utils.show_feedback_dialog("Atualizado!", level="success")
                            st.rerun()
                
                with c3:
                    # Delete button
                    if st.button("🗑️", key=f"del_prod_{row['id']}", help="Excluir registro"):
                        def do_delete_hist(rid=row['id'], pid=row['product_id'], qty=row['quantity'], pname=row['product_name']):
                            # Revert stock: subtract the quantity that was recorded
                            cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?", (qty, pid))
                            cursor.execute("DELETE FROM production_history WHERE id = ?", (rid,))
                            conn.commit()
                            product_service.get_all_products.clear()
                            audit.log_action(conn, 'DELETE', 'production_history', rid, {'product_name': pname, 'quantity': qty}, None)

                        admin_utils.show_confirmation_dialog(
                            f"Excluir este registro de produção? O estoque de '{row['product_name']}' será revertido (subtraído em {int(row['quantity'])}).",
                            on_confirm=do_delete_hist
                        )
    else:
        st.info("Nenhum registro de produção encontrado para os filtros selecionados.")

conn.close()
