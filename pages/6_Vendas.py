import streamlit as st
import pandas as pd
import database
import admin_utils
import auth
import audit
import reports
import services.product_service as product_service
import services.order_service as order_service

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
        
        if str(order_data.get('id', '')).startswith('ENC'):
             formatted_id = order_data.get('id') # Already formatted
             type_lbl = "Encomenda"
        else:
             # Venda format
             # Needs Date. order_data['date'] might be DD/MM/YYYY string or object.
             # Assuming 'date' key exists and is formatted or we use current date if new sale.
             # Actually, for new sales, ID is not generated until inserted. 
             # If order_data comes from DB, it has ID.
             # Let's assume order_data has 'date_created' or we use today.
             current_dt = datetime.now()
             # Try to parse date if string
             try:
                 if 'date' in order_data:
                     # Default format from show_receipt_dialog call might be string
                     current_dt = datetime.strptime(order_data['date'], '%d/%m/%Y')
             except: pass
             
             formatted_id = f"VEN-{current_dt.strftime('%y%m%d')}-{order_data.get('id')}"
             type_lbl = "Venda"

        rep_data = {
            "id": formatted_id,
            "type": type_lbl,
            "date": datetime.now().strftime("%d/%m/%Y"),
            "client_name": order_data.get('client', 'Cliente'),
            "salesperson": order_data.get('salesperson', '-'),
            "payment_method": order_data.get('payment_method', '-'), 
            "notes": order_data.get('notes', ''), 
            "date_due": order_data.get('date_due', None),
            "items": [],
            "total": order_data.get('total', 0),
            "discount": 0, 
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
            file_name=f"{formatted_id}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        admin_utils.show_feedback_dialog(f"Erro ao gerar PDF: {e}", level="error")

if 'last_order' in st.session_state:
    show_receipt_dialog(st.session_state['last_order'])

# --- New Sale ---
# 1. Select Client (Global fetch for Form and History)
clients_df = pd.read_sql("SELECT id, name FROM clients", conn)
client_dict = {row['name']: row['id'] for _, row in clients_df.iterrows()}
client_opts = [""] + list(client_dict.keys())

# 2. Select Product (Visual Catalog) - OUTSIDE FORM for interactivity
products_df = product_service.get_all_products(conn)

# --- Application State ---
if 'cart' not in st.session_state:
    st.session_state['cart'] = []

if 'selected_product_id' not in st.session_state:
    st.session_state['selected_product_id'] = None

# --- DIALOG DEFINITION ---
@st.dialog("Criar Orçamento")
def quote_creation_dialog(client_display_name, initial_notes, cart_items, cli_choice_val, n_name, n_phone, c_dict):
     st.write(f"Cliente: {client_display_name}")
     
     qd_valid = st.number_input("Validade (dias)", value=30, min_value=1)
     qd_deliv = st.text_input("Prazo Entrega", value="45 dias após confirmação")
     qd_pay = st.text_input("Condições Pagamento", value="50% entrada + saldo na entrega")
     qd_note = st.text_area("Observações", value=initial_notes)
     
     if st.button("Confirmar Criação", type="primary"):
         try:
             conn = database.get_connection() # Re-acquire inside thread/dialog context safe? Yes.
             cursor = conn.cursor()
             
             # Create Client if needed
             final_cid = None
             if cli_choice_val == "++ Cadastrar Novo ++":
                  cursor.execute("INSERT INTO clients (name, phone) VALUES (?, ?)", (n_name, n_phone))
                  conn.commit()
                  final_cid = cursor.lastrowid
             else:
                  # Handle bytes id issue if c_dict has bytes?
                  # The dict comes from helper which usually resolves?
                  # Let's assume passed c_dict values are usable.
                  final_cid = c_dict[cli_choice_val]
             
             if isinstance(final_cid, bytes): final_cid = int.from_bytes(final_cid, "little")

             # Create Quote
             valid_until = (date.today() + pd.Timedelta(days=qd_valid)).isoformat()
             
             # Ensure connection is fresh?
             # cursor.execute might fail if connection closed?
             # We got new connection above.
             
             cursor.execute("""
                INSERT INTO quotes (client_id, date_created, date_valid_until, status, total_price, notes, delivery_terms, payment_terms)
                VALUES (?, ?, ?, 'Pendente', 0, ?, ?, ?)
             """, (final_cid, date.today().isoformat(), valid_until, qd_note, qd_deliv, qd_pay))
             
             quote_id = cursor.lastrowid
             if isinstance(quote_id, bytes): quote_id = int.from_bytes(quote_id, "little")
             
             # Insert Items
             running_total = 0.0
             for item in cart_items:
                 note_txt = ""
                 if item.get('variant_name'):
                     note_txt = f"Variação: {item['variant_name']}"
                     
                 p_id = int(item['product_id'])
                 qty = int(item['qty'])
                 price = float(item['base_price'])
                 
                 cursor.execute("INSERT INTO quote_items (quote_id, product_id, quantity, unit_price, item_notes) VALUES (?, ?, ?, ?, ?)", 
                                (quote_id, p_id, qty, price, note_txt))
                 
                 running_total += (qty * price)

             # Update Total
             cursor.execute("UPDATE quotes SET total_price=? WHERE id=?", (running_total, quote_id))
             conn.commit()
             # conn.close() # Keep connection open or let verify handle it? safely remove to avoid closing shared conn
             
             st.session_state['cart'] = []
             admin_utils.show_feedback_dialog(f"Orçamento #{quote_id} criado com sucesso!", level="success")
             st.rerun()

         except Exception as e:
             admin_utils.show_feedback_dialog(f"Erro ao salvar orçamento: {e}", level="error")

# --- Tabs Structure ---
tab_pos, tab_quotes = st.tabs(["🛒 Nova Venda / Cotação", "📄 Orçamentos Salvos"])

# ==============================================================================
# TAB 1: POS (Catalog + Cart)
# ==============================================================================
with tab_pos:
    # --- Layout: 2 Columns (Catalog vs Cart/Checkout) ---
    col_catalog, col_cart = st.columns([1.1, 0.9], gap="large")

# ==========================
# LEFT COL: CATALOG
# ==========================
with col_catalog:
    st.subheader("📦 Catálogo de Produtos")
    
    # --- Filters ---
    c_filt1, c_filt2 = st.columns([1, 1])
    search_term = c_filt1.text_input("🔍 Buscar Produto", placeholder="Nome do produto...")
    
    # Helper for images handled by Service


    # Get Categories from DB
    all_cats = product_service.get_categories(conn, products_df)
    
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
                            display_thumbs = product_service.get_product_images(conn, product.id)
                            
                            if display_thumbs:
                                st.image(display_thumbs[:3], use_container_width=True)
                            else:
                                st.markdown("🖼️ *Sem Foto*")
                            
                            # Stock Logic (Handle Kits)
                            display_stock = product.stock_quantity
                            is_kit, kit_stock = product_service.get_kit_stock_status(conn, product.id)
                            
                            if is_kit:
                                display_stock = kit_stock
                            st.markdown(f"**{product.name}**")
                            
                            # Variant Logic (Visual Badges)
                            vars_df = product_service.get_product_variants(conn, product.id)
                            if not vars_df.empty:
                                st.markdown("<div style='margin-top: 5px; margin-bottom: 5px; font-size: 0.8em; color: #aaa;'>Variações:</div>", unsafe_allow_html=True)
                                badges = ""
                                for _, vr in vars_df.iterrows():
                                    s_qty = vr['stock_quantity']
                                    s_color = "#66ff66" if s_qty > 0 else "#ff6666"
                                    badges += f"""
                                    <div style="
                                        display: flex; 
                                        justify-content: space-between; 
                                        background-color: rgba(255,255,255,0.08); 
                                        padding: 2px 6px; 
                                        border-radius: 4px; 
                                        margin-bottom: 2px;
                                        align-items: center;
                                        font-size: 0.8em;">
                                        <span style="color: #e0e0e0;">{vr['variant_name']}</span>
                                        <span style="font-weight: bold; color: {s_color}; font-family: monospace;">{s_qty}</span>
                                    </div>
                                    """
                                st.markdown(badges, unsafe_allow_html=True)

                            stock_txt = f"📦 Kit: {display_stock}" if is_kit else f"Est. Base: {product.stock_quantity}"
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
            
            # --- Variant Selection ---
            variants_df = product_service.get_product_variants(conn, sel_row['id'])
            selected_variant = None
            price_adder = 0.0
            
            if not variants_df.empty:
                st.info("🎨 Selecione o Acabamento")
                var_opts = {f"{r['variant_name']} (+R$ {r['price_adder']:.2f})": r['id'] for _, r in variants_df.iterrows()}
                # Default empty to force choice? Or first? User requirement: "exibir um segundo st.selectbox"
                var_choice = st.selectbox("Variação (Esmalte)", list(var_opts.keys()))
                
                if var_choice:
                    v_id = var_opts[var_choice]
                    v_row = variants_df[variants_df['id'] == v_id].iloc[0]
                    selected_variant = {
                        "id": int(v_id),
                        "name": v_row['variant_name'],
                        "stock": int(v_row['stock_quantity']),
                        "price_adder": float(v_row['price_adder'])
                    }
                    price_adder = selected_variant['price_adder']
                    
                    st.caption(f"Estoque da Variação: {selected_variant['stock']}")
            
            # --- Qty & Disc ---
            c_qty, c_disc = st.columns(2)
            item_qty = c_qty.number_input("Qtd", min_value=1, step=1, value=1, key="item_qty")
            item_disc = c_disc.number_input("Desconto (Item)", min_value=0.0, step=0.1, value=0.0, key="item_disc")
            
            # Calc Preview
            base_price_effective = sel_row['base_price'] + price_adder
            base_total = base_price_effective * item_qty
            item_final = max(0.0, base_total - item_disc)
            
            st.write(f"Preço Unit.: **R$ {base_price_effective:.2f}**")
            st.write(f"Total Item: **R$ {item_final:.2f}**")
            
            # Check cart for this product/variant
            # Logic: Need to distinguish variants in cart
            in_cart = 0
            for i in st.session_state['cart']:
                # Same Product AND Same Variant (or both None)
                p_match = (i['product_id'] == sel_row['id'])
                v_match = (i.get('variant_id') == (selected_variant['id'] if selected_variant else None))
                if p_match and v_match:
                    in_cart += i['qty']
            
            # Helper to get Real Stock (Kit aware OR Variant aware)
            if selected_variant:
                real_stock = selected_variant['stock']
            else:
                real_stock = sel_row['stock_quantity']
                
                # Check Kit Stock (Quick Query) - Only if NOT variant
                is_kit, kit_stock = product_service.get_kit_stock_status(conn, sel_row['id'])
                if is_kit:
                    st.info(f"🧩 Produto Tipo Kit. Estoque Máximo: {kit_stock}")
                    real_stock = kit_stock

            if st.button("➕ Adicionar ao Carrinho", type="primary", use_container_width=True):
                # Validar estoque (Apenas aviso, permitir encomenda)
                if (in_cart + item_qty) > real_stock:
                    st.warning(f"⚠️ Pedido ({in_cart + item_qty}) excede estoque ({real_stock}). O excedente entrará como Encomenda.")
                
                # Add to Cart (Always allowed)
                product_display_name = sel_row['name']
                if selected_variant:
                    product_display_name += f" ({selected_variant['name']})"

                cart_item = {
                    "product_id": sel_row['id'],
                    "product_name": product_display_name,
                    "thumb": sel_row['thumb_path'],
                    "qty": item_qty,
                    "base_price": base_price_effective, # Store effective price
                    "discount": item_disc,
                    "total": item_final,
                    "variant_id": selected_variant['id'] if selected_variant else None,
                    "variant_name": selected_variant['name'] if selected_variant else None
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
                    
                    variant_id = item.get('variant_id') # New

                    if variant_id:
                        # Check Variant Stock
                        v_row = pd.read_sql("SELECT stock_quantity FROM product_variants WHERE id=?", conn, params=(variant_id,)).iloc[0]
                        r_stock = v_row['stock_quantity']
                    elif not k_check.empty:
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
                    
                    col_act1, col_act2, col_act3 = st.columns(3)
                    
                    # OPTION A: STANDARD / MIXED
                    # If shortage: "Vender parcial + Encomendar resto"
                    # If no shortage: "Finalizar Venda (Padrao)"
                    lbl_a = "📦 Entregar Agora + Encomendar Resto" if has_shortage else "✅ Finalizar Venda"
                    type_a = "secondary" if has_shortage else "primary"
                    
                    if col_act1.button(lbl_a, type=type_a, use_container_width=True):
                        # RESOLVE CLIENT VALIDATION
                        final_client_id = None
                        final_client_id = None
                        final_client_name = None
                        
                        valid_client = True
                        if cli_choice == "++ Cadastrar Novo ++":
                             if not new_cli_name:
                                 admin_utils.show_feedback_dialog("Digite o nome do novo cliente.", level="error")
                                 valid_client = False
                             else:
                                 cursor = conn.cursor()
                                 cursor.execute("INSERT INTO clients (name, phone) VALUES (?, ?)", (new_cli_name, new_cli_phone))
                                 conn.commit()
                                 final_client_id = cursor.lastrowid
                                 final_client_name = new_cli_name
                        elif not cli_choice:
                             admin_utils.show_feedback_dialog("Selecione o Cliente.", level="error")
                             valid_client = False
                        else:
                             final_client_id = client_dict[cli_choice]
                             final_client_name = cli_choice

                        if valid_client and not salesperson_choice:
                             admin_utils.show_feedback_dialog("Selecione a Vendedora.", level="error")
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
                                        
                                        # Create Sale (Service)
                                        sale_id = order_service.create_sale(cursor, {
                                            "date": date_order,
                                            "product_id": int(it['product_id']),
                                            "quantity": q_sell,
                                            "total_price": total_sell,
                                            "status": "Finalizada",
                                            "client_id": final_client_id,
                                            "discount": disc_sell,
                                            "payment_method": pay_method_choice,
                                            "notes": notes_order,
                                            "salesperson": salesperson_choice,
                                            "order_id": trans_uuid,
                                            "variant_id": it.get('variant_id')
                                        })
                                        
                                        # Audit
                                        audit.log_action(conn, 'CREATE', 'sales', sale_id, None, {'audit_msg': 'Partial Sale'}, commit=False)
                                        sales_created.append(f"{q_sell}x {it['product_name']}")
                                        
                                        # Deduct Stock (Service)
                                        logs = product_service.deduct_stock(cursor, p_id_check, q_sell, variant_id=it.get('variant_id'))
                                        # (Toasts for stock deduction can stay as non-blocking logs)
                                        for log in logs:
                                            st.toast(log, icon="📉")
                                        
                                        # Verify (Optional, kept for safety during transition)
                                        try:
                                            new_stock = cursor.execute("SELECT stock_quantity FROM products WHERE id=?", (p_id,)).fetchone()[0]
                                            st.toast(f"LOG: Estoque Novo: {new_stock}", icon="📉")
                                        except: pass

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

                                     new_ord_id = order_service.create_commission_order(cursor, {
                                         'client_id': final_client_id,
                                         'date_created': date.today(),
                                         'date_due': d_comm,
                                         'status': "Pendente",
                                         'total_price': 0, # Will be updated
                                         'notes': final_notes,
                                         'deposit_amount': deposit_val
                                     })
                                     
                                     # Prepare items for service
                                     items_for_service = []
                                     for oi in order_items:
                                         items_for_service.append({
                                             'product_id': int(oi['id']),
                                             'qty': oi['qty'],
                                             'qty_from_stock': 0,
                                             'unit_price': oi['price'],
                                             'variant_id': it.get('variant_id')
                                         })
                                     
                                     order_service.add_commission_items(cursor, new_ord_id, items_for_service)
                                     
                                     # Insert Deposit as Sale Record
                                     if deposit_val > 0:
                                         order_service.create_sale(cursor, {
                                              "date": date.today(),
                                              "product_id": None,
                                              "quantity": 1,
                                              "total_price": deposit_val,
                                              "status": "Finalizada",
                                              "client_id": final_client_id,
                                              "discount": 0,
                                              "payment_method": pay_method_choice,
                                              "notes": f"Sinal de Encomenda #{new_ord_id}",
                                              "salesperson": salesperson_choice,
                                              "order_id": f"ENC-{new_ord_id}"
                                          })
                                     conn.commit()
                                    
                                     # Format ID for Toast
                                     fmt_oid_toast = f"ENC-{datetime.now().strftime('%y%m%d')}-{new_ord_id}"
                                     admin_utils.show_feedback_dialog(f"Venda Finalizada! Encomenda {fmt_oid_toast} gerada automaticamente!", level="success")
                                 
                                 if 'new_ord_id' not in locals(): # Option A flow
                                     conn.commit()
                                     admin_utils.show_feedback_dialog("Venda Finalizada com Sucesso!", level="success")
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
                                 admin_utils.show_feedback_dialog(f"ERRO GRAVE DE TRANSAÇÃO: {e}", level="error")
                    
                    # --- QUOTE BUTTON (New) ---
                    if col_act3.button("📄 Salvar como Orçamento", type="secondary", use_container_width=True):
                         quote_creation_dialog(new_cli_name if cli_choice == '++ Cadastrar Novo ++' else cli_choice, notes_order, st.session_state['cart'], cli_choice, new_cli_name, new_cli_phone, client_dict)

                    lbl_b = "Finalizar Encomenda" 
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
                                 admin_utils.show_feedback_dialog("Digite o nome do novo cliente.", level="warning")
                                 valid_client = False
                             else:
                                 cursor = conn.cursor()
                                 cursor.execute("INSERT INTO clients (name, phone) VALUES (?, ?)", (new_cli_name, new_cli_phone))
                                 conn.commit()
                                 final_client_id = cursor.lastrowid
                                 final_client_name = new_cli_name
                        elif not cli_choice:
                             admin_utils.show_feedback_dialog("Selecione o Cliente.", level="warning")
                             valid_client = False
                        else:
                             final_client_id = client_dict[cli_choice]
                             final_client_name = cli_choice

                        if valid_client and not salesperson_choice:
                             admin_utils.show_feedback_dialog("Selecione a Vendedora.", level="warning")
                             valid_client = False
                        
                        if valid_client:
                             # EXECUTE B (Full Order)
                             cursor = conn.cursor()
                             
                             # Append Deposit Text
                             final_notes_B = f"Encomenda Total. Obs: {notes_order}"
                             if deposit_val > 0:
                                 final_notes_B += f"\n\nSinal no valor de R$ {deposit_val:.2f}, o restante do pagamento será realizado na entrega da encomenda."

                             # Create Order Header
                             new_ord_id = order_service.create_commission_order(cursor, {
                                 'client_id': final_client_id,
                                 'date_created': date.today(),
                                 'date_due': d_comm,
                                 'status': "Pendente",
                                 'total_price': 0, # Will be updated
                                 'notes': final_notes_B,
                                 'deposit_amount': deposit_val
                             })
                             
                             items_for_service = []
                             for ca in cart_analysis:
                                item = ca['item']
                                q_full = item['qty']
                                q_res = ca['can_sell'] if r_stock_chk else 0
                                
                                items_for_service.append({
                                    'product_id': int(item['product_id']),
                                    'qty': q_full,
                                    'qty_from_stock': q_res,
                                    'unit_price': item['base_price'],
                                    'variant_id': item.get('variant_id')
                                })
                                
                                # IF RESERVING, DEDUCT STOCK
                                if q_res > 0:
                                    logs = product_service.deduct_stock(cursor, int(item['product_id']), q_res, variant_id=item.get('variant_id'))
                                    for log in logs: st.toast(log, icon="📉")

                             order_service.add_commission_items(cursor, new_ord_id, items_for_service)
                             
                             # Insert Deposit as Sale Record
                             # Insert Deposit as Sale Record
                             if deposit_val > 0:
                                  order_service.create_sale(cursor, {
                                      "date": date.today(),
                                      "product_id": None,
                                      "quantity": 1,
                                      "total_price": deposit_val,
                                      "status": "Finalizada",
                                      "client_id": final_client_id,
                                      "discount": 0,
                                      "payment_method": pay_method_choice,
                                      "notes": f"Sinal de Encomenda #{new_ord_id}",
                                      "salesperson": salesperson_choice,
                                      "order_id": f"ENC-{new_ord_id}"
                                  })

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
                                "total": cart_total, # Should calculate based on items ordered? Yes cart total logic applies
                                "time": datetime.now().strftime("%H:%M:%S")
                             }
                             st.session_state['cart'] = []
                             st.rerun()
                    
    else:
        st.info("Seu carrinho está vazio.")

# Function quote_creation_dialog moved to top

# --- Receipt Section (Order Level) ---

# Dialog moved to top


# --- History & Edit ---
st.divider()

# Secure History
with st.expander("🔐 Histórico de Vendas (Área Restrita)"):
    curr_user = auth.get_current_user()
    
    # Session state for override
    if "hist_auth_override" not in st.session_state:
        st.session_state.hist_auth_override = False
        
    authorized = (curr_user and curr_user['role'] == 'admin') or st.session_state.hist_auth_override

    if authorized:
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
                       s.salesperson, s.payment_method, s.discount, s.notes, s.product_id,
                       pv.variant_name
                FROM sales s
                LEFT JOIN clients c ON s.client_id = c.id
                LEFT JOIN products p ON s.product_id = p.id
                LEFT JOIN product_variants pv ON s.variant_id = pv.id
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
            
            if not sales_view.empty:
                 # Clean variant name
                 sales_view['variant_name'] = sales_view['variant_name'].fillna('')
                 sales_view['produto'] = sales_view.apply(lambda x: f"{x['produto']} ({x['variant_name']})" if x['variant_name'] else x['produto'], axis=1)

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

                enc_view['date_created'] = pd.to_datetime(enc_view['date_created'], format='mixed', errors='coerce').dt.strftime('%d/%m/%Y')
                enc_view['date_due'] = pd.to_datetime(enc_view['date_due'], format='mixed', errors='coerce').dt.strftime('%d/%m/%Y')
               
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
                                except Exception:
                                    q_restore = 1  # Fallback if totally corrupted
                                    
                                p_id = orig_row['product_id']
                                
                                # Capture for audit before delete
                                old_data = {'id': did, 'quantity': q_restore, 'product_id': p_id, 'total_price': orig_row['total_price']}
                                
                                cursor.execute("DELETE FROM sales WHERE id=?", (did,))
                                
                                # RESTORE STOCK LOGIC (HANDLE KITS)
                                kit_restore = pd.read_sql("SELECT child_product_id, quantity FROM product_kits WHERE parent_product_id=?", conn, params=(p_id,))
                                
                                if not kit_restore.empty:
                                    for _, kr in kit_restore.iterrows():
                                        restore_qty = q_restore * kr['quantity']
                                        cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (int(restore_qty), int(kr['child_product_id'])))
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
                        admin_utils.show_feedback_dialog("Histórico atualizado com sucesso!", level="success")
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

    else:
        admin_utils.show_feedback_dialog("Acesso Restrito. Necessário autorização de Administrador.", level="warning", title="Acesso Negado")
        
        pwd_auth = st.text_input("Senha de Administrador", type="password", key="hist_auth_pwd")
        if pwd_auth:
             if auth.verify_admin_authorization(conn, pwd_auth):
                st.session_state.hist_auth_override = True
                admin_utils.show_feedback_dialog("Acesso Autorizado!", level="success")
                st.rerun()
             else:
                admin_utils.show_feedback_dialog("Senha incorreta.", level="error")


