import streamlit as st
import admin_utils
import time

st.set_page_config(page_title="Orçamentos (Mudou!)", page_icon="👋")
admin_utils.render_sidebar_logo()

st.title("🚧 Página de Orçamentos Mudou!")
st.warning("O módulo de Orçamentos foi integrado à página de **Vendas**.")
st.write("Você será redirecionado automaticamente em instantes...")

# Auto redirect
time.sleep(2)
st.switch_page("pages/6_Vendas.py")

if st.button("Ir para Vendas Agora"):
    st.switch_page("pages/6_Vendas.py")
