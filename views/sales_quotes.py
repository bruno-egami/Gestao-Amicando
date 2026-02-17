import streamlit as st
import pandas as pd
from datetime import date
import admin_utils
import auth
from services import order_service, reporting as reports, admin_service
from database import safe_transaction

def render_quotes_management(conn):
    curr_user = auth.get_current_user()
    current_salesperson = curr_user['name'] if curr_user else "Ira"

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
        # Nomenclature Pattern: ORC-YYMMDD-ID
        q_date = pd.to_datetime(quote['date_created'])
        formatted_id = f"ORC-{q_date.strftime('%y%m%d')}-{quote['id']}"
        
        status_icon = {"Pendente": "🟡", "Aprovado": "🟢"}.get(quote['status'], "⚪")
        with st.expander(f"{status_icon} {formatted_id} | {quote['name']} | R$ {quote['total_price']:.2f}"):
            st.write(f"Notas: {quote['notes']}")
            st.caption(f"📅 Prazo de Execução: {quote.get('delivery_days', 0)} dias (após aprovação)")
            
            # Fetch items
            items = order_service.get_quote_items(conn, quote['id'])
            # Reformat items for better display
            items_display = items[['product_name', 'quantity', 'unit_price', 'item_notes']].copy()
            items_display.columns = ['Produto', 'Qtd', 'Preço Unit.', 'Obs']
            st.table(items_display)
            
            c1, c2, c3 = st.columns(3)
            # PDF GEN
            # Fetch full item details for PDF
            pdf_items = order_service.get_quote_details_for_pdf(conn, quote['id'])
            
            pdf_data = reports.generate_quote_pdf({
                "id": formatted_id, 
                "client_name": quote.get('name', 'Cliente'),
                "date_created": q_date.strftime('%d/%m/%Y'),
                "date_valid_until": pd.to_datetime(quote['date_valid_until']).strftime('%d/%m/%Y'),
                "items": [{
                    "id": r['product_id'], "name": r['name'], "qty": r['quantity'], "price": r['unit_price'], "notes": r['item_notes'] or ""
                } for _, r in pdf_items.iterrows()],
                "total": quote['total_price'],
                "discount": 0,
                "notes": quote['notes'], 
                "delivery": f"{quote.get('delivery_days', 0)} dias após confirmação", 
                "payment": quote['payment_terms']
            })
            c1.download_button("📄 PDF", data=pdf_data, file_name=f"orcamento_{quote['id']}.pdf", mime="application/pdf", key=f"qp_{quote['id']}")
            
            if quote['status'] == 'Pendente':
                st.divider()
                st.caption("Aprovação e Sinal")
                col_dep1, col_dep2, col_dep3 = st.columns(3)
                
                # Pre-fill deposit with 50%
                default_dep = float(round(quote['total_price'] * 0.5, 2))
                
                dep_val = col_dep1.number_input("Sinal Recebido (R$)", value=default_dep, step=10.0, key=f"dep_{quote['id']}")
                
                # Default salesperson to logged user
                all_users = admin_service.get_all_users(conn)
                salesp_df = all_users[all_users['role'].isin(['admin', 'vendedor']) & (all_users['active'] == 1)]
                salesp_opts = sorted(salesp_df['name'].tolist())
                
                if current_salesperson not in salesp_opts:
                    salesp_opts.append(current_salesperson)
                
                salesp_app = col_dep2.selectbox("Vendedora", salesp_opts, index=salesp_opts.index(current_salesperson), key=f"sp_app_{quote['id']}")
                pay_method_app = col_dep3.selectbox("Forma Pagto", ["Pix", "Dinheiro", "Cartão", "Outro"], key=f"pay_app_{quote['id']}")
                
                if c2.button("✅ Aprovar e Encomendar", key=f"qa_{quote['id']}", use_container_width=True):
                    do_rerun = False
                    try:
                        with safe_transaction(conn):
                            cursor = conn.cursor()
                            
                            # Calculate date_due based on lead time
                            lead_days = int(quote.get('delivery_days', 0))
                            final_date_due = date.today() + pd.Timedelta(days=lead_days)

                            # 1. Create Commission Order head
                            new_ord_id = order_service.create_commission_order(cursor, {
                                'client_id': quote['client_id'], 
                                'total_price': quote['total_price'],
                                'status': 'Pendente', 
                                'date_created': date.today(), 
                                'date_due': final_date_due, 
                                'notes': f"Via {formatted_id}. {quote['notes']}", 
                                'deposit_amount': dep_val
                            })
                            
                            # 2. Add Items
                            q_items = order_service.get_quote_details_for_pdf(conn, quote['id'])
                            comm_items = []
                            for _, qi in q_items.iterrows():
                                comm_items.append({
                                    'product_id': int(qi['product_id']),
                                    'qty': int(qi['quantity']),
                                    'unit_price': float(qi['unit_price']),
                                    'variant_id': qi['variant_id'],
                                    'qty_from_stock': 0 
                                })
                            order_service.add_commission_items(cursor, new_ord_id, comm_items)
                            
                            # 3. Create Sale if deposit
                            if dep_val > 0:
                                order_service.create_sale(cursor, {
                                    "date": date.today(),
                                    "product_id": None,
                                    "quantity": 1,
                                    "total_price": dep_val,
                                    "status": "Finalizada",
                                    "client_id": quote['client_id'],
                                    "discount": 0,
                                    "payment_method": pay_method_app, 
                                    "notes": f"Sinal via {formatted_id} (Enc #{new_ord_id})",
                                    "salesperson": salesp_app,
                                    "order_id": f"ENC-{new_ord_id}"
                                })

                            # 4. Update status and link
                            cursor.execute("UPDATE quotes SET status='Aprovado', converted_order_id=? WHERE id=?", (new_ord_id, quote['id']))
                            do_rerun = True
                        
                        if do_rerun:
                            admin_utils.show_feedback_dialog(f"Orçamento aprovado! Encomenda #{new_ord_id} gerada.", level="success")
                            st.rerun()
                    except Exception as e:
                        if type(e).__name__ in ["RerunException", "StopException"]:
                            raise e
                        st.error(f"Erro ao aprovar orçamento: {e}")
                
                if c3.button("🗑️ Excluir", key=f"qd_{quote['id']}", use_container_width=True):
                    order_service.delete_quote(conn, quote['id'])
                    st.rerun()
