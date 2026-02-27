
import streamlit as st
import pandas as pd
from datetime import datetime
import database
from services import student_service
import admin_utils

def on_class_change(k, sid, class_opts):
    # Callback to update class immediately
    if k in st.session_state:
        sel_val = st.session_state[k]
        new_cid = class_opts.get(sel_val)
        # Explicit int conversion if valid
        if new_cid is not None: new_cid = int(new_cid)
        else: new_cid = None
        
        # Use FRESH connection for callback logic to ensure isolation/commit visibility
        conn_cb = database.get_connection()
        try:
            # CAST sid to native int to prevent numpy type issues in SQLite
            student_service.update_student_class(conn_cb, int(sid), new_cid)
            admin_utils.show_feedback_dialog(f"Turma do Aluno {sid} alterada para: {sel_val}", level="success")
        finally:
            conn_cb.close()
            
        st.cache_data.clear()

def render_student_management(conn):
    st.subheader("Cadastro de Alunos")
    
    # Load Classes for both Create and Edit forms
    classes_df = student_service.get_all_classes(conn)
    class_opts = {row['name']: row['id'] for _, row in classes_df.iterrows()} if not classes_df.empty else {}
    
    c1, c2 = st.columns([1, 2])
    
    with c1:
        with st.form("new_student"):
            st.markdown("**Novo Aluno**")
            n_nome = st.text_input("Nome completo")
            n_tel = st.text_input("Telefone/Zap")
            n_email = st.text_input("E-mail")
            n_end = st.text_input("Endereço")
            col_doc1, col_doc2 = st.columns(2)
            n_rg = col_doc1.text_input("RG")
            n_cpf = col_doc2.text_input("CPF")
            
            # Select class
            c_opts = ["++ Sem Turma ++"] + sorted(list(class_opts.keys()))
            n_turma = st.selectbox("Turma", c_opts)
            n_join_date = st.date_input("Data de Início", value=datetime.today())
            
            if st.form_submit_button("Cadastrar Aluno", type="primary"):
                if n_nome:
                    try:
                        cid = class_opts.get(n_turma)
                        if isinstance(cid, bytes): cid = int.from_bytes(cid, "little")

                        student_service.create_student(conn, n_nome, n_tel, cid, n_join_date.strftime('%Y-%m-%d'), rg=n_rg, cpf=n_cpf, endereco=n_end, email=n_email)
                        admin_utils.show_feedback_dialog(f"Aluno {n_nome} cadastrado!", level="success")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")
                else:
                    admin_utils.show_feedback_dialog("Nome obrigatório.", level="warning")
    
    with c2:
        st.markdown("**Alunos Ativos**")
        
        # Filter View
        f_class = st.selectbox("Filtrar por Turma", ["Todas"] + list(class_opts.keys()), key="filter_st_class")
        
        if f_class != "Todas":
            df_students = student_service.get_all_active_students(conn, class_id=class_opts[f_class])
        else:
            df_students = student_service.get_all_active_students(conn)
            
        if not df_students.empty:
            st.dataframe(
                df_students[['id', 'name', 'phone', 'class_name', 'join_date']], 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "name": "Nome", "phone": "Tel", "class_name": "Turma"
                }
            )
            
            # --- Inactive Students ---
            st.divider()
            with st.expander("👻 Lista de Alunos Inativos", expanded=False):
                inactive_df = student_service.get_all_inactive_students(conn)
                if not inactive_df.empty:
                    st.dataframe(inactive_df[['id', 'name', 'phone', 'class_name', 'join_date']], hide_index=True, use_container_width=True)
                else:
                    st.info("Nenhum aluno inativo.")
            
            # Edit Expander
            with st.expander("Editar / Desativar Aluno"):
                # Combine active and inactive for editing
                all_st_df = pd.concat([df_students, student_service.get_all_inactive_students(conn)])
                
                st_labels = {f"{row['id']} - {row['name']}": row['id'] for _, row in all_st_df.iterrows()}
                sel_st_label = st.selectbox("Selecionar aluno para editar", [""] + list(st_labels.keys()))
                
                if sel_st_label:
                    sid_target = st_labels[sel_st_label]
                    row = all_st_df[all_st_df['id'] == sid_target].iloc[0]
                    
                    # 1. Update Class (Reactive)
                    st.markdown("#### Turma do Aluno")
                    curr_cls_name = row['class_name'] if pd.notna(row['class_name']) else ""
                    cls_selection_opts = [""] + list(class_opts.keys())
                    try:
                        curr_idx = cls_selection_opts.index(curr_cls_name)
                    except: curr_idx = 0
                    
                    st.selectbox(
                        "Alterar Turma", 
                        cls_selection_opts, 
                        index=curr_idx, 
                        key=f"class_sel_{row['id']}", 
                        on_change=on_class_change,
                        args=(f"class_sel_{row['id']}", row['id'], class_opts)
                    )
                    
                    st.divider()
                    
                    # 2. Update Personal Info
                    with st.form(f"edit_personal_{row['id']}"):
                        st.markdown("#### Dados Pessoais")
                        en = st.text_input("Nome", value=row['name'])
                        ep = st.text_input("Telefone", value=row['phone'])
                        ee = st.text_input("E-mail", value=row.get('email', ''))
                        end = st.text_input("Endereço", value=row.get('endereco', ''))
                        col_d1, col_d2 = st.columns(2)
                        erg = col_d1.text_input("RG", value=row.get('rg', ''))
                        ecpf = col_d2.text_input("CPF", value=row.get('cpf', ''))
                        ea = st.checkbox("Ativo", value=bool(row['active']))
                        
                        if st.form_submit_button("Salvar Alterações"):
                            try:
                                student_service.update_student(conn, row['id'], en, ep, ea, rg=erg, cpf=ecpf, endereco=end, email=ee)
                                admin_utils.show_feedback_dialog("Dados atualizados!", level="success")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao atualizar: {e}")

                    # 3. Contract Generation
                    st.divider()
                    st.markdown("#### Documentos")
                    if st.button("📄 Gerar Contrato PDF (Aulas)", key=f"btn_pdf_{row['id']}"):
                        try:
                            # Re-fetch class details to get weekday, start/end time
                            c_id = row['class_id']
                            if isinstance(c_id, bytes): c_id = int.from_bytes(c_id, "little")
                            
                            class_info = classes_df[classes_df['id'] == c_id].iloc[0] if c_id else {}
                            
                            from services.reporting import contract_generator
                            
                            weekday_map = {0: 'Segunda-feira', 1: 'Terça-feira', 2: 'Quarta-feira', 3: 'Quinta-feira', 4: 'Sexta-feira', 5: 'Sábado', 6: 'Domingo'}
                            
                            prep_data = {
                                "name": en, "rg": erg, "cpf": ecpf, "endereco": end, "phone": ep, "email": ee,
                                "weekday_name": weekday_map.get(class_info.get('weekday'), "Não definida"),
                                "start_time": class_info.get('start_time', 'Não inf.'),
                                "end_time": class_info.get('end_time', 'Não inf.'),
                                "price_per_class": row.get('price_per_class') or student_service.get_global_price_per_class(conn),
                                "join_date": row.get('join_date')
                            }
                            
                            pdf_bytes = contract_generator.generate_student_contract_pdf(prep_data)
                            st.download_button(
                                label="⬇️ Baixar Contrato",
                                data=pdf_bytes,
                                file_name=f"contrato_{en.replace(' ', '_')}.pdf",
                                mime="application/pdf",
                                key=f"dl_pdf_{row['id']}"
                            )
                        except Exception as e:
                            st.error(f"Erro ao gerar contrato: {e}")
        else:
            st.info("Nenhum aluno ativo encontrado com os filtros aplicados.")
