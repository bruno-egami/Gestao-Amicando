
import streamlit as st
import database
import auth
import admin_utils
import utils.styles as styles

# Import Views
from views import dashboard_views, class_views, student_views, financial_views

st.set_page_config(page_title="Gestão de Aulas", page_icon="🎓", layout="wide")

# Apply Global Styles
styles.apply_custom_style()

# Database Connection
with database.db_session() as conn:

    # Auth
    if not auth.require_login(conn):
        st.stop()

    if not auth.check_page_access("Gestao_Aulas"):
        user = st.session_state.get('current_user')
        if user['role'] not in ['admin', 'gerente', 'vendedor']: 
             st.error("Acesso negado.")
             st.stop()

    auth.render_custom_sidebar()
    admin_utils.render_header_logo()

    st.title("🎓 Gestão de Aulas e Alunos")

    # TABS
    tab_summary, tab_classes, tab_students, tab_finance, tab_history = st.tabs(["📊 Resumo", "🗓️ Turmas", "👥 Alunos", "💰 Gestão Financeira", "📜 Histórico Financeiro"])

    # ==============================================================================
    # TAB 0: RESUMO
    # ==============================================================================
    with tab_summary:
        dashboard_views.render_dashboard_summary(conn)

    # ==============================================================================
    # TAB 0.5: TURMAS
    # ==============================================================================
    with tab_classes:
        class_views.render_class_management(conn)

    # ==============================================================================
    # TAB 1: ALUNOS
    # ==============================================================================
    with tab_students:
        student_views.render_student_management(conn)

    # ==============================================================================
    # TAB 3: GESTÃO FINANCEIRA
    # ==============================================================================
    with tab_finance:
        financial_views.render_financial_management(conn)

    # ==============================================================================
    # TAB 4: HISTÓRICO FINANCEIRO
    # ==============================================================================
    with tab_history:
        financial_views.render_financial_history(conn)
