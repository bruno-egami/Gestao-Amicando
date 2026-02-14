import streamlit as st
import pandas as pd
import database
from datetime import date, datetime, timedelta
import admin_utils
import services.product_service as product_service
import services.order_service as order_service
import audit
import reports
import time
import auth
import uuid
import os
import json
import logging
import sqlite3
from utils.logging_config import get_logger, log_exception

logger = get_logger(__name__)

st.set_page_config(page_title="Encomendas", page_icon="📦")

# Apply Global Styles
import utils.styles as styles
styles.apply_custom_style()

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
    conn_del = database.get_connection()
    try:
        order_service.delete_commission_order(conn_del, oid)
        return True
    except Exception as e:
        log_exception(logger, f"Error deleting order {oid}", e)
        admin_utils.show_feedback_dialog(f"Erro ao excluir encomenda: {e}", level="error")
        return False
    finally:
        conn_del.close()

# --- Filters ---
kf1, kf2, kf3 = st.columns([1.5, 1.5, 2])
with kf1:
    # Status Filter
    all_statuses = ["Pendente", "Em Produção", "Concluída", "Entregue"]
    sel_status = st.multiselect("Status", all_statuses, default=["Pendente", "Em Produção", "Concluída"])

with kf2:
    # Client Filter
    cli_opts = ["Todos"] + order_service.get_all_clients(conn)['name'].tolist()
    sel_client = st.selectbox("Cliente", cli_opts)

with kf3:
    # Date Range Filter (Due Date)
    d_start = st.date_input("De", value=None, format="DD/MM/YYYY")
    d_end = st.date_input("Até", value=None, format="DD/MM/YYYY")

