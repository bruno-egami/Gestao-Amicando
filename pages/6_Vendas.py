import streamlit as st
import pandas as pd
import database
import admin_utils
import auth
import audit
import time
from datetime import datetime

st.set_page_config(page_title="Vendas", page_icon="💰")

admin_utils.render_sidebar_logo()

# Sales view matches logic: Salesperson can access this.
# But Admin can too.

auth.render_custom_sidebar()
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

# --- Application State ---
if 'cart' not in st.session_state:
    st.session_state['cart'] = []

if 'selected_product_id' not in st.session_state:
    st.session_state['selected_product_id'] = None

# --- Layout: 2 Columns (Catalog vs Cart/Checkout) ---
col_catalog, col_cart = st.columns([1.2, 0.8], gap="large")

# ==========================
# LEFT COL: CATALOG
# ==========================
with col_catalog:
    st.subheader("📦 Catálogo de Produtos")
    
    # --- Filters ---
    c_filt1, c_filt2 = st.columns([1, 1])
    search_term = c_filt1.text_input("🔍 Buscar Produto", placeholder="Nome do produto...")
    
    # Helper for images (Defined locally or globally)
    def get_valid_path(paths_str):
        try:
            p = eval(paths_str)
            if p and len(p) > 0: return p[0]
            return None
        except: return None

    # Compute Thumbs globally on products_df so it is available for selection
    if not products_df.empty:
        products_df['thumb_path'] = products_df['image_paths'].apply(get_valid_path)
    else:
        products_df['thumb_path'] = None

    # Get Categories from DB
    try:
        all_cats = pd.read_sql("SELECT name FROM product_categories", conn)['name'].tolist()
    except:
        all_cats = products_df['category'].dropna().unique().tolist()
        
    if all_cats:
        sel_cats = c_filt2.multiselect("📂 Filtrar Categoria", options=all_cats, placeholder="Todas")
    else:
        sel_cats = []

    # --- Apply Filters ---
    filtered_df = products_df.copy()
    
    if search_term:
        filtered_df = filtered_df[filtered_df['name'].str.contains(search_term, case=False, na=False)]
    
    if sel_cats:
        filtered_df = filtered_df[filtered_df['category'].isin(sel_cats)]
    
    if filtered_df.empty:
        st.warning("Nenhum produto encontrado.")
    else:
        # Grid Layout
        cols_per_row = 3
        rows = [filtered_df.iloc[i:i+cols_per_row] for i in range(0, len(filtered_df), cols_per_row)]
        
        for row_chunk in rows:
            cols = st.columns(cols_per_row)
            for idx, (c, product) in enumerate(zip(cols, row_chunk.itertuples())):
                with c:
                    with st.container(border=True):
                        # Image
                        # Image Logic (Handle Kits)
                        # Image Logic (Handle Kits)
                        # Start with product's own images
                        display_thumbs = []
                        if product.thumb_path:
                            display_thumbs.append(product.thumb_path)
                        
                        # ALways check for Kit Components to append their images
                        kit_children = pd.read_sql("SELECT child_product_id FROM product_kits WHERE parent_product_id=?", conn, params=(product.id,))
                        if not kit_children.empty:
                            c_ids = ",".join(map(str, kit_children['child_product_id'].tolist()))
                            c_imgs_df = pd.read_sql(f"SELECT image_paths FROM products WHERE id IN ({c_ids})", conn)
                            for _, ci_row in c_imgs_df.iterrows():
                                ci_list = eval(ci_row['image_paths']) if ci_row['image_paths'] else []
                                if ci_list: display_thumbs.extend(ci_list)
                        
                        # Limit to distinct images (simple dedup by path string)
                        seen = set()
                        unique_thumbs = []
                        for x in display_thumbs:
                            if x not in seen:
                                unique_thumbs.append(x)
                                seen.add(x)
                        
                        display_thumbs = unique_thumbs[:3] # Show max 3 mixed images

                        if display_thumbs:
                            # Cannot nest columns > 2 levels (CatalogCol -> GridCol -> ImageCol is too deep)
                            # Passing list to st.image renders them (stacked vertically usually, but ensures visibility)
                            st.image(display_thumbs, use_container_width=True)
                        elif display_thumb:
                             st.image(display_thumb, use_container_width=True)
                        else:
                            st.markdown("🖼️ *Sem Foto*")
                        
                        # Stock Logic (Handle Kits)
                        display_stock = product.stock_quantity
                        is_kit = False
                        
                        # Check Kit Stock
                        kit_stock_df = pd.read_sql("""
                            SELECT pk.quantity, p.stock_quantity as child_stock 
                            FROM product_kits pk
                            JOIN products p ON pk.child_product_id = p.id
                            WHERE pk.parent_product_id = ?
                        """, conn, params=(product.id,))
                        
                        if not kit_stock_df.empty:
                            is_kit = True
                            kit_stock_df['max'] = kit_stock_df['child_stock'] // kit_stock_df['quantity']
                            display_stock = int(kit_stock_df['max'].min())
                            if display_stock < 0: display_stock = 0
                            
                        st.markdown(f"**{product.name}**")
                        stock_txt = f"📦 Kit: {display_stock}" if is_kit else f"Est: {product.stock_quantity}"
                        st.caption(f"ID: {product.id} | {stock_txt}")
                        st.markdown(f"**R$ {product.base_price:.2f}**")
                        
                        # Selection Logic
                        is_selected = (st.session_state['selected_product_id'] == product.id)
                        if st.button("Selecionar", key=f"btn_sel_{product.id}", 
                                     type="primary" if is_selected else "secondary",
                                     use_container_width=True):
                            st.session_state['selected_product_id'] = product.id
                            st.rerun()

