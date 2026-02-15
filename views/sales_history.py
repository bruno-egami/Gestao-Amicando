
import streamlit as st
import pandas as pd
import auth
import admin_utils
from services import order_service

def render_sales_history(conn, client_opts):
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
                if fil_pay and fil_pay != "Todas": filters['payment_method'] = fil_pay
                if fil_salesp and fil_salesp != "Todas": filters['salesperson'] = fil_salesp

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
