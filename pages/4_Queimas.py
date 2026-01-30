import streamlit as st
import pandas as pd
import database
import admin_utils
from datetime import datetime

st.set_page_config(page_title="Queimas", page_icon="🔥")

if not admin_utils.check_password():
    st.stop()

st.title("Gestão de Queimas e Forno")

conn = database.get_connection()

# --- Calculator (Meter Reading Mode) ---
with st.expander("Calculadora (Leitura de Relógio)", expanded=True):
    col1, col2 = st.columns(2)
    start_kwh = col1.number_input("Leitura Inicial (kWh)", min_value=0.0, step=0.1, format="%.1f")
    end_kwh = col2.number_input("Leitura Final (kWh)", min_value=0.0, step=0.1, format="%.1f")
    
    consumption = max(0.0, end_kwh - start_kwh)
    
    col3, col4 = st.columns(2)
    kwh_price = col3.number_input("Preço do kWh (R$)", min_value=0.0, step=0.01, value=0.80)
    
    cost = consumption * kwh_price
    
    st.metric("Consumo Real", f"{consumption:.1f} kWh")
    st.metric("Custo da Fornada", f"R$ {cost:.2f}")
    
    with st.form("save_firing"):
        date = st.date_input("Data da Queima", datetime.now())
        f_type = st.selectbox("Tipo", ["Biscoito", "Esmalte", "Outro"])
        
        if st.form_submit_button("Registrar Queima"):
            if consumption > 0:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO firings (date, type, power_consumption_kwh, cost) VALUES (?, ?, ?, ?)",
                               (date, f_type, consumption, cost))
                conn.commit()
                st.success("Queima registrada!")
                st.rerun()
            else:
                st.warning("Consumo zerado.")

# --- History ---
st.divider()
st.subheader("Histórico de Queimas")

df = pd.read_sql("SELECT * FROM firings ORDER BY date DESC", conn)
if not df.empty:
    edited = st.data_editor(df, num_rows="dynamic", hide_index=True, key="firings_edit")
    if st.button("Salvar Histórico"):
        cursor = conn.cursor()
        # Handle update logic similar to others
        # Ideally, we check for deletes
        original_ids = set(df['id'])
        new_ids = set(edited[edited['id'].notna()]['id'])
        deleted_ids = original_ids - new_ids
        
        for did in deleted_ids:
            cursor.execute("DELETE FROM firings WHERE id=?", (did,))
            
        conn.commit()
        st.success("Histórico atualizado.")
        st.rerun()
else:
    st.info("Nenhuma queima registrada.")

conn.close()
