
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
            name = st.text_input("Nome Completo")
            phone = st.text_input("Telefone (WhatsApp)")
            
            # Class Selection
            sel_class_name = st.selectbox("Turma", [""] + list(class_opts.keys()))
            
            join_date = st.date_input("Data de Início", value=datetime.today())
            
            if st.form_submit_button("Cadastrar Aluno", type="primary"):
                if name:
                    try:
                        cid = class_opts.get(sel_class_name)
                        nid = student_service.create_student(conn, name, phone, cid, join_date.strftime('%Y-%m-%d'))
                        admin_utils.show_feedback_dialog(f"Aluno {name} cadastrado com ID {nid}!", level="success")
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
            # Display readable
            # Ensure price_per_class exists in DF columns (might be NaN just after migration)
            if 'price_per_class' not in df_students.columns:
                 df_students['price_per_class'] = 0.0
            
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
                st_map = {f"{row['id']} - {row['name']}": row['id'] for _, row in all_st_df.iterrows()}
                sel_st_label = st.selectbox("Selecione para editar", [""] + list(st_map.keys()))
                
                if sel_st_label:
                    sid_target = st_map[sel_st_label]
                    # Filter by ID to be safe
                    row = all_st_df[all_st_df['id'] == sid_target].iloc[0]
                    
                    # --- Reactive Class Update ---
                    st.markdown("#### Alterar Turma")
                    
                    e_curr_class_id = row['class_id']
                    curr_cls_name = ""
                    for name, cid in class_opts.items():
                         if cid == e_curr_class_id:
                             curr_cls_name = name
                             break
                    
                    cls_names = [""] + list(class_opts.keys())
                    try:
                        curr_idx = cls_names.index(curr_cls_name)
                    except: curr_idx = 0
                    
                    st.selectbox(
                        "Turma", 
                        cls_names, 
                        index=curr_idx, 
                        key=f"class_sel_{row['id']}", 
                        on_change=on_class_change,
                        args=(f"class_sel_{row['id']}", row['id'], class_opts)
                    )
                    
                    st.divider()
                    
                    # --- Other Details Form ---
                    with st.form(key=f"edit_student_details_{row['id']}"):
                        st.markdown("#### Editar Dados Pessoais e Valor")
                        en = st.text_input("Nome", value=row['name'], key=f"edit_name_{row['id']}")
                        ep = st.text_input("Telefone", value=row['phone'], key=f"edit_phone_{row['id']}")
                        
                        ea = st.checkbox("Ativo", value=bool(row['active']), key=f"edit_active_{row['id']}")
                        
                        if st.form_submit_button("Salvar Dados Pessoais"):
                            try:
                                # Update only personal details and price.
                                student_service.update_student(conn, row['id'], en, ep, ea)
                                admin_utils.show_feedback_dialog("Dados atualizados!", level="success")
                                st.cache_data.clear()
                            except Exception as e:
                                admin_utils.show_feedback_dialog(f"Erro ao atualizar: {e}", level="error")