# ==============================================================================
# TAB 2: QUOTES MANAGEMENT
# ==============================================================================
with tab_quotes:
    # --- HELPER FUNCTIONS (Local) ---
    def delete_quote(quote_id):
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM quote_items WHERE quote_id=?", (quote_id,))
            cursor.execute("DELETE FROM quotes WHERE id=?", (quote_id,))
            audit.log_action(conn, 'DELETE', 'quotes', quote_id, commit=False)
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            admin_utils.show_feedback_dialog(f"Erro ao excluir orçamento: {e}", level="error")
            return False

    def calculate_quote_total(quote_id):
        cursor = conn.cursor()
        result = cursor.execute(
            "SELECT SUM(quantity * unit_price) FROM quote_items WHERE quote_id=?", 
            (quote_id,)
        ).fetchone()
        total = result[0] if result[0] else 0
        discount = cursor.execute("SELECT discount FROM quotes WHERE id=?", (quote_id,)).fetchone()[0] or 0
        final_total = total - discount
        cursor.execute("UPDATE quotes SET total_price=? WHERE id=?", (final_total, quote_id))
        conn.commit()
        return final_total

    def update_quote_item(item_id, quote_id, key_prefix):
        try:
            new_val = st.session_state[f"{key_prefix}_{item_id}"]
            cursor = conn.cursor()
            if key_prefix == "q": cursor.execute("UPDATE quote_items SET quantity=? WHERE id=?", (new_val, item_id))
            elif key_prefix == "n": cursor.execute("UPDATE quote_items SET item_notes=? WHERE id=?", (new_val, item_id))
            elif key_prefix == "p": cursor.execute("UPDATE quote_items SET unit_price=? WHERE id=?", (new_val, item_id))
            conn.commit()
            calculate_quote_total(quote_id)
            st.session_state['expanded_quote'] = quote_id
        except Exception as e: print(f"Error updating item: {e}")

    # --- FILTERS ---
    q_f1, q_f2, q_f3 = st.columns(3)
    with q_f1:
        sel_q_status = st.multiselect("Status", ["Pendente", "Aprovado", "Recusado", "Expirado"], default=["Pendente"])
    with q_f2:
        q_clients_df = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
        q_client_list = ["Todos"] + q_clients_df['name'].tolist()
        sel_q_client = st.selectbox("Cliente (Filtro)", q_client_list)
    with q_f3:
        sel_q_start = st.date_input("De", value=None, format="DD/MM/YYYY", key="q_date_filter")

    # --- FETCH QUOTES ---
    quotes_df = pd.read_sql("""
        SELECT q.id, c.name as client, q.date_created, q.date_valid_until, 
               q.status, q.total_price, q.discount, q.notes, q.client_id,
               q.delivery_terms, q.payment_terms
        FROM quotes q
        LEFT JOIN clients c ON q.client_id = c.id
        ORDER BY q.date_created DESC
    """, conn)

    if not quotes_df.empty:
        if sel_q_status: quotes_df = quotes_df[quotes_df['status'].isin(sel_q_status)]
        if sel_q_client != "Todos": quotes_df = quotes_df[quotes_df['client'] == sel_q_client]
        if sel_q_start: quotes_df = quotes_df[pd.to_datetime(quotes_df['date_created']).dt.date >= sel_q_start]
    
    if quotes_df.empty:
        st.info("Nenhum orçamento encontrado.")
    else:
        for _, quote in quotes_df.iterrows():
            status_colors = {"Pendente": "🟡", "Aprovado": "🟢", "Recusado": "🔴", "Expirado": "⚪"}
            status_icon = status_colors.get(quote['status'], "⚪")
            
            valid_until = pd.to_datetime(quote['date_valid_until']).date()
            is_expired = valid_until < date.today() and quote['status'] == 'Pendente'
            
            is_exp = (st.session_state.get('expanded_quote') == quote['id'])
            q_dt = pd.to_datetime(quote['date_created'])
            fmt_id = f"ORC-{q_dt.strftime('%y%m%d')}-{quote['id']}"
            
            with st.expander(f"{status_icon} {fmt_id} - {quote['client']} | R$ {quote['total_price']:.2f}", expanded=is_exp):
                c_info1, c_info2, c_info3 = st.columns(3)
                c_info1.write(f"📅 **Criado:** {q_dt.strftime('%d/%m/%Y')}")
                if is_expired: c_info2.write(f"⏰ **Validade:** :red[EXPIRADO]")
                else: c_info2.write(f"⏰ **Validade:** {valid_until.strftime('%d/%m/%Y')}")
                c_info3.metric("Total", f"R$ {quote['total_price']:.2f}")
                
                if quote['notes']: st.caption(f"📝 {quote['notes']}")
                st.caption(f"🚚 Ent: {quote['delivery_terms']} | 💲 Pag: {quote['payment_terms']}")
                st.divider()
                
                # Fetch Items
                items = pd.read_sql("""
                    SELECT qi.id, qi.product_id, p.name, p.image_paths, qi.quantity, qi.unit_price, qi.item_notes
                    FROM quote_items qi
                    LEFT JOIN products p ON qi.product_id = p.id
                    WHERE qi.quote_id = ?
                """, conn, params=(quote['id'],))
                
                # Item Display
                for _, item in items.iterrows():
                    ci1, ci2, ci3, ci4, ci5 = st.columns([0.5, 2, 1, 1, 1])
                    with ci1: st.write("📦") # Placeholder image
                    with ci2:
                        st.write(f"**{item['name']}**")
                        # Show Visual Badges for Variants (if needed, simplified here)
                        if 'Variação:' in (item['item_notes'] or ""):
                            st.caption(f"🎨 {item['item_notes']}")
                        elif item['item_notes']:
                            st.caption(f"📝 {item['item_notes']}")
                            
                    with ci3: st.write(f"Qtd: {item['quantity']}")
                    with ci4: st.write(f"R$ {item['unit_price']:.2f}")
                    with ci5: st.write(f"**R$ {item['quantity'] * item['unit_price']:.2f}**")
                
                st.divider()
                
                # Actions
                ca1, ca2, ca3, ca4 = st.columns(4)
                
                # PDF
                with ca1:
                    fname = f"{fmt_id}.pdf"
                    pdf_data = reports.generate_quote_pdf({
                        "id": fmt_id, 
                        "client_name": quote['client'],
                        "date_created": q_dt.strftime('%d/%m/%Y'),
                        "date_valid_until": valid_until.strftime('%d/%m/%Y'),
                        "items": [{
                            "id": r['product_id'], "name": r['name'], "qty": r['quantity'], "price": r['unit_price'], "notes": r['item_notes'] or ""
                        } for _, r in items.iterrows()],
                        "total": quote['total_price'],
                        "discount": quote['discount'],
                        "notes": quote['notes'], "delivery": quote['delivery_terms'], "payment": quote['payment_terms']
                    })
                    st.download_button("📄 PDF", data=pdf_data, file_name=fname, mime="application/pdf", key=f"qpdf_{quote['id']}")
                
                if quote['status'] == 'Pendente':
                    # Approve
                    with ca2:
                        with st.popover("✅ Aprovar"):
                            st.write("Confirmar aprovação? Uma encomenda será gerada.")
                            dep_val = st.number_input("Sinal (R$)", min_value=0.0, key=f"qdep_{quote['id']}")
                            if st.button("Confirmar", key=f"qconf_{quote['id']}", type="primary"):
                                # Conversion Logic
                                cursor = conn.cursor()
                                cursor.execute("INSERT INTO commission_orders (client_id, total_price, date_created, date_due, status, notes, deposit_amount) VALUES (?, ?, ?, ?, 'Pendente', ?, ?)", 
                                               (quote['client_id'], quote['total_price'], datetime.now().isoformat(), (date.today()+timedelta(days=30)).isoformat(), f"Via Orçamento {fmt_id}", dep_val))
                                new_oid = cursor.lastrowid
                                if isinstance(new_oid, bytes): new_oid = int.from_bytes(new_oid, "little")
                                
                                # Move Items
                                for _, it in items.iterrows():
                                    cursor.execute("INSERT INTO commission_items (order_id, product_id, quantity, unit_price, notes) VALUES (?, ?, ?, ?, ?)",
                                                   (new_oid, it['product_id'], it['quantity'], it['unit_price'], it['item_notes']))
                                
                                # Update Quote
                                cursor.execute("UPDATE quotes SET status='Aprovado', converted_order_id=? WHERE id=?", (new_oid, quote['id']))
                                conn.commit()
                                
                                fmt_oid = f"ENC-{datetime.now().strftime('%y%m%d')}-{new_oid}"
                                admin_utils.show_feedback_dialog(f"Aprovado! Encomenda {fmt_oid} gerada.", level="success")
                                st.rerun()

                    # Reject
                    if ca3.button("❌ Recusar", key=f"qrej_{quote['id']}"):
                        cursor = conn.cursor()
                        cursor.execute("UPDATE quotes SET status='Recusado' WHERE id=?", (quote['id'],))
                        conn.commit()
                        st.rerun()
                        
                    # Delete
                    if ca4.button("🗑️", key=f"qdel_{quote['id']}"):
                         delete_quote(quote['id'])
                         st.rerun()

conn.close()
