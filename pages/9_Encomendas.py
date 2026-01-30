import streamlit as st
import pandas as pd
import database
from datetime import date, datetime, timedelta
import admin_utils
import time

st.set_page_config(page_title="Encomendas", page_icon="📦")

admin_utils.render_sidebar_logo()
st.title("📦 Gestão de Encomendas")

if not admin_utils.check_password():
    st.stop()


conn = database.get_connection()
cursor = conn.cursor()

# --- TABS ---
tab_new, tab_list = st.tabs(["Nova Encomenda", "Gerenciar Encomendas"])

# ==============================================================================
# 1. NOVA ENCOMENDA (CARRINHO)
# ==============================================================================
with tab_new:
    st.subheader("Registrar Novo Pedido")
    
    if "cart_comm" not in st.session_state:
        st.session_state["cart_comm"] = []

    # 1. Header (Client, Date)
    col_h1, col_h2 = st.columns(2)
    
    # Load Clients
    clients = []
    try:
        clients_df = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
        clients = clients_df.to_dict('records')
    except: pass
    
    cli_names = [c['name'] for c in clients]
    sel_client_name = col_h1.selectbox("Cliente", cli_names, key="comm_cli")
    date_due = col_h2.date_input("Prazo de Entrega", value=date.today() + timedelta(days=15), key="comm_date")
    
    st.divider()
    
    # 2. Add Items
    st.write("🛒 **Adicionar Produtos**")
    
    # Load Products
    products = []
    prod_map = {}
    try:
        prods_df = pd.read_sql("SELECT id, name, stock_quantity, base_price FROM products ORDER BY name", conn)
        for _, row in prods_df.iterrows():
            label = f"{row['name']} (Est: {row['stock_quantity']}) - R$ {row['base_price']:.2f}"
            products.append(label)
            prod_map[label] = row
    except: pass
    
    c_add1, c_add2, c_add3, c_add4 = st.columns([3, 1, 1, 1])
    sel_prod = c_add1.selectbox("Selecione o Produto", products, key="comm_prod")
    qty_add = c_add2.number_input("Qtd", min_value=1, value=1, key="comm_qty")
    
    stock_avail = 0
    if sel_prod:
         stock_avail = prod_map[sel_prod]['stock_quantity']
    
    use_stock_chk = c_add3.checkbox("Usar Estoque?", key="comm_stock", help="Reserva do estoque atual")
    
    if c_add4.button("➕ Adicionar"):
        if sel_prod:
            p_data = prod_map[sel_prod]
            
            # Logic for reservation
            qty_res = 0
            if use_stock_chk:
                qty_res = min(stock_avail, qty_add)
            
            item = {
                "id": p_data['id'],
                "name": p_data['name'],
                "price": p_data['base_price'],
                "qty": qty_add,
                "qty_res": qty_res,
                "total": p_data['base_price'] * qty_add
            }
            st.session_state["cart_comm"].append(item)
            st.rerun()

    # 3. View Cart & Financials
    if st.session_state["cart_comm"]:
        st.write("---")
        st.write("📋 **Itens do Pedido:**")
        
        cart_df = pd.DataFrame(st.session_state["cart_comm"])
        
        # Display nicely
        for idx, item in enumerate(st.session_state["cart_comm"]):
            with st.container(border=True):
                ci1, ci2, ci3, ci4 = st.columns([4, 2, 2, 1])
                ci1.write(f"**{item['name']}**")
                ci2.write(f"{item['qty']} un (Reservar: {item['qty_res']})")
                ci3.write(f"R$ {item['total']:.2f}")
                if ci4.button("❌", key=f"rm_{idx}"):
                    st.session_state["cart_comm"].pop(idx)
                    st.rerun()
        
        # Totals
        subtotal = sum(i['total'] for i in st.session_state["cart_comm"])
        
        st.write("---")
        cf1, cf2, cf3 = st.columns(3)
        cf1.metric("Subtotal", f"R$ {subtotal:.2f}")
        
        manual_disc = cf2.number_input("Desconto (R$)", min_value=0.0, step=1.0, key="comm_disc")
        
        final_total = subtotal - manual_disc
        cf3.metric("Total Final", f"R$ {final_total:.2f}")
        
        if "comm_dep" not in st.session_state:
             st.session_state["comm_dep"] = final_total / 2

        # Update deposit if total changes (simple heuristic: if default 50% matches old total?)
        # Better: Just let user override. But if they add items, we should suggest new 50%.
        # We can track 'last_total' in session state to detect changes.
        if "last_comm_total" not in st.session_state:
            st.session_state["last_comm_total"] = final_total
            
        if st.session_state["last_comm_total"] != final_total:
             st.session_state["comm_dep"] = final_total / 2
             st.session_state["last_comm_total"] = final_total

        c_dep1, c_dep2 = st.columns(2)
        deposit_val = c_dep1.number_input("Sinal (50%)", value=st.session_state["comm_dep"], step=1.0, key="comm_dep")
        notes = c_dep2.text_area("Observações")
        
        if st.button("💾 Salvar Encomenda", type="primary"):
            if not sel_client_name:
                st.error("Selecione um Cliente.")
            else:
                client_id = next(c['id'] for c in clients if c['name'] == sel_client_name)
                
                success = False
                cursor.execute("BEGIN TRANSACTION")
                try:
                    # 1. Create Order
                    cursor.execute("""
                        INSERT INTO commission_orders (client_id, total_price, deposit_amount, manual_discount, 
                                                     date_created, date_due, status, notes)
                        VALUES (?, ?, ?, ?, ?, ?, 'Pendente', ?)
                    """, (client_id, final_total, deposit_val, manual_disc, date.today(), date_due, notes))
                    
                    new_order_id = cursor.lastrowid
                    
                    # 2. Insert Items & Reserve Stock
                    for item in st.session_state["cart_comm"]:
                        cursor.execute("""
                            INSERT INTO commission_items (order_id, product_id, quantity, quantity_from_stock, 
                                                        quantity_produced, unit_price)
                            VALUES (?, ?, ?, ?, 0, ?)
                        """, (new_order_id, item['id'], item['qty'], item['qty_res'], item['price']))
                        
                        # Reserve Stock
                        if item['qty_res'] > 0:
                            cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", 
                                         (item['qty_res'], item['id']))
                            
                    conn.commit()
                    success = True
                    st.session_state["cart_comm"] = []
                except Exception as e:
                    conn.rollback()
                    st.error(f"Erro ao salvar: {e}")
                
                if success:
                    st.success(f"Encomenda criada com sucesso!")
                    time.sleep(1)
                    st.rerun()

