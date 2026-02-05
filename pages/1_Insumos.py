import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import database
import auth
import audit
import admin_utils
from datetime import datetime

st.set_page_config(page_title="Insumos", page_icon="🧱", layout="wide")

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
                    cursor.execute("INSERT INTO material_categories (name) VALUES (?)", (new_cat_name,))
                    conn.commit()
                    admin_utils.show_feedback_dialog(f"Categoria '{new_cat_name}' criada!", level="success")
                except sqlite3.IntegrityError:
                    admin_utils.show_feedback_dialog("Categoria já existe.", level="error")
            else:
                admin_utils.show_feedback_dialog("Digite um nome.", level="warning")
                
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
                admin_utils.show_feedback_dialog("Insumo não encontrado.", level="error")
                st.session_state.insumo_edit_id = None
        
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
                            cursor.execute("""
                                INSERT INTO materials (name, price_per_unit, unit, stock_level, min_stock_alert, type, supplier_id, category_id, image_path)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (name, price, unit, stock, min_alert, m_type, sup_id, cat_id, final_img_path))
                            new_id = cursor.lastrowid
                            conn.commit()
                            audit.log_action(conn, 'CREATE', 'materials', new_id, None, {
                                'name': name, 'price_per_unit': price, 'unit': unit, 'stock_level': stock, 'type': m_type
                            })
                            st.session_state.insumo_edit_id = None
                            admin_utils.show_feedback_dialog("Criado com sucesso!", level="success")
                        else:
                            target_id = st.session_state.insumo_edit_id
                            # Get old data for audit
                            old_mat = pd.read_sql("SELECT name, price_per_unit, unit, stock_level, min_stock_alert, type FROM materials WHERE id=?", conn, params=(target_id,))
                            old_data = old_mat.iloc[0].to_dict() if not old_mat.empty else {}
                            
                            # Logic to detect manual stock change
                            old_stock = float(target_data.get('stock_level', 0.0))
                            new_stock = float(stock)
                            
                            cursor.execute("""
                                UPDATE materials 
                                SET name=?, category_id=?, supplier_id=?, type=?, price_per_unit=?, unit=?, stock_level=?, min_stock_alert=?, image_path=?
                                WHERE id=?
                            """, (name, cat_id, sup_id, m_type, price, unit, new_stock, min_alert, final_img_path, target_id))
                            
                            # Log if stock changed manually
                            if abs(new_stock - old_stock) > 0.001: # Use a small epsilon for float comparison
                                 diff = new_stock - old_stock
                                 current_u = auth.get_current_user()
                                 u_id = int(current_u['id']) if current_u else 1
                                 
                                 cursor.execute("""
                                    INSERT INTO inventory_transactions (material_id, date, type, quantity, cost, notes, user_id)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (int(target_id), datetime.now().isoformat(), 'AJUSTE', abs(diff), 0.0, "Ajuste Manual na Edição", u_id))
                            
                            conn.commit()
                            audit.log_action(conn, 'UPDATE', 'materials', target_id, old_data, {
                                'name': name, 'price_per_unit': price, 'unit': unit, 'stock_level': stock, 'type': m_type
                            })
                            admin_utils.show_feedback_dialog("Atualizado com sucesso!", level="success")

            # Delete Option (Only for Edit)
            if not is_new:
                st.markdown("---")
                with st.expander("Zona de Perigo"):
                    if st.button("EXCLUIR INSUMO", type="primary", use_container_width=True):
                        def do_delete(mid=st.session_state.insumo_edit_id, mname=target_data.get('name')):
                            try:
                                # Get old data for audit
                                old_mat = pd.read_sql("SELECT name, price_per_unit, unit, stock_level, type FROM materials WHERE id=?", conn, params=(mid,))
                                old_data = old_mat.iloc[0].to_dict() if not old_mat.empty else {}
                                
                                cursor.execute("DELETE FROM materials WHERE id=?", (mid,))
                                conn.commit()
                                audit.log_action(conn, 'DELETE', 'materials', mid, old_data, None)
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
                            # Logic
                            current_stock = target_data.get('stock_level', 0.0)
                            new_rec_stock = current_stock
                            
                            clean_type = t_type.split(" ")[0] # ENTRADA, SAIDA
                            
                            curr_price = float(target_data.get('price_per_unit', 0.0))
                            new_calc_price = curr_price
                            
                            if clean_type == "ENTRADA":
                                new_rec_stock += t_qtd
                                # Weighted Average Price Calculation
                                if t_cost > 0:
                                    pur_price = float(t_cost / t_qtd)
                                    if current_stock > 0:
                                        new_calc_price = ((current_stock * curr_price) + t_cost) / (current_stock + t_qtd)
                                    else:
                                        new_calc_price = pur_price
                            elif clean_type == "SAIDA":
                                new_rec_stock -= t_qtd

                            current_u = auth.get_current_user()
                            u_id = int(current_u['id']) if current_u else 1
                            
                            # Explicit casting
                            mat_id_py = int(target_data['id'])
                            t_qtd_py = float(t_qtd)
                            new_rec_stock_py = float(new_rec_stock)
                            
                            cursor.execute("""
                                INSERT INTO inventory_transactions (material_id, date, type, quantity, cost, notes, user_id)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (mat_id_py, t_date.isoformat(), clean_type, t_qtd_py, float(t_cost), t_obs, u_id))
                            
                            # Update Material Stock & Price
                            cursor.execute("UPDATE materials SET stock_level = ?, price_per_unit = ? WHERE id = ?", (new_rec_stock_py, float(new_calc_price), mat_id_py))
                            conn.commit()
                            
                            # Persistent feedback
                            details = f"Qtd: {t_qtd} {target_data['unit']}\n\nNovo Preço Médio: R$ {new_calc_price:.2f}\n\nNovo Saldo: {new_rec_stock:.2f}"
                            admin_utils.show_feedback_dialog("Movimentação registrada!", level="success", sub_message=details)

                st.divider()
                st.subheader("Extrato de Movimentações")
                
                # Fetch History
                # Cast to int to ensure SQLite matches INTEGER column (not BLOB)
                m_id_query = int(target_data['id'])
                
                hist_df = pd.read_sql("""
                    SELECT date, type, quantity, notes, username 
                    FROM inventory_transactions t
                    LEFT JOIN users u ON t.user_id = u.id
                    WHERE material_id = ?
                    ORDER BY t.id DESC
                """, conn, params=(m_id_query,))
                
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
                                        cursor_entry = conn.cursor()
                                        curr_stock = float(row['stock_level'])
                                        curr_price = float(row['price_per_unit'])
                                        
                                        # Use provided price or fallback to current
                                        purchase_price = float(q_price) if q_price is not None else curr_price
                                        
                                        # Weighted Average Logic
                                        if curr_stock > 0:
                                            new_avg_price = ((curr_stock * curr_price) + (q_qty * purchase_price)) / (curr_stock + q_qty)
                                        else:
                                            new_avg_price = purchase_price
                                        
                                        new_stock_entry = curr_stock + q_qty
                                        current_u = auth.get_current_user()
                                        u_id_entry = int(current_u['id']) if current_u else 1
                                        
                                        # 1. Log Transaction
                                        cursor_entry.execute("""
                                            INSERT INTO inventory_transactions (material_id, date, type, quantity, cost, notes, user_id)
                                            VALUES (?, ?, 'ENTRADA', ?, ?, ?, ?)
                                        """, (int(row['id']), q_date.isoformat(), float(q_qty), float(purchase_price * q_qty), q_obs, u_id_entry))
                                        
                                        # 2. Update Material (Stock and Price)
                                        cursor_entry.execute("""
                                            UPDATE materials 
                                            SET stock_level = ?, price_per_unit = ? 
                                            WHERE id = ?
                                        """, (float(new_stock_entry), float(new_avg_price), int(row['id'])))
                                        
                                        conn.commit()
                                        
                                        # Persistent feedback
                                        details = f"Qtd Adicionada: {q_qty} {row['unit']}\n\nNovo Preço Médio: R$ {new_avg_price:.2f}/{row['unit']}\n\nNovo Saldo: {new_stock_entry:.2f} {row['unit']}"
                                        admin_utils.show_feedback_dialog(
                                            f"Entrada de {row['name']} registrada!", 
                                            level="success",
                                            sub_message=details
                                        )
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
        from datetime import timedelta, date as dt_date
        h_period = st.selectbox("Período", ["Hoje", "Últimos 7 dias", "Últimos 30 dias", "Todo o Sempre"], index=1)
    
    with hf2:
        # Fetch materials for filter
        m_names = pd.read_sql("SELECT name FROM materials ORDER BY name", conn)
        h_mat_opts = ["Todos"] + m_names['name'].tolist()
        h_mat = st.selectbox("Material", h_mat_opts)
        
    with hf3:
        h_type = st.selectbox("Tipo de Movimento", ["Todos", "ENTRADA", "SAIDA", "AJUSTE"])
        
    with hf4:
        # Fetch users
        u_names = pd.read_sql("SELECT username FROM users ORDER BY username", conn)
        h_user_opts = ["Todos"] + u_names['username'].tolist()
        h_user = st.selectbox("Usuário", h_user_opts)
        
    # Build Query
    hq = """
        SELECT 
            t.id, t.date, m.name as material_name, t.type, t.quantity, m.unit, t.cost, t.notes, u.username
        FROM inventory_transactions t
        JOIN materials m ON t.material_id = m.id
        LEFT JOIN users u ON t.user_id = u.id
        WHERE 1=1
    """
    hp = []
    
    if h_period == "Hoje":
        hq += " AND t.date LIKE ?"
        hp.append(dt_date.today().isoformat() + '%')
    elif h_period == "Últimos 7 dias":
        start = (dt_date.today() - timedelta(days=7)).isoformat()
        hq += " AND t.date >= ?"
        hp.append(start)
    elif h_period == "Últimos 30 dias":
        start = (dt_date.today() - timedelta(days=30)).isoformat()
        hq += " AND t.date >= ?"
        hp.append(start)
        
    if h_mat != "Todos":
        hq += " AND m.name = ?"
        hp.append(h_mat)
        
    if h_type != "Todos":
        hq += " AND t.type = ?"
        hp.append(h_type)
        
    if h_user != "Todos":
        hq += " AND u.username = ?"
        hp.append(h_user)
        
    hq += " ORDER BY t.date DESC LIMIT 200"
    
    hdf = pd.read_sql(hq, conn, params=hp)
    
    # Stats
    if not hdf.empty:
        total_entradas = hdf[hdf['type'] == 'ENTRADA']['cost'].sum()
        count_saidas = hdf[hdf['type'] == 'SAIDA']['quantity'].count()
        
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
