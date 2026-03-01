import streamlit as st
import pandas as pd
import ast
import os
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
with database.db_session() as conn:

    if not auth.require_login(conn):
        st.stop()

    if not auth.check_page_access("Produtos"):
        st.stop()

    # cursor removed — all writes go through product_service

    auth.render_custom_sidebar()
    st.title("📦 Produtos e Fichas Técnicas")

    tab1, tab2 = st.tabs(["Catálogo & Produção", "Histórico de Produção"])

    # --- Tab 1: Catálogo & Produção ---
    with tab1:
        # Load Categories
        cat_opts = product_service.get_category_list(conn)

        with st.expander("Gerenciar Categorias", expanded=False):
            c_cat1, c_cat2 = st.columns([2, 1])
            new_cat_name = c_cat1.text_input("Nova Categoria", placeholder="Nome da categoria...")
            if c_cat2.button("Adicionar Categoria"):
                if new_cat_name and new_cat_name not in cat_opts:
                    try:
                        product_service.add_category(conn, new_cat_name)
                        product_service.get_categories.clear()
                        admin_utils.show_feedback_dialog(f"Categoria '{new_cat_name}' adicionada!", level="success")
                    except Exception as e:
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
                            with database.db_session() as ctx_conn:
                                product_service.delete_category(ctx_conn, name)
                            product_service.get_categories.clear()
                    
                        admin_utils.show_confirmation_dialog(
                            f"Deseja excluir a categoria '{del_cat}'? Isso não excluirá os produtos, mas eles ficarão sem categoria vinculada.",
                            on_confirm=do_del_cat
                        )

        # --- SHARED DATA FETCH ---
        try:
            products = product_service.get_all_products(conn)
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
                        try:
                            imgs = ast.literal_eval(row['image_paths']) if row['image_paths'] else []
                        except Exception: imgs = []
                    
                        # Logic: Always fetch component images for Kits to ensure freshness
                        kit_children = product_service.get_kit_components(conn, row['id'])
                        if not kit_children.empty:
                            child_ids = kit_children['child_product_id'].tolist()
                            c_imgs_df = product_service.get_images_for_products(conn, child_ids)
                            comp_imgs = []
                            for _, ci_row in c_imgs_df.iterrows():
                                try:
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
                            kit_stock_df = product_service.get_kit_detail_for_edit(conn, row['id'])
                        
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
                            recipe_df = product_service.get_pricing_recipe_items(conn, row['id'])
                        
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
                                vars_in_stock = vars_df[vars_df['stock_quantity'] > 0]
                                if not vars_in_stock.empty:
                                    st.markdown("<div style='margin-top: 5px; margin-bottom: 5px; font-size: 0.8em; color: #aaa;'>Esmaltes em Estoque:</div>", unsafe_allow_html=True)
                                    badges = ""
                                    for _, vr in vars_in_stock.iterrows():
                                        s_qty = vr['stock_quantity']
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
                                            <span style="font-weight: bold; color: #66ff66; font-family: monospace;">{s_qty}</span>
                                        </div>
                                        """
                                    st.markdown(badges, unsafe_allow_html=True)
                                else:
                                    st.caption(f"🎨 {len(vars_df)} esmaltes cadastrados — nenhum em estoque")
                    
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
                                    sel_v_label = st.selectbox("Variação", v_keys, key=f"sel_var_loop_{row['id']}")
                                    if sel_v_label != "Produto Base (Padrão)":
                                        prod_target = sel_v_label
                                        target_variant_id = v_opts[sel_v_label]
                            
                                qty_make = st.number_input("Qtd", min_value=1, value=1, key=f"make_qty_{row['id']}")
                            
                                if st.button("Confirmar", key=f"btn_make_{row['id']}", type="primary"):
                                    try:
                                        # Fetch Recipe (Base)
                                        recipe = product_service.get_recipe_for_production(conn, row['id'], qty_make)
                                    
                                        # Variation specific material?
                                        extra_mat_needed = []
                                        if target_variant_id:
                                            var_info = vars_df[vars_df['id'] == target_variant_id].iloc[0]
                                            if var_info['material_id'] and var_info['material_quantity'] > 0:
                                                 try:
                                                     vm = product_service.get_material_for_variant(conn, var_info['material_id']).iloc[0]
                                                     needed_vm = var_info['material_quantity'] * qty_make
                                                     extra_mat_needed.append({
                                                         'id': vm['id'], 'name': vm['name'], 'stock_level': vm['stock_level'], 
                                                         'needed': needed_vm, 'unit': vm['unit'], 'type': vm['type']
                                                     })
                                                 except Exception as e: logger.warning(f"Variação: material {var_info.get('material_id', '?')} não encontrado: {e}")

                                        # Check Stock (Physical only)
                                        is_burning = (recipe['unit'] == 'fornada') | (recipe['name'].str.startswith('Queima')) | (recipe['type'] == 'Queima')
                                        is_labor = (recipe['type'] == 'Mão de Obra') | (recipe['unit'] == 'hora (mão de obra)')
                                        is_physical = ~(is_burning | is_labor)
                                        insufficient = recipe[is_physical & (recipe['stock_level'] < recipe['needed'])]
                                    
                                        missing_extras = [em['name'] for em in extra_mat_needed if em['stock_level'] < em['needed']]
                                    
                                        if not insufficient.empty or missing_extras:
                                            admin_utils.show_feedback_dialog(f"Estoque insuficiente! {', '.join(insufficient['name'].tolist() + missing_extras)}", level="error")
                                        else:
                                            user_id, username = None, 'system'
                                            if 'current_user' in st.session_state and st.session_state.current_user:
                                                user_id = int(st.session_state.current_user.get('id'))
                                                username = st.session_state.current_user.get('username', 'unknown')
                                            
                                            kits = product_service.get_kit_components(conn, row['id'])
                                        
                                            if not kits.empty:
                                                try:
                                                    product_service.produce_from_kit(
                                                        conn, row['id'], row['name'], qty_make,
                                                        target_variant_id, prod_target, user_id, username
                                                    )
                                                    admin_utils.show_feedback_dialog(f"Kit Montado: {qty_make}x {row['name']}!", level="success")
                                                    st.rerun()
                                                except ValueError as ve:
                                                    admin_utils.show_feedback_dialog(f"Estoque insuficiente de componentes: {ve}", level="error")
                                            else:
                                                # === REGULAR PRODUCTION ===
                                                if recipe.empty and not extra_mat_needed:
                                                    admin_utils.show_feedback_dialog("Sem receita. Ajustando apenas estoque.", level="warning", title="Aviso de Receita")
                                            
                                                product_service.produce_regular(
                                                    conn, row['id'], row['name'], qty_make, recipe,
                                                    extra_mat_needed, target_variant_id, prod_target,
                                                    user_id, username
                                                )
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
                            new_id = product_service.create_product(conn, new_name, new_desc, new_cat, new_markup)
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
            curr_prod = product_service.get_product_by_id(conn, selected_prod_id)
        
            if curr_prod is None:
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
                        new_prod_id = product_service.duplicate_product(conn, selected_prod_id, curr_prod)
                        st.session_state.editing_product_id = new_prod_id
                        product_service.get_all_products.clear()
                        admin_utils.show_feedback_dialog(f"Produto '{curr_prod['name']} (Cópia)' criado com sucesso!", level="success")
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
                    check_kit = product_service.get_kit_detail_for_edit(conn, selected_prod_id)
                
                    kit_info_text = ""
                    if not check_kit.empty:
                        is_kit_edit = True
                        check_kit['max'] = check_kit['child_stock'] // check_kit['quantity']
                        kit_stock_calc = int(check_kit['max'].min())
                        if kit_stock_calc < 0: kit_stock_calc = 0
                    
                        kit_info_text = "Estoque calculado pelos componentes: " + ", ".join([f"{r['name']}: {int(r['child_stock'])} (Precisa {r['quantity']})" for _, r in check_kit.iterrows()])

                    if is_kit_edit:
                        st.info(f"📦 Este produto é um Kit. Estoque calculado: **{kit_stock_calc}**")
                        st.caption(kit_info_text)
                        new_stock = st.number_input("Estoque (Calculado Auto)", value=kit_stock_calc, disabled=True, help="O estoque de kits é baseado na disponibilidade dos seus componentes.")
                    else:
                        curr_stock = int(curr_prod['stock_quantity']) if curr_prod['stock_quantity'] else 0
                        new_stock = st.number_input("Estoque Atual", value=curr_stock, step=1, help="Alterar este valor registrará um ajuste manual no histórico.")
                
                    # cat_opts already fetched at top of tab

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
                                user_id, username = None, 'system'
                                if 'current_user' in st.session_state and st.session_state.current_user:
                                    user_id = int(st.session_state.current_user.get('id'))
                                    username = st.session_state.current_user.get('username', 'unknown')
                                product_service.log_stock_adjustment(conn, selected_prod_id, new_name, diff, user_id, username)

                        product_service.update_product_details(
                            conn, selected_prod_id, new_name, new_cat, new_desc, new_stock,
                            old_name=curr_prod['name'], old_stock=curr_prod['stock_quantity']
                        )
                        product_service.get_all_products.clear()
                        product_service.get_categories.clear()
                        admin_utils.show_feedback_dialog("Detalhes atualizados!", level="success")

            # TABS INTERFACE
            tab_recipe, tab_variants, tab_comp, tab_pricing, tab_images = st.tabs(["📜 Receita Base", "🎨 Esmaltes", "📦 Composição (Kit)", "💰 Precificação", "📷 Imagens"])

            # --- TAB 1: RECEITA (INSUMOS) ---
            with tab_recipe:
                st.caption("Componentes básicos: argilas, mão de obra e queimas.")
                with st.form("add_ingredient"):
                    c1, c2 = st.columns([3, 1])
                    materials = product_service.get_materials_for_base_recipe(conn)
                    mat_dict = {f"{row['name']} ({row['unit']}) - R$ {row['price_per_unit']:.2f}": row['id'] for _, row in materials.iterrows()}
                
                    mat_choice = c1.selectbox("Material/Mão de Obra", [""] + list(mat_dict.keys()))
                    qty_needed = c2.number_input("Qtd", min_value=0.0, step=0.001, format="%.3f")
                
                    if st.form_submit_button("➕ Adicionar Insumo"):
                        if qty_needed > 0 and mat_choice:
                            mat_id = mat_dict[mat_choice]
                            product_service.add_recipe_item(conn, selected_prod_id, mat_id, qty_needed)
                            st.rerun()

                # List Ingredients
                current_recipe = product_service.get_product_recipe(conn, selected_prod_id)
            
                if not current_recipe.empty:
                    st.dataframe(current_recipe, hide_index=True, use_container_width=True)
                    # Remove
                    del_id = st.selectbox("Remover Insumo ID", [""] + current_recipe['id'].astype(str).tolist())
                    if st.button("🗑️ Remover Insumo selecionado", use_container_width=True):
                        if del_id:
                            def do_del_rec(rid=del_id):
                                with database.db_session() as ctx_conn:
                                    product_service.delete_recipe_item(ctx_conn, rid)
                        
                            admin_utils.show_confirmation_dialog(
                                "Remover este insumo da receita do produto?",
                                on_confirm=do_del_rec
                            )
                else:
                    st.info("Nenhuma receita definida.")

            # --- TAB VARIANTS: VARIAÇÕES ---
            with tab_variants:
                st.caption("Gerencie os esmaltes deste produto. O estoque pode ser controlado por esmalte.")
            
                # --- AUTO-GENERATION BLOCK ---
                curr_markup_val = curr_prod['markup'] if curr_prod['markup'] else 2.0
                with st.expander("⚡ Gerar Esmaltes Automaticamente", expanded=False):
                    st.info("Cria uma variação para cada esmalte cadastrado na categoria **Esmaltes** que ainda não esteja vinculado a este produto.")
                    ag_c1, ag_c2 = st.columns(2)
                    ag_qty_kg = ag_c1.number_input("Qtd padrão (kg)", min_value=0.0, step=0.001, value=0.050, format="%.3f", help="Consumo padrão para esmaltes em pó")
                    ag_qty_l = ag_c2.number_input("Qtd padrão (Litros)", min_value=0.0, step=0.001, value=0.030, format="%.3f", help="Consumo padrão para esmaltes líquidos")
                    if st.button("⚡ Gerar Variações", type="primary"):
                        count = product_service.auto_generate_glaze_variants(conn, selected_prod_id, ag_qty_kg, ag_qty_l, float(curr_markup_val))
                        if count > 0:
                            admin_utils.show_feedback_dialog(f"{count} esmalte(s) adicionado(s)!", level="success")
                            st.rerun()
                        else:
                            admin_utils.show_feedback_dialog("Nenhum esmalte novo para adicionar (todos já estão cadastrados ou a categoria 'Esmaltes' está vazia).", level="warning")

                st.markdown("---")

                # Form to Add Variant (Dynamic - No st.form to allow calc)
                st.markdown("##### ➕ Novo Esmalte (Manual)")
            
                # Container for inputs
                vc_add = st.container(border=True)
                with vc_add:
                    v_c1, v_c2, v_c3 = st.columns([3, 2, 2])
                    # Name input moved down to be dynamic
                
                    # Material Link (Optional) - Glazes
                    materials_df = product_service.get_materials_for_variants(conn)
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
                    st.write("📋 Esmaltes Cadastrados:")
                
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
                                    with database.db_session() as ctx_conn:
                                        product_service.delete_variant(ctx_conn, vid)
                            
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
                    prods = product_service.get_products_for_kit(conn, selected_prod_id)
                    prod_dict = {row['name']: row['id'] for _, row in prods.iterrows()}
                
                    prod_choice = c1.selectbox("Produto Componente", [""] + list(prod_dict.keys()))
                    k_qty = c2.number_input("Qtd", min_value=1, value=1)
                
                    if st.form_submit_button("➕ Adicionar Componente"):
                        if prod_choice:
                            child_id = prod_dict[prod_choice]
                            product_service.add_kit_item(conn, selected_prod_id, child_id, k_qty)
                            st.toast("Componente adicionado!")
                            st.rerun()
            
                # List Kit Items
                kit_items = product_service.get_kit_items_detail(conn, selected_prod_id)
            
                if not kit_items.empty:
                    st.warning("⚠️ Nota: Ao produzir este KIT, o estoque dos componentes abaixo será descontado.")
                    st.dataframe(kit_items, hide_index=True, use_container_width=True)
                
                    del_kit_id = st.selectbox("Remover Componente ID", [""] + kit_items['id'].astype(str).tolist())
                    if st.button("🗑️ Remover Componente selecionado", use_container_width=True):
                         if del_kit_id:
                            def do_del_kit(kid=del_kit_id):
                                with database.db_session() as ctx_conn:
                                    product_service.delete_kit_item(ctx_conn, kid)

                            admin_utils.show_confirmation_dialog(
                                "Remover este componente do kit?",
                                on_confirm=do_del_kit
                            )

            # --- TAB 3: IMAGENS ---
            with tab_images:
                st.caption("Gerencie as fotos do produto.")
                # Reuse logic from expanding section
                try:
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
                                    product_service.update_product_images(conn, selected_prod_id, curr_imgs)
                                    product_service.get_all_products.clear()
                                    st.rerun()
                            except Exception:
                                pass
            
                new_imgs = st.file_uploader("Upload Novas Imagens", accept_multiple_files=True, type=["png", "jpg", "jpeg", "webp"], key="new_imgs_tab")
                if new_imgs:
                    if st.button("Salvar Imagens"):
                        for uf in new_imgs:
                             path = admin_utils.save_image(uf, "assets/product_images")
                             if path:
                                 curr_imgs.append(path)
                        product_service.update_product_images(conn, selected_prod_id, curr_imgs)
                        product_service.get_all_products.clear()
                        admin_utils.show_feedback_dialog("Salvo!", level="success")
                        st.rerun()

                # --- NEW: Auto-Display Component Images (Kits) ---
                comp_prods = product_service.get_kit_component_images(conn, selected_prod_id)
                if not comp_prods.empty:
                    st.markdown("---")
                    st.info("ℹ️ Abaixo são exibidas automaticamente as imagens dos produtos que compõem este kit.")
                
                    for _, cp in comp_prods.iterrows():
                        try:
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
            
                # ==============================================================
                # SECTION 1: CUSTO BASE
                # ==============================================================
                st.markdown("#### 📜 Custo Base")
                
                base_cost = 0.0
                cost_breakdown = []
            
                # Check Kit
                kit_components = product_service.get_pricing_kit_components(conn, selected_prod_id)
            
                if not kit_components.empty:
                    st.caption("Custo baseado nos produtos componentes (Kit).")
                    for _, row in kit_components.iterrows():
                        subtotal = row['quantity'] * row['base_price']
                        base_cost += subtotal
                        cost_breakdown.append({"Item": row['name'], "Qtd": row['quantity'], "Unit": f"R$ {row['base_price']:.2f}", "Total": f"R$ {subtotal:.2f}"})
                else:
                    # Check Recipe
                    recipe_items = product_service.get_pricing_recipe_items(conn, selected_prod_id)
                
                    if not recipe_items.empty:
                        st.caption("Custo baseado na receita de insumos (sem esmaltes).")
                        for _, row in recipe_items.iterrows():
                            subtotal = row['quantity'] * row['price_per_unit']
                            base_cost += subtotal
                            cost_breakdown.append({"Item": row['name'], "Qtd": f"{row['quantity']} {row['unit']}", "Unit": f"R$ {row['price_per_unit']:.2f}", "Total": f"R$ {subtotal:.2f}"})
                    else:
                        st.warning("⚠️ Sem receita ou composição definida. Custo base é zero.")
            
                if cost_breakdown:
                    st.dataframe(pd.DataFrame(cost_breakdown), hide_index=True, use_container_width=True)
                
                st.metric("Subtotal Base", f"R$ {base_cost:.2f}")

                # ==============================================================
                # SECTION 2: MARKUP & PREÇO FINAL
                # ==============================================================
                st.divider()
                st.markdown("#### 💰 Markup & Preços Finais")

                # Markup Input
                curr_markup = curr_prod['markup'] if curr_prod['markup'] else 2.0
                new_markup = st.number_input("Markup (Multiplicador)", value=float(curr_markup), step=0.1, help="Aplicado sobre (Custo Base + Custo Esmalte)")

                # Fetch variants for analysis
                vars_analysis = product_service.get_product_variants(conn, selected_prod_id)

                if not vars_analysis.empty:
                    st.markdown("##### 🎨 Preço por Esmalte")

                    analysis_data = []
                    for _, v_row in vars_analysis.iterrows():
                        # Calculate glaze cost
                        glaze_cost = 0.0
                        if v_row['material_id'] and v_row['material_quantity']:
                            try:
                                mat_p = product_service.get_material_price(conn, v_row['material_id']).iloc[0]
                                glaze_cost = v_row['material_quantity'] * mat_p['price_per_unit']
                            except Exception:
                                pass
                        
                        total_cost = base_cost + glaze_cost
                        ideal_price = total_cost * new_markup
                        
                        # Current Price (Base Price + Adder)
                        base_p = float(curr_prod['base_price']) if curr_prod['base_price'] else 0.0
                        current_final_price = base_p + v_row['price_adder']

                        analysis_data.append({
                            "id": v_row['id'],
                            "Esmalte": v_row['variant_name'],
                            "Custo Base": base_cost,
                            "Custo Esmalte": glaze_cost,
                            "Custo Total": total_cost,
                            "Markup": new_markup,
                            "Preço Sugerido": ideal_price,
                            "Preço Atual": current_final_price,
                        })
                
                    df_analysis = pd.DataFrame(analysis_data)
                
                    st.dataframe(
                        df_analysis,
                        column_config={
                            "id": None,
                            "Esmalte": st.column_config.TextColumn(disabled=True),
                            "Custo Base": st.column_config.NumberColumn(format="R$ %.2f", disabled=True),
                            "Custo Esmalte": st.column_config.NumberColumn(format="R$ %.2f", disabled=True),
                            "Custo Total": st.column_config.NumberColumn(format="R$ %.2f", disabled=True, help="Base + Esmalte"),
                            "Markup": st.column_config.NumberColumn(format="%.1fx", disabled=True),
                            "Preço Sugerido": st.column_config.NumberColumn(format="R$ %.2f", disabled=True, help="Custo Total × Markup"),
                            "Preço Atual": st.column_config.NumberColumn(format="R$ %.2f", disabled=True),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                
                    # --- Quick Actions ---
                    ac1, ac2 = st.columns(2)
                    
                    # Apply Suggested to All
                    if ac1.button("⬇️ Aplicar Sugerido a Todos", use_container_width=True, help="Define o preço de cada esmalte como (Custo Total × Markup)"):
                        # IMPORTANT: Save base_price FIRST, then compute adders with the new value
                        new_base_price = base_cost * new_markup
                        product_service.save_product_pricing(conn, selected_prod_id, new_markup, new_base_price)
                        
                        # Now compute adders relative to the NEW base_price
                        for _, ad in pd.DataFrame(analysis_data).iterrows():
                            new_adder = ad['Preço Sugerido'] - new_base_price
                            if new_adder < 0: new_adder = 0
                            product_service.update_variant_price(conn, int(ad['id']), new_adder)
                        
                        product_service.get_all_products.clear()
                        admin_utils.show_feedback_dialog("Preços atualizados para todos os esmaltes!", level="success")
                        st.rerun()

                    # --- Individual Edit ---
                    st.divider()
                    st.markdown("##### 🛠️ Editar Preço Individual")
                
                    var_opts = {r['variant_name']: r for _, r in vars_analysis.iterrows()}
                    sel_var_name = st.selectbox("Selecione o Esmalte", list(var_opts.keys()))
                
                    if sel_var_name:
                        sel_var = var_opts[sel_var_name]
                    
                        # Calculate Metrics
                        v_mat_price = 0.0
                        if sel_var['material_id']:
                             try:
                                 mp = product_service.get_material_price(conn, sel_var['material_id']).iloc[0]['price_per_unit']
                                 v_mat_price = mp * sel_var['material_quantity']
                             except Exception as e: logger.warning(f"Erro ao buscar preço do material da variação: {e}")
                    
                        v_total_cost = base_cost + v_mat_price
                        v_curr_price = (float(curr_prod['base_price']) if curr_prod['base_price'] else 0) + sel_var['price_adder']
                    
                        svc1, svc2, svc3 = st.columns(3)
                    
                        svc1.metric("Custo Total (Base + Esmalte)", f"R$ {v_total_cost:.2f}")
                        v_suggested = v_total_cost * new_markup
                        svc2.metric("Preço Sugerido", f"R$ {v_suggested:.2f}")
                    
                        v_final_price = svc3.number_input("Preço Final (Venda)", value=float(v_curr_price), step=1.0, key=f"vp_{sel_var['id']}")
                    
                        # Helper button for suggested
                        if svc2.button("⬇️ Usar Sugerido", key=f"vus_{sel_var['id']}"):
                             st.session_state[f"vp_{sel_var['id']}"] = float(v_suggested)
                             st.rerun()

                        if svc3.button("💾 Salvar", key=f"vsave_{sel_var['id']}", type="primary", use_container_width=True):
                             base_p = float(curr_prod['base_price']) if curr_prod['base_price'] else 0.0
                             new_adder = v_final_price - base_p
                             if new_adder < 0: new_adder = 0
                         
                             product_service.update_variant_price(conn, sel_var['id'], new_adder)
                             admin_utils.show_feedback_dialog(f"Preço de '{sel_var_name}' atualizado!", level="success")
                else:
                    # No variants - simple pricing
                    st.caption("Sem esmaltes cadastrados. Preço calculado apenas com a receita base.")
                    
                    col_sug, col_final = st.columns(2)
                    suggested = base_cost * new_markup
                    col_sug.metric("Preço Sugerido", f"R$ {suggested:.2f}")
                    
                    curr_price = float(curr_prod['base_price']) if (curr_prod['base_price'] is not None and curr_prod['base_price'] != '') else 0.0
                    default_val = curr_price if curr_price > 0.01 else suggested
                    
                    if f"final_price_{selected_prod_id}" not in st.session_state:
                        st.session_state[f"final_price_{selected_prod_id}"] = float(default_val)
                    
                    new_price = col_final.number_input("Preço Final (Venda)", step=1.0, key=f"final_price_{selected_prod_id}")
                    
                    if col_sug.button("⬇️ Usar Sugerido"):
                        st.session_state[f"final_price_{selected_prod_id}"] = float(suggested)
                        st.rerun()

                    if col_final.button("💾 Salvar", type="primary", use_container_width=True):
                        product_service.save_product_pricing(conn, selected_prod_id, new_markup, new_price)
                        product_service.get_all_products.clear()
                        admin_utils.show_feedback_dialog("Preço Base Salvo!", level="success")

                # Save Markup (always, regardless of variants)
                if st.button("💾 Salvar Markup", help="Salvar apenas o multiplicador de markup"):
                    product_service.save_product_pricing(conn, selected_prod_id, new_markup, float(curr_prod['base_price']) if curr_prod['base_price'] else 0.0)
                    product_service.get_all_products.clear()
                    admin_utils.show_feedback_dialog("Markup salvo!", level="success")

            st.markdown("---")
            with st.expander("🚫 Zona de Perigo"):
                if st.button("EXCLUIR PRODUTO", type="primary", use_container_width=True):
                    def do_delete_prod(pid=selected_prod_id, pname=curr_prod['name']):
                        product_service.delete_product(conn, pid, pname)
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
            prod_names = product_service.get_production_history_product_names(conn)
            prod_filter_opts = ["Todos"] + (prod_names['product_name'].tolist() if not prod_names.empty else [])
            filter_prod = st.selectbox("Produto", prod_filter_opts)
    
        with fh3:
            # User filter
            user_names = product_service.get_production_history_usernames(conn)
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
    
        history_df = product_service.get_production_history_filtered(conn, " ".join(query_parts), params)
    
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
                            
                                product_service.update_production_history_qty(
                                    conn, row['id'], new_qty, row['quantity'], row['product_id']
                                )
                            
                                product_service.get_all_products.clear()
                                admin_utils.show_feedback_dialog("Atualizado!", level="success")
                                st.rerun()
                
                    with c3:
                        # Delete button
                        if st.button("🗑️", key=f"del_prod_{row['id']}", help="Excluir registro"):
                            def do_delete_hist(rid=row['id'], pid=row['product_id'], qty=row['quantity'], pname=row['product_name']):
                                with database.db_session() as ctx_conn:
                                    product_service.delete_production_history(ctx_conn, rid, pid, qty, pname)
                                product_service.get_all_products.clear()

                            admin_utils.show_confirmation_dialog(
                                f"Excluir este registro de produção? O estoque de '{row['product_name']}' será revertido (subtraído em {int(row['quantity'])}).",
                                on_confirm=do_delete_hist
                            )
        else:
            st.info("Nenhum registro de produção encontrado para os filtros selecionados.")