# ==============================================================================
# 2. GERENCIAR ENCOMENDAS
# ==============================================================================
with tab_list:
    st.subheader("Gerenciar Pedidos")
    
    # Logic to Delete Order (and restore stock)
    def delete_order(oid):
        # 1. Get reserved items to restore
        items = pd.read_sql(f"SELECT product_id, quantity_from_stock FROM commission_items WHERE order_id={oid}", conn)
        
        cursor.execute("BEGIN TRANSACTION")
        try:
            for _, it in items.iterrows():
                if it['quantity_from_stock'] > 0:
                    cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                                 (it['quantity_from_stock'], it['product_id']))
            
            cursor.execute("DELETE FROM commission_items WHERE order_id=?", (oid,))
            cursor.execute("DELETE FROM commission_orders WHERE id=?", (oid,))
            conn.commit()
            return True
        except:
            conn.rollback()
            return False

    # Fetch Orders
    orders = pd.read_sql("""
        SELECT o.id, c.name as client, o.date_due, o.status, o.total_price, o.notes, o.client_id,
               o.manual_discount, o.deposit_amount
        FROM commission_orders o
        JOIN clients c ON o.client_id = c.id
        ORDER BY o.date_due ASC
    """, conn)
    
    if orders.empty:
        st.info("Nenhuma encomenda registrada.")
    else:
        for _, order in orders.iterrows():
            with st.expander(f"📦 #{order['id']} - {order['client']} (Prazo: {pd.to_datetime(order['date_due']).strftime('%d/%m/%Y')}) - {order['status']}"):
                
                # Fetch Items
                items = pd.read_sql(f"""
                    SELECT ci.id, p.name, ci.quantity, ci.quantity_from_stock, ci.quantity_produced, ci.product_id, ci.unit_price
                    FROM commission_items ci
                    JOIN products p ON ci.product_id = p.id
                    WHERE ci.order_id = {order['id']}
                """, conn)
                
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

                st.divider()
                
                # Actions Row
                c_act1, c_act2, c_act3 = st.columns([2, 1, 1])
                
                # Add Item Button
                with c_act1:
                     with st.popover("➕ Adicionar Produto"):
                        with st.form(f"add_item_{order['id']}"):
                            # Load Products
                            try:
                                prods_df = pd.read_sql("SELECT id, name, stock_quantity, base_price FROM products ORDER BY name", conn)
                                prod_opts = [f"{r['name']} (R$ {r['base_price']:.2f})" for _, r in prods_df.iterrows()]
                            except: prod_opts = []
                            
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
                                    
                                    # Reserve Stock
                                    if qty_res_new > 0:
                                        cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", (int(qty_res_new), int(p_row['id'])))
                                    
                                    # Update Order Total
                                    cursor.execute("UPDATE commission_orders SET total_price = total_price + ? WHERE id=?", (price * new_qty, order['id']))
                                    
                                    conn.commit()
                                    success = True
                                except:
                                    conn.rollback()
                                
                                if success:
                                    st.success("Item adicionado!")
                                    st.rerun()                
                # Edit Order Button
                with c_act2:
                    with st.popover("✏️ Editar"):
                        with st.form(f"edit_ord_{order['id']}"):
                            new_date = st.date_input("Novo Prazo", value=pd.to_datetime(order['date_due']))
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
                            except: cli_list = []
                            
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
                
                st.divider()
                st.write("**Itens:**")
                
                all_complete = True
                
                for _, item in items.iterrows():
                    target_prod = item['quantity'] - item['quantity_from_stock']
                    
                    ci1, ci2, ci3 = st.columns([2, 2, 1.5])
                    with ci1:
                        st.write(f"• **{item['name']}**")
                        
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
                                        except: conn.rollback()
                                        
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
                                with st.popover(f"Lançar Produção ({item['id']})"):
                                    amount = st.number_input("Qtd", min_value=1, max_value=(target_prod - produced), key=f"prod_in_{item['id']}")
                                    if st.button("Confirmar", key=f"conf_{item['id']}"):
                                        # Deduct materials query...
                                        recipe = pd.read_sql(f"SELECT material_id, quantity FROM product_recipes WHERE product_id={item['product_id']}", conn)
                                        success = False
                                        cursor.execute("BEGIN TRANSACTION")
                                        try:
                                            # Update Materials
                                            for _, r in recipe.iterrows():
                                                 cursor.execute("UPDATE materials SET stock_level = stock_level - ? WHERE id=?", 
                                                              (r['quantity'] * amount, r['material_id']))
                                            
                                            # Update Item
                                            cursor.execute("UPDATE commission_items SET quantity_produced = quantity_produced + ? WHERE id=?", (amount, item['id']))
                                            cursor.execute("UPDATE commission_orders SET status='Em Produção' WHERE id=?", (order['id'],))
                                            conn.commit()
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
                                    cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                                                 (rest_qty, item['product_id']))
                                cursor.execute("DELETE FROM commission_items WHERE id=?", (item['id'],))
                                
                                # Recalc Total Price of Order
                                deduction = item['unit_price'] * item['quantity']
                                cursor.execute("UPDATE commission_orders SET total_price = total_price - ? WHERE id=?", 
                                             (deduction, order['id']))
                                
                                conn.commit()
                                success = True
                            except:
                                conn.rollback()
                            
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
                            for _, it in items.iterrows():
                                cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", 
                                             (it['quantity'], it['product_id']))
                            
                            # 2. Create Sale Record
                            import uuid
                            ord_uuid = f"ENC-{datetime.now().strftime('%y%m%d')}-{order['id']}"
                            
                            for _, it in items.iterrows():
                                cursor.execute("""
                                    INSERT INTO sales (date, product_id, quantity, total_price, status, client_id, 
                                                     discount, payment_method, notes, salesperson, order_id)
                                    VALUES (?, ?, ?, ?, 'Finalizada', ?, 0, 'Misto', ?, 'Sistema', ?)
                                """, (date.today(), it['product_id'], it['quantity'], (it['unit_price'] * it['quantity']), 
                                      order['client_id'], f"Encomenda #{order['id']}", ord_uuid))
                                
                                # 3. Deduct Stock (Sales Logic)
                                cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", 
                                             (it['quantity'], it['product_id']))
                            
                            # 4. Close Order
                            cursor.execute("UPDATE commission_orders SET status='Entregue' WHERE id=?", (order['id'],))
                            
                            conn.commit()
                            success = True
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Erro: {e}")
                        
                        if success:
                            st.success("Entrega realizada com sucesso!")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()

conn.close()
