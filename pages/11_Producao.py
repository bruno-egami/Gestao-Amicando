import streamlit as st
import pandas as pd
import database
import auth
from datetime import date, datetime

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
    
    # Sort by date (handle nulls)
    query += " ORDER BY w.start_date, co.date_due"
    return pd.read_sql(query, conn, params=params)

def deduct_production_materials(cursor, product_id, quantity, filter_type=None, exclude_ids=None):
    """
    Deducts materials from stock based on product recipe.
    filter_type: 'clay' (only materials with Massa/Argila in name), 
                 'others' (everything except clay and material_ids in exclude_ids)
    """
    query = "SELECT m.id, m.name, r.quantity as qty_per_unit FROM product_recipes r JOIN materials m ON r.material_id = m.id WHERE r.product_id=?"
    recipes = pd.read_sql(query, conn, params=(product_id,))
    
    logs = []
    for _, r in recipes.iterrows():
        is_clay = any(keyword in r['name'].lower() for keyword in ['massa', 'argila'])
        
        should_deduct = False
        if filter_type == 'clay' and is_clay:
            should_deduct = True
        elif filter_type == 'others' and not is_clay:
            if not exclude_ids or r['id'] not in exclude_ids:
                should_deduct = True
        elif filter_type is None:
            should_deduct = True
            
        if should_deduct:
            d_qty = r['qty_per_unit'] * quantity
            cursor.execute("UPDATE materials SET stock_level = stock_level - ? WHERE id=?", (d_qty, r['id']))
            cursor.execute("INSERT INTO inventory_transactions (date, material_id, quantity, type, notes) VALUES (?, ?, ?, 'SAIDA', ?)", 
                          (date.today().isoformat(), r['id'], d_qty, f"Produção ID {product_id}"))
            logs.append(f"Deduzido {d_qty} de {r['name']}")
    return logs

def move_stage(item_id, current_stage, next_stage, qty_move, total_qty, selected_variant_id=None, deduct_glaze=False):
    cursor = conn.cursor()
    try:
        # Fetch current record using pandas for safe name-based access
        df_curr = pd.read_sql("SELECT * FROM production_wip WHERE id=?", conn, params=(item_id,))
        if df_curr.empty: return
        curr = df_curr.iloc[0]
        
        # Load existing history
        import json
        try:
            history = json.loads(curr['stage_history']) if curr['stage_history'] else {}
        except:
            history = {}
        
        # Add next stage timestamp
        history[next_stage] = datetime.now().strftime("%d/%m %H:%M")
        history_json = json.dumps(history)

        # 1. Automatic Material Deduction
        # Clay (if moving from Modelagem)
        m_deducted = curr['materials_deducted']
        if current_stage == 'Modelagem' and m_deducted == 0:
            deduct_production_materials(cursor, int(curr['product_id']), qty_move, filter_type='clay')
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

# --- TABS ---
tab_kanban, tab_new, tab_hist = st.tabs(["Kanban", "Nova Produção", "Histórico"])

# --- TAB 1: KANBAN ---
with tab_kanban:
    # Kanban Columns (Updated with Queima de Alta)
    stages = ["Modelagem", "Secagem", "Biscoito", "Esmaltação", "Queima de Alta"]
    cols = st.columns(len(stages))
    
    for i, stage in enumerate(stages):
        with cols[i]:
            st.subheader(stage)
            items = get_wip_items(stage)
            st.caption(f"{len(items)} lotes")
            
            for _, item in items.iterrows():
                with st.container(border=True):
                    # Card Header
                    st.markdown(f"**{item['product_name']}**")
                    st.markdown(f"📦 {item['quantity']} un")
                    
                    # Context Badge (Order vs Stock)
                    if pd.notna(item['client_name']):
                        st.caption(f"👤 {item['client_name']} (Enc #{int(item['real_order_id'])})")
                    else:
                        st.caption("🏢 Estoque / Loja")
                    
                    if item.get('notes'):
                        st.info(item['notes'])
                    
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
                                    
                                    deduct_production_materials(cursor, item['product_id'], qty, filter_type='others', exclude_ids=[glaze_mat_id] if glaze_mat_id else None)

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
                import json
                history = {"Iniciado": datetime.now().strftime("%d/%m %H:%M"), "Modelagem": datetime.now().strftime("%d/%m %H:%M")}
                history_json = json.dumps(history)
                
                cursor.execute("""
                    INSERT INTO production_wip (product_id, variant_id, order_id, order_item_id, stage, quantity, start_date, materials_deducted, stage_history, notes)
                    VALUES (?, ?, NULL, NULL, 'Modelagem', ?, ?, 0, ?, ?)
                """, (int(pid), int(vid) if vid else None, int(qty_new), start_dt.isoformat(), history_json, obs))
                
                conn.commit()
                st.success("Produção iniciada! Atualizando...")
                import time
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

# --- TAB 3: HISTÓRICO ---
with tab_hist:
    st.header("Histórico de Produção")
    
    # Simple table
    hist = pd.read_sql("""
        SELECT ph.timestamp, ph.product_name, ph.quantity, ph.username, ph.order_id
        FROM production_history ph
        ORDER BY ph.timestamp DESC
        LIMIT 100
    """, conn)
    
    st.dataframe(hist, use_container_width=True)
