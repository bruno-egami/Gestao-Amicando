import streamlit as st
import pandas as pd
import database
import admin_utils
from datetime import datetime

st.set_page_config(page_title="Vendas", page_icon="💰")

# Sales view matches logic: Salesperson can access this.
# But Admin can too.

st.title("Frente de Vendas")

conn = database.get_connection()

# --- New Sale ---
# --- New Sale ---
# --- New Sale ---
# --- New Sale ---
# 1. Select Client (Global fetch for Form and History)
clients_df = pd.read_sql("SELECT id, name FROM clients", conn)
client_dict = {row['name']: row['id'] for _, row in clients_df.iterrows()}
client_opts = [""] + list(client_dict.keys())

# 2. Select Product (Visual Catalog) - OUTSIDE FORM for interactivity
products_df = pd.read_sql("SELECT id, name, base_price, stock_quantity, image_paths, category FROM products", conn)

with st.expander("Nova Venda", expanded=True):
    
    if products_df.empty:
        st.warning("Sem produtos.")
        sel_row = None
    else:
        st.markdown("### 1. Selecione o Produto:")
        
        # Prepare helper for images
        def get_valid_path(paths_str):
            try:
                p = eval(paths_str)
                if p and len(p) > 0: return p[0]
                return None
            except: return None
            
        products_df['thumb_path'] = products_df['image_paths'].apply(get_valid_path)
        
        # --- Grid Layout Selector ---
        # Initialize selection state if needed (using query params logic or session state for selection?)
        # Simply use buttons that set a session state 'selected_product_id'
        
        if 'selected_product_id' not in st.session_state:
            st.session_state['selected_product_id'] = None
            
        # Display in chunks of 4 columns
        cols_per_row = 4
        rows = [products_df.iloc[i:i+cols_per_row] for i in range(0, len(products_df), cols_per_row)]
        
        for row_chunk in rows:
            cols = st.columns(cols_per_row)
            for idx, (c, product) in enumerate(zip(cols, row_chunk.itertuples())):
                with c:
                    with st.container(border=True):
                        # Image
                        if product.thumb_path:
                            st.image(product.thumb_path, use_container_width=True)
                        else:
                            st.markdown("🖼️ *Sem Foto*")
                        
                        st.markdown(f"**{product.name}**")
                        st.caption(f"{product.category} | Est: {product.stock_quantity}")
                        st.markdown(f"**R$ {product.base_price:.2f}**")
                        
                        # Selection Button
                        # Logic: If this product is selected, show "Selected" styling or disabled button?
                        is_selected = (st.session_state['selected_product_id'] == product.id)
                        if st.button("Selecionar" if not is_selected else "✅ Selecionado", 
                                     key=f"btn_sel_{product.id}", 
                                     type="primary" if is_selected else "secondary"):
                            st.session_state['selected_product_id'] = product.id
                            st.rerun()

        # Resolve selected row from Session State
        if st.session_state['selected_product_id']:
            sel_row = products_df[products_df['id'] == st.session_state['selected_product_id']].iloc[0]
        else:
            sel_row = None
            st.info("👆 Clique em 'Selecionar' no produto desejado.")

    # 3. Form (Only shows if product selected)
    if sel_row is not None:
        st.divider()
        st.markdown(f"**Produto Selecionado:** {sel_row['name']} (Estoque: {sel_row['stock_quantity']})")
        
        # Store temporary preview
        if 'pending_sale' not in st.session_state:
            st.session_state['pending_sale'] = None
            
        with st.form("new_sale_form"):
            default_client_idx = 0
            # Try to persist client choice if in pending
            if st.session_state['pending_sale']:
                try: default_client_idx = client_opts.index(st.session_state['pending_sale']['client_name'])
                except: pass
                
            client_choice = st.selectbox("Cliente", client_opts, index=default_client_idx)
            
            c1, c2 = st.columns(2)
            qty = c1.number_input("Quantidade", min_value=1, step=1, value=1)
            salesperson = c2.selectbox("Vendedora", ["", "Ira", "Neli"])
            
            c3, c4 = st.columns(2)
            discount = c3.number_input("Desconto (R$)", min_value=0.0, step=0.1, value=0.0)
            pay_method = c4.selectbox("Forma de Pagamento", ["Pix", "Cartão Crédito", "Cartão Débito", "Dinheiro", "Outro"])
            
            notes = st.text_area("Observações", height=1)
            date_sale = st.date_input("Data da Venda", datetime.now())
            
            # Calc
            item_total = sel_row['base_price'] * qty
            final_total = max(0.0, item_total - discount)
            
            st.markdown(f"### Total Final: **R$ {final_total:.2f}**")
            
            # Button 1: Review
            if st.form_submit_button("Revisar Pedido"):
                if not client_choice:
                    st.error("Selecione o Cliente.")
                elif not salesperson:
                    st.error("Selecione a Vendedora.")
                elif sel_row['stock_quantity'] < qty:
                    st.error(f"Estoque insuficiente! Disponível: {sel_row['stock_quantity']}")
                else:
                    # Save to Pending State
                    st.session_state['pending_sale'] = {
                        "date": date_sale,
                        "product_id": int(sel_row['id']),
                        "product_name": sel_row['name'],
                        "product_thumb": sel_row['thumb_path'], # Save thumb
                        "qty": qty,
                        "total": final_total,
                        "client_name": client_choice,
                        "client_id": client_dict[client_choice],
                        "discount": discount,
                        "payment": pay_method,
                        "notes": notes,
                        "salesperson": salesperson
                    }
                    st.rerun()

    # 4. Confirmation Section (Outside Form)
    if st.session_state.get('pending_sale'):
        ps = st.session_state['pending_sale']
        
        # Check if product matches currently selected (sanity check)
        if sel_row is None or ps['product_id'] != sel_row['id']:
             st.warning("Produto alterado. Revise o pedido.")
             st.session_state['pending_sale'] = None
             st.rerun()
        
        with st.container(border=True):
            st.markdown("### 📝 Confirmar Detalhes da Venda")
            c_conf1, c_conf2 = st.columns([1, 2])
            with c_conf1:
                if ps.get('product_thumb'):
                    st.image(ps['product_thumb'], use_container_width=True)
                else:
                    st.write("🖼️ *Sem Foto*")
            
            with c_conf2:
                st.write(f"**Produto:** {ps['product_name']}")
                st.write(f"**Cliente:** {ps['client_name']}")
                st.write(f"**Vendedora:** {ps['salesperson']}")
                st.write(f"**Qtd:** {ps['qty']}")
                st.write(f"**Total:** R$ {ps['total']:.2f}")
                st.write(f"**Pagamento:** {ps['payment']}")
            
            c_btn1, c_btn2 = st.columns(2)
            if c_btn1.button("✅ CONFIRMAR VENDA", type="primary", use_container_width=True):
                # Save to DB
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sales (date, product_id, quantity, total_price, status, client_id, discount, payment_method, notes, salesperson)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (ps['date'], ps['product_id'], ps['qty'], ps['total'], "Finalizada", ps['client_id'], ps['discount'], ps['payment'], ps['notes'], ps['salesperson']))
                
                # Update Stock
                cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?",
                               (ps['qty'], ps['product_id']))
                
                conn.commit()
                
                # Move to Receipt
                st.session_state['last_sale'] = {
                    "product": ps['product_name'],
                    "thumb": ps['product_thumb'],
                    "qty": ps['qty'],
                    "salesperson": ps['salesperson'],
                    "total": ps['total'],
                    "client": ps['client_name'],
                    "time": datetime.now().strftime("%H:%M:%S")
                }
                st.session_state['pending_sale'] = None # Clear pending
                st.session_state['selected_product_id'] = None # Clear Selection to reset flow
                st.rerun()
            
            if c_btn2.button("❌ Cancelar / Editar", use_container_width=True):
                st.session_state['pending_sale'] = None
                st.rerun()

