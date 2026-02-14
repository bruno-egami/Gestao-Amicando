import streamlit as st
import pandas as pd
import database
import admin_utils
import auth
import audit
import reports
import services.product_service as product_service
import services.order_service as order_service
import utils.styles as styles
import uuid
from datetime import datetime, date, timedelta
from utils.logging_config import get_logger

logger = get_logger(__name__)

st.set_page_config(page_title="Vendas", page_icon="💰", layout="wide")

# Apply Global Styles
styles.apply_custom_style()

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
        if str(order_data.get('id', '')).startswith('ENC'):
             formatted_id = order_data.get('id') 
             type_lbl = "Encomenda"
        else:
             current_dt = datetime.now()
             try:
                 if 'date' in order_data:
                     # Default format from show_receipt_dialog call might be string
                     # If it's a date object, handle it
                     if hasattr(order_data['date'], 'strftime'):
                        current_dt = order_data['date']
                     else:
                        current_dt = datetime.strptime(order_data['date'], '%d/%m/%Y')
             except Exception as e:
                 logger.warning(f"Error parsing date in Vendas receipt: {e}")
                 pass
             
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
clients_df = order_service.get_all_clients(conn)
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
             # Create Client if needed
             final_cid = None
             if cli_choice_val == "++ Cadastrar Novo ++":
                  final_cid = order_service.create_client(conn, n_name, n_phone)
             else:
                  final_cid = c_dict[cli_choice_val]
             
             if isinstance(final_cid, bytes): final_cid = int.from_bytes(final_cid, "little")

             # Prepare Items for Service
             service_items = []
             for item in cart_items:
                 note_txt = ""
                 if item.get('variant_name'):
                     note_txt = f"Variação: {item['variant_name']}"
                     
                 service_items.append({
                     'product_id': int(item['product_id']),
                     'qty': int(item['qty']),
                     'price': float(item['base_price']),
                     'notes': note_txt
                 })

             # Create Quote via Service
             quote_id = order_service.create_quote(conn, {
                 'client_id': final_cid,
                 'notes': qd_note,
                 'delivery_terms': qd_deliv,
                 'payment_terms': qd_pay,
                 'valid_days': qd_valid
             }, service_items)
             
             if isinstance(quote_id, bytes): quote_id = int.from_bytes(quote_id, "little")
             
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
                                        badges += f"<div style='display: flex; justify-content: space-between; background-color: rgba(255,255,255,0.08); padding: 2px 6px; border-radius: 4px; margin-bottom: 2px; align-items: center; font-size: 0.8em;'><span style='color: #e0e0e0;'>{vr['variant_name']}</span><span style='font-weight: bold; color: {s_color}; font-family: monospace;'>{s_qty}</span></div>"
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
                in_cart = 0
                for i in st.session_state['cart']:
                    p_match = (i['product_id'] == sel_row['id'])
                    v_match = (i.get('variant_id') == (selected_variant['id'] if selected_variant else None))
                    if p_match and v_match:
                        in_cart += i['qty']
                
                # Helper to get Real Stock
                if selected_variant:
                    real_stock = selected_variant['stock']
                else:
                    real_stock = sel_row['stock_quantity']
                    is_kit, kit_stock = product_service.get_kit_stock_status(conn, sel_row['id'])
                    if is_kit:
                        st.info(f"🧩 Produto Tipo Kit. Estoque Máximo: {kit_stock}")
                        real_stock = kit_stock

                if st.button("➕ Adicionar ao Carrinho", type="primary", use_container_width=True):
                    if (in_cart + item_qty) > real_stock:
                        st.warning(f"⚠️ Pedido ({in_cart + item_qty}) excede estoque ({real_stock}). O excedente entrará como Encomenda.")
                    
                    product_display_name = sel_row['name']
                    if selected_variant:
                        product_display_name += f" ({selected_variant['name']})"

                    cart_item = {
                        "product_id": sel_row['id'],
                        "product_name": product_display_name,
                        "thumb": sel_row['thumb_path'],
                        "qty": item_qty,
                        "base_price": base_price_effective, 
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
            cart_df = pd.DataFrame(st.session_state['cart'])
            if 'exclude' not in cart_df.columns:
                cart_df['exclude'] = False

            with st.container(height=400):
                edited_cart = st.data_editor(
                    cart_df,
                    column_config={
                        "product_name": st.column_config.TextColumn("Produto", width="medium", disabled=True),
                        "qty": st.column_config.NumberColumn("Qtd", width="small"),
                        "total": st.column_config.NumberColumn("Total", format="R$ %.2f", width="small", disabled=True),
                        "exclude": st.column_config.CheckboxColumn("🗑️", help="Marque para excluir do carrinho"),
                        "product_id": None, "thumb": None, "base_price": None, "discount": None
                    },
                    num_rows="fixed", hide_index=True, use_container_width=True, key="cart_editor"
                )
            
            # Sync Logic
            new_cart_data = edited_cart.to_dict('records')
            final_cart = []
            
            for item in new_cart_data:
                if item.get('exclude', False): continue
                clean_item = item.copy()
                if 'exclude' in clean_item: del clean_item['exclude']
                final_cart.append(clean_item)
                
            if final_cart != st.session_state['cart']:
                for item in final_cart:
                    item['total'] = item['qty'] * item['base_price']
                st.session_state['cart'] = final_cart
                st.rerun()
            
            cart_total = sum(item['total'] for item in st.session_state['cart'])
            st.markdown(f"## Total Pedido: R$ {cart_total:.2f}")
            
            st.divider()
            st.markdown("### 📝 Dados do Pedido")
            
            with st.container(border=False):
                # Order Details
                cli_choice = st.selectbox("Cliente", client_opts + ["++ Cadastrar Novo ++"])
                
                new_cli_name = None
                new_cli_phone = None
                if cli_choice == "++ Cadastrar Novo ++":
                    c_nc1, c_nc2 = st.columns(2)
                    new_cli_name = c_nc1.text_input("Nome Completo", placeholder="Nome do Cliente")
                    new_cli_phone = c_nc2.text_input("Telefone", placeholder="(XX) 99999-9999")
                
                current_u = auth.get_current_user()
                u_name = current_u['name'] if current_u else "Desconhecido"
                salesperson_choice = st.text_input("Vendedora", value=u_name, disabled=True)
                pay_method_choice = st.selectbox("Pagamento", ["Pix", "Cartão Crédito", "Cartão Débito", "Dinheiro", "Outro"])
                notes_order = st.text_area("Observações Gerais")
                date_order = st.date_input("Data do Pedido", datetime.now())
                
                # Analysis (Unchanged logic, just cleanup)
                if True: 
                    # Start checking stock
                    shortages = []
                    has_shortage = False
                    cart_analysis = []
                    
                    for item in st.session_state['cart']:
                        r_stock = 0
                        p_id_check = int(item['product_id'])
                        
                        is_kit, kit_stock = product_service.get_kit_stock_status(conn, p_id_check)
                        
                        p_stock_row = product_service.get_product_by_id(conn, p_id_check)
                        
                        variant_id = item.get('variant_id')
                        if variant_id:
                            v_row = product_service.get_variant_by_id(conn, variant_id)
                            r_stock = v_row['stock_quantity']
                        elif is_kit:
                            r_stock = kit_stock
                        elif p_stock_row is not None:
                            r_stock = p_stock_row['stock_quantity']
                        
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

                    if has_shortage:
                        st.warning(f"⚠️ **Estoque Insuficiente detectado:** {', '.join(shortages)}")
                        st.info("Escolha como prosseguir:")
                    else:
                        st.success("✅ Estoque Completo para todos os itens.")

                    with st.container(border=True):
                        st.markdown("### Finalizar Pedido")
                        
                        calc_shortage_val = sum([c['must_order'] * c['item']['base_price'] for c in cart_analysis])
                        calc_total_val = sum([c['item']['qty'] * c['item']['base_price'] for c in cart_analysis])
                        default_dep = calc_shortage_val * 0.5 if calc_shortage_val > 0 else calc_total_val * 0.5
                            
                        c_dates1, c_dates2 = st.columns(2)
                        d_comm = c_dates1.date_input("Prazo para Encomenda (se houver)", value=datetime.now() + pd.Timedelta(days=30), format="DD/MM/YYYY")
                        deposit_val = c_dates2.number_input("Valor Sinal/Adiantamento (R$)", min_value=0.0, step=10.0, value=float(round(default_dep, 2)))
                        
                        col_act1, col_act2, col_act3 = st.columns(3)
                        
                        lbl_a = "📦 Entregar Agora + Encomendar Resto" if has_shortage else "✅ Finalizar Venda"
                        type_a = "secondary" if has_shortage else "primary"
                        
                        if col_act1.button(lbl_a, type=type_a, use_container_width=True):
                            # Resolve Client
                            final_client_id = None
                            final_client_name = None
                            valid_client = True
                            
                            if cli_choice == "++ Cadastrar Novo ++":
                                 if not new_cli_name:
                                     admin_utils.show_feedback_dialog("Digite o nome do novo cliente.", level="error")
                                     valid_client = False
                                 else:
                                     final_client_id = order_service.create_client(conn, new_cli_name, new_cli_phone)
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
                                 try:
                                     trans_uuid = f"TRX-{datetime.now().strftime('%y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
                                     order_items = []
                                     cursor = conn.cursor()
                                     
                                     for ca in cart_analysis:
                                        it = ca['item']
                                        q_sell = int(ca['can_sell'])
                                        q_order = int(ca['must_order'])
                                        
                                        # 1. Sale Portion
                                        if q_sell > 0:
                                            unit_disc = it['discount'] / it['qty']
                                            total_sell = (it['base_price'] * q_sell) - (unit_disc * q_sell)
                                            disc_sell = unit_disc * q_sell
                                            
                                            sale_data = {
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
                                            }
                                            order_service.create_sale(cursor, sale_data)
                                            
                                            # Audit
                                            audit.log_action(conn, 'CREATE', 'sales', trans_uuid, None, {'audit_msg': 'Partial Sale'}, commit=False)
                                            # Deduct Stock
                                            logs = product_service.deduct_stock(cursor, int(it['product_id']), q_sell, variant_id=it.get('variant_id'))
                                            for log in logs: st.toast(log, icon="📉")

                                        # 2. Order Portion
                                        if q_order > 0:
                                            order_items.append({
                                                'product_id': it['product_id'],
                                                'qty': q_order,
                                                'unit_price': it['base_price'],
                                                'variant_id': it.get('variant_id')
                                            })
                                            
                                     # Create Commission Order
                                     final_notes = notes_order
                                     if order_items:
                                         final_notes = f"Gerado via Venda #{trans_uuid}. Obs: {notes_order}"
                                         if deposit_val > 0:
                                             final_notes += f"\n\nSinal: R$ {deposit_val:.2f}"

                                         order_data = {
                                             'client_id': final_client_id,
                                             'date_created': date.today(),
                                             'date_due': d_comm,
                                             'status': "Pendente",
                                             'total_price': 0, 
                                             'notes': final_notes,
                                             'deposit_amount': deposit_val
                                         }
                                         new_ord_id = order_service.create_commission_order(cursor, order_data)
                                         order_service.add_commission_items(cursor, new_ord_id, order_items)
                                         
                                         # Deposit as Sale
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
                                                  "notes": f"Sinal Enc #{new_ord_id}",
                                                  "salesperson": salesperson_choice,
                                                  "order_id": f"ENC-{new_ord_id}"
                                              })
                                         
                                         admin_utils.show_feedback_dialog(f"Encomenda gerada: #{new_ord_id}", level="success")
                                     
                                     conn.commit()
                                     admin_utils.show_feedback_dialog("Venda Finalizada!", level="success")
                                     
                                     st.session_state['last_order'] = {
                                        "id": trans_uuid,
                                        "client": final_client_name,
                                        "salesperson": salesperson_choice,
                                        "payment_method": pay_method_choice,
                                        "notes": final_notes,
                                        "total": cart_total,
                                        "deposit": deposit_val if order_items else 0,
                                        "date_due": d_comm.strftime("%d/%m/%Y") if order_items else None,
                                        "items": st.session_state['cart'] 
                                     }
                                     st.session_state['cart'] = []
                                     st.rerun()

                                 except Exception as e:
                                     admin_utils.show_feedback_dialog(f"ERRO DE TRANSAÇÃO: {e}", level="error")
                        
                        # --- QUOTE BUTTON ---
                        if col_act3.button("📄 Salvar como Orçamento", type="secondary", use_container_width=True):
                             quote_creation_dialog(new_cli_name if cli_choice == '++ Cadastrar Novo ++' else cli_choice, notes_order, st.session_state['cart'], cli_choice, new_cli_name, new_cli_phone, client_dict)

                        lbl_b = "Finalizar Encomenda" 
                        force_order = col_act2.button(lbl_b, use_container_width=True, type="primary")
                        r_stock_chk = col_act2.checkbox("Usar estoque existente?", value=False)
                        
                        if force_order:
                            # Client Logic copied from above (simplified for brevity in this replace block, can be functionized further)
                            final_client_id = None
                            final_client_name = None
                            valid_client = True
                            if cli_choice == "++ Cadastrar Novo ++":
                                 if not new_cli_name:
                                     admin_utils.show_feedback_dialog("Digite o nome.", level="warning")
                                     valid_client = False
                                 else:
                                     final_client_id = order_service.create_client(conn, new_cli_name, new_cli_phone)
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
                                 cursor = conn.cursor()
                                 final_notes_B = f"Encomenda Total. Obs: {notes_order}"
                                 if deposit_val > 0:
                                     final_notes_B += f"\n\nSinal: R$ {deposit_val:.2f}"

                                 new_ord_id = order_service.create_commission_order(cursor, {
                                     'client_id': final_client_id,
                                     'date_created': date.today(),
                                     'date_due': d_comm,
                                     'status': "Pendente",
                                     'total_price': 0, 
                                     'notes': final_notes_B,
                                     'deposit_amount': deposit_val
                                 })
                                 
                                 order_items = []
                                 for ca in cart_analysis:
                                    item = ca['item']
                                    q_full = item['qty']
                                    q_res = ca['can_sell'] if r_stock_chk else 0
                                    
                                    order_items.append({
                                        'product_id': int(item['product_id']),
                                        'qty': q_full,
                                        'qty_from_stock': q_res,
                                        'unit_price': item['base_price'],
                                        'variant_id': item.get('variant_id')
                                    })
                                    
                                    if q_res > 0:
                                        logs = product_service.deduct_stock(cursor, int(item['product_id']), q_res, variant_id=item.get('variant_id'))
                                        for log in logs: st.toast(log, icon="📉")

                                 order_service.add_commission_items(cursor, new_ord_id, order_items)
                                 
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
                                          "notes": f"Sinal Enc #{new_ord_id}",
                                          "salesperson": salesperson_choice,
                                          "order_id": f"ENC-{new_ord_id}"
                                      })

                                 conn.commit()
                                 
                                 st.session_state['last_order'] = {
                                    "id": f"ENC-{new_ord_id}",
                                    "client": final_client_name,
                                    "salesperson": salesperson_choice,
                                    "payment_method": "Encomenda", 
                                    "notes": final_notes_B,
                                    "deposit": deposit_val,
                                    "date_due": d_comm.strftime("%d/%m/%Y"),
                                    "items": st.session_state['cart'], 
                                    "total": cart_total, 
                                 }
                                 st.session_state['cart'] = []
                                 st.rerun()
        else:
            st.info("Seu carrinho está vazio.")


