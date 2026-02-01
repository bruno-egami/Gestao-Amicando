import streamlit as st
import pandas as pd
import database
from datetime import date, datetime, timedelta
import admin_utils
import audit
import reports
import time
import auth
import uuid
import os

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
st.subheader("Gerenciar Pedidos")
    
# Logic to Delete Order (and restore stock)
def delete_order(oid):
    # 1. Get reserved items to restore
    items = pd.read_sql("SELECT product_id, quantity_from_stock FROM commission_items WHERE order_id=?", conn, params=(oid,))
    
    # Helper for binary
    def clean_bin(val):
        if isinstance(val, bytes):
            return int.from_bytes(val, 'little')
        return val

    items['quantity_from_stock'] = items['quantity_from_stock'].apply(clean_bin)
    items['product_id'] = items['product_id'].apply(clean_bin)

    # Get order data for audit
    order_data = pd.read_sql("SELECT client_id, total_price, status FROM commission_orders WHERE id=?", conn, params=(oid,))
    old_data = order_data.iloc[0].to_dict() if not order_data.empty else {}
    
    cursor.execute("BEGIN TRANSACTION")
    try:
        for _, it in items.iterrows():
            qty_rest = int(it['quantity_from_stock'])
            if qty_rest > 0:
                cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                             (qty_rest, int(it['product_id'])))
        
        cursor.execute("DELETE FROM commission_items WHERE order_id=?", (oid,))
        cursor.execute("DELETE FROM commission_orders WHERE id=?", (oid,))
        conn.commit()
        
        # Audit log
        audit.log_action(conn, 'DELETE', 'commission_orders', oid, old_data, None)
        
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao excluir encomenda: {e}")
        return False

