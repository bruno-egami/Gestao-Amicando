import streamlit as st
import pandas as pd
import os
import database
import auth
import audit
import admin_utils
from datetime import datetime, date
import services.material_service as material_service

st.set_page_config(page_title="Insumos", page_icon="🧱", layout="wide")

# Apply Global Styles
import utils.styles as styles
styles.apply_custom_style()

conn = database.get_connection()

# Auth
if not auth.require_login(conn):
    st.stop()

if not auth.check_page_access("Insumos"):
    st.stop()

auth.render_custom_sidebar()
st.title("Gestão de Insumos (Matérias-Primas)")

tab_cat, tab_hist_global = st.tabs(["Catálogo", "Movimentações (Histórico)"])

with tab_cat:
    # --- 1. Top Bar: Controls & Filters ---
    cats_df = material_service.get_all_categories(conn)
    cat_map = {row['name']: row['id'] for _, row in cats_df.iterrows()}
    cat_options = ["Todas"] + list(cat_map.keys())

    # Suppliers
    sup_df = material_service.get_all_suppliers(conn)
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
        if st.button("➕ Novo Insumo", use_container_width=True, type="primary"):
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
                    material_service.create_category(conn, new_cat_name)
                    admin_utils.show_feedback_dialog(f"Categoria '{new_cat_name}' criada!", level="success")
                    st.rerun()
                except Exception as e:
                    if "UNIQUE constraint failed" in str(e):
                        admin_utils.show_feedback_dialog("Categoria já existe.", level="error")
                    else:
                        admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")
            else:
                admin_utils.show_feedback_dialog("Digite um nome.", level="warning")
                
        # List Existing (small editor)
        if not cats_df.empty:
            st.write("Categorias Existentes:")
            st.dataframe(cats_df, hide_index=True)

    st.divider()

    # --- 3. Main Data Fetch ---
    df_materials = material_service.get_all_materials(conn)

    # In-memory filtering
    if not df_materials.empty:
        if f_cat != "Todas":
            df_materials = df_materials[df_materials['category_name'] == f_cat]
        if f_sup != "Todos":
            df_materials = df_materials[df_materials['supplier_name'] == f_sup]
        if f_search:
            df_materials = df_materials[df_materials['name'].str.contains(f_search, case=False, na=False)]

    # --- 4. Logic: Detail View OR Grid View ---

    if st.session_state.insumo_edit_id is not None:
        # === DETAIL / EDIT MODE ===
        
        # Check if creating NEW or EDITING existing
        is_new = st.session_state.insumo_edit_id == "NEW"
        
        target_data = {}
        if not is_new:
            # Get fresh data
            target_data = material_service.get_material_by_id(conn, st.session_state.insumo_edit_id)
            if not target_data:
                admin_utils.show_feedback_dialog("Insumo não encontrado.", level="error")
                st.session_state.insumo_edit_id = None
                st.rerun()
        
        # Header
        c_back, c_tit = st.columns([1, 5])
        
        def reset_insumo_edit():
            st.session_state.insumo_edit_id = None
            
        c_back.button("⬅️ Voltar ao Catálogo", on_click=reset_insumo_edit)
        
        st.header("Cadastrar Novo Insumo" if is_new else f"Editar: {target_data.get('name')}")

        # Tabs
        tab_details, tab_history = st.tabs(["📝 Detalhes do Material", "📊 Histórico de Estoque"])

        with tab_details:
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
                
                # Safe Key Generation
                safe_id = target_data.get('id', 'new')
                stock = c7.number_input("Estoque Atual (Ajuste Manual)", value=float(target_data.get('stock_level', 0.0)), step=0.1, help="Use a aba Histórico para registrar entradas/saídas do dia a dia.", key=f"stock_adj_{safe_id}_{target_data.get('stock_level')}")
                min_alert = st.number_input("Alerta Mínimo", value=float(target_data.get('min_stock_alert', 0.0)), step=0.1)
                
                # Image Upload
                st.markdown("---")
                st.write("Imagem do Insumo")
                curr_img = target_data.get('image_path')
                if curr_img and os.path.exists(curr_img):
                    st.image(curr_img, width=150, caption="Imagem Atual")
                    
                new_img_file = st.file_uploader("Carregar nova imagem", type=["png", "jpg", "jpeg", "webp"])
                
                # Buttons
                submitted = st.form_submit_button("Salvar Insumo")
                
                if submitted:
                    if not name:
                        admin_utils.show_feedback_dialog("Nome é obrigatório.", level="error")
                    else:
                        cat_id = cat_map.get(sel_cat)
                        sup_id = sup_map.get(sel_sup)
                        
                        # Handle Image
                        final_img_path = curr_img # keep old if no new
                        if new_img_file:
                            save_dir = "assets/material_images"
                            if not os.path.exists(save_dir): os.makedirs(save_dir)
                            file_path = os.path.join(save_dir, new_img_file.name)
                            with open(file_path, "wb") as f:
                                f.write(new_img_file.getbuffer())
                            final_img_path = file_path
                        
                        if is_new:
                            try:
                                new_id = material_service.create_material(conn, name, cat_id, sup_id, price, unit, stock, min_alert, m_type, final_img_path)
                                audit.log_action(conn, 'CREATE', 'materials', new_id, None, {
                                    'name': name, 'price_per_unit': price, 'unit': unit, 'stock_level': stock, 'type': m_type
                                })
                                st.session_state.insumo_edit_id = None
                                admin_utils.show_feedback_dialog("Criado com sucesso!", level="success")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao criar: {e}")
                        else:
                            target_id = st.session_state.insumo_edit_id
                            old_data = target_data
                            
                            old_stock = float(target_data.get('stock_level', 0.0))
                            new_stock = float(stock)
                            
                            try:
                                material_service.update_material(conn, target_id, name, cat_id, sup_id, price, unit, new_stock, min_alert, m_type, final_img_path)
                                
                                # Log if stock changed manually
                                if abs(new_stock - old_stock) > 0.001:
                                     diff = new_stock - old_stock
                                     current_u = auth.get_current_user()
                                     u_id = int(current_u['id']) if current_u else 1
                                     
                                     material_service.log_transaction(conn, int(target_id), datetime.now().isoformat(), 'AJUSTE', abs(diff), 0.0, "Ajuste Manual na Edição", u_id)
                                
                                audit.log_action(conn, 'UPDATE', 'materials', target_id, old_data, {
                                    'name': name, 'price_per_unit': price, 'unit': unit, 'stock_level': stock, 'type': m_type
                                })
                                admin_utils.show_feedback_dialog("Atualizado com sucesso!", level="success")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao atualizar: {e}")

            # Delete Option (Only for Edit)
            if not is_new:
                st.markdown("---")
                with st.expander("Zona de Perigo"):
                    if st.button("EXCLUIR INSUMO", type="primary", use_container_width=True):
                        def do_delete(mid=st.session_state.insumo_edit_id, mname=target_data.get('name')):
                            try:
                                with database.db_session() as ctx_conn:
                                    original = material_service.get_material_by_id(ctx_conn, mid)
                                    material_service.delete_material(ctx_conn, mid)
                                    audit.log_action(ctx_conn, 'DELETE', 'materials', mid, original, None)
                                st.session_state.insumo_edit_id = None
                            except Exception as e:
                                st.error(f"Erro ao excluir: {e}")

                        admin_utils.show_confirmation_dialog(
                            f"Tem certeza que deseja EXCLUIR PERMANENTEMENTE o insumo '{target_data.get('name')}'?",
                            on_confirm=do_delete
                        )

        with tab_history:
            if is_new:
                st.info("Salve o novo insumo antes de registrar movimentações.")
            else:
                st.subheader("Registrar Movimentação")
                
                with st.form("trans_form"):
                    col_t1, col_t2, col_t3, col_t4 = st.columns(4)
                    t_type = col_t1.selectbox("Tipo", ["ENTRADA (Compra/Add)", "SAIDA (Consumo/Baixa)"])
                    t_qtd = col_t2.number_input("Quantidade", min_value=0.0, step=0.1, value=None)
                    t_date = col_t3.date_input("Data", value=datetime.now())
                    t_obs = st.text_input("Observação", placeholder="Ex: NF 123, Uso na queima X...")
                    
                    # Optional Cost for Entrada
                    t_cost = 0.0
                    if "ENTRADA" in t_type:
                        t_cost = col_t4.number_input("Custo Total (Opcional)", min_value=0.0, step=0.01, help="Quanto custou essa entrada?")
                    else:
                        col_t4.write("") # Spacer or info

                    if st.form_submit_button("💾 Registrar Movimento", type="primary"):
                        if t_qtd is None or t_qtd <= 0:
                            st.error("Informe uma quantidade válida.")
                        else:
                            clean_type = t_type.split(" ")[0] # ENTRADA, SAIDA
                            current_u = auth.get_current_user()
                            u_id = int(current_u['id']) if current_u else 1
                            
                            try:
                                if clean_type == "ENTRADA":
                                    new_stock, new_price = material_service.register_entry(
                                        conn, int(target_data['id']), float(t_qtd), float(t_cost), t_obs, u_id
                                    )
                                    details = f"Qtd: {t_qtd} {target_data['unit']}\n\nNovo Preço Médio: R$ {new_price:.2f}\n\nNovo Saldo: {new_stock:.2f}"
                                    admin_utils.show_feedback_dialog("Movimentação registrada!", level="success", sub_message=details)
                                
                                elif clean_type == "SAIDA":
                                    new_stock = material_service.register_exit(
                                        conn, int(target_data['id']), float(t_qtd), t_obs, u_id
                                    )
                                    details = f"Qtd: {t_qtd} {target_data['unit']}\n\nNovo Saldo: {new_stock:.2f}"
                                    admin_utils.show_feedback_dialog("Saída registrada!", level="success", sub_message=details)
                                
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao registrar: {e}")

                st.divider()
                st.subheader("Extrato de Movimentações")
                
                # Fetch History via Service
                hist_df = material_service.get_material_history(conn, int(target_data['id']))
                
                if not hist_df.empty:
                    st.dataframe(hist_df, use_container_width=True)
                else:
                    st.info("Nenhuma movimentação registrada.")

    else:
        # === CATALOG / GRID VIEW ===
        if df_materials.empty:
            st.info("Nenhum insumo encontrado com os filtros atuais.")
        else:
            # Display as Vertical List (Standardized with Products)
            for i, row in df_materials.iterrows():
                with st.container(border=True):
                    # Layout: Image | Info | Price/Sup | Action
                    c_img, c_info, c_price, c_act1, c_act2 = st.columns([1, 4, 3, 1, 1])
                    
                    # Image
                    with c_img:
                        if row['image_path'] and os.path.exists(row['image_path']):
                            st.image(row['image_path'], width=60)
                        else:
                            st.write("🧱") # Placeholder icon
                    
                    # Info
                    with c_info:
                        st.markdown(f"**{row['name']}** `#{row['id']}`")
                        cat_lbl = row['category_name'] if row['category_name'] else "Geral"
                        st.caption(f"{cat_lbl} | {row['type']}")
                        
                        # Stock Highlight
                        stock_val = row['stock_level']
                        if row['type'] in ['Mão de Obra', 'Queima'] or row['unit'] in ['hora (mão de obra)', 'fornada']:
                            st.write("Estoque: N/A")
                        else:
                            color = "red" if stock_val <= row['min_stock_alert'] else "green"
                            st.markdown(f"Estoque: :{color}[{stock_val} {row['unit']}]")

                    # Price & Supplier
                    with c_price:
                         st.write(f"**R$ {row['price_per_unit']:.2f}** / {row['unit']}")
                         sup_lbl = row['supplier_name'] if row['supplier_name'] else "Sem Fornecedor"
                         st.caption(f"Fornecedor: {sup_lbl}")
                    
                    # Quick Entry Button (Popover)
                    with c_act1:
                        with st.popover("➕ Entrada"):
                            st.markdown(f"**Registrar Entrada: {row['name']}**")
                            q_qty = st.number_input("Qtd", min_value=0.0, step=0.1, value=None, key=f"q_qty_{row['id']}")
                            q_price = st.number_input("Preço da Nova Compra (R$/un)", min_value=0.0, value=None, placeholder=f"{row['price_per_unit']:.2f}", step=0.01, key=f"q_price_{row['id']}", help="O preço médio ponderado do estoque será recalculado. Se deixar vazio, usará o preço atual.")
                            q_date = st.date_input("Data", value=datetime.now(), key=f"q_date_{row['id']}")
                            q_obs = st.text_input("Obs", placeholder="Ex: NF 123", key=f"q_obs_{row['id']}")
                            
                            if st.button("Confirmar Entrada", key=f"q_btn_{row['id']}", type="primary"):
                                if q_qty is None or q_qty <= 0:
                                    st.error("Informe uma quantidade válida.")
                                else:
                                    try:
                                        curr_price = float(row['price_per_unit'])
                                        purchase_price = float(q_price) if q_price is not None else curr_price
                                        total_cost = purchase_price * float(q_qty)
                                        
                                        current_u = auth.get_current_user()
                                        u_id_entry = int(current_u['id']) if current_u else 1
                                        
                                        new_stock_entry, new_avg_price = material_service.register_entry(
                                            conn, int(row['id']), float(q_qty), total_cost, q_obs, u_id_entry
                                        )
                                        
                                        # Persistent feedback
                                        details = f"Qtd Adicionada: {q_qty} {row['unit']}\n\nNovo Preço Médio: R$ {new_avg_price:.2f}/{row['unit']}\n\nNovo Saldo: {new_stock_entry:.2f} {row['unit']}"
                                        admin_utils.show_feedback_dialog(
                                            f"Entrada de {row['name']} registrada!", 
                                            level="success",
                                            sub_message=details
                                        )
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro: {e}")

                    # Edit Button
                    with c_act2:
                        if st.button("✏️", key=f"edit_{row['id']}", use_container_width=True, help="Editar cadastro completo"):
                            st.session_state.insumo_edit_id = row['id']
                            st.rerun()

