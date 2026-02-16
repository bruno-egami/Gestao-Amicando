import streamlit as st
import services.calendar_service as calendar_service
from datetime import datetime, date, timedelta

def render_calendar_export(conn):
    st.subheader("📅 Exportar Agenda (.ics)")
    st.info("💡 **Dica:** Recomendamos criar uma agenda separada no seu Google Agenda ou Outlook chamada 'Amicando' e importar este arquivo nela. Assim você pode ocultar/excluir os eventos facilmente se desejar.")
    
    # Filters
    c1, c2 = st.columns(2)
    today = date.today()
    export_period = c1.selectbox("Período de Exportação", ["Próximos 30 dias", "Mês Atual", "Próximos 90 dias", "Intervalo Personalizado"])
    
    if export_period == "Próximos 30 dias":
        start_date = today
        end_date = today + timedelta(days=30)
    elif export_period == "Mês Atual":
        start_date = today.replace(day=1)
        # Next month's first day - 1
        if today.month == 12:
            end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
    elif export_period == "Próximos 90 dias":
        start_date = today
        end_date = today + timedelta(days=90)
    else:
        # Personalizado
        cc1, cc2 = st.columns(2)
        start_date = cc1.date_input("De", today, format="DD/MM/YYYY")
        end_date = cc2.date_input("Até", today + timedelta(days=30), format="DD/MM/YYYY")

    st.markdown("---")
    st.markdown("##### Categorias para Exportar")
    cc1, cc2 = st.columns(2)
    exp_orders = cc1.checkbox("📦 Encomendas (Data de Entrega)", value=True)
    exp_classes = cc2.checkbox("🎓 Aulas (Conforme Agenda)", value=True)
    
    selected_cats = []
    if exp_orders: selected_cats.append('Encomendas')
    if exp_classes: selected_cats.append('Aulas')
    
    if not selected_cats:
        st.warning("Selecione pelo menos uma categoria.")
    else:
        # Generate ICS
        ics_data = calendar_service.generate_ics_file(conn, start_date, end_date, selected_cats)
        
        st.download_button(
            label="💾 Baixar Arquivo .ics",
            data=ics_data,
            file_name=f"Agenda_Amicando_{datetime.now().strftime('%Y%m%d')}.ics",
            mime="text/calendar",
            type="primary",
            use_container_width=True
        )
