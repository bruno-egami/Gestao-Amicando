import streamlit as st
import pandas as pd
import database
from datetime import date, datetime, timedelta
import admin_utils
import services.product_service as product_service
import audit
import reports
import time
import auth
import uuid
import os
import json

st.set_page_config(page_title="Encomendas", page_icon="📦")

admin_utils.render_sidebar_logo()
conn = database.get_connection()

if not auth.require_login(conn):
    st.stop()

if not auth.check_page_access("Encomendas"):
    st.stop()

auth.render_custom_sidebar()
st.title("📦 Gestão de Encomendas")
cursor = conn.cursor()

# --- FILTERS & MANAGEMENT ---
# --- Dialogs ---
@st.dialog("Entrega Realizada")
def show_delivery_success(pdf_data, pdf_name):
    st.balloons()
    st.success("✅ Entrega realizada e registrada com sucesso!")
    st.download_button("📄 BAIXAR RECIBO (FINAL)", data=pdf_data, file_name=pdf_name, mime="application/pdf", type="primary")

if 'delivered_pdf' in st.session_state:
    d_pdf = st.session_state['delivered_pdf']
    d_name = st.session_state.get('delivered_name', 'recibo.pdf')
    
    # Show Dialog
    show_delivery_success(d_pdf, d_name)
    
    # Clear state immediately so it doesn't persist on reload/nav
    del st.session_state['delivered_pdf']
    if 'delivered_name' in st.session_state:
        del st.session_state['delivered_name']

st.subheader("Gerenciar Pedidos")
    
# Logic to Delete Order (and restore stock)
def delete_order(oid):
    # Use discrete connection for deletion
    conn_del = database.get_connection()
    cursor_del = conn_del.cursor()
    try:
        # 1. Get reserved items to restore
        items = pd.read_sql("SELECT product_id, quantity_from_stock, variant_id FROM commission_items WHERE order_id=?", conn_del, params=(oid,))
        
        def clean_bin(val):
            if isinstance(val, bytes): return int.from_bytes(val, 'little')
            return val

        items['quantity_from_stock'] = items['quantity_from_stock'].apply(clean_bin)
        items['product_id'] = items['product_id'].apply(clean_bin)
        
        # Get order data for audit
        order_data = pd.read_sql("SELECT client_id, total_price, status FROM commission_orders WHERE id=?", conn_del, params=(oid,))
        old_data = order_data.iloc[0].to_dict() if not order_data.empty else {}
        
        cursor_del.execute("BEGIN TRANSACTION")
        for _, it in items.iterrows():
            qty_rest = int(it['quantity_from_stock'])
            if qty_rest > 0:
                if pd.notna(it['variant_id']) and it['variant_id'] > 0:
                     cursor_del.execute("UPDATE product_variants SET stock_quantity = stock_quantity + ? WHERE id=?", 
                                  (qty_rest, int(it['variant_id'])))
                else:
                     cursor_del.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                                  (qty_rest, int(it['product_id'])))
        
        cursor_del.execute("DELETE FROM commission_items WHERE order_id=?", (oid,))
        cursor_del.execute("DELETE FROM commission_orders WHERE id=?", (oid,))
        conn_del.commit()
        
        # Audit log (needs a connection, using global for simplicity as it's a read-then-write but better to use del or its own)
        audit.log_action(conn_del, 'DELETE', 'commission_orders', oid, old_data, None)
        return True
    except Exception as e:
        conn_del.rollback()
        admin_utils.show_feedback_dialog(f"Erro ao excluir encomenda: {e}", level="error")
        return False
    finally:
        cursor_del.close()
        conn_del.close()

# --- Filters ---
kf1, kf2, kf3 = st.columns([1.5, 1.5, 2])
with kf1:
    # Status Filter
    all_statuses = ["Pendente", "Em Produção", "Concluída", "Entregue"]
    sel_status = st.multiselect("Status", all_statuses, default=["Pendente", "Em Produção", "Concluída"])

with kf2:
    # Client Filter
    cli_opts = ["Todos"] + pd.read_sql("SELECT name FROM clients ORDER BY name", conn)['name'].tolist()
    sel_client = st.selectbox("Cliente", cli_opts)

with kf3:
    # Date Range Filter (Due Date)
    d_start = st.date_input("De", value=None, format="DD/MM/YYYY")
    d_end = st.date_input("Até", value=None, format="DD/MM/YYYY")

# Fetch Orders
orders = pd.read_sql("""
    SELECT o.id, c.name as client, o.date_due, o.status, o.total_price, o.notes, o.client_id,
           o.manual_discount, o.deposit_amount, o.date_created, o.image_paths
    FROM commission_orders o
    JOIN clients c ON o.client_id = c.id
    ORDER BY o.date_due ASC
""", conn)