# Fetch Orders
orders = order_service.get_orders_for_management(conn)

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
            items = order_service.get_order_items_detail(conn, order['id'])
            
            # Helper for images from product
            def get_prod_imgs(p_str):
                try:
                    import ast
                    l = ast.literal_eval(p_str)
                    return l if l and isinstance(l, list) else []
                except: return []
            
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
                                    try:
                                        order_service.update_order_images(conn_write, order['id'], order_images)
                                        st.rerun()
                                    except Exception as e:
                                        log_exception(logger, f"Error deleting image for order {order['id']}", e)
                                        st.error(f"Erro ao excluir imagem: {e}")
                                    finally:
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
                            try:
                                order_service.update_order_images(conn_write, order['id'], order_images)
                                admin_utils.show_feedback_dialog(f"{len(new_photos)} foto(s) salva(s)!", level="success")
                            except Exception as e:
                                log_exception(logger, f"Error uploading photos for order {order['id']}", e)
                                admin_utils.show_feedback_dialog(f"Erro ao salvar fotos: {e}", level="error")
                            finally:
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
                            prods_df = order_service.get_products_for_selection(conn)
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
                            vars_df = order_service.get_product_variants(conn, p_row_sel['id'])
                            
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
                                with database.db_session() as conn_check:
                                    v_stock = order_service.get_product_variants(conn_check, p_row['id'])
                                    v_match = v_stock[v_stock['id'] == sel_variant_id]
                                    if not v_match.empty:
                                        stock_av = v_match.iloc[0]['stock_quantity']
                            
                            qty_res_new = min(stock_av, new_qty) if use_stock_new else 0
                            
                            # BLOCK logic if user wants to reserve but balance is insufficient
                            if use_stock_new and new_qty > stock_av:
                                admin_utils.show_feedback_dialog(f"Estoque insuficiente para reserva! (Necessário: {new_qty}, Disponível: {int(stock_av)})", level="error")
                            else:
                                price = p_row['base_price'] + price_mod
                                
                                conn_write = database.get_connection()
                                try:
                                    order_service.add_commission_item_with_stock(
                                        conn_write, order['id'], int(p_row['id']), new_qty, 
                                        int(qty_res_new), float(price), 
                                        int(sel_variant_id) if sel_variant_id else None
                                    )
                                    admin_utils.show_feedback_dialog("Item adicionado!", level="success")
                                    st.rerun()
                                except Exception as e:
                                    log_exception(logger, f"Error adding item to order {order['id']}", e)
                                    admin_utils.show_feedback_dialog(f"Erro ao adicionar item: {e}", level="error")
                                finally:
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
                            all_clients = order_service.get_all_clients(conn)
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
                            try:
                                order_service.update_order_details(conn, order['id'], new_date, new_notes, new_discount, new_deposit, new_client_id)
                                admin_utils.show_feedback_dialog("Atualizado!", level="success")
                                st.rerun()
                            except Exception as e:
                                log_exception(logger, f"Error updating order {order['id']}", e)
                                admin_utils.show_feedback_dialog(f"Erro ao atualizar: {e}", level="error")

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
                                    conn_write = database.get_connection()
                                    try:
                                        order_service.update_item_quantity(
                                            conn_write, order['id'], item['id'], qty_edit, old_qty,
                                            item['quantity_from_stock'], item['unit_price'], item['product_id']
                                        )
                                        st.rerun()
                                    except Exception as e:
                                        log_exception(logger, f"Error updating qty for item {item['id']}", e)
                                        admin_utils.show_feedback_dialog(f"Erro na operação: {e}", level="error")
                                    finally:
                                        conn_write.close()

                    st.caption(f"Reservado: {item['quantity_from_stock']} | A Produzir: {target_prod}")
                
                with ci2:
                    produced = item['quantity_produced']
                    # WIP Qty
                    wip_qty = order_service.get_wip_quantity(conn, item['id'])
                    
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
                                        old_order_status = order['status']
                                        user_id, username = None, 'system'
                                        if 'current_user' in st.session_state and st.session_state.current_user:
                                            user_id = st.session_state.current_user.get('id')
                                            username = st.session_state.current_user.get('username', 'unknown')
                                        
                                        conn_write = database.get_connection()
                                        try:
                                            def _deduct_mats(cursor, pid, amt):
                                                product_service.deduct_production_materials_central(cursor, pid, amt, note_suffix=f"Produção Rápida Encomenda #{fmt_id}")
                                            
                                            order_service.quick_produce_item(
                                                conn_write, order['id'], item['id'], item['product_id'], amount,
                                                old_order_status, item['quantity_produced'],
                                                deduct_materials_fn=_deduct_mats,
                                                user_id=user_id, username=username
                                            )
                                            st.session_state['expanded_order_id'] = order['id']
                                            admin_utils.show_feedback_dialog("Produção lançada!", level="success")
                                            st.rerun()
                                        except Exception as e:
                                            log_exception(logger, f"Error quick producing item {item['id']}", e)
                                            admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")
                                        finally:
                                            conn_write.close()

                            with b_wip:
                                with st.popover("⏳ Iniciar Produção", use_container_width=True):
                                    st.caption("Envia para Kanban (Modelagem)")
                                    wip_amount = st.number_input("Qtd", min_value=1, max_value=remaining, value=remaining, key=f"wip_in_{item['id']}")
                                    wip_date = st.date_input("Data Início", value=date.today(), key=f"wip_date_{item['id']}")
                                    
                                    if st.button("Iniciar", key=f"wip_go_{item['id']}", type="primary"):
                                        conn_write = database.get_connection()
                                        try:
                                            order_service.start_wip_production(
                                                conn_write, order['id'], item['id'], item['product_id'], 
                                                item['variant_id'], wip_amount, wip_date.isoformat(),
                                                notes=item.get('notes'), old_order_status=order['status']
                                            )
                                            st.session_state['expanded_order_id'] = order['id']
                                            admin_utils.show_feedback_dialog("Enviado para Fluxo de Produção!", level="success")
                                            st.rerun()
                                        except Exception as e:
                                            log_exception(logger, f"Error starting WIP for item {item['id']}", e)
                                            admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")
                                        finally:
                                            conn_write.close()
                    else:
                        st.info("✅ Produção Concluída (ou Totalmente Reservado)")

                # Delete Item Button
                with ci3:
                    if st.button("❌", key=f"del_item_{item['id']}", help="Remover item da encomenda"):
                        conn_write = database.get_connection()
                        try:
                            order_service.delete_commission_item(
                                conn_write, order['id'], item['id'], item['product_id'],
                                item['quantity'], item['quantity_from_stock'], item['unit_price']
                            )
                            st.session_state['expanded_order_id'] = order['id']
                            st.rerun()
                        except Exception as e:
                            log_exception(logger, f"Error deleting item {item['id']}", e)
                            admin_utils.show_feedback_dialog(f"Erro ao excluir item: {e}", level="error")
                        finally:
                            conn_write.close()

            st.divider()
            
            # Delivery / Completion Actions
            if all_complete and order['status'] != 'Entregue':
                # Option to mark as "Ready" (Concluído) without delivering yet
                if order['status'] != 'Concluída':
                    if st.button("🏁 Marcar como Pronto", key=f"ready_{order['id']}", help="Marcar produção como finalizada e aguardando retirada"):
                        conn_write = database.get_connection()
                        try:
                            order_service.update_order_status(conn_write, order['id'], 'Concluída', old_status=order['status'])
                            st.session_state['expanded_order_id'] = order['id']
                            admin_utils.show_feedback_dialog("Status atualizado para Concluído!", level="success")
                            st.rerun()
                        except Exception as e:
                            log_exception(logger, f"Error marking ready order {order['id']}", e)
                            admin_utils.show_feedback_dialog(f"Erro ao atualizar status: {e}", level="error")
                        finally:
                            conn_write.close()

                if st.button("📦 Realizar Entrega", key=f"dlv_{order['id']}"):
                    conn_write = database.get_connection()
                    try:
                        order_data_dict = {
                            'client_id': order['client_id'],
                            'total_price': order['total_price'],
                            'deposit_amount': order['deposit_amount'],
                            'status': order['status']
                        }
                        order_service.deliver_order(conn_write, order['id'], order_data_dict, items)
                    
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
                    except Exception as e:
                        log_exception(logger, f"Error delivering order {order['id']}", e)
                        admin_utils.show_feedback_dialog(f"Erro na entrega: {e}", level="error")
                    finally:
                        conn_write.close()

conn.close()
