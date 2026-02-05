import streamlit as st
import pandas as pd
import database
import auth
from datetime import date, datetime
import services.product_service as product_service
import time
import json

st.set_page_config(page_title="Produção", layout="wide", page_icon="🏭")

# Check Auth
conn = database.get_connection()
if not auth.require_login(conn):
    st.stop()

# Updated key to 'Producao' matching auth.py
if not auth.check_page_access('Producao'):
    st.stop()

auth.render_custom_sidebar()

st.title("🏭 Produção")



# Helper Functions
def get_wip_items(stage=None):
    query = """
        SELECT w.*, p.name as product_name, p.image_paths, c.name as client_name, co.date_due, co.id as real_order_id
        FROM production_wip w
        JOIN products p ON w.product_id = p.id
        LEFT JOIN commission_orders co ON w.order_id = co.id
        LEFT JOIN clients c ON co.client_id = c.id
    """
    params = []
    if stage:
        query += " WHERE w.stage = ?"
        params.append(stage)
    
    # Sort by priority first, then date
    query += " ORDER BY w.priority DESC, w.start_date, co.date_due"
    return pd.read_sql(query, conn, params=params)

def move_stage(item_id, current_stage, next_stage, qty_move, total_qty, selected_variant_id=None, deduct_glaze=False):
    cursor = conn.cursor()
    try:
        # Fetch current record using pandas for safe name-based access
        df_curr = pd.read_sql("SELECT * FROM production_wip WHERE id=?", conn, params=(item_id,))
        if df_curr.empty: return
        curr = df_curr.iloc[0]
        
        # Load existing history
        try:
            history = json.loads(curr['stage_history']) if curr['stage_history'] else {}
        except:
            history = {}
        
        # Add next stage timestamp
        history[next_stage] = datetime.now().strftime("%d/%m %H:%M")
        history_json = json.dumps(history)

        # 1. Automatic Material Deduction
        # Clay (if moving TO Modelagem)
        m_deducted = curr['materials_deducted']
        if next_stage == 'Modelagem' and m_deducted == 0:
            product_service.deduct_production_materials_central(cursor, int(curr['product_id']), qty_move, filter_type='clay')
            m_deducted = 1
            
        # Glaze (if moving to Esmaltação)
        if current_stage == 'Biscoito' and next_stage == 'Esmaltação' and deduct_glaze and selected_variant_id:
            var_data = pd.read_sql("SELECT material_id, material_quantity FROM product_variants WHERE id=?", conn, params=(int(selected_variant_id),))
            if not var_data.empty:
                vd = var_data.iloc[0]
                if vd['material_id'] and vd['material_quantity'] > 0:
                    d_qty = vd['material_quantity'] * qty_move
                    cursor.execute("UPDATE materials SET stock_level = stock_level - ? WHERE id=?", (d_qty, int(vd['material_id'])))
                    cursor.execute("INSERT INTO inventory_transactions (date, material_id, quantity, type, notes) VALUES (?, ?, ?, 'SAIDA', ?)", 
                                  (date.today().isoformat(), int(vd['material_id']), d_qty, f"Esmaltação Produto {curr['product_id']}"))

        # Use provided variant or keep existing
        final_variant_id = selected_variant_id if selected_variant_id else curr['variant_id']

        # 2. Perform Move
        if qty_move == total_qty:
            cursor.execute("""
                UPDATE production_wip 
                SET stage=?, variant_id=?, materials_deducted=?, stage_history=? 
                WHERE id=?
            """, (next_stage, final_variant_id, int(m_deducted), history_json, item_id))
        else:
            # Update current (reduce qty)
            cursor.execute("UPDATE production_wip SET quantity = quantity - ? WHERE id=?", (qty_move, item_id))
            # Insert new item with updated history and stage
            cursor.execute("""
                INSERT INTO production_wip (product_id, variant_id, order_id, order_item_id, stage, quantity, start_date, materials_deducted, stage_history, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (int(curr['product_id']), final_variant_id, 
                  int(curr['order_id']) if pd.notna(curr['order_id']) else None, 
                  int(curr['order_item_id']) if pd.notna(curr['order_item_id']) else None, 
                  next_stage, qty_move, curr['start_date'], int(m_deducted), history_json, curr['notes']))
            
        conn.commit()
        st.success("Movimentação concluída!")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao mover: {e}")

def update_priority(item_id, increment):
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE production_wip SET priority = priority + ? WHERE id=?", (increment, item_id))
        conn.commit()
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao atualizar prioridade: {e}")

# --- TABS ---
tab_kanban, tab_new, tab_hist, tab_analysis = st.tabs(["Kanban", "Nova Produção", "Histórico", "📊 Análise de Perdas"])

# --- TAB 1: KANBAN ---
with tab_kanban:
    # Kanban Columns (Updated with Waiting Queue)
    stages = ["Fila de Espera", "Modelagem", "Secagem", "Biscoito", "Esmaltação", "Queima de Alta"]
    cols = st.columns(len(stages))
    
    for i, stage in enumerate(stages):
        with cols[i]:
            items = get_wip_items(stage)
            
            st.subheader(stage)
            st.caption(f"{len(items)} lotes")
            
            for _, item in items.iterrows():
                with st.container(border=True):
                    # Card Header
                    st.markdown(f"**{item['product_name']}**")
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
                    st.markdown(f"Prioridade: **{int(item['priority'])}**")
                    p_cols = st.columns(2)
                    if p_cols[0].button("Subir 🔼", key=f"pri_up_{item['id']}", use_container_width=True):
                        update_priority(item['id'], 1)
                    if p_cols[1].button("Baixar 🔽", key=f"pri_dn_{item['id']}", use_container_width=True):
                        update_priority(item['id'], -1)
                    
                    # --- Timeline ---
                    import json
                    try:
                        history = json.loads(item['stage_history']) if item.get('stage_history') else {}
                        if history:
                            with st.expander("🕒 Histórico", expanded=False):
                                for s, dt in history.items():
                                    st.caption(f"📍 **{s}**: {dt}")
                    except:
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
                                variants = pd.read_sql("SELECT id, variant_name FROM product_variants WHERE product_id=?", conn, params=(item['product_id'],))
                                
                                curr_idx = 0
                                if not pd.isna(item['variant_id']) and item['variant_id'] in variants['id'].values:
                                     curr_idx = list(variants['id'].values).index(item['variant_id'])
                                
                                sel_var_name = st.selectbox("Esmalte/Variação", variants['variant_name'], index=curr_idx, key=f"var_sel_{item['id']}")
                                if not variants.empty:
                                    selected_variant_id = variants[variants['variant_name'] == sel_var_name].iloc[0]['id']
                                
                                deduct_glaze = st.checkbox("Baixar estoque esmalte?", value=True, key=f"glz_{item['id']}")
                            
                            if st.button("Confirmar", key=f"go_{item['id']}", type="primary"):
                                move_stage(item['id'], stage, next_s, qty, int(item['quantity']), selected_variant_id, deduct_glaze)
                    
                    else: # LAST STAGE (Queima de Alta) -> Finish
                        with st.popover("✅ Concluir", use_container_width=True):
                            qty = st.number_input("Qtd Finalizada", 1, int(item['quantity']), int(item['quantity']), key=f"fin_{item['id']}")
                            
                            # Default increment stock to TRUE if it's Stock Production (no order)
                            default_inc = True if pd.isna(item['real_order_id']) else False
                            inc_stock = st.checkbox("Incrementar Estoque Produto?", value=default_inc, key=f"inc_{item['id']}")
                            
                            if st.button("Finalizar", key=f"end_{item['id']}", type="primary"):
                                cursor = conn.cursor()
                                try:
                                    # 0. Deduct Remaining Materials (everything else in recipe)
                                    # We skip Clay and the Glaze material used in existing variant if it was already deducted
                                    glaze_mat_id = None
                                    if item.get('variant_id'):
                                        glz_info = cursor.execute("SELECT material_id FROM product_variants WHERE id=?", (int(item['variant_id']),)).fetchone()
                                        if glz_info: glaze_mat_id = glz_info[0]
                                    
                                    product_service.deduct_production_materials_central(cursor, int(item['product_id']), qty, filter_type='others', exclude_ids=[glaze_mat_id] if glaze_mat_id else None)

                                    # 1. Update Order Item (if exists)
                                    if pd.notna(item['real_order_id']):
                                        cursor.execute("UPDATE commission_items SET quantity_produced = quantity_produced + ? WHERE id=?", (qty, item['order_item_id']))
                                    
                                    # 2. Increment Stock
                                    if inc_stock:
                                        cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (qty, item['product_id']))
                                        if item.get('variant_id'):
                                            cursor.execute("UPDATE product_variants SET stock_quantity = stock_quantity + ? WHERE id=?", (qty, item['variant_id']))
                                            
                                    # 3. History
                                    cursor.execute("""
                                        INSERT INTO production_history (timestamp, product_id, product_name, quantity, order_id, user_id, username)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """, (datetime.now().isoformat(), item['product_id'], item['product_name'], qty, item.get('real_order_id'), None, 'WIP'))
                                    
                                    # 4. Check Order Completion
                                    if pd.notna(item['real_order_id']):
                                        cursor.execute("""
                                            SELECT COUNT(*) FROM commission_items 
                                            WHERE order_id=? AND quantity_produced < (quantity - quantity_from_stock)
                                        """, (item['real_order_id'],))
                                        if cursor.fetchone()[0] == 0:
                                            cursor.execute("UPDATE commission_orders SET status='Concluída' WHERE id=?", (item['real_order_id'],))
                                    
                                    # 5. Remove WIP
                                    if qty == item['quantity']:
                                        cursor.execute("DELETE FROM production_wip WHERE id=?", (item['id'],))
                                    else:
                                        cursor.execute("UPDATE production_wip SET quantity = quantity - ? WHERE id=?", (qty, item['id']))
                                    
                                    conn.commit()
                                    st.success("Finalizado!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro: {e}")

                    # 3. Breakage (Loss) Logic - Only for items IN production (not in Fila de Espera)
                    if stage != 'Fila de Espera':
                        with st.popover("💔 Quebra", use_container_width=True):
                            st.caption("Registrar perda de peças")
                            qty_loss = st.number_input("Quantidade quebrada", 1, int(item['quantity']), 1, key=f"loss_qty_{item['id']}")
                            reason_loss = st.text_input("Motivo (opcional)", key=f"loss_reason_{item['id']}")
                            
                            if st.button("Confirmar Quebra", key=f"loss_btn_{item['id']}", type="secondary"):
                                cursor = conn.cursor()
                                try:
                                    # 1. Record Loss
                                    cursor.execute("""
                                        INSERT INTO production_losses (timestamp, product_id, variant_id, stage, quantity, reason, order_id)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """, (datetime.now().isoformat(), item['product_id'], item['variant_id'], stage, qty_loss, reason_loss, item.get('real_order_id')))
                                    
                                    # 2. Update Stage History
                                    try:
                                        history = json.loads(item['stage_history']) if item.get('stage_history') else {}
                                    except:
                                        history = {}
                                    
                                    break_key = f"Quebra ({stage})"
                                    history[break_key] = f"-{qty_loss} pcs | {datetime.now().strftime('%d/%m %H:%M')}"
                                    history_json = json.dumps(history)
                                    
                                    # 3. Update WIP
                                    if qty_loss == item['quantity']:
                                        cursor.execute("DELETE FROM production_wip WHERE id=?", (item['id'],))
                                    else:
                                        cursor.execute("UPDATE production_wip SET quantity = quantity - ?, stage_history=? WHERE id=?", (qty_loss, history_json, item['id']))
                                    
                                    # 4. Automated Replenishment (for Orders)
                                    if pd.notna(item['real_order_id']):
                                        # Create same-day replenishment card
                                        rep_history = {"Iniciado": datetime.now().strftime("%d/%m %H:%M"), "Fila de Espera (Reposição)": datetime.now().strftime("%d/%m %H:%M")}
                                        rep_history_json = json.dumps(rep_history)
                                        
                                        cursor.execute("""
                                            INSERT INTO production_wip (product_id, variant_id, order_id, order_item_id, stage, quantity, start_date, materials_deducted, stage_history, notes)
                                            VALUES (?, ?, ?, ?, 'Fila de Espera', ?, ?, 0, ?, ?)
                                        """, (int(item['product_id']), 
                                              int(item['variant_id']) if pd.notna(item['variant_id']) else None, 
                                              int(item['real_order_id']), 
                                              int(item['order_item_id']), 
                                              qty_loss, date.today().isoformat(), rep_history_json, f"Reposição após quebra em {stage}"))
                                        
                                        st.info(f"🔄 Um novo card de {qty_loss} peças foi criado em **Fila de Espera** para repor a quebra da encomenda.")

                                    conn.commit()
                                    st.warning(f"Registrado: {qty_loss} peças perdidas.")
                                    time.sleep(2) # Give user time to read the replacements notice
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao registrar quebra: {e}")

# --- TAB 2: NOVA PRODUÇÃO (ESTOQUE) ---
with tab_new:
    st.header("Iniciar Produção para Estoque")
    
    products = pd.read_sql("SELECT id, name FROM products ORDER BY name", conn)
    sel_prod_name = st.selectbox("Produto", products['name'])
    
    if sel_prod_name:
        pid = products[products['name'] == sel_prod_name].iloc[0]['id']
        
        # Variants
        variants = pd.read_sql("SELECT id, variant_name FROM product_variants WHERE product_id=?", conn, params=(pid,))
        vid = None
        if not variants.empty:
            vname = st.selectbox("Variação (Opcional)", ["Padrão"] + variants['variant_name'].tolist())
            if vname != "Padrão":
                vid = variants[variants['variant_name'] == vname].iloc[0]['id']
        
        qty_new = st.number_input("Quantidade", 1, 1000, 1)
        start_dt = st.date_input("Data Início", value=date.today())
        obs = st.text_area("Observações")
        
        # Phased deduction is now automatic, no checkbox needed
        
        if st.button("🚀 Iniciar Produção", type="primary"):
            cursor = conn.cursor()
            try:
                # Insert WIP
                # stage default Modelagem
                history = {"Iniciado": datetime.now().strftime("%d/%m %H:%M"), "Fila de Espera": datetime.now().strftime("%d/%m %H:%M")}
                history_json = json.dumps(history)
                
                cursor.execute("""
                    INSERT INTO production_wip (product_id, variant_id, order_id, order_item_id, stage, quantity, start_date, materials_deducted, stage_history, notes)
                    VALUES (?, ?, NULL, NULL, 'Fila de Espera', ?, ?, 0, ?, ?)
                """, (int(pid), int(vid) if vid else None, int(qty_new), start_dt.isoformat(), history_json, obs))
                
                conn.commit()
                st.success("Produção iniciada! Atualizando...")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

# --- TAB 3: HISTÓRICO ---
with tab_hist:
    sub_prod, sub_loss = st.tabs(["✅ Produção Concluída", "💔 Quebras/Perdas"])
    
    with sub_prod:
        st.subheader("Itens Finalizados")
        # Simple table
        hist = pd.read_sql("""
            SELECT ph.timestamp as Data, ph.product_name as Produto, ph.quantity as Qtd, ph.username as Usuário, ph.order_id as Encomenda
            FROM production_history ph
            ORDER BY ph.timestamp DESC
            LIMIT 100
        """, conn)
        st.dataframe(hist, use_container_width=True, hide_index=True)
        
    with sub_loss:
        st.subheader("Registro de Perdas")
        losses = pd.read_sql("""
            SELECT l.timestamp as Data, p.name as Produto, l.stage as Etapa, l.quantity as Qtd, l.reason as Motivo, l.order_id as Encomenda
            FROM production_losses l
            JOIN products p ON l.product_id = p.id
            ORDER BY l.timestamp DESC
        """, conn)
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
        all_prods = pd.read_sql("SELECT id, name, category FROM products ORDER BY name", conn)
        cats = sorted(all_prods['category'].unique().tolist()) if not all_prods.empty else []
        
        with f2:
            sel_cats = st.multiselect("Categorias", options=cats)
        with f3:
            # Filter product options based on categories if selected
            prod_opts_df = all_prods[all_prods['category'].isin(sel_cats)] if sel_cats else all_prods
            sel_prods = st.multiselect("Produtos", options=prod_opts_df['name'].tolist())
            
    # --- DATA LOADING & FILTERING ---
    # 1. Load All Relevant Data
    losses_df = pd.read_sql("""
        SELECT l.stage, l.quantity, p.name as product_name, p.category, l.timestamp, l.reason
        FROM production_losses l
        JOIN products p ON l.product_id = p.id
    """, conn)
    
    finished_df = pd.read_sql("""
        SELECT ph.timestamp, ph.product_name, ph.quantity, p.category
        FROM production_history ph
        JOIN products p ON ph.product_id = p.id
    """, conn)
    
    # 2. Apply Filters to Dataframes
    def apply_filters(df):
        if df.empty: return df
        # Date filter
        df['dt'] = pd.to_datetime(df['timestamp']).dt.date
        df = df[(df['dt'] >= date_range[0]) & (df['dt'] <= date_range[1])]
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