# Apply Filters
if not orders.empty:
    # Status
    if sel_status:
        orders = orders[orders['status'].isin(sel_status)]
    
    # Client
    if sel_client != "Todos":
        orders = orders[orders['client'] == sel_client]
        
    # Date Range
    if d_start:
        orders = orders[pd.to_datetime(orders['date_due']).dt.date >= d_start]
    if d_end:
        orders = orders[pd.to_datetime(orders['date_due']).dt.date <= d_end]

# Search filter (Legacy Text Search)
search_orders = st.text_input("🔍 Buscar (Texto)", placeholder="ID, Notas...", key="search_orders")
if search_orders and not orders.empty:
    mask = orders.apply(lambda row: search_orders.lower() in str(row).lower(), axis=1)
    orders = orders[mask]
    
st.caption(f"{len(orders)} pedido(s)")

if orders.empty:
    st.info("Nenhuma encomenda encontrada.")
else:
    for _, order in orders.iterrows():
        # Format ID for Display
        created_dt = pd.to_datetime(order['date_created']) if order['date_created'] else datetime.now()
        fmt_id = f"ENC-{created_dt.strftime('%y%m%d')}-{order['id']}"
        
        # Determine if expanded
        is_expanded = (st.session_state.get('expanded_order_id') == order['id'])
        
        # Status Color Logic
        today = date.today()
        due_date = pd.to_datetime(order['date_due']).date()
        is_overdue = due_date < today and order['status'] not in ['Entregue', 'Concluída']
        
        status_color = "grey"
        if order['status'] == 'Concluída':
            status_color = "green"
        elif order['status'] == 'Em Produção':
            status_color = "blue"
        elif order['status'] == 'Pendente':
            status_color = "orange"
            
        # Overwrite if overdue
        if is_overdue:
            status_color = "red"
            
        status_text = f":{status_color}[{order['status']}]"
        
        with st.expander(f"📦 {fmt_id} - {order['client']} (Prazo: {due_date.strftime('%d/%m/%Y')}) - {status_text}", expanded=is_expanded):
            
            # Fetch Items
            # Fetch Items
            items = pd.read_sql("""
                SELECT ci.id, p.name, ci.quantity, ci.quantity_from_stock, ci.quantity_produced, ci.product_id, ci.unit_price, ci.notes, p.image_paths,
                       ci.variant_id, pv.variant_name
                FROM commission_items ci
                LEFT JOIN products p ON ci.product_id = p.id
                LEFT JOIN product_variants pv ON ci.variant_id = pv.id
                WHERE ci.order_id = ?
            """, conn, params=(order['id'],))
            
            # Helper for binary data cleanup
            def clean_numeric(val):
                if isinstance(val, bytes):
                    return int.from_bytes(val, 'little')
                return val
            
            # Helper for images from product
            def get_prod_imgs(p_str):
                try:
                    import ast
                    l = ast.literal_eval(p_str)
                    return l if l and isinstance(l, list) else []
                except: return []
            
            # Apply cleanup
            for col in ['quantity', 'quantity_from_stock', 'quantity_produced', 'product_id']:
                items[col] = items[col].apply(clean_numeric)

            items['quantity'] = items['quantity'].fillna(0).astype(int)
            items['quantity_from_stock'] = items['quantity_from_stock'].fillna(0).astype(int)
            items['quantity_produced'] = items['quantity_produced'].fillna(0).astype(int)
            items['name'] = items['name'].fillna("Produto Desconhecido")
            items['notes'] = items['notes'].fillna("")
            items['image_paths'] = items['image_paths'].apply(get_prod_imgs)
            
            # Financials & Dates Highlighting
            c_inf1, c_inf2, c_inf3, c_inf4 = st.columns(4)
            
            days_left = (pd.to_datetime(order['date_due']).date() - date.today()).days
            date_color = "red" if days_left < 3 else "orange" if days_left < 7 else "green"
            
            c_inf1.markdown(f"📅 **Prazo:** :{date_color}[{pd.to_datetime(order['date_due']).strftime('%d/%m/%Y')}] ({days_left} dias)")
            
            total_val = order['total_price']
            deposit_val = order['deposit_amount']
            remaining_val = total_val - deposit_val
            
            c_inf2.metric("Valor Total", f"R$ {total_val:.2f}")
            c_inf3.metric("Sinal Pago", f"R$ {deposit_val:.2f}")
            c_inf4.metric("Restante", f"R$ {remaining_val:.2f}")

            # --- Reference Photos Section ---
            with st.expander("📸 Fotos de Referência", expanded=False):
                # Parse existing images
                order_images = []
                if order.get('image_paths'):
                    try:
                        import ast
                        order_images = ast.literal_eval(order['image_paths'])
                        if not isinstance(order_images, list):
                            order_images = []
                    except Exception:
                        order_images = []
                
                # Display existing images
                if order_images:
                    st.caption(f"📷 {len(order_images)} foto(s)")
                    img_cols = st.columns(min(len(order_images), 4))
                    for idx, img_path in enumerate(order_images):
                        with img_cols[idx % 4]:
                            if os.path.exists(img_path):
                                st.image(img_path, width=150)
                                if st.button("🗑️", key=f"del_img_{order['id']}_{idx}"):
                                    order_images.pop(idx)
                                    conn_write = database.get_connection()
                                    cursor_write = conn_write.cursor()
                                    try:
                                        cursor_write.execute("BEGIN TRANSACTION")
                                        cursor_write.execute("UPDATE commission_orders SET image_paths=? WHERE id=?", 
                                                       (str(order_images), order['id']))
                                        conn_write.commit()
                                        st.rerun()
                                    except Exception as e:
                                        conn_write.rollback()
                                        st.error(f"Erro ao excluir imagem: {e}")
                                    finally:
                                        cursor_write.close()
                                        conn_write.close()
                else:
                    st.caption("Nenhuma foto anexada")
                
                # Upload new photos using form to preserve state
                with st.form(f"photo_form_{order['id']}"):
                    new_photos = st.file_uploader(
                        "Adicionar fotos de referência",
                        accept_multiple_files=True,
                        type=['png', 'jpg', 'jpeg', 'webp'],
                        key=f"upload_ref_{order['id']}"
                    )
                    
                    if st.form_submit_button("💾 Salvar Fotos"):
                        if new_photos:
                            # Create folder for order images
                            img_folder = f"assets/orders/{order['id']}"
                            if not os.path.exists(img_folder):
                                os.makedirs(img_folder)
                            
                            for photo in new_photos:
                                file_path = os.path.join(img_folder, f"{uuid.uuid4().hex[:8]}_{photo.name}")
                                with open(file_path, "wb") as f:
                                    f.write(photo.getbuffer())
                                order_images.append(file_path)
                            
                            # Save to database
                            conn_write = database.get_connection()
                            cursor_write = conn_write.cursor()
                            try:
                                cursor_write.execute("BEGIN TRANSACTION")
                                cursor_write.execute("UPDATE commission_orders SET image_paths=? WHERE id=?", 
                                               (str(order_images), order['id']))
                                conn_write.commit()
                                admin_utils.show_feedback_dialog(f"{len(new_photos)} foto(s) salva(s)!", level="success")
                            except Exception as e:
                                conn_write.rollback()
                                admin_utils.show_feedback_dialog(f"Erro ao salvar fotos: {e}", level="error")
                            finally:
                                cursor_write.close()
                                conn_write.close()
                        else:
                            admin_utils.show_feedback_dialog("Selecione pelo menos uma foto.", level="warning")

            st.divider()
            
            # Actions Row
            c_act1, c_act2, c_act3, c_act4 = st.columns([1.5, 0.8, 0.8, 0.8])
            
            # Add Item Button
            with c_act1:
                 with st.popover("➕ Adicionar Produto"):
                    with st.form(f"add_item_{order['id']}"):
                        # Load Products
                        try:
                            prods_df = pd.read_sql("SELECT id, name, stock_quantity, base_price FROM products ORDER BY name", conn)
                            prod_opts = [f"{r['name']} (R$ {r['base_price']:.2f})" for _, r in prods_df.iterrows()]
                        except Exception:
                            prod_opts = []
                        
                        sel_new_prod = st.selectbox("Produto", prod_opts)
                        
                        # Variant Selector Logic
                        sel_variant_id = None
                        price_mod = 0.0
                        
                        if sel_new_prod:
                            p_name_core = sel_new_prod.split(' (')[0]
                            p_row_sel = prods_df[prods_df['name'] == p_name_core].iloc[0]
                            vars_df = pd.read_sql("SELECT id, variant_name, price_adder, stock_quantity FROM product_variants WHERE product_id=?", conn, params=(p_row_sel['id'],))
                            
                            if not vars_df.empty:
                                v_opts = {f"{r['variant_name']} (+{r['price_adder']})": r['id'] for _, r in vars_df.iterrows()}
                                sel_v_txt = st.selectbox("Variação (Esmalte)", [""] + list(v_opts.keys()))
                                if sel_v_txt:
                                    sel_variant_id = v_opts[sel_v_txt]
                                    v_infos = vars_df[vars_df['id'] == sel_variant_id].iloc[0]
                                    price_mod = float(v_infos['price_adder'])
                                    st.caption(f"Estoque Variação: {v_infos['stock_quantity']}")
                        
                        new_qty = st.number_input("Quantidade", min_value=1, value=1)
                        use_stock_new = st.checkbox("Reservar do Estoque?")
                        
                        if st.form_submit_button("Adicionar"):
                            # Find prod id
                            p_row = prods_df[prods_df['name'] == sel_new_prod.split(' (')[0]].iloc[0]
                            
                            # Check stock source (Variant vs Product)
                            stock_av = p_row['stock_quantity']
                            if sel_variant_id:
                                # Discrete connection for stock check and write
                                with database.db_session() as conn_check:
                                    stock_av = pd.read_sql("SELECT stock_quantity FROM product_variants WHERE id=?", conn_check, params=(sel_variant_id,)).iloc[0]['stock_quantity']
                            
                            qty_res_new = min(stock_av, new_qty) if use_stock_new else 0
                            
                            # BLOCK logic if user wants to reserve but balance is insufficient
                            if use_stock_new and new_qty > stock_av:
                                admin_utils.show_feedback_dialog(f"Estoque insuficiente para reserva! (Necessário: {new_qty}, Disponível: {int(stock_av)})", level="error")
                            else:
                                price = p_row['base_price'] + price_mod
                                
                                conn_write = database.get_connection()
                                cursor_write = conn_write.cursor()
                                try:
                                    cursor_write.execute("BEGIN TRANSACTION")
                                    # Insert Item
                                    cursor_write.execute("""
                                        INSERT INTO commission_items (order_id, product_id, quantity, quantity_from_stock, quantity_produced, unit_price, variant_id)
                                        VALUES (?, ?, ?, ?, 0, ?, ?)
                                    """, (order['id'], int(p_row['id']), new_qty, int(qty_res_new), float(price), int(sel_variant_id) if sel_variant_id else None))
                                    
                                    # Reserve Stock (Handle Kits)
                                    if qty_res_new > 0:
                                        if sel_variant_id:
                                             cursor_write.execute("UPDATE product_variants SET stock_quantity = stock_quantity - ? WHERE id=?", (int(qty_res_new), int(sel_variant_id)))
                                        else:
                                            kit_comps = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn_write, params=(int(p_row['id']),))
                                            if not kit_comps.empty:
                                                for _, kc in kit_comps.iterrows():
                                                    deduct_res = qty_res_new * kc['quantity']
                                                    cursor_write.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", (int(deduct_res), int(kc['child_product_id'])))
                                            else:
                                                cursor_write.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", (int(qty_res_new), int(p_row['id'])))
                                    
                                    # Update Order Total
                                    cursor_write.execute("UPDATE commission_orders SET total_price = total_price + ? WHERE id=?", (price * new_qty, order['id']))
                                    
                                    success = True
                                    conn_write.commit()
                                    admin_utils.show_feedback_dialog("Item adicionado!", level="success")
                                    st.rerun()
                                except Exception as e:
                                    conn_write.rollback()
                                    admin_utils.show_feedback_dialog(f"Erro ao adicionar item: {e}", level="error")
                                finally:
                                    cursor_write.close()
                                    conn_write.close()
            # Edit Order Button
            with c_act2:
                with st.popover("✏️ Editar"):
                    with st.form(f"edit_ord_{order['id']}"):
                        new_date = st.date_input("Novo Prazo", value=pd.to_datetime(order['date_due']), format="DD/MM/YYYY")
                        new_notes = st.text_area("Notas", value=order['notes'])
                        new_discount = st.number_input("Desconto Manual (R$)", value=order['manual_discount'] or 0.0, step=1.0)
                        new_deposit = st.number_input("Valor Sinal (R$)", value=order['deposit_amount'] or 0.0, step=1.0)
                        
                        # Client Edit (Advanced)
                        current_cli_index = 0
                        try:
                            all_clients = pd.read_sql("SELECT id, name FROM clients", conn)
                            cli_list = all_clients['name'].tolist()
                            if order['client'] in cli_list:
                                current_cli_index = cli_list.index(order['client'])
                        except Exception:
                            cli_list = []
                        
                        new_client_name = st.selectbox("Cliente", cli_list, index=current_cli_index)

                        if st.form_submit_button("Salvar Alterações"):
                            # Find new client ID
                            new_client_id = all_clients[all_clients['name'] == new_client_name]['id'].values[0]
                            
                            # Update Order
                            cursor.execute("""
                                UPDATE commission_orders 
                                SET date_due=?, notes=?, manual_discount=?, deposit_amount=?, client_id=? 
                                WHERE id=?
                            """, (new_date, new_notes, new_discount, new_deposit, int(new_client_id), order['id']))
                            conn.commit()
                            admin_utils.show_feedback_dialog("Atualizado!", level="success")
                            st.rerun()

            # Delete Order
            if c_act3.button("🗑️ Excluir", key=f"del_ord_{order['id']}"):
                if delete_order(order['id']):
                    admin_utils.show_feedback_dialog("Encomenda excluída e estoque restaurado!", level="success")
                    st.rerun()

 
            
            # Format Order ID (ENC-YYMMDD-ID)
            created_dt = pd.to_datetime(order['date_created']) if order['date_created'] else datetime.now()
            formatted_id = f"ENC-{created_dt.strftime('%y%m%d')}-{order['id']}"
            
            # Formatted Filename
            fname = f"{formatted_id}.pdf"
            
            # Direct Download Button
            c_act4.download_button(
                label="📄 PDF",
                data=reports.generate_receipt_pdf({
                        "id": formatted_id,
                        "type": "Encomenda",
                        "date": created_dt.strftime('%d/%m/%Y'),
                        "date_due": pd.to_datetime(order['date_due']).strftime('%d/%m/%Y'),
                        "client_name": order['client'],
                        "notes": order['notes'],
                        "items": [
                            {
                                "name": f"{r['name']} ({r['variant_name']})" if r['variant_name'] else r['name'], 
                                "qty": r['quantity'], 
                                "price": r['unit_price'],
                                "notes": r['notes'],
                                "images": r['image_paths']
                            } 
                            for _, r in items.iterrows()
                        ],
                        "total": order['total_price'],
                        "discount": order['manual_discount'] or 0,
                        "deposit": order['deposit_amount'] or 0,
                        "status": order['status']
                }),
                file_name=fname,
                mime="application/pdf",
                key=f"dl_pdf_{order['id']}"
            )
            
            st.divider()
            st.write("**Itens:**")
            
            all_complete = True
            
            for _, item in items.iterrows():
                target_prod = item['quantity'] - item['quantity_from_stock']
                
                # Create columns for item display (Added Img col)
                ci_img, ci1, ci2, ci3 = st.columns([0.5, 2, 2, 1.5])
                
                with ci_img:
                    if item['image_paths']:
                         if os.path.exists(item['image_paths'][0]):
                             st.image(item['image_paths'][0], width=50)
                         else: st.write("📦")
                    else: st.write("📦")

                with ci1:
                    # Display Product Name and Edit Popover
                    st.markdown(f"📦 **{item['name']}**")
                    if pd.notna(item['variant_name']):
                         st.caption(f"🎨 {item['variant_name']}")
                    
                    if item['notes']:
                        st.caption(f"📝 {item['notes']}")
                    
                    # Edit Quantity Popover
                    with st.popover(f"Qtd: {item['quantity']}"):
                        with st.form(f"edit_qty_{item['id']}"):
                            qty_edit = st.number_input("Nova Quantidade", min_value=1, value=item['quantity'])
                            if st.form_submit_button("Alterar"):
                                old_qty = item['quantity']
                                diff = qty_edit - old_qty
                                
                                if diff != 0:
                                    success = False
                                    conn_write = database.get_connection()
                                    cursor_write = conn_write.cursor()
                                    try:
                                        cursor_write.execute("BEGIN TRANSACTION")
                                        # Update Item
                                        cursor_write.execute("UPDATE commission_items SET quantity=? WHERE id=?", (qty_edit, item['id']))
                                        
                                        # Update Order Total
                                        cost_diff = diff * item['unit_price']
                                        cursor_write.execute("UPDATE commission_orders SET total_price = total_price + ? WHERE id=?", (cost_diff, order['id']))
                                        
                                        if qty_edit < item['quantity_from_stock']:
                                            # Return difference to stock
                                            to_return = item['quantity_from_stock'] - qty_edit
                                            cursor_write.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (to_return, item['product_id']))
                                            cursor_write.execute("UPDATE commission_items SET quantity_from_stock=? WHERE id=?", (qty_edit, item['id']))
                                        
                                        conn_write.commit()
                                        success = True
                                    except Exception as e:
                                        conn_write.rollback()
                                        admin_utils.show_feedback_dialog(f"Erro na operação: {e}", level="error")
                                    finally:
                                        cursor_write.close()
                                        conn_write.close()
                                    
                                    if success:
                                        st.rerun()

                    st.caption(f"Reservado: {item['quantity_from_stock']} | A Produzir: {target_prod}")
                
                with ci2:
                    produced = item['quantity_produced']
                    # WIP Qty
                    wip_res = pd.read_sql("SELECT SUM(quantity) as qty FROM production_wip WHERE order_item_id=?", conn, params=(item['id'],))
                    wip_qty = wip_res.iloc[0]['qty'] if not wip_res.empty and pd.notna(wip_res.iloc[0]['qty']) else 0
                    
                    total_acc = produced + wip_qty
                    remaining = max(0, target_prod - total_acc)
                    
                    # Progress
                    if target_prod > 0:
                        pct = min(1.0, total_acc / target_prod)
                        st.progress(pct, text=f"{produced} Pronto | {wip_qty} Fluxo | {remaining} Falta")
                        
                        if remaining > 0:
                            all_complete = False
                            all_complete = False
                            # Production Options (Quick vs WIP)
                            b_quick, b_wip = st.columns(2)
                            
                            with b_quick:
                                with st.popover("⚡ Registrar Produção", use_container_width=True):
                                    st.caption("Baixa estoque e finaliza imediatamente")
                                    amount = st.number_input("Qtd", min_value=1, max_value=remaining, key=f"prod_in_{item['id']}")
                                    if st.button("Confirmar", key=f"conf_{item['id']}", type="primary"):
                                        success = False
                                        old_order_status = order['status']
                                        conn_write = database.get_connection()
                                        cursor_write = conn_write.cursor()
                                        try:
                                            cursor_write.execute("BEGIN TRANSACTION")
                                            # Use centralized deduction
                                            glaze_id = item.get('variant_id') if item.get('variant_id') and item['variant_id'] > 0 else None
                                            product_service.deduct_production_materials_central(cursor_write, item['product_id'], amount, note_suffix=f"Produção Rápida Encomenda #{fmt_id}")
                                            
                                            # Update Item
                                            cursor_write.execute("UPDATE commission_items SET quantity_produced = quantity_produced + ? WHERE id=?", (amount, item['id']))
                                            
                                            # Check pending items
                                            cursor_write.execute("""
                                                SELECT COUNT(*) FROM commission_items 
                                                WHERE order_id=? AND quantity_produced < (quantity - quantity_from_stock)
                                            """, (order['id'],))
                                            pending_count = cursor_write.fetchone()[0]
                                            
                                            new_status = 'Concluída' if pending_count == 0 else 'Em Produção'
                                            cursor_write.execute("UPDATE commission_orders SET status=? WHERE id=?", (new_status, order['id']))
                                            
                                            # Log status change
                                            if old_order_status != new_status:
                                                audit.log_action(conn_write, 'UPDATE', 'commission_orders', order['id'], 
                                                    {'status': old_order_status}, {'status': new_status})
                                            
                                            # Log production history
                                            from datetime import datetime as dt
                                            user_id, username = None, 'system'
                                            if 'current_user' in st.session_state and st.session_state.current_user:
                                                user_id = st.session_state.current_user.get('id')
                                                username = st.session_state.current_user.get('username', 'unknown')
                                            
                                            prod_name_row = pd.read_sql("SELECT name FROM products WHERE id=?", conn_write, params=(item['product_id'],))
                                            prod_name = prod_name_row.iloc[0]['name'] if not prod_name_row.empty else 'Produto'
                                            
                                            cursor_write.execute("""
                                                INSERT INTO production_history (timestamp, product_id, product_name, quantity, order_id, user_id, username)
                                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                            """, (dt.now().isoformat(), item['product_id'], prod_name, amount, order['id'], user_id, username))
                                            new_hist_id = cursor_write.lastrowid
                                            
                                            conn_write.commit()
                                            
                                            # Audit Logs
                                            audit.log_action(conn_write, 'CREATE', 'production_history', new_hist_id, None, {
                                                'product_id': item.get('product_id'), 'product_name': prod_name, 'quantity': amount, 'order_id': order.get('id')
                                            })
                                            audit.log_action(conn_write, 'UPDATE', 'commission_items', item.get('id'), 
                                                {'quantity_produced': item.get('quantity_produced')}, {'quantity_produced': item.get('quantity_produced', 0) + amount})
                                            
                                            success = True
                                        except Exception as e:
                                            conn_write.rollback()
                                            admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")
                                        finally:
                                            cursor_write.close()
                                            conn_write.close()
                                        
                                        if success:
                                            st.session_state['expanded_order_id'] = order['id']
                                            admin_utils.show_feedback_dialog("Produção lançada!", level="success")
                                            st.rerun()

                            with b_wip:
                                with st.popover("⏳ Iniciar Produção", use_container_width=True):
                                    st.caption("Envia para Kanban (Modelagem)")
                                    wip_amount = st.number_input("Qtd", min_value=1, max_value=remaining, value=remaining, key=f"wip_in_{item['id']}")
                                    wip_date = st.date_input("Data Início", value=date.today(), key=f"wip_date_{item['id']}")
                                    
                                    if st.button("Iniciar", key=f"wip_go_{item['id']}", type="primary"):
                                        success = False
                                        conn_write = database.get_connection()
                                        cursor_write = conn_write.cursor()
                                        try:
                                            cursor_write.execute("BEGIN TRANSACTION")
                                            # Insert into WIP (materials_deducted = 0)
                                            history = {"Iniciado": datetime.now().strftime("%d/%m %H:%M"), "Fila de Espera": datetime.now().strftime("%d/%m %H:%M")}
                                            history_json = json.dumps(history)

                                            cursor_write.execute("""
                                                INSERT INTO production_wip (product_id, variant_id, order_id, order_item_id, stage, quantity, start_date, materials_deducted, stage_history, notes)
                                                VALUES (?, ?, ?, ?, 'Fila de Espera', ?, ?, 0, ?, ?)
                                            """, (item['product_id'], item['variant_id'], order['id'], item['id'], wip_amount, wip_date.isoformat(), history_json, item.get('notes')))
                                            
                                            # Update Order Status to "Em Produção" if not already
                                            if order['status'] == 'Pendente':
                                                cursor_write.execute("UPDATE commission_orders SET status='Em Produção' WHERE id=?", (order['id'],))
                                                audit.log_action(conn_write, 'UPDATE', 'commission_orders', order['id'], {'status': 'Pendente'}, {'status': 'Em Produção'})
                                            
                                            conn_write.commit()
                                            success = True
                                        except Exception as e:
                                            conn_write.rollback()
                                            admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")
                                        finally:
                                            cursor_write.close()
                                            conn_write.close()
                                            
                                        if success:
                                            st.session_state['expanded_order_id'] = order['id']
                                            admin_utils.show_feedback_dialog("Enviado para Fluxo de Produção!", level="success")
                                            st.rerun()
                    else:
                        st.info("✅ Produção Concluída (ou Totalmente Reservado)")

                # Delete Item Button
                with ci3:
                     if st.button("❌", key=f"del_item_{item['id']}", help="Remover item da encomenda"):
                        # Restore Stock if reserved
                        # Restore Stock if reserved
                        rest_qty = item['quantity_from_stock']
                        success = False
                        conn_write = database.get_connection()
                        cursor_write = conn_write.cursor()
                        try:
                            cursor_write.execute("BEGIN TRANSACTION")
                            if rest_qty > 0:
                                old_stock = pd.read_sql("SELECT stock_quantity FROM products WHERE id=?", conn_write, params=(item['product_id'],)).iloc[0]['stock_quantity']
                                
                                # Check Kit Restore
                                kit_comps = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn_write, params=(item['product_id'],))
                                if not kit_comps.empty:
                                    for _, kc in kit_comps.iterrows():
                                        restore_amt = rest_qty * kc['quantity']
                                        cursor_write.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (int(restore_amt), int(kc['child_product_id'])))
                                else:
                                    cursor_write.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                                                 (rest_qty, item['product_id']))

                                # Audit log logic simplified (logging parent change even if virtual? actually audit is tricky for kits. Let's keep parent audit generic or skip detail for components to avoid complexity)
                                audit.log_action(conn_write, 'UPDATE', 'products', item['product_id'], 
                                    {'stock_quantity': old_stock}, {'stock_quantity': old_stock + rest_qty})
                            
                            cursor_write.execute("DELETE FROM commission_items WHERE id=?", (item['id'],))
                            
                            # Recalc Total Price of Order
                            deduction = item['unit_price'] * item['quantity']
                            old_price = order['total_price']
                            cursor_write.execute("UPDATE commission_orders SET total_price = total_price - ? WHERE id=?", 
                                         (deduction, order['id']))
                            
                            # Capture old data for audit
                            old_data = {'id': item['id'], 'product_id': item['product_id'], 'quantity': item['quantity']}
                            
                            conn_write.commit()
                            
                            # Audit Logs
                            audit.log_action(conn_write, 'DELETE', 'commission_items', item['id'], old_data, None)
                            audit.log_action(conn_write, 'UPDATE', 'commission_orders', order['id'], 
                                {'total_price': old_price}, {'total_price': old_price - deduction})
                            
                            success = True
                        except Exception as e:
                            conn_write.rollback()
                            admin_utils.show_feedback_dialog(f"Erro ao excluir item: {e}", level="error")
                        finally:
                            cursor_write.close()
                            conn_write.close()
                        
                        if success:
                            st.session_state['expanded_order_id'] = order['id']
                            st.rerun()

            st.divider()
            
            # Delivery / Completion Actions
            if all_complete and order['status'] != 'Entregue':
                # Option to mark as "Ready" (Concluído) without delivering yet
                if order['status'] != 'Concluída':
                    if st.button("🏁 Marcar como Pronto", key=f"ready_{order['id']}", help="Marcar produção como finalizada e aguardando retirada"):
                        conn_write = database.get_connection()
                        cursor_write = conn_write.cursor()
                        try:
                            cursor_write.execute("BEGIN TRANSACTION")
                            cursor_write.execute("UPDATE commission_orders SET status='Concluída' WHERE id=?", (order['id'],))
                            audit.log_action(conn_write, 'UPDATE', 'commission_orders', order['id'], {'status': order['status']}, {'status': 'Concluída'})
                            conn_write.commit()
                            st.session_state['expanded_order_id'] = order['id']
                            admin_utils.show_feedback_dialog("Status atualizado para Concluído!", level="success")
                            st.rerun()
                        except Exception as e:
                            conn_write.rollback()
                            admin_utils.show_feedback_dialog(f"Erro ao atualizar status: {e}", level="error")
                        finally:
                            cursor_write.close()
                            conn_write.close()

                if st.button("📦 Realizar Entrega", key=f"dlv_{order['id']}"):
                    success = False
                    conn_write = database.get_connection()
                    cursor_write = conn_write.cursor()
                    try:
                        cursor_write.execute("BEGIN TRANSACTION")
                        # 1. Re-inject ALL items to stock momentarily
                        for _, it in items.iterrows():
                            p_row_chk = pd.read_sql("SELECT stock_quantity FROM products WHERE id=?", conn_write, params=(it['product_id'],))
                            if p_row_chk.empty: continue

                            old_stock = p_row_chk.iloc[0]['stock_quantity']
                            kit_comps = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn_write, params=(it['product_id'],))
                            
                            if not kit_comps.empty:
                                for _, kc in kit_comps.iterrows():
                                    restore_amt = it['quantity'] * kc['quantity'] 
                                    cursor_write.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (int(restore_amt), int(kc['child_product_id'])))
                            else:
                                cursor_write.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (it['quantity'], it['product_id']))
                            
                            audit.log_action(conn_write, 'UPDATE', 'products', it['product_id'], {'stock_quantity': old_stock}, {'stock_quantity': old_stock + it['quantity']})
                        
                        # 2. Create Sale Record
                        ord_uuid = f"ENC-{datetime.now().strftime('%y%m%d')}-{order['id']}"
                        total_ord_price = order['total_price']
                        deposit_total = order['deposit_amount'] or 0
                        deposit_ratio = deposit_total / total_ord_price if total_ord_price > 0 else 0
                        
                        for _, it in items.iterrows():
                            item_subtotal = it['unit_price'] * it['quantity']
                            discount_share = item_subtotal * deposit_ratio
                            final_item_price = item_subtotal - discount_share
                            notes_item = f"Encomenda #{order['id']}"
                            if deposit_total > 0: notes_item += f" (Sinal: R$ {discount_share:.2f})"

                            cursor_write.execute("""
                                INSERT INTO sales (date, product_id, quantity, total_price, status, client_id, 
                                                 discount, payment_method, notes, salesperson, order_id)
                                VALUES (?, ?, ?, ?, 'Finalizada', ?, ?, 'Misto', ?, 'Sistema', ?)
                            """, (date.today(), it['product_id'], it['quantity'], final_item_price, 
                                  order['client_id'], discount_share, notes_item, ord_uuid))
                            
                            # 3. Deduct Stock (Sales Logic)
                            p_row_chk = pd.read_sql("SELECT stock_quantity FROM products WHERE id=?", conn_write, params=(it['product_id'],))
                            if not p_row_chk.empty:
                                old_stock_after = p_row_chk.iloc[0]['stock_quantity']
                                kit_comps_2 = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn_write, params=(it['product_id'],))
                                if not kit_comps_2.empty:
                                     for _, kc in kit_comps_2.iterrows():
                                        deduct_amt = it['quantity'] * kc['quantity']
                                        cursor_write.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", (int(deduct_amt), int(kc['child_product_id'])))
                                else:
                                    cursor_write.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", (it['quantity'], it['product_id']))
                                
                                audit.log_action(conn_write, 'UPDATE', 'products', it['product_id'], {'stock_quantity': old_stock_after}, {'stock_quantity': old_stock_after - it['quantity']})
                            
                            audit.log_action(conn_write, 'CREATE', 'sales', cursor_write.lastrowid, None, {
                                'order_id': order['id'], 'product_id': it['product_id'], 'quantity': it['quantity'], 'total_price': (it['unit_price'] * it['quantity'])
                            })
                        
                        # 4. Finalize Order Status
                        old_status = order['status']
                        cursor_write.execute("UPDATE commission_orders SET status='Entregue' WHERE id=?", (order['id'],))
                        conn_write.commit()
                        audit.log_action(conn_write, 'UPDATE', 'commission_orders', order['id'], {'status': old_status}, {'status': 'Entregue'})
                        success = True
                    except Exception as e:
                        conn_write.rollback()
                        admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")
                    finally:
                        cursor_write.close()
                        conn_write.close()
                    
                    if success:
                        # Prepare data for Receipt
                        rec_data = {
                            "id": formatted_id,
                            "type": "Encomenda (Entrega)",
                            "date": created_dt.strftime('%d/%m/%Y'),
                            "date_due": pd.to_datetime(order['date_due']).strftime('%d/%m/%Y'),
                            "client_name": order['client'],
                            "items": [
                                {
                                    "name": r['name'], 
                                    "qty": r['quantity'], 
                                    "price": r['unit_price'],
                                    "notes": r['notes'],
                                    "images": r['image_paths']
                                } 
                                for _, r in items.iterrows()
                            ],
                            "total": order['total_price'],
                            "discount": order['manual_discount'] or 0,
                            "deposit": order['deposit_amount'] or 0,
                            "status": "Entregue",
                            "notes": order['notes']
                        }
                        
                        # Generate PDF
                        pdf_bytes = reports.generate_receipt_pdf(rec_data)
                        
                        # Set Session State to show Download Button after rerun
                        st.session_state['delivered_pdf'] = pdf_bytes
                        st.session_state['delivered_name'] = f"Recibo_Final_{formatted_id}.pdf"
                        st.session_state['expanded_order_id'] = order['id']
                        
                        st.rerun()

conn.close()
