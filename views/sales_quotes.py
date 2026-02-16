
import streamlit as st
import pandas as pd
from datetime import date
import services.reporting as reports
import admin_utils
from services import order_service
from database import safe_transaction

def render_quotes_management(conn):
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
                    try:
                        with safe_transaction(conn):
                            cursor = conn.cursor()
                            order_service.create_commission_order(cursor, {
                                'client_id': quote['client_id'], 'total_price': quote['total_price'],
                                'status': 'Pendente', 'date_created': date.today(), 'date_due': date.today(),
                                'notes': f"Via ORC-{quote['id']}", 'deposit_amount': 0
                            })
                            # Update status
                            cursor.execute("UPDATE quotes SET status='Aprovado' WHERE id=?", (quote['id'],))
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao aprovar orçamento: {e}")
                
                if c3.button("🗑️ Excluir", key=f"qd_{quote['id']}"):
                    order_service.delete_quote(conn, quote['id'])
                    st.rerun()