# --- Receipt Section ---
if 'last_sale' in st.session_state:
    ls = st.session_state['last_sale']
    with st.container(border=True):
        st.success("✅ Venda Realizada com Sucesso!")
        
        rc1, rc2 = st.columns([1, 3])
        with rc1:
            if ls.get('thumb'):
                st.image(ls['thumb'], use_container_width=True)
                
        with rc2:
            st.markdown(f"""
            **Resumo da Transação**:
            - **Produto**: {ls['product']} (x{ls['qty']})
            - **Cliente**: {ls['client']}
            - **Total**: **R$ {ls['total']:.2f}**
            - **Vendedora**: {ls['salesperson']}
            
            *Registrado às {ls['time']}*
            """)
            
        # Button to clear receipt
        if st.button("Nova Venda (Limpar)", type="primary"):
            del st.session_state['last_sale']
            st.rerun()


# --- History & Edit ---
    st.divider()
    
    # Secure History
    with st.expander("🔐 Histórico de Vendas (Área Restrita)"):
        if admin_utils.check_password():
            st.subheader("Gerenciar Vendas")
            
            # Filters
            fc1, fc2, fc3, fc4 = st.columns(4)
            fil_date = fc1.date_input("Período", [], key="hist_dates")
            fil_client = fc2.selectbox("Cliente", client_opts, key="hist_cli")
            fil_pay = fc3.selectbox("Pagamento", ["Todas"] + ["Pix", "Cartão Crédito", "Cartão Débito", "Dinheiro", "Outro"], key="hist_pay")
            fil_salesp = fc4.selectbox("Vendedora", ["Todas", "Ira", "Neli"], key="hist_sp")
            
            # Query Construction
            query = """
                SELECT s.id, s.date, c.name as cliente, p.name as produto, s.quantity, s.total_price, 
                       s.salesperson, s.payment_method, s.discount, s.notes, s.product_id
                FROM sales s
                LEFT JOIN clients c ON s.client_id = c.id
                JOIN products p ON s.product_id = p.id
                WHERE 1=1
            """
            params = []
            
            if len(fil_date) == 2:
                query += " AND s.date BETWEEN ? AND ?"
                params.append(fil_date[0])
                params.append(fil_date[1])
            if fil_client:
                query += " AND c.name = ?"
                params.append(fil_client)
            if fil_pay != "Todas":
                query += " AND s.payment_method = ?"
                params.append(fil_pay)
            if fil_salesp != "Todas":
                query += " AND s.salesperson = ?"
                params.append(fil_salesp)
            
            query += " ORDER BY s.date DESC"
            
            sales_view = pd.read_sql(query, conn, params=params)
            
            if not sales_view.empty:
                # Fix Date Type
                sales_view['date'] = pd.to_datetime(sales_view['date'])
                
                # Add Delete col
                sales_view['remove'] = False 
                
                # Display Editor
                edited_sales = st.data_editor(
                    sales_view,
                    column_config={
                        "id": st.column_config.NumberColumn(disabled=True),
                        "date": st.column_config.DateColumn("Data"),
                        "cliente": st.column_config.TextColumn("Cliente", disabled=True), # Simplify client edit to avoid ID complex logic or allow? Let's keep disabled for safety or just Text. Actually user might want to edit. But Selectbox logic in editor is tricky if not mapped perfectly. Let's keep Read-Only for Client Name in History for now or use Selectbox if easy.
                        # Using Text for Client Name (Not ID) means we can't easily change client ID back. 
                        # Ideally we load Client Name. If they change Name, it doesn't change ID. 
                        # We need client_id in query to allow re-assignment? 
                        # Let's keep it simple: Read Only meta data, allow Date/Notes edit.
                        
                        "produto": st.column_config.TextColumn("Produto", disabled=True),
                        "quantity": st.column_config.NumberColumn("Qtd", disabled=True),
                        "total_price": st.column_config.NumberColumn("Total", format="R$ %.2f", disabled=True),
                        "salesperson": st.column_config.SelectboxColumn("Vendedora", options=["Ira", "Neli"]),
                        "payment_method": st.column_config.SelectboxColumn("Pagamento", options=["Pix", "Cartão Crédito", "Cartão Débito", "Dinheiro", "Outro"]),
                        "discount": st.column_config.NumberColumn("Desc.", format="R$ %.2f", disabled=True),
                        "notes": st.column_config.TextColumn("Obs"),
                        
                        "product_id": st.column_config.NumberColumn(disabled=True, width=None), 
                        "remove": st.column_config.CheckboxColumn("Cancelar?", help="Estorna estoque")
                    },
                    hide_index=True,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="sales_editor"
                )
                
                if st.button("Salvar Alterações (Histórico)"):
                    cursor = conn.cursor()
                    
                    # 1. Handle Cancellations
                    to_delete_ids = set(edited_sales[edited_sales['remove'] == True]['id'])
                    
                    orig_ids = set(sales_view['id'])
                    present_ids = set(edited_sales[edited_sales['id'].notna()]['id'])
                    missing_ids = orig_ids - present_ids
                    all_deletes = to_delete_ids.union(missing_ids)
                    
                    if all_deletes:
                        for did in all_deletes:
                            orig_row = sales_view[sales_view['id'] == did].iloc[0]
                            q_restore = orig_row['quantity']
                            p_id = orig_row['product_id']
                            cursor.execute("DELETE FROM sales WHERE id=?", (did,))
                            cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (int(q_restore), int(p_id)))

                    # 2. Handle Updates (Date, Salesperson, Payment, Notes)
                    for i, row in edited_sales.iterrows():
                        if row['id'] and row['id'] not in all_deletes:
                            cursor.execute("""
                                UPDATE sales SET date=?, salesperson=?, payment_method=?, notes=?
                                WHERE id=?
                            """, (row['date'], row['salesperson'], row['payment_method'], row['notes'], row['id']))
                    
                    conn.commit()
                    st.success("Histórico atualizado!")
                    st.rerun()

            else:
                st.info("Nenhuma venda encontrada com estes filtros.")
    
    conn.close()