# ==============================================================================
# TAB 2: HISTORY
# ==============================================================================
st.divider()

with st.expander("🔐 Histórico de Vendas (Área Restrita)"):
    curr_user = auth.get_current_user()
    if "hist_auth_override" not in st.session_state:
        st.session_state.hist_auth_override = False
        
    authorized = (curr_user and curr_user['role'] == 'admin') or st.session_state.hist_auth_override

    if authorized:
        st.subheader("Gerenciar Vendas")
        
        fc1, fc2, fc3, fc4 = st.columns(4)
        fil_date = fc1.date_input("Período", [], key="hist_dates", format="DD/MM/YYYY")
        fil_client = fc2.selectbox("Cliente", client_opts, key="hist_cli")
        fil_pay = fc3.selectbox("Pagamento", ["Todas", "Pix", "Cartão Crédito", "Cartão Débito", "Dinheiro", "Outro"], key="hist_pay")
        fil_salesp = fc4.selectbox("Vendedora", ["Todas", "Ira", "Neli"], key="hist_sp")
        
        tab_vendas, tab_encomendas = st.tabs(["✅ Vendas Realizadas", "📦 Encomendas Geradas"])

        with tab_vendas:
            # Service Call
            filters = {}
            if len(fil_date) == 2: filters.update({'start_date': fil_date[0], 'end_date': fil_date[1]})
            if fil_client: filters['client_name'] = fil_client
            if fil_pay: filters['payment_method'] = fil_pay
            if fil_salesp: filters['salesperson'] = fil_salesp

            sales_view = order_service.get_sales(conn, filters)
            
            group_by_order = st.checkbox("📂 Agrupar por Pedido", value=True)
        
            if not sales_view.empty:
                if group_by_order:
                    grouped = sales_view.groupby('order_id').agg({
                        'date': 'first',
                        'cliente': 'first',
                        'produto_display': lambda x: ", ".join(x),
                        'quantity': 'sum',
                        'total_price': 'sum',
                        'salesperson': 'first',
                        'payment_method': 'first',
                        'id': 'first'
                    }).reset_index().sort_values(by='id', ascending=False)
                    
                    st.data_editor(
                        grouped,
                        column_config={
                            "order_id": st.column_config.TextColumn("Pedido", disabled=True),
                            "date": st.column_config.DateColumn("Data", disabled=True, format="DD/MM/YYYY"),
                            "cliente": "Cliente",
                            "produto_display": st.column_config.TextColumn("Produtos", disabled=True),
                            "quantity": st.column_config.NumberColumn("Items", disabled=True),
                            "total_price": st.column_config.NumberColumn("Total", format="R$ %.2f", disabled=True),
                            "id": None
                        },
                        hide_index=True, key="grouped_sales_editor"
                    )
                else:
                    sales_view['remove'] = False 
                    edited_sales = st.data_editor(
                        sales_view,
                        column_config={
                            "id": st.column_config.NumberColumn(disabled=True),
                            "order_id": st.column_config.TextColumn("Pedido", disabled=True),
                            "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                            "cliente": st.column_config.TextColumn("Cliente", disabled=True),
                            "produto_display": st.column_config.TextColumn("Produto", disabled=True),
                            "quantity": st.column_config.NumberColumn("Qtd", disabled=True),
                            "total_price": st.column_config.NumberColumn("Total", format="R$ %.2f", disabled=True),
                            "remove": st.column_config.CheckboxColumn("Cancelar?", help="Estorna estoque")
                        },
                        hide_index=True, num_rows="dynamic", key="sales_editor"
                    )
                
                    if st.button("Salvar Alterações (Histórico)"):
                        # Handle Deletes
                        to_delete_ids = set(edited_sales[edited_sales['remove'] == True]['id'])
                        for did in to_delete_ids:
                            order_service.delete_sale(conn, did, restore_stock=True)
                            
                        # Handle Updates (Date, Notes...)
                        for i, row in edited_sales.iterrows():
                            if row['id'] not in to_delete_ids:
                                dv = row['date']
                                if hasattr(dv, 'date'): dv = dv.date()
                                order_service.update_sale(conn, row['id'], {
                                    'date': dv,
                                    'salesperson': row['salesperson'],
                                    'payment_method': row['payment_method'],
                                    'notes': row['notes']
                                })
                        
                        admin_utils.show_feedback_dialog("Histórico atualizado!", level="success")
                        st.rerun()
            else:
                st.info("Nenhuma venda encontrada.")

        with tab_encomendas:
             enc_filters = {}
             if len(fil_date) == 2: enc_filters.update({'start_date': fil_date[0], 'end_date': fil_date[1]})
             if fil_client: enc_filters['client_name'] = fil_client
             
             enc_view = order_service.get_commission_orders(conn, enc_filters)
             
             if not enc_view.empty:
                # Fetch items to verify
                items_df = order_service.get_commission_items(conn, enc_view['id'].tolist())
                items_df['desc'] = items_df['name'] + " (" + items_df['quantity'].astype(str) + ")"
                grouped = items_df.groupby('order_id')['desc'].apply(lambda x: ", ".join(x)).reset_index()
                grouped.columns = ['id', 'produtos']
                enc_view = enc_view.merge(grouped, on='id', how='left').fillna("-")
                
                st.dataframe(enc_view, column_config={"total_price": st.column_config.NumberColumn(format="R$ %.2f")}, use_container_width=True, hide_index=True)
             else:
                st.info("Nenhuma encomenda.")

    else:
        admin_utils.show_feedback_dialog("Acesso Restrito.", level="warning", title="Acesso Negado")
        pwd_auth = st.text_input("Senha de Administrador", type="password", key="hist_auth_pwd")
        if pwd_auth:
             if auth.verify_admin_authorization(conn, pwd_auth):
                st.session_state.hist_auth_override = True
                st.rerun()