# --- TAB 2: GLOBAL HISTORY ---
with tab_hist_global:
    st.subheader("📜 Histórico Global de Movimentações")
    
    # Filters
    hf1, hf2, hf3, hf4 = st.columns(4)
    
    with hf1:
        h_period_ui = st.selectbox("Período", ["Hoje", "Últimos 7 dias", "Últimos 30 dias", "Todo o Sempre"], index=1)
        # Map to service inputs
        period_map = {
            "Hoje": "Hoje",
            "Últimos 7 dias": "7d",
            "Últimos 30 dias": "30d",
            "Todo o Sempre": "all"
        }
        h_period = period_map[h_period_ui]
    
    with hf2:
        m_names = material_service.get_all_materials(conn)
        h_mat_opts = ["Todos"] + sorted(m_names['name'].unique().tolist())
        h_mat = st.selectbox("Material", h_mat_opts)
        
    with hf3:
        h_type = st.selectbox("Tipo de Movimento", ["Todos", "ENTRADA", "SAIDA", "AJUSTE"])
        
    with hf4:
        # We need a user list service method or direct query (User Service exists?)
        # For now, let's just use what we have in material_service helper or direct if needed?
        # material_service doesn't have get_all_users.
        # But we previously used direct SQL.
        # I should add get_all_users to auth or admin_utils?
        # Or just use direct SQL for users list as it's minor?
        # I'll use direct SQL for now to avoid creating User Service right now.
        # Wait, I removed sqlite3 import.
        # I can use pd.read_sql since pandas is imported.
        u_names = pd.read_sql("SELECT username FROM users ORDER BY username", conn)
        h_user_opts = ["Todos"] + u_names['username'].tolist()
        h_user = st.selectbox("Usuário", h_user_opts)
        
    # Fetch History
    filters = {
        'period': h_period,
        'material_name': h_mat,
        'type': h_type,
        'user_name': h_user
    }
    
    hdf = material_service.get_global_history(conn, filters)
    
    # Stats
    if not hdf.empty:
        total_entradas = hdf[hdf['type'] == 'ENTRADA']['cost'].sum()
        
        st.caption(f"Exibindo {len(hdf)} registros. Custo Total de Entradas (no período): **R$ {total_entradas:.2f}**")
        
        st.dataframe(
            hdf, 
            column_config={
                "date": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY HH:mm"),
                "material_name": "Material",
                "type": "Tipo",
                "quantity": st.column_config.NumberColumn("Qtd", format="%.2f"),
                "unit": "Unid",
                "cost": st.column_config.NumberColumn("Custo (R$)", format="R$ %.2f"),
                "notes": "Obs",
                "username": "Usuário"
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Nenhuma movimentação encontrada para os filtros selecionados.")

conn.close()