# --- Filters ---
kf1, kf2, kf3 = st.columns([1.5, 1.5, 2])
with kf1:
    # Status Filter
    all_statuses = ["Pendente", "Em Produção", "Concluída", "Entregue"]
    sel_status = st.multiselect("Status", all_statuses, default=["Pendente", "Em Produção"])

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
        with st.expander(f"📦 #{order['id']} - {order['client']} (Prazo: {pd.to_datetime(order['date_due']).strftime('%d/%m/%Y')}) - {order['status']}"):
            
            # Fetch Items
            # Fetch Items
            items = pd.read_sql("""
                SELECT ci.id, p.name, ci.quantity, ci.quantity_from_stock, ci.quantity_produced, ci.product_id, ci.unit_price
                FROM commission_items ci
                LEFT JOIN products p ON ci.product_id = p.id
                WHERE ci.order_id = ?
            """, conn, params=(order['id'],))
            
            # Helper for binary data cleanup
            def clean_numeric(val):
                if isinstance(val, bytes):
                    return int.from_bytes(val, 'little')
                return val
            
            # Apply cleanup
            for col in ['quantity', 'quantity_from_stock', 'quantity_produced', 'product_id']:
                items[col] = items[col].apply(clean_numeric)

            items['quantity'] = items['quantity'].fillna(0).astype(int)
            items['quantity_from_stock'] = items['quantity_from_stock'].fillna(0).astype(int)
            items['quantity_produced'] = items['quantity_produced'].fillna(0).astype(int)
            items['name'] = items['name'].fillna("Produto Desconhecido")
            
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
                        order_images = eval(order['image_paths'])
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
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE commission_orders SET image_paths=? WHERE id=?", 
                                                   (str(order_images), order['id']))
                                    conn.commit()
                                    st.rerun()
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
                            cursor = conn.cursor()
                            cursor.execute("UPDATE commission_orders SET image_paths=? WHERE id=?", 
                                           (str(order_images), order['id']))
                            conn.commit()
                            st.success(f"✅ {len(new_photos)} foto(s) salva(s)!")
                            st.rerun()
                        else:
                            st.warning("Selecione pelo menos uma foto.")

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
                        new_qty = st.number_input("Quantidade", min_value=1, value=1)
                        use_stock_new = st.checkbox("Reservar do Estoque?")
                        
                        if st.form_submit_button("Adicionar"):
                            # Find prod id
                            p_row = prods_df[prods_df['name'] == sel_new_prod.split(' (')[0]].iloc[0]
                            stock_av = p_row['stock_quantity']
                            
                            qty_res_new = min(stock_av, new_qty) if use_stock_new else 0
                            price = p_row['base_price']
                            
                            success = False
                            cursor.execute("BEGIN TRANSACTION")
                            try:
                                # Insert Item
                                cursor.execute("""
                                    INSERT INTO commission_items (order_id, product_id, quantity, quantity_from_stock, quantity_produced, unit_price)
                                    VALUES (?, ?, ?, ?, 0, ?)
                                """, (order['id'], int(p_row['id']), new_qty, int(qty_res_new), float(price)))
                                
                                # Reserve Stock (Handle Kits)
                                if qty_res_new > 0:
                                    kit_comps = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn, params=(int(p_row['id']),))
                                    if not kit_comps.empty:
                                        for _, kc in kit_comps.iterrows():
                                            deduct_res = qty_res_new * kc['quantity']
                                            cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", (int(deduct_res), kc['child_product_id']))
                                    else:
                                        cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", (int(qty_res_new), int(p_row['id'])))
                                
                                # Update Order Total
                                cursor.execute("UPDATE commission_orders SET total_price = total_price + ? WHERE id=?", (price * new_qty, order['id']))
                                
                                conn.commit()
                                success = True
                            except Exception as e:
                                conn.rollback()
                                st.error(f"Erro ao adicionar item: {e}")
                            
                            if success:
                                st.success("Item adicionado!")
                                st.rerun()                
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
                            st.success("Atualizado!")
                            st.rerun()

            # Delete Order
            if c_act3.button("🗑️ Excluir", key=f"del_ord_{order['id']}"):
                if delete_order(order['id']):
                    st.success("Encomenda excluída e estoque restaurado!")
                    st.rerun()

 
            
            # Direct Download Button attempt (cleaner than nested button state)
            c_act4.download_button(
                label="📄 PDF",
                data=reports.generate_receipt_pdf({
                        "id": f"ENC-{order['id']}",
                        "type": "Encomenda",
                        "date": pd.to_datetime(order['date_created']).strftime('%d/%m/%Y') if order['date_created'] else datetime.now().strftime('%d/%m/%Y'),
                        "date_due": pd.to_datetime(order['date_due']).strftime('%d/%m/%Y'),
                        "client_name": order['client'],
                        "notes": order['notes'],
                        "items": [
                            {"name": r['name'], "qty": r['quantity'], "price": r['unit_price']} 
                            for _, r in items.iterrows()
                        ],
                        "total": order['total_price'],
                        "discount": order['manual_discount'] or 0,
                        "deposit": order['deposit_amount'] or 0
                }),
                file_name=f"encomenda_{order['id']}.pdf",
                mime="application/pdf",
                key=f"dl_pdf_{order['id']}"
            )
            
            st.divider()
            st.write("**Itens:**")
            
            all_complete = True
            
            for _, item in items.iterrows():
                target_prod = item['quantity'] - item['quantity_from_stock']
                
                # Create columns for item display
                ci1, ci2, ci3 = st.columns([2, 2, 1.5])
                with ci1:
                    # Display Product Name and Edit Popover
                    st.markdown(f"📦 **{item['name']}**")
                    
                    # Edit Quantity Popover
                    with st.popover(f"Qtd: {item['quantity']}"):
                        with st.form(f"edit_qty_{item['id']}"):
                            qty_edit = st.number_input("Nova Quantidade", min_value=1, value=item['quantity'])
                            if st.form_submit_button("Alterar"):
                                old_qty = item['quantity']
                                diff = qty_edit - old_qty
                                
                                if diff != 0:
                                    success = False
                                    cursor.execute("BEGIN TRANSACTION")
                                    try:
                                        # Update Item
                                        cursor.execute("UPDATE commission_items SET quantity=? WHERE id=?", (qty_edit, item['id']))
                                        
                                        # Update Order Total
                                        cost_diff = diff * item['unit_price']
                                        cursor.execute("UPDATE commission_orders SET total_price = total_price + ? WHERE id=?", (cost_diff, order['id']))
                                        
                                        # Note: We are NOT changing reservation logic here for simplicity, 
                                        # unless user decreases below reserved amount.
                                        if qty_edit < item['quantity_from_stock']:
                                            # Return difference to stock
                                            to_return = item['quantity_from_stock'] - qty_edit
                                            cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (to_return, item['product_id']))
                                            cursor.execute("UPDATE commission_items SET quantity_from_stock=? WHERE id=?", (qty_edit, item['id']))
                                        
                                        conn.commit()
                                        success = True
                                    except Exception as e:
                                        conn.rollback()
                                        st.error(f"Erro na operação: {e}")
                                    
                                    if success:
                                        st.rerun()

                    st.caption(f"Reservado: {item['quantity_from_stock']} | A Produzir: {target_prod}")
                
                with ci2:
                    produced = item['quantity_produced']
                    
                    # Progress
                    if target_prod > 0:
                        pct = min(1.0, produced / target_prod)
                        st.progress(pct, text=f"{produced}/{target_prod} Produzidos")
                        
                        if produced < target_prod:
                            all_complete = False
                            # Production Input
                            with st.popover("Lançar Produção"):
                                amount = st.number_input("Qtd", min_value=1, max_value=(target_prod - produced), key=f"prod_in_{item['id']}")
                                if st.button("Confirmar", key=f"conf_{item['id']}"):
                                    # Deduct materials query...
                                    recipe = pd.read_sql("SELECT material_id, quantity FROM product_recipes WHERE product_id=?", conn, params=(item['product_id'],))
                                    success = False
                                    old_order_status = order['status']
                                    cursor.execute("BEGIN TRANSACTION")
                                    try:
                                        # Update Materials
                                        for _, r in recipe.iterrows():
                                             cursor.execute("UPDATE materials SET stock_level = stock_level - ? WHERE id=?", 
                                                          (r['quantity'] * amount, r['material_id']))
                                        
                                        # Update Item
                                        cursor.execute("UPDATE commission_items SET quantity_produced = quantity_produced + ? WHERE id=?", (amount, item['id']))
                                        cursor.execute("UPDATE commission_orders SET status='Em Produção' WHERE id=?", (order['id'],))
                                        
                                        # Log production history
                                        from datetime import datetime as dt
                                        user_id, username = None, 'system'
                                        if 'current_user' in st.session_state and st.session_state.current_user:
                                            user_id = st.session_state.current_user.get('id')
                                            username = st.session_state.current_user.get('username', 'unknown')
                                        
                                        # Get product name
                                        prod_name_row = pd.read_sql("SELECT name FROM products WHERE id=?", conn, params=(item['product_id'],))
                                        prod_name = prod_name_row.iloc[0]['name'] if not prod_name_row.empty else 'Produto'
                                        
                                        cursor.execute("""
                                            INSERT INTO production_history (timestamp, product_id, product_name, quantity, order_id, user_id, username)
                                            VALUES (?, ?, ?, ?, ?, ?, ?)
                                        """, (dt.now().isoformat(), item['product_id'], prod_name, amount, order['id'], user_id, username))
                                        new_hist_id = cursor.lastrowid
                                        
                                        conn.commit()
                                        
                                        # Audit Log
                                        audit.log_action(conn, 'CREATE', 'production_history', new_hist_id, None, {
                                            'product_id': item.get('product_id'), 'product_name': prod_name, 'quantity': amount, 'order_id': order.get('id')
                                        })
                                        audit.log_action(conn, 'UPDATE', 'commission_items', item.get('id'), 
                                            {'quantity_produced': item.get('quantity_produced')}, {'quantity_produced': item.get('quantity_produced', 0) + amount})
                                        if old_order_status != 'Em Produção':
                                            audit.log_action(conn, 'UPDATE', 'commission_orders', order['id'], 
                                                {'status': old_order_status}, {'status': 'Em Produção'})
                                        
                                        success = True
                                    except Exception as e:
                                        conn.rollback()
                                        st.error(f"Erro: {e}")
                                    
                                    if success:
                                        st.success("Produção lançada!")
                                        st.rerun()
                    else:
                        st.success("✅ Produção Concluída (ou Totalmente Reservado)")

                # Delete Item Button
                with ci3:
                     if st.button("❌", key=f"del_item_{item['id']}", help="Remover item da encomenda"):
                        # Restore Stock if reserved
                        # Restore Stock if reserved
                        rest_qty = item['quantity_from_stock']
                        success = False
                        cursor.execute("BEGIN TRANSACTION")
                        try:
                            if rest_qty > 0:
                                old_stock = pd.read_sql("SELECT stock_quantity FROM products WHERE id=?", conn, params=(item['product_id'],)).iloc[0]['stock_quantity']
                                
                                # Check Kit Restore
                                kit_comps = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn, params=(item['product_id'],))
                                if not kit_comps.empty:
                                    for _, kc in kit_comps.iterrows():
                                        restore_amt = rest_qty * kc['quantity']
                                        cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (restore_amt, kc['child_product_id']))
                                else:
                                    cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                                                 (rest_qty, item['product_id']))

                                # Audit log logic simplified (logging parent change even if virtual? actually audit is tricky for kits. Let's keep parent audit generic or skip detail for components to avoid complexity)
                                audit.log_action(conn, 'UPDATE', 'products', item['product_id'], 
                                    {'stock_quantity': old_stock}, {'stock_quantity': old_stock + rest_qty})
                            
                            cursor.execute("DELETE FROM commission_items WHERE id=?", (item['id'],))
                            
                            # Recalc Total Price of Order
                            deduction = item['unit_price'] * item['quantity']
                            old_price = order['total_price']
                            cursor.execute("UPDATE commission_orders SET total_price = total_price - ? WHERE id=?", 
                                         (deduction, order['id']))
                            
                            # Capture old data for audit
                            old_data = {'id': item['id'], 'product_id': item['product_id'], 'quantity': item['quantity']}
                            
                            conn.commit()
                            
                            # Audit Logs
                            audit.log_action(conn, 'DELETE', 'commission_items', item['id'], old_data, None)
                            audit.log_action(conn, 'UPDATE', 'commission_orders', order['id'], 
                                {'total_price': old_price}, {'total_price': old_price - deduction})
                            
                            success = True
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Erro ao excluir item: {e}")
                        
                        if success:
                            st.rerun()

            st.divider()
            
            # Delivery Action
            if all_complete and order['status'] != 'Entregue':
                if st.button("📦 Realizar Entrega", key=f"dlv_{order['id']}"):
                    # 1. Re-inject ALL items to stock momentarily
                    success = False
                    cursor.execute("BEGIN TRANSACTION")
                    try:
                        # Re-add totals to stock
                        # Re-add totals to stock (Handle Kits)
                        # Re-add totals to stock (Handle Kits)
                        for _, it in items.iterrows():
                            # Check if product exists
                            p_row_chk = pd.read_sql("SELECT stock_quantity FROM products WHERE id=?", conn, params=(it['product_id'],))
                            if p_row_chk.empty:
                                continue # Skip stock logic for deleted products

                            old_stock = p_row_chk.iloc[0]['stock_quantity']
                            
                            kit_comps = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn, params=(it['product_id'],))
                            if not kit_comps.empty:
                                for _, kc in kit_comps.iterrows():
                                    restore_amt = it['quantity'] * kc['quantity'] 
                                    cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (restore_amt, kc['child_product_id']))
                            else:
                                cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                                             (it['quantity'], it['product_id']))
                            
                            audit.log_action(conn, 'UPDATE', 'products', it['product_id'], 
                                {'stock_quantity': old_stock}, {'stock_quantity': old_stock + it['quantity']})
                        
                        # 2. Create Sale Record
                        ord_uuid = f"ENC-{datetime.now().strftime('%y%m%d')}-{order['id']}"
                        
                        # Calculate Deposit Ratio (Pro-rata)
                        total_ord_price = order['total_price']
                        deposit_total = order['deposit_amount'] or 0
                        deposit_ratio = 0
                        if total_ord_price > 0:
                            deposit_ratio = deposit_total / total_ord_price
                        
                        for _, it in items.iterrows():
                            # Calculate values
                            item_subtotal = it['unit_price'] * it['quantity']
                            
                            # Discount share (The part already paid via deposit)
                            discount_share = item_subtotal * deposit_ratio
                            
                            # Final Sale Price (The new money coming in now)
                            final_item_price = item_subtotal - discount_share
                            
                            notes_item = f"Encomenda #{order['id']}"
                            if deposit_total > 0:
                                notes_item += f" (Sinal: R$ {discount_share:.2f})"

                            cursor.execute("""
                                INSERT INTO sales (date, product_id, quantity, total_price, status, client_id, 
                                                 discount, payment_method, notes, salesperson, order_id)
                                VALUES (?, ?, ?, ?, 'Finalizada', ?, ?, 'Misto', ?, 'Sistema', ?)
                            """, (date.today(), it['product_id'], it['quantity'], final_item_price, 
                                  order['client_id'], discount_share, notes_item, ord_uuid))
                            
                            # 3. Deduct Stock (Sales Logic - Handle Kits)
                            p_row_chk = pd.read_sql("SELECT stock_quantity FROM products WHERE id=?", conn, params=(it['product_id'],))
                            if not p_row_chk.empty:
                                old_stock = p_row_chk.iloc[0]['stock_quantity']
                                
                                kit_comps = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn, params=(it['product_id'],))
                                if not kit_comps.empty:
                                     for _, kc in kit_comps.iterrows():
                                        deduct_amt = it['quantity'] * kc['quantity']
                                        cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", (deduct_amt, kc['child_product_id']))
                                else:
                                    cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", 
                                                 (it['quantity'], it['product_id']))
                                
                                audit.log_action(conn, 'UPDATE', 'products', it['product_id'], 
                                    {'stock_quantity': old_stock}, {'stock_quantity': old_stock - it['quantity']})
                            
                            # Audit Log for Sale creation from Order (Always log sale even if product missing)
                            audit.log_action(conn, 'CREATE', 'sales', cursor.lastrowid, None, {
                                'order_id': order['id'], 'product_id': it['product_id'], 'quantity': it['quantity'], 'total_price': (it['unit_price'] * it['quantity'])
                            })
                        
                        # 4. Finalize Order Status
                        old_status = order['status']
                        cursor.execute("UPDATE commission_orders SET status='Entregue' WHERE id=?", (order['id'],))
                        conn.commit()
                        
                        # Audit Log for Order fulfillment
                        audit.log_action(conn, 'UPDATE', 'commission_orders', order['id'], {'status': old_status}, {'status': 'Entregue'})
                        
                        success = True
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Erro: {e}")
                    
                    if success:
                        st.success("Entrega realizada com sucesso!")
                        st.balloons()
                        st.rerun()

conn.close()
