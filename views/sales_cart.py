
import streamlit as st
import pandas as pd
from datetime import datetime, date
import admin_utils
import auth
import services.reporting as reports
from services import product_service, order_service, sales_service
from utils.logging_config import get_logger
import database
from database import safe_transaction

logger = get_logger(__name__)

# ==============================================================================
# DIALOGS
# ==============================================================================

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
        st.session_state['receipt_dismissed'] = True
        st.rerun()

    # PDF Download
    try:
        if str(order_data.get('id', '')).startswith('ENC'):
             formatted_id = order_data.get('id') 
             type_lbl = "Encomenda"
             current_dt = datetime.now()
             # If it's already ENC-YYMMDD-ID, we keep it. If it's ENC-ID, we reformat if we have the date.
             if "-" in formatted_id and len(formatted_id.split("-")) == 2:
                  # ENC-ID -> ENC-YYMMDD-ID
                  raw_id = formatted_id.split("-")[1]
                  formatted_id = f"ENC-{current_dt.strftime('%y%m%d')}-{raw_id}"

             rep_data = {
                 "id": formatted_id,
                 "type": type_lbl,
                 "date": current_dt.strftime("%d/%m/%Y"),
                 "date_due": order_data.get('date_due', "-"),
                 "client_name": order_data.get('client', 'Cliente'),
                 "salesperson": order_data.get('salesperson', '-'),
                 "notes": order_data.get('notes', ''),
                 "items": [],
                 "total": order_data.get('total', 0),
                 "deposit": order_data.get('deposit', 0)
             }
             for item in order_data['items']:
                 rep_data['items'].append({
                     "name": item.get('product_name', item.get('name', 'Item')),
                     "qty": item['qty'],
                     "price": item.get('base_price', item.get('price', 0)),
                     "notes": item.get('variant_name', '')
                 })
             pdf_bytes = reports.generate_commission_receipt_pdf(rep_data)
        else:
             current_dt = datetime.now()
             try:
                 if 'date' in order_data:
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
                 "items": [],
                 "total": order_data.get('total', 0),
                 "discount": 0, 
                 "deposit": order_data.get('deposit', 0)
             }
             for item in order_data['items']:
                 rep_data['items'].append({
                     "name": item.get('product_name', item.get('name', 'Item')),
                     "qty": item['qty'],
                     "price": item.get('base_price', item.get('price', 0)),
                     "total": item.get('total', item['qty'] * item.get('base_price', item.get('price', 0)))
                 })
             pdf_bytes = reports.generate_receipt_pdf(rep_data)
        
        st.download_button(
            label="📄 Baixar Recibo (PDF)",
            data=pdf_bytes,
            file_name=f"{formatted_id}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")

@st.dialog("Criar Orçamento")
def quote_creation_dialog(client_display_name, initial_notes, cart_items, cli_choice_val, n_name, n_phone, c_dict):
    if 'quote_created_id' not in st.session_state:
        st.session_state.quote_created_id = None

    if st.session_state.quote_created_id:
        # Standard ID for success message
        success_id = f"ORC-{date.today().strftime('%y%m%d')}-{st.session_state.quote_created_id}"
        st.success(f"Orçamento #{success_id} criado com sucesso!")
        if st.button("Concluir", type="primary", use_container_width=True):
            st.session_state.quote_created_id = None
            st.rerun()
        return

    st.write(f"Cliente: {client_display_name}")
    
    qd_valid = st.number_input("Validade (dias)", value=30, min_value=1)
    qd_deliv = st.text_input("Prazo Entrega", value="45 dias após confirmação")
    qd_pay = st.text_input("Condições Pagamento", value="50% entrada + saldo na entrega")
    qd_note = st.text_area("Observações", value=initial_notes)
    
    if st.button("Confirmar Criação", type="primary"):
        try:
            with database.db_session() as conn:
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
                        'notes': note_txt,
                        'variant_id': item.get('variant_id') # Added variant_id
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
                
                # Success state
                st.session_state.quote_created_id = quote_id
                st.session_state['cart'] = []
                st.rerun()

        except Exception as e:
            if type(e).__name__ in ["RerunException", "StopException"]:
                raise e
            st.error(f"Erro ao salvar orçamento: {e}")

# ==============================================================================
# RENDER CART & CHECKOUT
# ==============================================================================

