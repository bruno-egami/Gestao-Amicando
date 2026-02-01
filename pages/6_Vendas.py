import streamlit as st
import pandas as pd
import database
import admin_utils
import auth
import audit
import reports
import time
import uuid
from datetime import datetime, date

st.set_page_config(page_title="Vendas", page_icon="💰")

admin_utils.render_sidebar_logo()

# Sales view matches logic: Salesperson can access this.
# But Admin can too.

conn = database.get_connection()

if not auth.require_login(conn):
    st.stop()

if not auth.check_page_access("Vendas"):
    st.stop()

auth.render_custom_sidebar()
st.title("Frente de Vendas")

# --- Receipt Dialog (Top Level) ---
@st.dialog("🎉 Pedido Concluído")
def show_receipt_dialog(order_data):
    st.subheader(f"#{order_data.get('id', '---')}")
    st.markdown(f"**Cliente:** {order_data['client']}")
    st.markdown(f"**Vendedora:** {order_data['salesperson']}")
    st.metric("Total", f"R$ {order_data['total']:.2f}")
    
    st.divider()
    st.markdown("### Itens:")
    for item in order_data['items']:
         st.text(f"{item['qty']}x {item['product_name']} (R$ {item['total']:.2f})")
    
    # Custom Close Logic
    if st.button("Fechar e Nova Venda", key="btn_close_receipt", type="primary", use_container_width=True):
        if 'last_order' in st.session_state:
            del st.session_state['last_order']
        st.rerun()

    # PDF Download
    try:
        # Prepare data for report
        # Needs: id, date, client_name, items, total, discount, deposit
        
        # Calculate totals from items if not explicit
        # But order_data has total.
        
        rep_data = {
            "id": order_data.get('id', '???'),
            "type": "Encomenda" if str(order_data.get('id', '')).startswith('ENC') else "Venda",
            "date": datetime.now().strftime("%d/%m/%Y"),
            "client_name": order_data.get('client', 'Cliente'),
            "salesperson": order_data.get('salesperson', '-'),
            "payment_method": order_data.get('payment_method', '-'), # Need to ensure this is passed/available
            "notes": order_data.get('notes', ''), # Need to ensure this is passed
            "date_due": order_data.get('date_due', None),
            "items": [],
            "total": order_data.get('total', 0),
            "discount": 0, # Not carried over easily in session state currently, maybe add to session state later
            "deposit": order_data.get('deposit', 0)
        }
        
        # Items
        for item in order_data['items']:
            rep_data['items'].append({
                "name": item['product_name'],
                "qty": item['qty'],
                "price": item['base_price']
            })
            
        pdf_bytes = reports.generate_receipt_pdf(rep_data)
        
        st.download_button(
            label="📄 Baixar Recibo (PDF)",
            data=pdf_bytes,
            file_name=f"recibo_{order_data.get('id')}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")