# ==============================================================================
# TAB 3: QUOTES MANAGEMENT (Re-implemented with Tab_2 due to index match?)
# Wait, Tab structure was at top.
# ==============================================================================
with tab_quotes:
    # FILTERS
    q_f1, q_f2 = st.columns(2)
    sel_q_status = q_f1.multiselect("Status", ["Pendente", "Aprovado", "Recusado", "Expirado"], default=["Pendente"])
    sel_q_client = q_f2.text_input("Filtrar Cliente")

    quotes_df = order_service.get_all_quotes(conn) # Basic fetch
    # Join client name
    c_df = order_service.get_all_clients(conn)
    quotes_df = quotes_df.merge(c_df, left_on='client_id', right_on='id', suffixes=('', '_cli'))
    
    if sel_q_status: quotes_df = quotes_df[quotes_df['status'].isin(sel_q_status)]
    if sel_q_client: quotes_df = quotes_df[quotes_df['name'].str.contains(sel_q_client, case=False)]
    
    for _, quote in quotes_df.iterrows():
        status_icon = {"Pendente": "🟡", "Aprovado": "🟢"}.get(quote['status'], "⚪")
        with st.expander(f"{status_icon} ORC-{quote['id']} | {quote['name']} | R$ {quote['total_price']:.2f}"):
            st.write(f"Notas: {quote['notes']}")
            
            # Fetch items
            items = order_service.get_quote_items(conn, quote['id'])
            st.dataframe(items)
            
            c1, c2, c3 = st.columns(3)
            # PDF GEN
            # Fetch full item details for PDF
            pdf_items = order_service.get_quote_details_for_pdf(conn, quote['id'])
            
            pdf_data = reports.generate_quote_pdf({
                "id": f"ORC-{quote['id']}", 
                "client_name": quote.get('name', 'Cliente'),
                "date_created": pd.to_datetime(quote['date_created']).strftime('%d/%m/%Y'),
                "date_valid_until": pd.to_datetime(quote['date_valid_until']).strftime('%d/%m/%Y'),
                "items": [{
                    "id": r['product_id'], "name": r['name'], "qty": r['quantity'], "price": r['unit_price'], "notes": r['item_notes'] or ""
                } for _, r in pdf_items.iterrows()],
                "total": quote['total_price'],
                "discount": 0,
                "notes": quote['notes'], 
                "delivery": quote['delivery_terms'], 
                "payment": quote['payment_terms']
            })
            c1.download_button("📄 PDF", data=pdf_data, file_name=f"orcamento_{quote['id']}.pdf", mime="application/pdf", key=f"qp_{quote['id']}")
            
            if quote['status'] == 'Pendente':
                if c2.button("✅ Aprovar", key=f"qa_{quote['id']}"):
                    # Convert
                    order_service.create_commission_order(conn.cursor(), {
                        'client_id': quote['client_id'], 'total_price': quote['total_price'],
                        'status': 'Pendente', 'date_created': date.today(), 'date_due': date.today(),
                        'notes': f"Via ORC-{quote['id']}", 'deposit_amount': 0
                    })
                    # Update status
                    conn.cursor().execute("UPDATE quotes SET status='Aprovado' WHERE id=?", (quote['id'],))
                    conn.commit()
                    st.rerun()
                
                if c3.button("🗑️ Excluir", key=f"qd_{quote['id']}"):
                    order_service.delete_quote(conn, quote['id'])
                    st.rerun()

conn.close()
