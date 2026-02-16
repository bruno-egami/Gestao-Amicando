import streamlit as st
import pandas as pd
import database
import auth
import services.production_service as production_service
import services.product_service as product_service
import admin_utils
from datetime import date, datetime
import json
import os
from utils.logging_config import get_logger

logger = get_logger(__name__)

st.set_page_config(page_title="Produção", layout="wide", page_icon="🏭")

# Apply Global Styles
import utils.styles as styles
styles.apply_custom_style()

# Check Auth
with database.db_session() as conn:
    if not auth.require_login(conn):
        st.stop()

    # Updated key to 'Producao' matching auth.py
    if not auth.check_page_access('Producao'):
        st.stop()

    auth.render_custom_sidebar()

    st.title("🏭 Produção")

    # --- TABS ---
    tab_kanban, tab_new, tab_hist, tab_analysis = st.tabs(["Kanban", "Nova Produção", "Histórico", "📊 Análise de Perdas"])

    # --- TAB 1: KANBAN ---
    with tab_kanban:
        stages = ["Fila de Espera", "Modelagem", "Secagem", "Biscoito", "Esmaltação", "Queima de Alta"]
    
        # Load ALL items once for global filtering
        all_items = production_service.get_wip_items(conn)
    
        # --- FILTERS SECTION ---
        with st.expander("🔍 Filtros e Busca", expanded=False):
            f_col1, f_col2, f_col3 = st.columns([2, 2, 3])
        
            with f_col1:
                clients_in_wip = sorted([c for c in all_items['client_name'].dropna().unique()])
                has_stock_items = all_items['client_name'].isna().any()
                client_opts = (["Estoque / Loja"] if has_stock_items else []) + clients_in_wip
                sel_clients = st.multiselect("Filtrar por Cliente", options=client_opts)
            
            with f_col2:
                cats_in_wip = sorted([k for k in all_items['product_category'].dropna().unique()])
                sel_cats_kanban = st.multiselect("Filtrar por Categoria", options=cats_in_wip)
            
            with f_col3:
                search_query = st.text_input("Buscar Produto", placeholder="Nome do produto...")

        # Apply Filters
        filtered_items = all_items.copy()
        if sel_clients:
            # If "Estoque / Loja" is selected, we include rows where client_name is NA
            include_stock = "Estoque / Loja" in sel_clients
            actual_clients = [c for c in sel_clients if c != "Estoque / Loja"]
        
            if include_stock:
                filtered_items = filtered_items[filtered_items['client_name'].isin(actual_clients) | filtered_items['client_name'].isna()]
            else:
                filtered_items = filtered_items[filtered_items['client_name'].isin(actual_clients)]
        if sel_cats_kanban:
            filtered_items = filtered_items[filtered_items['product_category'].isin(sel_cats_kanban)]
        if search_query:
            filtered_items = filtered_items[filtered_items['product_name'].str.contains(search_query, case=False, na=False)]

        cols = st.columns(len(stages))
    
        for i, stage in enumerate(stages):
            with cols[i]:
                # Get items for this stage from the filtered list
                items = filtered_items[filtered_items['stage'] == stage]
            
                st.subheader(stage)
                st.caption(f"{len(items)} lotes")
            
                for _, item in items.iterrows():
                    with st.container(border=True):
                        # Card Header
                        title_prefix = ""
                        days_msg = ""
                        # Delayed Indicator (started > 7 days ago)
                        try:
                            started_dt = pd.to_datetime(item['start_date']).date()
                            days_in = (date.today() - started_dt).days
                            if days_in > 7:
                                title_prefix = "⚠️ "
                                days_msg = f" (:red[{days_in} dias])"
                        except Exception as e:
                            logger.warning(f"Error calculating days in stage for item {item.get('id')}: {e}")

                        st.markdown(f"**{title_prefix}{item['product_name']}**{days_msg}")
                        st.markdown(f"📦 {item['quantity']} un")
                    
                        # Context Badge (Order vs Stock)
                        if pd.notna(item['client_name']):
                            st.caption(f"👤 {item['client_name']} (Enc #{int(item['real_order_id'])})")
                        
                            # Deadline display
                            if pd.notna(item['date_due']):
                                d_due = pd.to_datetime(item['date_due']).date()
                                if d_due < date.today():
                                    st.markdown(f"📅 **Prazo:** :red[{d_due.strftime('%d/%m/%Y')}]")
                                else:
                                    st.markdown(f"📅 **Prazo:** {d_due.strftime('%d/%m/%Y')}")
                        else:
                            st.caption("🏢 Estoque / Loja")
                    
                        if item.get('notes'):
                            st.info(item['notes'])
                    
                        # --- Priority (Every stage) ---
                        p_cols = st.columns(2)
                        if p_cols[0].button("Subir 🔼", key=f"pri_up_{item['id']}", use_container_width=True):
                            conn_write = database.get_connection()
                            cursor_write = conn_write.cursor()
                            try:
                                cursor_write.execute("BEGIN TRANSACTION")
                                production_service.update_priority(cursor_write, item['id'], 1)
                                conn_write.commit()
                                st.rerun()
                            except Exception as e:
                                conn_write.rollback()
                                st.error(f"Erro: {e}")
                            finally:
                                cursor_write.close()
                                conn_write.close()
                    
                        if p_cols[1].button("Baixar 🔽", key=f"pri_dn_{item['id']}", use_container_width=True):
                            conn_write = database.get_connection()
                            cursor_write = conn_write.cursor()
                            try:
                                cursor_write.execute("BEGIN TRANSACTION")
                                production_service.update_priority(cursor_write, item['id'], -1)
                                conn_write.commit()
                                st.rerun()
                            except Exception as e:
                                conn_write.rollback()
                                st.error(f"Erro: {e}")
                            finally:
                                cursor_write.close()
                                conn_write.close()
                    
                        # --- Timeline ---
                        import json
                        try:
                            history = json.loads(item['stage_history']) if item.get('stage_history') else {}
                            if history:
                                with st.expander("🕒 Histórico", expanded=False):
                                    for s, dt in history.items():
                                        st.caption(f"📍 **{s}**: {dt}")
                        except Exception:
                            pass
                        
                        # --- Actions ---
    
                        # 2. Move Logic
                        if i < len(stages) - 1: # Not last stage
                            next_s = stages[i+1]
                        
                            # Custom Popover label
                            pop_label = f"➡️ {next_s}"
                        
                            with st.popover(pop_label, use_container_width=True):
                                qty = st.number_input("Qtd a avançar", 1, int(item['quantity']), int(item['quantity']), key=f"mv_{item['id']}")
                            
                                # --- Esmaltação Logic (Triggered when moving FROM Esmaltação? No, triggered when moving TO Esmaltação usually? 
                                # Logic revision: User said 'When moving from Biscoito to Esmaltação'.
                                # So if CURRENT stage is Biscoito and NEXT is Esmaltacao.
                            
                                selected_variant_id = item['variant_id']
                                deduct_glaze = False
                            
                                if stage == 'Biscoito' and next_s == 'Esmaltação':
                                    st.divider()
                                    st.markdown("🎨 **Esmaltação**")
                                
                                    # Use product_service
                                    variants = product_service.get_product_variants(conn, item['product_id'])
                                
                                    curr_idx = 0
                                    if not pd.isna(item['variant_id']) and not variants.empty and item['variant_id'] in variants['id'].values:
                                         curr_idx = list(variants['id'].values).index(item['variant_id'])
                                
                                    sel_var_name = st.selectbox("Esmalte/Variação", ["Padrão"] + variants['variant_name'].tolist() if not variants.empty else ["Padrão"], index=curr_idx if not variants.empty else 0, key=f"var_sel_{item['id']}")
                                
                                    if not variants.empty and sel_var_name != "Padrão":
                                        selected_variant_id = variants[variants['variant_name'] == sel_var_name].iloc[0]['id']
                                
                                    deduct_glaze = st.checkbox("Baixar estoque esmalte?", value=True, key=f"glz_{item['id']}")
                            
                                if st.button("Confirmar", key=f"go_{item['id']}", type="primary"):
                                    conn_write = database.get_connection()
                                    cursor_write = conn_write.cursor()
                                    try:
                                        cursor_write.execute("BEGIN TRANSACTION")
                                        # Get current user
                                        user = auth.get_current_user()
                                        u_id = user['id'] if user else None
                                        u_name = user['username'] if user else 'Unknown'
                                    
                                        production_service.move_stage(cursor_write, conn_write, item['id'], stage, next_s, qty, int(item['quantity']), selected_variant_id, deduct_glaze, user_id=u_id, username=u_name)
                                        conn_write.commit()
                                        st.toast(f"Movido para {next_s}!", icon="✅")
                                        st.rerun()
                                    except Exception as e:
                                        conn_write.rollback()
                                        st.error(f"Erro ao mover: {e}")
                                    finally:
                                        cursor_write.close()
                                        conn_write.close()
                    
                        else: # LAST STAGE (Queima de Alta) -> Finish
                            with st.popover("✅ Concluir", use_container_width=True):
                                qty = st.number_input("Qtd Finalizada", 1, int(item['quantity']), int(item['quantity']), key=f"fin_{item['id']}")
                            
                                # Default increment stock to TRUE if it's Stock Production (no order)
                                default_inc = True if pd.isna(item['real_order_id']) else False
                                inc_stock = st.checkbox("Incrementar Estoque Produto?", value=default_inc, key=f"inc_{item['id']}")
                            
                                if st.button("Finalizar", key=f"end_{item['id']}", type="primary"):
                                    conn_write = database.get_connection()
                                    cursor_write = conn_write.cursor()
                                    try:
                                        cursor_write.execute("BEGIN TRANSACTION")
                                        # Get current user
                                        user = auth.get_current_user()
                                        u_id = user['id'] if user else None
                                        u_name = user['username'] if user else 'Unknown'

                                        production_service.finalize_production(cursor_write, item, qty, inc_stock, user_id=u_id, username=u_name)
                                        conn_write.commit()
                                        admin_utils.show_feedback_dialog(f"Produção de {item['product_name']} finalizada!", level="success")
                                    except Exception as e:
                                        conn_write.rollback()
                                        st.error(f"Erro: {e}")
                                    finally:
                                        cursor_write.close()
                                        conn_write.close()

                        # 3. Breakage (Loss) Logic - Only for items IN production (not in Fila de Espera)
                        if stage != 'Fila de Espera':
                            with st.popover("💔 Quebra", use_container_width=True):
                                st.caption("Registrar perda de peças")
                                qty_loss = st.number_input("Quantidade quebrada", 1, int(item['quantity']), 1, key=f"loss_qty_{item['id']}")
                                reason_loss = st.text_input("Motivo (opcional)", key=f"loss_reason_{item['id']}")
                            
                                if st.button("Confirmar Quebra", key=f"loss_btn_{item['id']}", type="secondary"):
                                    conn_write = database.get_connection()
                                    cursor_write = conn_write.cursor()
                                    try:
                                        cursor_write.execute("BEGIN TRANSACTION")
                                        replenished = production_service.register_loss(cursor_write, item, stage, qty_loss, reason_loss)
                                        conn_write.commit()
                                        if replenished:
                                            st.info(f"🔄 Um novo card de {qty_loss} peças foi criado em **Fila de Espera** para repor a quebra.")
                                        admin_utils.show_feedback_dialog(f"Registrado: {qty_loss} peças perdidas em {stage}.", level="warning")
                                    except Exception as e:
                                        conn_write.rollback()
                                        admin_utils.show_feedback_dialog(f"Erro ao registrar quebra: {e}", level="error")
                                    finally:
                                        cursor_write.close()
                                        conn_write.close()

    # --- TAB 2: NOVA PRODUÇÃO (ESTOQUE) ---
    with tab_new:
        st.header("Iniciar Produção para Estoque")

        # --- DIALOG FOR PRODUCTION START ---
        @st.dialog("🚀 Iniciar Produção")
        def show_production_dialog(product_row):
            # Use a fresh connection to avoid "closed database" issues in dialogs
            ctx_conn = database.get_connection()
            try:
                st.markdown(f"### {product_row['name']}")
            
                # Image in dialog
                if product_row['thumb_path'] and os.path.exists(product_row['thumb_path']):
                    st.image(product_row['thumb_path'], width=150)
                
                pid = product_row['id']
            
                # Variants Logic using clean connection
                variants = product_service.get_product_variants(ctx_conn, pid)
                vid = None
            
                # Form
                with st.form("prod_start_form"):
                    c1, c2 = st.columns(2)
                    qty_new = c1.number_input("Quantidade", 1, 1000, 1)
                    start_dt = c2.date_input("Data Início", value=date.today())
                
                    if not variants.empty:
                        vname = st.selectbox("Variação (Opcional)", ["Padrão"] + variants['variant_name'].tolist())
                        if vname != "Padrão":
                            vid = variants[variants['variant_name'] == vname].iloc[0]['id']
                
                    obs = st.text_area("Observações")
                
                    if st.form_submit_button("Confirmar Produção", type="primary"):
                        conn_write = database.get_connection()
                        cursor_write = conn_write.cursor()
                        try:
                            cursor_write.execute("BEGIN TRANSACTION")
                            production_service.start_production(cursor_write, pid, qty_new, start_dt.isoformat(), obs, vid)
                            conn_write.commit()
                            st.toast(f"Produção iniciada: {qty_new} un de {product_row['name']}", icon="✅")
                            st.rerun()
                        except Exception as e:
                            conn_write.rollback()
                            st.error(f"Erro: {e}")
                        finally:
                            cursor_write.close()
                            conn_write.close()
            finally:
                 ctx_conn.close()

        # --- CATALOG FILTERING ---
        # 1. Filters
        filter_col1, filter_col2 = st.columns([1, 2])
    
        # Categories
        cats_list = product_service.get_categories(conn)
        sel_cat = filter_col1.selectbox("Filtrar por Categoria", ["Todas"] + sorted(cats_list), key="new_prod_cat")
    
        # Search
        search_prod = filter_col2.text_input("🔍 Buscar Produto", placeholder="Nome do produto...", key="new_prod_search")
    
        # 2. Get Data
        all_prods = product_service.get_all_products(conn)
    
        # 3. Apply Filters
        if not all_prods.empty:
            filtered_prods = all_prods.copy()
        
            if sel_cat != "Todas":
                filtered_prods = filtered_prods[filtered_prods['category'] == sel_cat]
            
            if search_prod:
                filtered_prods = filtered_prods[filtered_prods['name'].str.contains(search_prod, case=False)]
            
            filtered_prods = filtered_prods.sort_values('name')
        else:
            filtered_prods = pd.DataFrame()

        # --- GRID DISPLAY ---
        if not filtered_prods.empty:
            st.divider()
            st.caption(f"{len(filtered_prods)} produtos encontrados.")
        
            # Determine Grid Columns (e.g. 4 columns)
            cols_per_row = 4
        
            # Iterate in chunks
            for i in range(0, len(filtered_prods), cols_per_row):
                cols = st.columns(cols_per_row)
                batch = filtered_prods.iloc[i:i+cols_per_row]
            
                for idx, (_, row) in enumerate(batch.iterrows()):
                    with cols[idx]:
                        with st.container(border=True):
                            # Image
                            if row['thumb_path'] and os.path.exists(row['thumb_path']):
                                st.image(row['thumb_path'], use_container_width=True)
                            else:
                                # Placeholder or empty space
                                st.markdown("📷 *Sem imagem*")
                            
                            st.markdown(f"**{row['name']}**")
                            st.caption(f"{row['category']}")
                        
                            if st.button("Produzir 🏭", key=f"start_prod_{row['id']}", use_container_width=True):
                                show_production_dialog(row)
        else:
            st.info("Nenhum produto encontrado com os filtros selecionados.")

    # --- TAB 3: HISTÓRICO ---
    with tab_hist:
        sub_prod, sub_loss = st.tabs(["✅ Produção Concluída", "💔 Quebras/Perdas"])
    
        with sub_prod:
            st.subheader("Itens Finalizados")
            # Use service
            hist = production_service.get_recent_finished_items(conn, limit=100)
            st.dataframe(hist, use_container_width=True, hide_index=True)
        
        with sub_loss:
            st.subheader("Registro de Perdas")
            # Use service
            losses = production_service.get_recent_loss_items(conn, limit=100)
            if not losses.empty:
                st.dataframe(losses, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma quebra registrada até o momento.")

    # --- TAB 4: ANÁLISE DE PERDAS ---
    with tab_analysis:
        st.header("📊 Análise de Rendimento e Perdas")
    
        # --- FILTERS SECTION ---
        with st.expander("🔍 Filtros de Análise", expanded=True):
            f1, f2, f3 = st.columns(3)
            with f1:
                date_range = st.date_input("Período", value=[date(date.today().year, date.today().month, 1), date.today()])
        
            # Load options for filters
            all_prods = product_service.get_all_products(conn)
            cats = sorted(all_prods['category'].dropna().unique().tolist()) if not all_prods.empty else []
        
            with f2:
                sel_cats = st.multiselect("Categorias", options=cats)
            with f3:
                # Filter product options based on categories if selected
                prod_opts_df = all_prods[all_prods['category'].isin(sel_cats)] if sel_cats and not all_prods.empty else all_prods
                sel_prods = st.multiselect("Produtos", options=prod_opts_df['name'].tolist() if not prod_opts_df.empty else [])
            
        # --- DATA LOADING & FILTERING ---
        if len(date_range) == 2:
            start_d, end_d = date_range
        else:
            start_d, end_d = date.today(), date.today()

        # Use service to get raw data
        losses_df, finished_df = production_service.get_yield_analysis_data(conn, start_d, end_d)
    
        # 2. Apply Filters to Dataframes
        def apply_filters(df):
            if df.empty: return df
            # Date filter is already applied by service query optimization, but redundant check is fine
            # Category filter
            if sel_cats:
                df = df[df['category'].isin(sel_cats)]
            # Product filter
            if sel_prods:
                df = df[df['product_name'].isin(sel_prods)]
            return df

        l_filtered = apply_filters(losses_df)
        f_filtered = apply_filters(finished_df)
    
        # 3. Calculate Metrics
        total_finished = f_filtered['quantity'].sum() if not f_filtered.empty else 0
        total_broken = l_filtered['quantity'].sum() if not l_filtered.empty else 0
        total_started = total_finished + total_broken
    
        # 4. Display Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("🏺 Total Produzido", f"{int(total_finished)} un")
        m2.metric("💔 Total Perdas", f"{int(total_broken)} un", delta=f"{int(total_broken)}" if total_broken > 0 else None, delta_color="inverse")
    
        yield_rate = (total_finished / total_started * 100) if total_started > 0 else 100
        m3.metric("📈 Rendimento (Yield)", f"{yield_rate:.1f}%")
        st.divider()
    
        # 5. Visualizations
        if not l_filtered.empty or not f_filtered.empty:
            c1, c2 = st.columns(2)
        
            with c1:
                st.subheader("📍 Perdas por Etapa")
                if not l_filtered.empty:
                    stage_groups = l_filtered.groupby('stage')['quantity'].sum()
                    stage_order = ["Fila de Espera", "Modelagem", "Secagem", "Biscoito", "Esmaltação", "Queima de Alta"]
                    stage_groups = stage_groups.reindex(stage_order).fillna(0)
                    st.bar_chart(stage_groups, color="#FF4B4B")
                else:
                    st.info("Nenhuma perda no filtro selecionado.")
            
            with c2:
                st.subheader("🏺 Perdas por Produto")
                if not l_filtered.empty:
                    prod_groups = l_filtered.groupby('product_name')['quantity'].sum().sort_values(ascending=False).head(10)
                    st.bar_chart(prod_groups, color="#FF4B4B")
                else:
                    st.info("Nenhuma perda no filtro selecionado.")
            
            st.divider()
            st.subheader("📉 Distribuição de Motivos")
            if not l_filtered.empty:
                reasons = l_filtered[l_filtered['reason'].notna() & (l_filtered['reason'] != '')]
                if not reasons.empty:
                    reason_summary = reasons.groupby('reason')['quantity'].sum().reset_index().sort_values('quantity', ascending=False)
                    st.dataframe(reason_summary, use_container_width=True, hide_index=True, column_config={"reason": "Motivo", "quantity": "Qtd Total"})
                else:
                    st.caption("Nenhum motivo específico registrado para este filtro.")
            else:
                st.caption("Sem dados de perdas para este filtro.")
        else:
            st.info("Nenhum dado encontrado para os filtros selecionados.")

