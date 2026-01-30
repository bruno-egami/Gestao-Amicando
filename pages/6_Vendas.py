import streamlit as st
import pandas as pd
import database
import admin_utils
from datetime import datetime

st.set_page_config(page_title="Vendas", page_icon="💰")

# Sales view matches logic: Salesperson can access this.
# But Admin can too.

st.title("Frente de Vendas")

conn = database.get_connection()

# --- New Sale ---
with st.expander("Nova Venda", expanded=True):
    with st.form("new_sale"):
        
        # 1. Select Client
        clients = pd.read_sql("SELECT id, name FROM clients", conn)
        client_dict = {row['name']: row['id'] for _, row in clients.iterrows()}
        client_choice = st.selectbox("Cliente", [""] + list(client_dict.keys()))
        
        # 2. Select Product
        products_df = pd.read_sql("SELECT id, name, base_price, stock_quantity FROM products", conn)
        if products_df.empty:
            st.warning("Sem produtos.")
        else:
            # Filter only products with stock? Optional. User didn't mandate.
            # Showing stock is helpful.
            prod_dict = {f"{row['name']} (Est: {row['stock_quantity']}) - R$ {row['base_price']:.2f}": row['id'] 
                         for _, row in products_df.iterrows()}
            selected_prod_label = st.selectbox("Produto", list(prod_dict.keys()))
            selected_id = prod_dict[selected_prod_label]
            
            sel_row = products_df[products_df['id'] == selected_id].iloc[0]
            
            qty = st.number_input("Quantidade", min_value=1, step=1, value=1)
            date = st.date_input("Data", datetime.now())
            
            total = sel_row['base_price'] * qty
            st.write(f"**Total: R$ {total:.2f}**")
            
            if st.form_submit_button("Finalizar Venda"):
                if not client_choice:
                    st.error("Selecione o Cliente.")
                elif sel_row['stock_quantity'] < qty:
                    st.error("Estoque insuficiente!")
                else:
                    client_id = client_dict[client_choice]
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO sales (date, product_id, quantity, total_price, status, client_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (date, int(selected_id), qty, total, "Finalizada", client_id))
                    
                    # Update Stock
                    cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?",
                                   (qty, int(selected_id)))
                    
                    conn.commit()
                    st.success("Venda registrada!")
                    st.rerun()

# --- History & Edit ---
st.divider()
st.subheader("Histórico de Vendas (Recentes)")

# Date Filter could be global or local here. Local for simplicity.
sales_view = pd.read_sql("""
    SELECT s.id, s.date, c.name as cliente, p.name as produto, s.quantity, s.total_price, s.product_id
    FROM sales s
    LEFT JOIN clients c ON s.client_id = c.id
    JOIN products p ON s.product_id = p.id
    ORDER BY s.date DESC
""", conn)

if not sales_view.empty:
    st.dataframe(sales_view.drop(columns=['product_id']))
    
    # Deletion / Correction logic
    with st.expander("Correção / Cancelamento"):
        sale_id = st.number_input("ID da Venda para Cancelar", min_value=0)
        if st.button("Cancelar Venda (Estornar Estoque)"):
            # Fetch sale details
            target = sales_view[sales_view['id'] == sale_id]
            if not target.empty:
                row = target.iloc[0]
                q_restore = row['quantity']
                p_id = row['product_id']
                
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sales WHERE id=?", (sale_id,))
                cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (q_restore, int(p_id)))
                conn.commit()
                st.success(f"Venda {sale_id} cancelada e estoque estornado.")
                st.rerun()
            else:
                st.error("ID não encontrado.")
else:
    st.info("Nenhuma venda.")

conn.close()