def render_cart_section(conn, products_df, client_opts, client_dict):
    # A. ITEM FORM (If product selected)
    if st.session_state.get('selected_product_id'):
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
            
            # Checkbox for Discount (Discreet)
            item_disc = 0.0
            with c_disc:
                if st.checkbox("Desconto", key=f"chk_disc_{sel_row['id']}"):
                    item_disc = st.number_input("Valor (R$)", min_value=0.0, step=0.1, value=0.0, key="item_disc")
            
            # Calc Preview
            base_price_effective = sel_row['base_price'] + price_adder
            base_total = base_price_effective * item_qty
            item_final = max(0.0, base_total - item_disc)
            
            st.write(f"Preço Unit.: **R$ {base_price_effective:.2f}**")
            st.write(f"Total Item: **R$ {item_final:.2f}**")
            
            # Check cart for this product/variant
            in_cart = 0
            for i in st.session_state.get('cart', []):
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

                # Check if item already exists in cart to merge
                existing_item = None
                if 'cart' not in st.session_state: st.session_state['cart'] = []
                
                for item in st.session_state['cart']:
                    p_match = (item['product_id'] == sel_row['id'])
                    v_match = (item.get('variant_id') == (selected_variant['id'] if selected_variant else None))
                    if p_match and v_match:
                        existing_item = item
                        break
                
                if existing_item:
                    # Merge
                    existing_item['qty'] += item_qty
                    existing_item['discount'] += item_disc
                    # Recalculate total
                    base_val = existing_item['qty'] * existing_item['base_price']
                    existing_item['total'] = max(0.0, base_val - existing_item['discount'])
                    st.toast(f"Item atualizado no carrinho! Qtd: {existing_item['qty']}", icon="🔄")
                else:
                    # Add New
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
                    st.toast("Item adicionado ao carrinho!", icon="🛒")

                st.session_state['selected_product_id'] = None # Deselect
                st.rerun()

    # B. CART DISPLAY
    st.divider()
    st.subheader(f"🛒 Carrinho ({len(st.session_state.get('cart', []))})")
    
    if st.session_state.get('cart'):
        cart_df = pd.DataFrame(st.session_state['cart'])
        if 'exclude' not in cart_df.columns:
            cart_df['exclude'] = False
        
        # Reorder columns
        cols_order = ['exclude', 'product_name', 'qty', 'base_price', 'discount', 'total']
        existing_cols = cart_df.columns.tolist()
        final_order = [c for c in cols_order if c in existing_cols] + [c for c in existing_cols if c not in cols_order]
        cart_df = cart_df[final_order]

        with st.container(height=400):
            edited_cart = st.data_editor(
                cart_df,
                column_config={
                    "exclude": st.column_config.CheckboxColumn("🗑️", width="small", help="Marque para excluir"),
                    "product_name": st.column_config.TextColumn("Produto", width="medium", disabled=True),
                    "qty": st.column_config.NumberColumn("Qtd", width="small", min_value=1),
                    "base_price": st.column_config.NumberColumn("Preço Unit.", format="R$ %.2f", disabled=True),
                    "discount": st.column_config.NumberColumn("Desc.", format="R$ %.2f", min_value=0.0, step=0.1),
                    "total": st.column_config.NumberColumn("Total", format="R$ %.2f", disabled=True),
                    "product_id": None, "thumb": None, "variant_id": None, "variant_name": None
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
            # Recalculate totals if Qty or Discount changed
            for item in final_cart:
                # Protect against NaN
                qty = float(item.get('qty', 1))
                price = float(item.get('base_price', 0))
                disc = float(item.get('discount', 0))
                item['total'] = max(0.0, (qty * price) - disc)
                item['qty'] = int(qty)
                
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
            
            # Analysis
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
                                # Call Sales Service
                                result = sales_service.process_sale_transaction(
                                    conn, 
                                    cart_analysis, 
                                    final_client_id, 
                                    salesperson_choice, 
                                    pay_method_choice, 
                                    notes_order, 
                                    d_comm, 
                                    deposit_val
                                )
                                
                                trans_uuid = result['trans_id']
                                new_ord_id = result['order_id']
                                logs = result['logs']
                                
                                for log in logs: st.toast(log, icon="📉")
                                
                                if new_ord_id:
                                    admin_utils.show_feedback_dialog(f"Encomenda gerada: #{new_ord_id}", level="success")
                                
                                admin_utils.show_feedback_dialog("Venda Finalizada!", level="success")
                                
                                # Construct Receipt Data
                                final_notes = notes_order
                                if new_ord_id:
                                    final_notes = f"Gerado via Venda #{trans_uuid}. Obs: {notes_order}"
                                    if deposit_val > 0:
                                        final_notes += f"\n\nSinal: R$ {deposit_val:.2f}"
                                
                                has_order = new_ord_id is not None
                                
                                current_date_str = date.today().strftime('%y%m%d')
                                st.session_state['last_order'] = {
                                    "id": f"ENC-{current_date_str}-{new_ord_id}" if has_order else trans_uuid,
                                    "client": final_client_name,
                                    "salesperson": salesperson_choice,
                                    "payment_method": pay_method_choice,
                                    "notes": final_notes,
                                    "total": cart_total,
                                    "deposit": deposit_val if has_order else 0,
                                    "date_due": d_comm.strftime("%d/%m/%Y") if has_order else None,
                                    "items": st.session_state['cart'] 
                                }
                                st.session_state['cart'] = []
                                st.session_state['receipt_dismissed'] = False
                                # Moved rerun outside the big try-except block later
                                do_rerun = True

                            except Exception as e:
                                if type(e).__name__ in ["RerunException", "StopException"]:
                                    raise e
                                admin_utils.show_feedback_dialog(f"ERRO DE TRANSAÇÃO: {e}", level="error")
                     
                        if do_rerun:
                            st.rerun()
                    
                    # --- QUOTE BUTTON ---
                    if col_act3.button("📄 Salvar como Orçamento", type="secondary", use_container_width=True):
                        quote_creation_dialog(new_cli_name if cli_choice == '++ Cadastrar Novo ++' else cli_choice, notes_order, st.session_state['cart'], cli_choice, new_cli_name, new_cli_phone, client_dict)

                    lbl_b = "Finalizar Encomenda" 
                    force_order = col_act2.button(lbl_b, use_container_width=True, type="primary")
                    r_stock_chk = col_act2.checkbox("Usar estoque existente?", value=False)
                    
                    if force_order:
                        # Client Logic copied
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
                            try:
                                with safe_transaction(conn):
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

                                    current_date_str = date.today().strftime('%y%m%d')
                                    st.session_state['last_order'] = {
                                        "id": f"ENC-{current_date_str}-{new_ord_id}",
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
                                    st.session_state['receipt_dismissed'] = False
                                    do_rerun_enc = True
                                    
                            except Exception as e:
                                if type(e).__name__ in ["RerunException", "StopException"]:
                                    raise e
                                admin_utils.show_feedback_dialog(f"Erro ao finalizar encomenda: {e}", level="error")
                             
                            if do_rerun_enc:
                                st.rerun()
    else:
        st.info("Seu carrinho está vazio.")