if 'last_order' in st.session_state:
    show_receipt_dialog(st.session_state['last_order'])

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
col_catalog, col_cart = st.columns([1, 1], gap="large")

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
        with st.container(height=800): # Scrollable Catalog
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
                # Validar estoque (Apenas aviso, permitir encomenda)
                if (in_cart + item_qty) > real_stock:
                    st.warning(f"⚠️ Pedido ({in_cart + item_qty}) excede estoque ({real_stock}). O excedente entrará como Encomenda.")
                
                # Add to Cart (Always allowed)
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
        
        # Add Exclude Column if not exists
        if 'exclude' not in cart_df.columns:
            cart_df['exclude'] = False

        # Interactive Editor to allow deletion
        # Wrap TABLE in scrollable container to prevent long lists taking over
        with st.container(height=400):
            edited_cart = st.data_editor(
                cart_df,
                column_config={
                    "product_name": st.column_config.TextColumn("Produto", width="medium", disabled=True),
                    "qty": st.column_config.NumberColumn("Qtd", width="small"),
                    "total": st.column_config.NumberColumn("Total", format="R$ %.2f", width="small", disabled=True),
                    "exclude": st.column_config.CheckboxColumn("🗑️", help="Marque para excluir do carrinho"),
                    "product_id": None, "thumb": None, "base_price": None, "discount": None # Hide internals
                },
                num_rows="fixed", # Disable native add/delete to avoid confusion
                hide_index=True,
                use_container_width=True,
                key="cart_editor"
            )
        
        # Sync Logic
        new_cart_data = edited_cart.to_dict('records')
        
        # 1. Reconstruct clean cart (remove deleted, strip exclude key)
        final_cart = []
        has_deletion = False
        
        for item in new_cart_data:
            if item.get('exclude', False):
                has_deletion = True
                continue # Skip -> Deleted
            
            # Clean item for comparison/storage
            clean_item = item.copy()
            if 'exclude' in clean_item: del clean_item['exclude']
            final_cart.append(clean_item)
            
        # 2. Compare with current valid state
        # This prevents infinite loop because we compare "Cleaned New" vs "Cleaned Old"
        if final_cart != st.session_state['cart']:
            # Recalculate totals (in case Qty changed)
            for item in final_cart:
                # Basic price reclac
                item['total'] = item['qty'] * item['base_price']
            
            st.session_state['cart'] = final_cart
            st.rerun()
        
        # Total Cart
        cart_total = sum(item['total'] for item in st.session_state['cart'])
        st.markdown(f"## Total Pedido: R$ {cart_total:.2f}")
        
        st.divider()
        st.markdown("### 📝 Dados do Pedido")
        
        # Order Details: Direct Inputs (No Form to allow branching logic)
        with st.container(border=False):
            # Order Details
            cli_choice = st.selectbox("Cliente", client_opts + ["++ Cadastrar Novo ++"])
            
            new_cli_name = None
            new_cli_phone = None
            if cli_choice == "++ Cadastrar Novo ++":
                c_nc1, c_nc2 = st.columns(2)
                new_cli_name = c_nc1.text_input("Nome Completo", placeholder="Nome do Cliente")
                new_cli_phone = c_nc2.text_input("Telefone", placeholder="(XX) 99999-9999")
            
            # Auto-fill salesperson from loggedin user
            current_u = auth.get_current_user()
            u_name = current_u['name'] if current_u else "Desconhecido"
            salesperson_choice = st.text_input("Vendedora", value=u_name, disabled=True)
            pay_method_choice = st.selectbox("Pagamento", ["Pix", "Cartão Crédito", "Cartão Débito", "Dinheiro", "Outro"])
            notes_order = st.text_area("Observações Gerais")
            date_order = st.date_input("Data do Pedido", datetime.now())
            
            # 1. Client Creation Logic (Run immediately if needed or defer? Defer to button click is safer to avoid accidental creates)
            # Actually, Client Validations should happen inside the Action Buttons. 
            
            # 2. START ANALYSIS (Always Run to show status)
            if True: 
                # 1. Validate Client (Just for UI feedback, not blocking yet)
                # ...
                # 1. Validate Client (Deferred to Button Click)
                # Logic moved inside buttons to prevent accidental creation
                pass

                # 2. Start Finalization Process (Check Stock)
                shortages = []
                has_shortage = False
                
                # Pre-calculate shortages for decision
                cart_analysis = []
                for item in st.session_state['cart']:
                    # Get Real Stock
                    r_stock = 0
                    p_id_check = int(item['product_id'])
                    
                    # Check Kit
                    k_check = pd.read_sql("SELECT pk.quantity, p.stock_quantity as child_stock FROM product_kits pk JOIN products p ON pk.child_product_id = p.id WHERE pk.parent_product_id=?", conn, params=(p_id_check,))
                    
                    p_stock_row = pd.read_sql("SELECT stock_quantity FROM products WHERE id=?", conn, params=(p_id_check,))
                    
                    if not k_check.empty:
                        k_check['max'] = k_check['child_stock'] // k_check['quantity']
                        r_stock = int(k_check['max'].min())
                        if r_stock < 0: r_stock = 0
                    elif not p_stock_row.empty:
                        r_stock = p_stock_row.iloc[0]['stock_quantity']
                    
                    qty_req = item['qty']
                    can_sell = min(r_stock, qty_req)
                    must_order = max(0, qty_req - r_stock)
                    
                    cart_analysis.append({
                        "item": item,
                        "stock": r_stock,
                        "can_sell": can_sell,
                        "must_order": must_order
                    })
                    
                    if must_order > 0:
                        has_shortage = True
                        shortages.append(f"{item['product_name']} (Ped: {qty_req}, Est: {r_stock})")

                # UI DECISION BRANCH
                if has_shortage:
                    st.warning(f"⚠️ **Estoque Insuficiente detectado:** {', '.join(shortages)}")
                    st.info("Escolha como prosseguir:")
                else:
                    st.success("✅ Estoque Completo para todos os itens.")

                with st.container(border=True):
                    st.markdown("### Finalizar Pedido")
                    
                    # Calculate Default Deposit (50% of Order Portion)
                    # If shortage exists, assume Option A (Mixed) -> 50% of Shortage Value
                    # If no shortage, assume Option B (Force Order) -> 50% of Total Value
                    calc_shortage_val = sum([c['must_order'] * c['item']['base_price'] for c in cart_analysis])
                    calc_total_val = sum([c['item']['qty'] * c['item']['base_price'] for c in cart_analysis])
                    
                    default_dep = 0.0
                    if calc_shortage_val > 0:
                        default_dep = calc_shortage_val * 0.5
                    else:
                        default_dep = calc_total_val * 0.5
                        
                    c_dates1, c_dates2 = st.columns(2)
                    d_comm = c_dates1.date_input("Prazo para Encomenda (se houver)", value=datetime.now() + pd.Timedelta(days=30), format="DD/MM/YYYY")
                    deposit_val = c_dates2.number_input("Valor Sinal/Adiantamento (R$)", min_value=0.0, step=10.0, value=float(round(default_dep, 2)))
                    
                    col_act1, col_act2 = st.columns(2)
                    
                    # OPTION A: STANDARD / MIXED
                    # If shortage: "Vender parcial + Encomendar resto"
                    # If no shortage: "Finalizar Venda (Padrao)"
                    lbl_a = "📦 Entregar Agora + Encomendar Resto" if has_shortage else "✅ Finalizar Venda"
                    type_a = "secondary" if has_shortage else "primary"
                    
                    if col_act1.button(lbl_a, type=type_a, use_container_width=True):
                        # RESOLVE CLIENT
                        final_client_id = None
                        final_client_name = None
                        
                        valid_client = True
                        if cli_choice == "++ Cadastrar Novo ++":
                             if not new_cli_name:
                                 st.error("Digite o nome do novo cliente.")
                                 valid_client = False
                             else:
                                 cursor = conn.cursor()
                                 cursor.execute("INSERT INTO clients (name, phone) VALUES (?, ?)", (new_cli_name, new_cli_phone))
                                 conn.commit()
                                 final_client_id = cursor.lastrowid
                                 final_client_name = new_cli_name
                        elif not cli_choice:
                             st.error("Selecione o Cliente.")
                             valid_client = False
                        else:
                             final_client_id = client_dict[cli_choice]
                             final_client_name = cli_choice

                        if valid_client and not salesperson_choice:
                             st.error("Selecione a Vendedora.")
                             valid_client = False
                             
                        if valid_client:
                             # EXECUTE A (Mixed)
                             try:
                                 # 1. Generate IDs
                                 trans_uuid = f"TRX-{datetime.now().strftime('%y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
                                 
                                 sales_created = []
                                 order_items = []
                                 
                                 cursor = conn.cursor()
                                 
                                 for ca in cart_analysis:
                                    it = ca['item']
                                    # FORCE INT CAST to avoid Numpy/Pandas type issues
                                    q_sell = int(ca['can_sell'])
                                    q_order = int(ca['must_order'])
                                    
                                    # 1.1 Process Sale Portion
                                    if q_sell > 0:
                                        # Calculate proportional total/discount? 
                                        # Simple Pro-rata
                                        unit_price = it['base_price']
                                        # Discount is tricky if it was lump sum. Assuming item discount is per unit... 
                                        # Wait, item['discount'] in cart form seems to be Total Item Discount? 
                                        # Let's assume item['discount'] is TOTAL discount for that line.
                                        # So unit discount = total_disc / qty
                                        unit_disc = it['discount'] / it['qty']
                                        
                                        total_sell = (unit_price * q_sell) - (unit_disc * q_sell)
                                        disc_sell = unit_disc * q_sell
                                        
                                        cursor.execute("""
                                            INSERT INTO sales (date, product_id, quantity, total_price, status, client_id, discount, payment_method, notes, salesperson, order_id)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                        """, (date_order, int(it['product_id']), q_sell, total_sell, "Finalizada", final_client_id, disc_sell, pay_method_choice, notes_order, salesperson_choice, trans_uuid))
                                        
                                        # Audit
                                        audit.log_action(conn, 'CREATE', 'sales', cursor.lastrowid, None, {'audit_msg': 'Partial Sale'}, commit=False)
                                        sales_created.append(f"{q_sell}x {it['product_name']}")
                                        
                                        # Deduct Stock (Logic duplicated from before)
                                        # Deduct Stock (Logic duplicated from before)
                                        p_id = int(it['product_id'])
                                        kit_comps = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn, params=(p_id,))
                                        if not kit_comps.empty:
                                            st.toast(f"ℹ️ Item ID {p_id} identificado como KIT. Baixando componentes...", icon="🧩")
                                            for _, kc in kit_comps.iterrows():
                                                qtd_deduct = q_sell * kc['quantity']
                                                cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?", (qtd_deduct, kc['child_product_id']))
                                                st.toast(f" - Baixado {qtd_deduct} de Componente ID {kc['child_product_id']}", icon="📉")
                                        else:
                                            cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?", (q_sell, p_id))
                                            if cursor.rowcount == 0:
                                                st.error(f"FALHA AO ATUALIZAR ESTOQUE DO PRODUTO ID {p_id}")
                                            else:
                                                # Debugging Stock Update
                                                new_stock = cursor.execute("SELECT stock_quantity FROM products WHERE id=?", (p_id,)).fetchone()[0]
                                                st.toast(f"LOG: Baixando {q_sell} de ID {p_id}. Linhas: {cursor.rowcount}. Estoque Novo (Transaction): {new_stock}", icon="📉")

                                    # 1.2 Process Order Portion
                                    if q_order > 0:
                                        order_items.append({
                                            'id': it['product_id'],
                                            'qty': q_order,
                                            'price': it['base_price'],
                                            'qty_res': 0 # Backlog has NO reservation
                                        })
                                        
                                 # Create Order if needed
                                 final_notes = notes_order # Default fallback
                                 if order_items:
                                     # Create Order Header
                                     # Append Deposit Text if Order
                                     final_notes = f"Gerado via Venda #{trans_uuid}. Obs: {notes_order}"
                                     if deposit_val > 0:
                                         final_notes += f"\n\nSinal no valor de R$ {deposit_val:.2f}, o restante do pagamento será realizado na entrega da encomenda."

                                     cursor.execute("""
                                        INSERT INTO commission_orders (client_id, date_created, date_due, status, total_price, notes, deposit_amount)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                     """, (final_client_id, date.today(), d_comm, "Pendente", 0, final_notes, deposit_val))
                                     new_ord_id = cursor.lastrowid
                                     
                                     total_ord_val = 0
                                     for oi in order_items:
                                         val = oi['qty'] * oi['price']
                                         total_ord_val += val
                                         cursor.execute("""
                                            INSERT INTO commission_items (order_id, product_id, quantity, quantity_from_stock, unit_price)
                                            VALUES (?, ?, ?, ?, ?)
                                         """, (new_ord_id, int(oi['id']), oi['qty'], 0, oi['price']))
                                     
                                     cursor.execute("UPDATE commission_orders SET total_price = ? WHERE id = ?", (total_ord_val, new_ord_id))
                                     
                                     # Insert Deposit as Sale Record
                                     if deposit_val > 0:
                                         cursor.execute("""
                                             INSERT INTO sales (date, product_id, quantity, total_price, status, client_id, discount, payment_method, notes, salesperson, order_id)
                                             VALUES (?, NULL, 1, ?, 'Finalizada', ?, 0, ?, ?, ?, ?)
                                         """, (date.today(), deposit_val, final_client_id, pay_method_choice, f"Sinal de Encomenda #{new_ord_id}", salesperson_choice,  f"ENC-{new_ord_id}")) # Using ENC ID for reference logic? Or keeping trans_uuid? Let's use standard ENC ref.

                                     st.toast(f"Encomenda #{new_ord_id} gerada automaticamente!", icon="📦")
                                 
                                 if 'new_ord_id' not in locals(): # Option A flow
                                     conn.commit()
                                     
                                     # FORCE VERIFY
                                     check_stock = conn.execute("SELECT stock_quantity FROM products WHERE id=?", (p_id,)).fetchone()[0]
                                     if check_stock != new_stock:
                                         st.error(f"CRITICAL ERROR: Transaction Rolled Back? Expected {new_stock}, Got {check_stock}")
                                     else:
                                         st.toast(f"✅ Transaction Persisted. Stock in DB: {check_stock}", icon="💾")
                                 else:
                                     # Option B flow handles its own commit
                                     pass
                                 # Receipt & Reset
                                 st.session_state['last_order'] = {
                                    "id": trans_uuid,
                                    "client": final_client_name,
                                    "salesperson": salesperson_choice,
                                    "payment_method": pay_method_choice,
                                    "notes": final_notes,
                                    "deposit": deposit_val if order_items else 0,
                                    "date_due": (d_comm.strftime("%d/%m/%Y") if d_comm else None) if order_items else None,
                                    "items": st.session_state['cart'], # Keep original cart for receipt visual? Or update to reflect split? Let's keep original for simplicity, maybe add note.
                                    "total": cart_total,
                                    "time": datetime.now().strftime("%H:%M:%S")
                                 }
                                 st.session_state['cart'] = []
                                 st.rerun()

                             except Exception as e:
                                 st.error(f"❌ ERRO GRAVE DE TRANSAÇÃO: {e}")
                                 st.exception(e)

                    lbl_b = "🚨 Encomendar Tudo (Entrega Única)" 
                    # Add checkbox for reservation if they WANT to use stock?
                    # User requested: "podendo ser feita uma encomenda de todo o pedido (pra não ficar com peças em lotes diferentes)"
                    # Implies Reservation = 0 (Produce all new). But maybe allow toggle.
                    
                    force_order = col_act2.button(lbl_b, use_container_width=True, type="primary")
                    r_stock_chk = col_act2.checkbox("Usar estoque existente?", value=False, help="Se marcado, reserva (prende) as peças do estoque para esta encomenda. Se desmarcado, manda produzir tudo novo (Lote Único).")
                    
                    if force_order:
                        # RESOLVE CLIENT
                        final_client_id = None
                        final_client_name = None
                        
                        valid_client = True
                        if cli_choice == "++ Cadastrar Novo ++":
                             if not new_cli_name:
                                 st.error("Digite o nome do novo cliente.")
                                 valid_client = False
                             else:
                                 cursor = conn.cursor()
                                 cursor.execute("INSERT INTO clients (name, phone) VALUES (?, ?)", (new_cli_name, new_cli_phone))
                                 conn.commit()
                                 final_client_id = cursor.lastrowid
                                 final_client_name = new_cli_name
                        elif not cli_choice:
                             st.error("Selecione o Cliente.")
                             valid_client = False
                        else:
                             final_client_id = client_dict[cli_choice]
                             final_client_name = cli_choice

                        if valid_client and not salesperson_choice:
                             st.error("Selecione a Vendedora.")
                             valid_client = False
                        
                        if valid_client:
                             # EXECUTE B (Full Order)
                             cursor = conn.cursor()
                             
                             # Append Deposit Text
                             final_notes_B = f"Encomenda Total. Obs: {notes_order}"
                             if deposit_val > 0:
                                 final_notes_B += f"\n\nSinal no valor de R$ {deposit_val:.2f}, o restante do pagamento será realizado na entrega da encomenda."

                             # Create Order Header
                             cursor.execute("""
                                INSERT INTO commission_orders (client_id, date_created, date_due, status, total_price, notes, deposit_amount)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                             """, (final_client_id, date.today(), d_comm, "Pendente", 0, final_notes_B, deposit_val))
                             new_ord_id = cursor.lastrowid
                             
                             total_ord_val = 0
                             
                             for ca in cart_analysis:
                                it = ca['item']
                                q_full = it['qty']
                                q_res = ca['can_sell'] if r_stock_chk else 0
                                
                                val = q_full * it['base_price']
                                total_ord_val += val
                                
                                cursor.execute("""
                                    INSERT INTO commission_items (order_id, product_id, quantity, quantity_from_stock, unit_price)
                                    VALUES (?, ?, ?, ?, ?)
                                """, (new_ord_id, int(it['product_id']), q_full, q_res, it['base_price']))
                                
                                # IF RESERVING, DEDUCT STOCK
                                if q_res > 0:
                                     # Kit Logic Deduct
                                    p_id = int(it['product_id'])
                                    kit_comps = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn, params=(p_id,))
                                    if not kit_comps.empty:
                                        for _, kc in kit_comps.iterrows():
                                            cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?", (q_res * kc['quantity'], kc['child_product_id']))
                                    else:
                                        cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?", (q_res, p_id))

                             cursor.execute("UPDATE commission_orders SET total_price = ? WHERE id = ?", (total_ord_val, new_ord_id))
                             
                             # Insert Deposit as Sale Record
                             if deposit_val > 0:
                                 cursor.execute("""
                                     INSERT INTO sales (date, product_id, quantity, total_price, status, client_id, discount, payment_method, notes, salesperson, order_id)
                                     VALUES (?, NULL, 1, ?, 'Finalizada', ?, 0, ?, ?, ?, ?)
                                 """, (date.today(), deposit_val, final_client_id, pay_method_choice, f"Sinal de Encomenda #{new_ord_id}", salesperson_choice, f"ENC-{new_ord_id}"))

                             conn.commit()
                             
                             # Receipt & Reset
                             st.session_state['last_order'] = {
                                "id": f"ENC-{new_ord_id}",
                                "client": final_client_name,
                                "salesperson": salesperson_choice,
                                "payment_method": "A Definir (Encomenda)", # Payment not finalized yet for full orders usually
                                "notes": final_notes_B,
                                "deposit": deposit_val,
                                "date_due": d_comm.strftime("%d/%m/%Y") if d_comm else None,
                                "items": st.session_state['cart'], 
                                "total": total_ord_val,
                                "time": datetime.now().strftime("%H:%M:%S")
                             }
                             st.session_state['cart'] = []
                             st.rerun()
                    
    else:
        st.info("Seu carrinho está vazio.")

