
import streamlit as st
from services import student_service

def render_dashboard_summary(conn):
    st.subheader("Visão Geral do Atelier")
    
    stats = student_service.get_module_summary_stats(conn)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Alunos Ativos", stats.get('total_students', 0))
    c2.metric("Receita Pendente", f"R$ {stats.get('pending_revenue', 0):.2f}")
    c3.metric("Receita Paga (Total)", f"R$ {stats.get('total_revenue_paid', 0):.2f}")
    
    st.divider()
    
    st.info("💡 Este painel mostra o resumo consolidado de alunos e mensalidades.")
