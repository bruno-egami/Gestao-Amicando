import streamlit as st
import pandas as pd
import database
from datetime import date, datetime, timedelta
import admin_utils
import audit
import reports
import auth
import os
import uuid
import time

st.set_page_config(page_title="Orçamentos", page_icon="📝", layout="wide")

admin_utils.render_sidebar_logo()
conn = database.get_connection()

if not auth.require_login(conn):
    st.stop()

auth.render_custom_sidebar()
current_user = auth.get_current_user()
st.title("📝 Orçamentos")

if 'expanded_quote' not in st.session_state:
    st.session_state['expanded_quote'] = None

# --- HELPER FUNCTIONS ---
def delete_quote(quote_id):
    """Delete a quote and its items"""
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quote_items WHERE quote_id=?", (quote_id,))
        cursor.execute("DELETE FROM quotes WHERE id=?", (quote_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao excluir orçamento: {e}")
        return False

def calculate_quote_total(quote_id):
    """Calculate and update quote total"""
    cursor = conn.cursor()
    result = cursor.execute(
        "SELECT SUM(quantity * unit_price) FROM quote_items WHERE quote_id=?", 
        (quote_id,)
    ).fetchone()
    total = result[0] if result[0] else 0
    
    # Get discount
    discount = cursor.execute("SELECT discount FROM quotes WHERE id=?", (quote_id,)).fetchone()[0] or 0
    final_total = total - discount
    
    cursor.execute("UPDATE quotes SET total_price=? WHERE id=?", (final_total, quote_id))
    conn.commit()
    return final_total

def update_quote_item(item_id, quote_id, key_prefix):
    """Callback to update quote item on change"""
    try:
        new_val = st.session_state[f"{key_prefix}_{item_id}"]
        cursor = conn.cursor()
        
        if key_prefix == "q": # Qty
            cursor.execute("UPDATE quote_items SET quantity=? WHERE id=?", (new_val, item_id))
        elif key_prefix == "n": # Note
            cursor.execute("UPDATE quote_items SET item_notes=? WHERE id=?", (new_val, item_id))
        elif key_prefix == "p": # Price
            cursor.execute("UPDATE quote_items SET unit_price=? WHERE id=?", (new_val, item_id))
            
        conn.commit()
        calculate_quote_total(quote_id)
        st.session_state['expanded_quote'] = quote_id
        # No need to rerun manually as callback happens during rerun flow or triggers one? 
        # Streamlit callbacks run before the script reruns. So the rerun will reflect the new state.
        # We don't need st.rerun() here usually.
    except Exception as e:
        print(f"Error updating item: {e}")

# --- FILTERS ---
st.subheader("🔍 Filtros")
c_filt1, c_filt2, c_filt3 = st.columns(3)

with c_filt1:
    status_opts = ["Pendente", "Aprovado", "Recusado", "Expirado"]
    sel_status = st.multiselect("Status", status_opts, default=["Pendente"])

with c_filt2:
    clients_df = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    client_opts = ["Todos"] + clients_df['name'].tolist()
    sel_client = st.selectbox("Cliente", client_opts)

with c_filt3:
    d_start = st.date_input("De", value=None, format="DD/MM/YYYY", key="q_start")

# --- FETCH QUOTES ---
quotes = pd.read_sql("""
    SELECT q.id, c.name as client, q.date_created, q.date_valid_until, 
           q.status, q.total_price, q.discount, q.notes, q.client_id,
           q.delivery_terms, q.payment_terms
    FROM quotes q
    JOIN clients c ON q.client_id = c.id
    ORDER BY q.date_created DESC
""", conn)

# Apply filters
if not quotes.empty:
    if sel_status:
        quotes = quotes[quotes['status'].isin(sel_status)]
    if sel_client != "Todos":
        quotes = quotes[quotes['client'] == sel_client]
    if d_start:
        quotes = quotes[pd.to_datetime(quotes['date_created']).dt.date >= d_start]

st.divider()

# --- NEW QUOTE BUTTON ---
with st.expander("➕ Novo Orçamento", expanded=False):
    nc_tab1, nc_tab2 = st.tabs(["👥 Cliente Existente", "✨ Novo Cliente"])
    
    # Existing Client
    with nc_tab1:
        with st.form("new_quote_form"):
            nq_col1, nq_col2 = st.columns(2)
            with nq_col1:
                nq_client = st.selectbox("Cliente*", clients_df['name'].tolist())
                nq_valid = st.number_input("Validade (dias)", min_value=1, value=30)
            with nq_col2:
                nq_delivery = st.text_input("Prazo de Entrega", value="45 dias após a confirmação do orçamento e pagamento da entrada")
                nq_payment = st.text_input("Condições Pagamento", value="50% de entrada + saldo na entrega")
            
            nq_notes = st.text_area("Observações Gerais", value="O envio do logo é responsabilidade do cliente.")
            
            if st.form_submit_button("✅ Criar Orçamento"):
                try:
                    client_id = int(clients_df[clients_df['name'] == nq_client]['id'].values[0])
                    valid_date = (date.today() + timedelta(days=nq_valid)).isoformat()
                    
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO quotes (client_id, date_created, date_valid_until, status, total_price, notes, delivery_terms, payment_terms)
                        VALUES (?, ?, ?, 'Pendente', 0, ?, ?, ?)
                    """, (client_id, date.today().isoformat(), valid_date, nq_notes, nq_delivery, nq_payment))
                    conn.commit()
                    st.success("✅ Orçamento criado! Adicione produtos abaixo.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    # New Client
    with nc_tab2:
        with st.form("new_client_quote"):
            nc_col1, nc_col2 = st.columns(2)
            with nc_col1:
                new_c_name = st.text_input("Nome do Cliente*")
                new_c_doc = st.text_input("CPF/CNPJ")
            with nc_col2:
                new_c_email = st.text_input("Email")
                new_c_phone = st.text_input("Telefone")
            
            st.divider()
            qc_col1, qc_col2 = st.columns(2)
            with qc_col1:
                nc_valid = st.number_input("Validade do Orçamento (dias)", min_value=1, value=30, key="nc_valid")
            with qc_col2:
                nc_delivery = st.text_input("Prazo de Entrega", value="45 dias após a confirmação do orçamento e pagamento da entrada", key="nc_delivery")
                nc_payment = st.text_input("Condições Pagamento", value="50% de entrada + saldo na entrega", key="nc_payment")
                
            nc_notes = st.text_area("Observações Gerais (Orçamento)", value="O envio do logo é responsabilidade do cliente.")
            
            if st.form_submit_button("✅ Cadastrar e Criar"):
                if not new_c_name:
                    st.error("Nome é obrigatório")
                else:
                    try:
                        cursor = conn.cursor()
                        # Create Client
                        cursor.execute("""
                            INSERT INTO clients (name, document, email, phone)
                            VALUES (?, ?, ?, ?)
                        """, (new_c_name, new_c_doc, new_c_email, new_c_phone))
                        new_client_id = cursor.lastrowid
                        if isinstance(new_client_id, bytes):
                            new_client_id = int.from_bytes(new_client_id, "little")
                        
                        # Create Quote
                        valid_date = (date.today() + timedelta(days=nc_valid)).isoformat()
                        cursor.execute("""
                            INSERT INTO quotes (client_id, date_created, date_valid_until, status, total_price, notes, delivery_terms, payment_terms)
                            VALUES (?, ?, ?, 'Pendente', 0, ?, ?, ?)
                        """, (new_client_id, date.today().isoformat(), valid_date, nc_notes, nc_delivery, nc_payment))
                        conn.commit()
                        
                        st.success("✅ Cliente cadastrado e orçamento criado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

# --- DISPLAY QUOTES ---
if quotes.empty:
    st.info("Nenhum orçamento encontrado com os filtros atuais.")
else:
    # Helper to get image path safely (return LIST)
    def get_img_paths(p_str):
        try:
             l = eval(p_str)
             return l if l and isinstance(l, list) else []
        except: return []

    for _, quote in quotes.iterrows():
        # Status color
        status_colors = {
            "Pendente": "🟡",
            "Aprovado": "🟢",
            "Recusado": "🔴",
            "Expirado": "⚪"
        }
        status_icon = status_colors.get(quote['status'], "⚪")
        
        # Check expiration
        valid_until = pd.to_datetime(quote['date_valid_until']).date()
        is_expired = valid_until < date.today() and quote['status'] == 'Pendente'
        
        is_exp = (st.session_state.get('expanded_quote') == quote['id'])
        
        # Format ID for Display
        q_dt = pd.to_datetime(quote['date_created'])
        fmt_id = f"ORC-{q_dt.strftime('%y%m%d')}-{quote['id']}"
        
        with st.expander(f"{status_icon} {fmt_id} - {quote['client'] or 'Cliente Removido'} | R$ {quote['total_price']:.2f} | {quote['status']}", expanded=is_exp):
            # Info row
            c_info1, c_info2, c_info3 = st.columns(3)
            with c_info1:
                st.write(f"📅 **Criado:** {pd.to_datetime(quote['date_created']).strftime('%d/%m/%Y')}")
            
            with c_info2:
                if is_expired:
                    st.write(f"⏰ **Validade:** :red[EXPIRADO - {valid_until.strftime('%d/%m/%Y')}]")
                else:
                    days_left = (valid_until - date.today()).days
                    st.write(f"⏰ **Validade:** {valid_until.strftime('%d/%m/%Y')} ({days_left} dias)")
            
            with c_info3:
                st.metric("Total", f"R$ {quote['total_price']:.2f}")
            
            if quote['notes']:
                st.caption(f"📝 {quote['notes']}")
            if quote['delivery_terms'] or quote['payment_terms']:
                st.caption(f"🚚 Entrega: {quote['delivery_terms'] or 'N/A'} | 💲 Pagamento: {quote['payment_terms'] or 'N/A'}")
            
            st.divider()
            
            # Fetch items
            items = pd.read_sql("""
                SELECT qi.id, qi.product_id, p.name, p.image_paths, qi.quantity, qi.unit_price, qi.item_notes
                FROM quote_items qi
                LEFT JOIN products p ON qi.product_id = p.id
                WHERE qi.quote_id = ?
            """, conn, params=(quote['id'],))
            
            # Display items with images
            if not items.empty:
                st.write("**Itens do Orçamento:**")
                for _, item in items.iterrows():
                    ci1, ci2, ci3, ci4, ci5 = st.columns([0.5, 2, 1, 1, 1])
                    
                    # Product image
                    with ci1:
                        if item['image_paths']:
                            try:
                                imgs = eval(item['image_paths'])
                                if imgs and os.path.exists(imgs[0]):
                                    st.image(imgs[0], width=50)
                                else:
                                    st.write("📦")
                            except Exception:
                                st.write("📦")
                        else:
                            st.write("📦")
                    
                    with ci2:
                        st.write(f"**{item['name'] or 'Produto (ID: ' + str(item['product_id']) + ')'}**")
                        if quote['status'] == 'Pendente':
                            st.text_input(
                                "Obs", 
                                value=item['item_notes'] or "", 
                                key=f"n_{item['id']}",
                                label_visibility="collapsed",
                                placeholder="Notas do item...",
                                on_change=lambda id=item['id']: update_quote_item(id, quote['id'], "n")
                            )
                        else:
                             if item['item_notes']:
                                 st.caption(f"📝 {item['item_notes']}")
                    
                    with ci3:
                        if quote['status'] == 'Pendente':
                            st.number_input(
                                "Qtd", 
                                value=int(item['quantity']), 
                                min_value=1, 
                                key=f"q_{item['id']}",
                                label_visibility="collapsed",
                                on_change=lambda id=item['id']: update_quote_item(id, quote['id'], "q")
                            )
                        else:
                            st.write(f"Qtd: {item['quantity']}")

                    with ci4:
                        if quote['status'] == 'Pendente':
                            st.number_input(
                                "Preço (R$)", 
                                value=float(item['unit_price']), 
                                min_value=0.0, 
                                step=1.0, 
                                format="%.2f",
                                key=f"p_{item['id']}",
                                label_visibility="collapsed",
                                on_change=lambda id=item['id']: update_quote_item(id, quote['id'], "p")
                            )
                        else:
                            st.write(f"R$ {item['unit_price']:.2f}")

                    with ci5:
                         st.write(f"**R$ {item['quantity'] * item['unit_price']:.2f}**")
                         if quote['status'] == 'Pendente':
                             if st.button("🗑️", key=f"del_{item['id']}"):
                                 delete_quote_item(item['id'], quote['id'])
                         else:
                             st.write(f"Qtd: {item['quantity']}")
                    
                    with ci4:
                        st.write(f"R$ {item['quantity'] * item['unit_price']:.2f}")

                        if quote['status'] == 'Pendente':
                             # Delete Button (Aligned with price somewhat)
                             if st.button("🗑️", key=f"del_{quote['id']}_{item['id']}"):
                                 cursor = conn.cursor()
                                 cursor.execute("DELETE FROM quote_items WHERE id=?", (item['id'],))
                                 conn.commit()
                                 calculate_quote_total(quote['id'])
                                 st.session_state['expanded_quote'] = quote['id']
                                 st.rerun()
            else:
                st.caption("Nenhum item adicionado ainda.")
            
            st.divider()
            
            # ACTIONS SECTION
            st.write("**Ações:**")
            
            # Logic: All statuses get PDF. Pending gets Edit/Delete/Approve.
            if quote['status'] == 'Pendente':
                 c_act1, c_act2, c_act3, c_act4, c_act5 = st.columns(5)
            else:
                 c_act5 = st.container() # Just for PDF if not pending
            
            # PDF Generation (Available for ALL statuses)
            with c_act5:
                # Formatted Filename and ID
                q_date = pd.to_datetime(quote['date_created'])
                fmt_id = f"ORC-{q_date.strftime('%y%m%d')}-{quote['id']}"
                fname = f"{fmt_id}.pdf"
                
                # Generate PDF
                pdf_data = reports.generate_quote_pdf({
                    "id": fmt_id, 
                    "client_name": quote['client'] or "Cliente não identificado",
                    "date_created": pd.to_datetime(quote['date_created']).strftime('%d/%m/%Y'),
                    "date_valid_until": valid_until.strftime('%d/%m/%Y'),
                    "items": [{
                        "name": r['name'] or f"Produto #{r['product_id']}", 
                        "id": r['product_id'], 
                        "qty": r['quantity'] or 0, 
                        "price": r['unit_price'] or 0.0, 
                        "notes": r.get('item_notes', ''),
                        "images": get_img_paths(r['image_paths'])
                    } for _, r in items.iterrows()],
                    "total": quote['total_price'],
                    "discount": quote['discount'] or 0,
                    "notes": quote['notes'],
                    "delivery": quote['delivery_terms'],
                    "payment": quote['payment_terms']
                })
                
                st.download_button(
                    "📄 PDF",
                    data=pdf_data,
                    file_name=fname,
                    mime="application/pdf",
                    key=f"pdf_{quote['id']}"
                )

            # Pending-only Actions
            if quote['status'] == 'Pendente':
                # Add Product
                with c_act1:

                    with st.popover("➕ Adicionar Produto"):
                        base_tab, new_tab = st.tabs(["📦 Existente", "✨ Novo"])
                        
                        # --- Tab 1: Existing Product ---
                        # --- Tab 1: Catalog (Visual Grid) ---
                        with base_tab:
                            # Fetch products with images
                            all_products = pd.read_sql("SELECT id, name, base_price, image_paths, category FROM products ORDER BY name", conn)
                            
                            # Filters
                            c_cat_f1, c_cat_f2 = st.columns([1, 1])
                            
                            cats = ["Todas"] + sorted(all_products['category'].fillna("Sem Categoria").unique().tolist())
                            sel_cat_add = c_cat_f1.selectbox("Categoria", cats, key=f"cat_s_{quote['id']}")
                            cat_search = c_cat_f2.text_input("🔍 Buscar", placeholder="Nome...", key=f"s_{quote['id']}")
                            
                            # Filter Logic
                            filtered_prods = all_products.copy()
                            if sel_cat_add != "Todas":
                                filtered_prods = filtered_prods[filtered_prods['category'] == sel_cat_add]
                            
                            if cat_search:
                                filtered_prods = filtered_prods[filtered_prods['name'].str.contains(cat_search, case=False, na=False)]
                                
                            if filtered_prods.empty:
                                st.warning("Nenhum produto encontrado.")
                            else:
                                # Grid Logic (3 cols)
                                cols_per_row = 3
                                rows = [filtered_prods.iloc[i:i+cols_per_row] for i in range(0, len(filtered_prods), cols_per_row)]
                                
                                for row_chunk in rows:
                                    g_cols = st.columns(cols_per_row)
                                    for g_idx, (g_col, product) in enumerate(zip(g_cols, row_chunk.itertuples())):
                                        with g_col:
                                            with st.container(border=True):
                                                # Image Display
                                                thumb = None
                                                if product.image_paths:
                                                    try:
                                                        paths = eval(product.image_paths)
                                                        if paths and os.path.exists(paths[0]):
                                                            thumb = paths[0]
                                                    except: pass
                                                
                                                if thumb:
                                                    st.image(thumb, use_container_width=True)
                                                else:
                                                    st.markdown("<div style='height:100px; display:flex; align-items:center; justify-content:center; background:#f0f0f0;'>Unknown</div>", unsafe_allow_html=True)
                                                
                                                # Info
                                            st.markdown(f"**{product.name}**")
                                            st.caption(f"R$ {product.base_price:.2f}")
                                            
                                            # Inputs
                                            qty = st.number_input("Qtd", min_value=1, value=1, label_visibility="collapsed", key=f"q_{quote['id']}_{product.id}")
                                            item_note = st.text_input("Obs (opcional)", key=f"n_{quote['id']}_{product.id}", placeholder="Personalização...")
                                            
                                            if st.button("➕ Add", key=f"add_{quote['id']}_{product.id}", type="primary", use_container_width=True):
                                                try:
                                                    # FIX: Force int casting to avoid byte corruption
                                                    safe_prod_id = int(product.id)
                                                    
                                                    cursor = conn.cursor()
                                                    cursor.execute("""
                                                        INSERT INTO quote_items (quote_id, product_id, quantity, unit_price, item_notes)
                                                        VALUES (?, ?, ?, ?, ?)
                                                    """, (quote['id'], safe_prod_id, qty, product.base_price, item_note))
                                                    conn.commit()
                                                    
                                                    calculate_quote_total(quote['id'])
                                                    st.toast(f"✅ {product.name} adicionado!", icon="🛒")
                                                    time.sleep(0.5) 
                                                    st.session_state['expanded_quote'] = quote['id']
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(f"Erro: {e}")

                        # --- Tab 2: New Product (Orçamento) ---
                        with new_tab:
                            with st.form(f"create_prod_quote_{quote['id']}"):
                                new_p_name = st.text_input("Nome do Produto")
                                new_p_price = st.number_input("Preço Sugerido", min_value=0.0, step=0.1)
                                new_p_qty = st.number_input("Quantidade", min_value=1, value=1, key=f"np_qty_{quote['id']}")
                                new_p_note = st.text_input("Obs (opcional)")
                                new_p_img = st.file_uploader("Imagem", type=["png", "jpg", "jpeg", "webp"])
                                
                                if st.form_submit_button("Criar e Adicionar"):
                                    if not new_p_name:
                                        st.error("Nome obrigatório")
                                    else:
                                        try:
                                            cursor = conn.cursor()
                                            
                                            # Ensure 'Orçamento' category exists
                                            cursor.execute("INSERT OR IGNORE INTO product_categories (name) VALUES ('Orçamento')")
                                            
                                            # Handle image
                                            img_paths = []
                                            if new_p_img:
                                                save_dir = "assets/product_images"
                                                if not os.path.exists(save_dir): os.makedirs(save_dir)
                                                f_path = os.path.join(save_dir, f"{uuid.uuid4().hex[:8]}_{new_p_img.name}")
                                                with open(f_path, "wb") as f:
                                                    f.write(new_p_img.getbuffer())
                                                img_paths.append(f_path)
                                            
                                            # Create Product
                                            cursor.execute("""
                                                INSERT INTO products 
                                                (name, category, base_price, stock_quantity, image_paths, date_added)
                                                VALUES (?, 'Orçamento', ?, 0, ?, ?)
                                            """, (new_p_name, new_p_price, str(img_paths), date.today().isoformat()))
                                            
                                            new_prod_id = cursor.lastrowid
                                            if isinstance(new_prod_id, bytes):
                                                new_prod_id = int.from_bytes(new_prod_id, "little")
                                            
                                            # Add to Quote
                                            cursor.execute("""
                                                INSERT INTO quote_items (quote_id, product_id, quantity, unit_price, item_notes)
                                                VALUES (?, ?, ?, ?, ?)
                                            """, (quote['id'], new_prod_id, new_p_qty, new_p_price, new_p_note))
                                            conn.commit()
                                            
                                            calculate_quote_total(quote['id'])
                                            st.session_state['expanded_quote'] = quote['id']
                                            st.success("Produto criado e adicionado!")
                                            st.rerun()
                                            
                                        except Exception as e:
                                            st.error(f"Erro: {e}")
                
                # Edit Quote Button
                with c_act2:
                    with st.popover("✏️ Editar"):
                        with st.form(f"edit_quote_{quote['id']}"):
                            eq_client = st.selectbox("Cliente", clients_df['name'].tolist(), index=int(clients_df[clients_df['name'] == quote['client']].index[0]) if quote['client'] in clients_df['name'].tolist() else 0)
                            eq_valid = st.number_input("Validade (dias)", value=30)
                            eq_delivery = st.text_input("Prazo de Entrega", value=quote['delivery_terms'] or "")
                            eq_payment = st.text_input("Condições Pagamento", value=quote['payment_terms'] or "")
                            eq_notes = st.text_area("Notas Gerais", value=quote['notes'] or "")
                            
                            if st.form_submit_button("Salvar Alterações"):
                                try:
                                    new_cid = int(clients_df[clients_df['name'] == eq_client]['id'].values[0])
                                    new_valid = (date.today() + timedelta(days=eq_valid)).isoformat()
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE quotes SET client_id=?, date_valid_until=?, notes=?, delivery_terms=?, payment_terms=? WHERE id=?", 
                                                   (new_cid, new_valid, eq_notes, eq_delivery, eq_payment, quote['id']))
                                    conn.commit()
                                    st.success("Atualizado!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro: {e}")

                # Approve (convert to order)
                with c_act3:
                    with st.popover("✅ Aprovar"):
                        st.markdown("**Confirmar aprovação?**")
                        st.caption("Uma encomenda será gerada automaticamente.")
                        
                        # Deposit Input
                        deposit_val = st.number_input(
                            "Valor do Sinal Recebido (R$)", 
                            min_value=0.0, 
                            value=0.0, 
                            step=10.0,
                            format="%.2f",
                            key=f"dep_app_{quote['id']}"
                        )
                        
                        if st.button("Confirmar", key=f"confirm_app_{quote['id']}", type="primary"):
                            if items.empty:
                                st.error("Adicione pelo menos um item!")
                            else:
                                # Create commission order
                                cursor = conn.cursor()
                                
                                # Format Quote ID for reference
                                q_date_obj = pd.to_datetime(quote['date_created'])
                                fmt_q_id = f"ORC-{q_date_obj.strftime('%y%m%d')}-{quote['id']}"
                                
                                cursor.execute("""
                                    INSERT INTO commission_orders 
                                    (client_id, total_price, date_created, date_due, status, notes, deposit_amount)
                                    VALUES (?, ?, ?, ?, 'Pendente', ?, ?)
                                """, (
                                    quote['client_id'], 
                                    quote['total_price'],
                                    datetime.now().isoformat(),
                                    (date.today() + timedelta(days=30)).isoformat(),
                                    f"Originado do Orçamento #{fmt_q_id}.\nPrazo: {quote['delivery_terms'] or 'N/A'}\nPagamento: {quote['payment_terms'] or 'N/A'}\nObs: {quote['notes'] or ''}",
                                    deposit_val
                                ))
                                order_id = cursor.lastrowid
                                if isinstance(order_id, bytes):
                                    order_id = int.from_bytes(order_id, "little")
                                
                                # Copy items to order
                                for _, item in items.iterrows():
                                    cursor.execute("""
                                        INSERT INTO commission_items (order_id, product_id, quantity, unit_price, notes)
                                        VALUES (?, ?, ?, ?, ?)
                                    """, (order_id, item['product_id'], item['quantity'], item['unit_price'], item.get('item_notes', '')))
                                    
                                # Update quote status
                                cursor.execute(
                                    "UPDATE quotes SET status='Aprovado', converted_order_id=? WHERE id=?",
                                    (order_id, quote['id'])
                                )
                                conn.commit()
                                
                                st.success(f"✅ Orçamento aprovado! Encomenda #{order_id} criada.")
                                st.rerun()
                
                # Reject
                with c_act3:
                    if st.button("❌ Recusar", key=f"reject_{quote['id']}"):
                        cursor = conn.cursor()
                        cursor.execute("UPDATE quotes SET status='Recusado' WHERE id=?", (quote['id'],))
                        conn.commit()
                        st.warning("Orçamento marcado como recusado.")
                        st.rerun()
                
                # Delete
                with c_act4:
                    if st.button("🗑️ Excluir", key=f"del_quote_{quote['id']}"):
                        if delete_quote(quote['id']):
                            st.success("Orçamento excluído!")
                            st.rerun()
            
            # View converted order link
            elif quote['status'] == 'Aprovado':
                st.info(f"✅ Este orçamento foi convertido em encomenda. Acesse a página de Encomendas para gerenciá-la.")