# --- Receipt Section (Order Level) ---

# Dialog moved to top


# --- History & Edit ---
st.divider()

# Secure History
with st.expander("🔐 Histórico de Vendas (Área Restrita)"):
    if admin_utils.check_password():
        st.subheader("Gerenciar Vendas")
        
        # Filters
        fc1, fc2, fc3, fc4 = st.columns(4)
        fil_date = fc1.date_input("Período", [], key="hist_dates", format="DD/MM/YYYY")
        fil_client = fc2.selectbox("Cliente", client_opts, key="hist_cli")
        fil_pay = fc3.selectbox("Pagamento", ["Todas"] + ["Pix", "Cartão Crédito", "Cartão Débito", "Dinheiro", "Outro"], key="hist_pay")
        fil_salesp = fc4.selectbox("Vendedora", ["Todas", "Ira", "Neli"], key="hist_sp")
        
        # Tabs for Sales vs Orders
        tab_vendas, tab_encomendas = st.tabs(["✅ Vendas Realizadas", "📦 Encomendas Geradas"])

        with tab_vendas:
            # Query Construction (Sales)
            query = """
                SELECT s.id, s.order_id, s.date, c.name as cliente, p.name as produto, s.quantity, s.total_price, 
                       s.salesperson, s.payment_method, s.discount, s.notes, s.product_id
                FROM sales s
                LEFT JOIN clients c ON s.client_id = c.id
                LEFT JOIN products p ON s.product_id = p.id
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
            
            query += " ORDER BY s.date DESC, s.id DESC"
            
            sales_view = pd.read_sql(query, conn, params=params)

        with tab_encomendas:
            # Query Construction (Orders)
            # Query Construction (Orders)
            q_orders = """
                SELECT co.id, co.date_created, c.name as cliente, co.total_price, co.status, co.date_due
                FROM commission_orders co
                LEFT JOIN clients c ON co.client_id = c.id
                WHERE 1=1
            """
            p_orders = []
            
            if len(fil_date) == 2:
                q_orders += " AND co.date_created BETWEEN ? AND ?"
                p_orders.append(fil_date[0])
                p_orders.append(fil_date[1])
            if fil_client:
                q_orders += " AND c.name = ?"
                p_orders.append(fil_client)
            
            q_orders += " ORDER BY co.date_created DESC"
            
            enc_view = pd.read_sql(q_orders, conn, params=p_orders)
            
            if not enc_view.empty:
                # Manual Fetch of Items to Handle Binary Data Issues
                order_ids = enc_view['id'].tolist()
                order_ids_placeholder = ",".join(["?"] * len(order_ids))
                
                # Fetch Items
                q_items = f"""
                    SELECT ci.order_id, ci.product_id, ci.quantity 
                    FROM commission_items ci 
                    WHERE ci.order_id IN ({order_ids_placeholder})
                """
                items_df = pd.read_sql(q_items, conn, params=order_ids)
                
                if not items_df.empty:
                    # Clean Binary Product IDs
                    def clean_pid(pid):
                        if isinstance(pid, bytes):
                            return int.from_bytes(pid, 'little')
                        return pid
                    
                    items_df['product_id'] = items_df['product_id'].apply(clean_pid)
                    
                    # Fetch Product Names
                    unique_pids = items_df['product_id'].dropna().unique().tolist()
                    if unique_pids:
                        p_ph = ",".join(["?"] * len(unique_pids))
                        p_df = pd.read_sql(f"SELECT id, name FROM products WHERE id IN ({p_ph})", conn, params=unique_pids)
                        
                        # Merge Name -> Items
                        items_df = items_df.merge(p_df, left_on='product_id', right_on='id', how='left')
                        items_df['name'] = items_df['name'].fillna("Desconhecido")
                        
                        # Create Display String: "Name (Qty)"
                        items_df['desc'] = items_df['name'] + " (" + items_df['quantity'].astype(str) + ")"
                        
                        # Group by Order
                        grouped = items_df.groupby('order_id')['desc'].apply(lambda x: ", ".join(x)).reset_index()
                        grouped.columns = ['id', 'produtos']
                        
                        # Merge back to Orders
                        enc_view = enc_view.merge(grouped, on='id', how='left')
                        enc_view['produtos'] = enc_view['produtos'].fillna("-")
                else:
                     enc_view['produtos'] = "-"

                enc_view['date_created'] = pd.to_datetime(enc_view['date_created']).dt.strftime('%d/%m/%Y')
                enc_view['date_due'] = pd.to_datetime(enc_view['date_due']).dt.strftime('%d/%m/%Y')
               
                st.dataframe(
                   enc_view,
                   column_config={
                       "id": st.column_config.NumberColumn("ID"),
                       "date_created": "Data Criação",
                       "cliente": "Cliente",
                       "produtos": st.column_config.TextColumn("Produtos", width="large"),
                       "total_price": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                       "status": st.column_config.TextColumn("Status"),
                       "date_due": "Prazo"
                   },
                   hide_index=True,
                   use_container_width=True
                )
            else:
                st.info("Nenhuma encomenda encontrada com estes filtros.")
        
        with tab_vendas:
            # TOGGLE VIEW
            group_by_order = st.checkbox("📂 Agrupar por Pedido", value=True)
        
            if not sales_view.empty:
                # Fix Date Type
                sales_view['date'] = pd.to_datetime(sales_view['date'])
                sales_view['produto'] = sales_view['produto'].fillna("Sinal / Ajuste")
                
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
                    
                    # Sort by id (proxy for creation time) descending
                    grouped = grouped.sort_values(by='id', ascending=False)
                    
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
                            "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                            "cliente": st.column_config.TextColumn("Cliente", disabled=True),
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
                                q_raw = orig_row['quantity']
                                
                                # Fix for corrupted/legacy binary data
                                try:
                                    if isinstance(q_raw, bytes):
                                        q_restore = int.from_bytes(q_raw, 'little')
                                    else:
                                        q_restore = int(q_raw)
                                except:
                                    q_restore = 1 # Fallback if totally corrupted
                                    
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
                                    cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (q_restore, int(p_id)))
                                
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
                        st.rerun()
            
                # --- RECEIPT GENERATION FOR HISTORY ---
                st.divider()
                with st.expander("📄 Gerar 2ª Via de Recibo"):
                    unique_uuids = sales_view['order_id'].dropna().unique().tolist()
                    sel_uuid = st.selectbox("Selecione o ID da Transação/Encomenda", unique_uuids)
                    
                    if st.button("Gerar PDF"):
                        # Fetch Data for this UUID
                        subset = sales_view[sales_view['order_id'] == sel_uuid]
                        
                        if not subset.empty:
                            first = subset.iloc[0]
                            
                            # Try to find date_due if available in view
                            d_due = ""
                            if 'date_due' in first and first['date_due']:
                                d_due = str(first['date_due']) # Already formatted in string in view?

                            rep_data = {
                                "id": sel_uuid,
                                "type": "Venda/Enc",
                                "date": pd.to_datetime(first['date']).strftime('%d/%m/%Y'),
                                "date_due": d_due,
                                "client_name": first['cliente'],
                                "salesperson": first['salesperson'] if 'salesperson' in first else '-',
                                "payment_method": first['payment_method'] if 'payment_method' in first else '-',
                                "notes": first['notes'] if 'notes' in first else '',
                                "items": [],
                                "total": subset['total_price'].sum(),
                                "discount": subset['discount'].sum() if 'discount' in subset.columns else 0,
                                "deposit": first['deposit_amount'] if 'deposit_amount' in first else 0
                            }
                            
                            # Use raw values or displayed values? Raw is safer.
                            # Need to re-fetch to ensure clean data?
                            # Using displayed view for speed
                            for _, row in subset.iterrows():
                                # Need product name. Logic in query was GROUP_CONCAT. In detailed view, it is 'produto'.
                                rep_data['items'].append({
                                    "name": row['produto'],
                                    "qty": row['quantity'],
                                    "price": row['total_price'] / row['quantity'] if row['quantity'] else 0
                                })
                                
                            pdf_bytes = reports.generate_receipt_pdf(rep_data)
                            st.download_button(
                                label="⬇️ Baixar PDF",
                                data=pdf_bytes,
                                file_name=f"recibo_{sel_uuid}.pdf",
                                mime="application/pdf"
                            )
            
            else:
                st.info("Nenhuma venda encontrada com estes filtros.")

conn.close()
