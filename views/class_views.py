
import streamlit as st
import pandas as pd
from datetime import datetime
from services import student_service
import admin_utils

def render_class_management(conn):
    st.subheader("Gestão de Turmas")
    c1, c2 = st.columns([1, 2])
    
    WEEKDAYS = {
        "Segunda-feira": 0, "Terça-feira": 1, "Quarta-feira": 2, 
        "Quinta-feira": 3, "Sexta-feira": 4, "Sábado": 5, "Domingo": 6
    }
    WEEKDAYS_REV = {v: k for k, v in WEEKDAYS.items()}
    
    with c1:
        with st.form("new_class"):
            st.markdown("**Nova Turma**")
            c_name = st.text_input("Nome da Turma (Ex: Terça Manhã)")
            c_sched = st.text_input("Horário (Ex: Terça 09:00 - 12:00)")
            
            # Weekday Selector
            c_wday_label = st.selectbox("Dia da Semana (Recorrente)", list(WEEKDAYS.keys()))
            c_wday = WEEKDAYS[c_wday_label]
            
            c_notes = st.text_area("Notas")
            
            if st.form_submit_button("Criar Turma", type="primary"):
                if c_name:
                    try:
                        student_service.create_class(conn, c_name, c_sched, c_notes, c_wday)
                        admin_utils.show_feedback_dialog("Turma criada!", level="success")
                    except Exception as e:
                        admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")
                else:
                    admin_utils.show_feedback_dialog("Nome obrigatório.", level="warning")
    
    with c2:
        classes = student_service.get_all_classes(conn)
        if not classes.empty:
            # Display Weekday
            if 'weekday' in classes.columns:
                classes['dia_semana'] = classes['weekday'].map(WEEKDAYS_REV).fillna("-")
            else:
                classes['dia_semana'] = "-"
                
            st.dataframe(
                classes[['id', 'name', 'schedule', 'dia_semana', 'student_count', 'notes']], 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "name": "Nome",
                    "schedule": "Horário",
                    "dia_semana": "Dia (Sistema)",
                    "student_count": st.column_config.NumberColumn("Qtd Alunos", format="%d"),
                    "notes": "Notas"
                }
            )
            
            with st.expander("Editar Turma"):
                sel_c = st.selectbox("Editar", classes['name'].tolist(), key="edit_cls_sel")
                if sel_c:
                    row = classes[classes['name'] == sel_c].iloc[0]
                    with st.form("edit_class_form"):
                        ec_name = st.text_input("Nome", value=row['name'])
                        ec_sched = st.text_input("Horário", value=row['schedule'])
                        
                        # Weekday Edit
                        curr_wd = int(row['weekday']) if pd.notnull(row['weekday']) else 0
                        curr_wd_label = WEEKDAYS_REV.get(curr_wd, "Segunda-feira")
                        try:
                            # Safely find index
                            wd_idx = list(WEEKDAYS.keys()).index(curr_wd_label)
                        except: wd_idx = 0
                            
                        ec_wday_label = st.selectbox("Dia da Semana", list(WEEKDAYS.keys()), index=wd_idx)
                        ec_wday = WEEKDAYS[ec_wday_label]
                        
                        ec_notes = st.text_area("Notas", value=row['notes'])
                        if st.form_submit_button("Salvar"):
                            student_service.update_class(conn, row['id'], ec_name, ec_sched, ec_notes, ec_wday)
                            admin_utils.show_feedback_dialog("Atualizado!", level="success")
            
            st.divider()
            
            with st.expander("📅 Gerenciar Cancelamentos / Feriados"):
                st.info("Adicione datas onde NÃO haverá aula. Isso reduzirá o cálculo da mensalidade para os alunos desta turma.")
                
                # Select Class for cancellation (reuse existing or dedicated selectbox)
                # We can reuse 'classes' DF
                c_opts = classes['name'].tolist()
                sel_c_canc = st.selectbox("Selecione a Turma", c_opts, key="canc_cls_sel")
                
                if sel_c_canc:
                    row_c = classes[classes['name'] == sel_c_canc].iloc[0]
                    cid = row_c['id']
                    
                    # List existing
                    cancs = student_service.get_class_cancellations(conn, cid)
                    if not cancs.empty:
                        st.markdown("**Cancelamentos Registrados:**")
                        for _, cr in cancs.iterrows():
                            cc1, cc2 = st.columns([4, 1])
                            # Format date for display (stored as YYYY-MM-DD)
                            try:
                                d_disp = datetime.strptime(cr['date'], '%Y-%m-%d').strftime('%d/%m/%Y')
                            except: d_disp = cr['date']
                            
                            cc1.text(f"{d_disp} - {cr['reason']}")
                            if cc2.button("🗑️", key=f"del_canc_{cr['id']}"):
                                student_service.delete_class_cancellation(conn, cr['id'])
                                st.rerun()
                    else:
                        st.text("Nenhum cancelamento registrado.")
                        
                    st.markdown("---")
                    st.markdown("**Adicionar Novo Cancelamento:**")
                    with st.form(f"add_canc_{cid}"):
                        new_date = st.date_input("Data", value=datetime.today())
                        new_reason = st.text_input("Motivo (Ex: Feriado, Professor Doente)")
                        
                        if st.form_submit_button("Adicionar Cancelamento"):
                            d_str = new_date.strftime('%Y-%m-%d')
                            # Check duplication? Db constraint or python check. Service returns True/False.
                            # Just try add.
                            if student_service.add_class_cancellation(conn, cid, d_str, new_reason):
                                st.success("Cancelamento adicionado!")
                                st.rerun()
                            else:
                                st.error("Erro ao adicionar.")