# ==========================
# RIGHT COL: CART & ACTION
# ==========================
with col_cart:
    # A. ITEM FORM (If product selected)
    if st.session_state['selected_product_id']:
        sel_row = products_df[products_df['id'] == st.session_state['selected_product_id']].iloc[0]
        
        with st.container(border=True):
            st.markdown(f"### Adicionar: {sel_row['name']}")
            
            c_qty, c_disc = st.columns(2)
            item_qty = c_qty.number_input("Qtd", min_value=1, step=1, value=1, key="item_qty")
            item_disc = c_disc.number_input("Desconto (Item)", min_value=0.0, step=0.1, value=0.0, key="item_disc")
            
            # Calc Preview
            base_total = sel_row['base_price'] * item_qty
            item_final = max(0.0, base_total - item_disc)
            
            st.write(f"Total Item: **R$ {item_final:.2f}**")
            
            # Check cart for this product
            in_cart = sum(i['qty'] for i in st.session_state['cart'] if i['product_id'] == sel_row['id'])
            
            # Helper to get Real Stock (Kit aware)
            real_stock = sel_row['stock_quantity']
            
            # Check Kit Stock (Quick Query)
            ks_df = pd.read_sql("""
                SELECT pk.quantity, p.stock_quantity as child_stock 
                FROM product_kits pk
                JOIN products p ON pk.child_product_id = p.id
                WHERE pk.parent_product_id = ?
            """, conn, params=(sel_row['id'],))
            
            if not ks_df.empty:
                ks_df['max'] = ks_df['child_stock'] // ks_df['quantity']
                real_stock = int(ks_df['max'].min())
                if real_stock < 0: real_stock = 0

            if st.button("➕ Adicionar ao Carrinho", type="primary", use_container_width=True):
                if (in_cart + item_qty) > real_stock:
                    st.error(f"Estoque insuficiente! (Disponível: {real_stock}, No Carrinho: {in_cart})")
                else:
                    # Add to Cart
                    cart_item = {
                        "product_id": sel_row['id'],
                        "product_name": sel_row['name'],
                        "thumb": sel_row['thumb_path'],
                        "qty": item_qty,
                        "base_price": sel_row['base_price'],
                        "discount": item_disc,
                        "total": item_final
                    }
                    st.session_state['cart'].append(cart_item)
                    st.session_state['selected_product_id'] = None # Deselect
                    st.rerun()

    # B. CART DISPLAY
    st.divider()
    st.subheader(f"🛒 Carrinho ({len(st.session_state['cart'])})")
    
    if st.session_state['cart']:
        # Convert to DF for editor (allow delete)
        cart_df = pd.DataFrame(st.session_state['cart'])
        
        # Interactive Editor to allow deletion
        edited_cart = st.data_editor(
            cart_df,
            column_config={
                "product_name": st.column_config.TextColumn("Produto", width="medium"),
                "qty": st.column_config.NumberColumn("Qtd", width="small"),
                "total": st.column_config.NumberColumn("Total", format="R$ %.2f", width="small"),
                "product_id": None, "thumb": None, "base_price": None, "discount": None # Hide internals
            },
            num_rows="dynamic", # Allow delete
            hide_index=True,
            use_container_width=True,
            key="cart_editor"
        )
        
        # Sync Deletions
        if len(edited_cart) < len(st.session_state['cart']):
            # Rebuild cart from edited_cart data to allow deletion
            # But data_editor returns a dataframe. We need to convert back to list of dicts.
            # However, data_editor modifications (edits) are complex.
            # Simplification: Just overwrite cart with edited data (if just deleted/qty changed).
            st.session_state['cart'] = edited_cart.to_dict('records')
            st.rerun()
        
        # Total Cart
        cart_total = sum(item['total'] for item in st.session_state['cart'])
        st.markdown(f"## Total Pedido: R$ {cart_total:.2f}")
        
        st.divider()
        st.markdown("### 📝 Dados do Pedido")
        
        with st.form("checkout_form"):
            # Order Details
            cli_choice = st.selectbox("Cliente", client_opts + ["++ Cadastrar Novo ++"])
            
            new_cli_name = None
            new_cli_phone = None
            if cli_choice == "++ Cadastrar Novo ++":
                c_nc1, c_nc2 = st.columns(2)
                new_cli_name = c_nc1.text_input("Nome Completo", placeholder="Nome do Cliente")
                new_cli_phone = c_nc2.text_input("Telefone", placeholder="(XX) 99999-9999")
            
            salesperson_choice = st.selectbox("Vendedora", ["", "Ira", "Neli"])
            pay_method_choice = st.selectbox("Pagamento", ["Pix", "Cartão Crédito", "Cartão Débito", "Dinheiro", "Outro"])
            notes_order = st.text_area("Observações Gerais")
            date_order = st.date_input("Data do Pedido", datetime.now())
            
            if st.form_submit_button("✅ Finalizar Venda", type="primary", use_container_width=True):
                # 1. Validate Client
                final_client_id = None
                final_client_name = None
                
                if cli_choice == "++ Cadastrar Novo ++":
                    if not new_cli_name:
                        st.error("Digite o nome do novo cliente.")
                    else:
                        # Create Client
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO clients (name, phone) VALUES (?, ?)", (new_cli_name, new_cli_phone))
                        conn.commit()
                        final_client_id = cursor.lastrowid
                        final_client_name = new_cli_name
                elif not cli_choice:
                    st.error("Selecione o Cliente.")
                else:
                    final_client_id = client_dict[cli_choice]
                    final_client_name = cli_choice

                # 2. Validate Other Fields
                if final_client_id and not salesperson_choice:
                    st.error("Selecione a Vendedora.")
                elif final_client_id and salesperson_choice:
                    # PROCESS ORDER
                    import uuid
                    # Generate unique Order ID for this transaction
                    # Short ID for readability or UUID? user wants to see it. 
                    # Let's use a simpler timestamp based or short UUID.
                    # e.g ORD-YYYYMMDD-XXXX
                    order_uuid = f"ORD-{datetime.now().strftime('%y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
                    
                    cursor = conn.cursor()
                    
                    # Iterate Items
                    for item in st.session_state['cart']:
                        cursor.execute("""
                            INSERT INTO sales (date, product_id, quantity, total_price, status, client_id, discount, payment_method, notes, salesperson, order_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (date_order, int(item['product_id']), item['qty'], item['total'], "Finalizada", final_client_id, item['discount'], pay_method_choice, notes_order, salesperson_choice, order_uuid))
                        
                        # Get inserted sale ID for audit
                        sale_id = cursor.lastrowid
                        
                        # Audit log for sale creation
                        audit.log_action(conn, 'CREATE', 'sales', sale_id, None, {
                            'product_id': item.get('product_id'), 
                            'product_name': item.get('product_name') or item.get('product', 'Desconhecido'), 
                            'quantity': item.get('qty', 0),
                            'total_price': item.get('total', 0), 
                            'client_id': final_client_id, 
                            'payment_method': pay_method_choice
                        })
                        
                        # Stock Update Logic (Handle Kits)
                        p_id = int(item['product_id'])
                        q_sold = item['qty']
                        
                        # Check if it's a Kit
                        kit_comps = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn, params=(p_id,))
                        
                        if not kit_comps.empty:
                            # It is a Kit: Deduct from components
                            for _, kc in kit_comps.iterrows():
                                deduct_qty = q_sold * kc['quantity']
                                cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?",
                                               (deduct_qty, kc['child_product_id']))
                        else:
                            # Standard Product: Deduct directly
                            cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?",
                                           (q_sold, p_id))
                    
                    conn.commit()
                    
                    # Save Receipt Data
                    st.session_state['last_order'] = {
                        "id": order_uuid,
                        "client": final_client_name,
                        "salesperson": salesperson_choice,
                        "items": st.session_state['cart'],
                        "total": cart_total,
                        "time": datetime.now().strftime("%H:%M:%S")
                    }
                    
                    # Clear Cart
                    st.session_state['cart'] = []
                    st.rerun()
                    
    else:
        st.info("Seu carrinho está vazio.")

# --- Receipt Section (Order Level) ---
# --- Receipt Section (Order Level) ---
if 'last_order' in st.session_state:
    lo = st.session_state['last_order']
    
    # Using container for Receipt instead of experimental dialog
    with st.container(border=True):
        st.success("✅ Pedido Finalizado!")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.write(f"**Cliente:** {lo['client']}")
            st.write(f"**Vendedora:** {lo['salesperson']}")
        with col_r2:
            st.metric("Total", f"R$ {lo['total']:.2f}")
            
        st.caption("Itens:")
        for item in lo['items']:
             st.text(f"{item['qty']}x {item['product_name']} (R$ {item['total']:.2f})")
             
        if st.button("Nova Venda (Limpar Comprovante)"):
             del st.session_state['last_order']
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
            SELECT s.id, s.order_id, s.date, c.name as cliente, p.name as produto, s.quantity, s.total_price, 
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
        
        # TOGGLE VIEW
        group_by_order = st.checkbox("📂 Agrupar por Pedido", value=True)
        
        if not sales_view.empty:
            # Fix Date Type
            sales_view['date'] = pd.to_datetime(sales_view['date'])
            
            # --- GROUPED VIEW LOGIC ---
            if group_by_order:
                # Aggregate
                grouped = sales_view.groupby('order_id').agg({
                    'date': 'first',
                    'cliente': 'first',
                    'produto': lambda x: ", ".join(x),
                    'quantity': 'sum',
                    'total_price': 'sum',
                    'salesperson': 'first',
                    'payment_method': 'first',
                    'notes': 'first',
                    'id': 'first' # Just for key
                }).reset_index()
                
                # Sort by date
                grouped = grouped.sort_values(by='date', ascending=False)
                
                st.data_editor(
                    grouped,
                    column_config={
                        "order_id": st.column_config.TextColumn("Pedido", disabled=True),
                        "date": st.column_config.DateColumn("Data", disabled=True, format="DD/MM/YYYY"),
                        "cliente": "Cliente",
                        "produto": st.column_config.TextColumn("Produtos", disabled=True),
                        "quantity": st.column_config.NumberColumn("Qtd Itens", disabled=True),
                        "total_price": st.column_config.NumberColumn("Total", format="R$ %.2f", disabled=True),
                        "id": None # Hide ID
                    },
                    hide_index=True,
                    key="grouped_sales_editor"
                )
                st.caption("ℹ️ Para editar ou excluir itens individuais, desmarque 'Agrupar por Pedido'.")
            
            else:
                # --- DETAILED VIEW (Original) ---
                # Add Delete col
                sales_view['remove'] = False 
                
                # Display Editor
                edited_sales = st.data_editor(
                sales_view,
                column_config={
                    "id": st.column_config.NumberColumn(disabled=True),
                    "order_id": st.column_config.TextColumn("Pedido", disabled=True, width="medium"),
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
                            
                            # Capture for audit before delete
                            old_data = {'id': did, 'quantity': q_restore, 'product_id': p_id, 'total_price': orig_row['total_price']}
                            
                            cursor.execute("DELETE FROM sales WHERE id=?", (did,))
                            
                            # RESTORE STOCK LOGIC (HANDLE KITS)
                            kit_restore = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn, params=(p_id,))
                            
                            if not kit_restore.empty:
                                for _, kr in kit_restore.iterrows():
                                    restore_qty = q_restore * kr['quantity']
                                    cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (restore_qty, kr['child_product_id']))
                            else:
                                cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (int(q_restore), int(p_id)))
                            
                            # Audit log for sale deletion
                            audit.log_action(conn, 'DELETE', 'sales', did, old_data, None)

                    # 2. Handle Updates (Date, Salesperson, Payment, Notes)
                    for i, row in edited_sales.iterrows():
                        if row['id'] and row['id'] not in all_deletes:
                            # Fix Date binding (Pandas Timestamp -> Python Date/String)
                            dv = row['date']
                            if hasattr(dv, 'date'):
                                dv = dv.date()
                            
                            cursor.execute("""
                                UPDATE sales SET date=?, salesperson=?, payment_method=?, notes=?
                                WHERE id=?
                            """, (dv, row['salesperson'], row['payment_method'], row['notes'], row['id']))
                    
                    conn.commit()
                    st.success("Histórico atualizado com sucesso!")
                    time.sleep(1)
                    st.rerun()
        
        else:
            st.info("Nenhuma venda encontrada com estes filtros.")

conn.close()
