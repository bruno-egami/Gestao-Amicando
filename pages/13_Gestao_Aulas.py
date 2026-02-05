import streamlit as st
import pandas as pd
from datetime import datetime
import database
import auth
import admin_utils
from services import student_service
import reports

st.set_page_config(page_title="Gestão de Aulas", page_icon="🎓", layout="wide")

# Database Connection
conn = database.get_connection()

# Auth
if not auth.require_login(conn):
    st.stop()

if not auth.check_page_access("Gestao_Aulas"): # Ensure this permission exists or add it
    # Fallback or strict check. Let's assume admins have access or we add it safely.
    # For now, if role is admin/manager.
    user = st.session_state.get('current_user')
    if user['role'] not in ['admin', 'gerente', 'vendedor']: 
         st.error("Acesso negado.")
         st.stop()

auth.render_custom_sidebar()
admin_utils.render_header_logo()

st.title("🎓 Gestão de Aulas e Alunos")

# TABS
tab_summary, tab_classes, tab_students, tab_consume, tab_finance = st.tabs(["📊 Resumo", "🗓️ Turmas", "👥 Alunos", "📦 Lançar Consumo", "💰 Financeiro e Extratos"])

# ==============================================================================
# TAB 0.5: TURMAS (NEW)
# ==============================================================================
with tab_classes:
    st.subheader("Gestão de Turmas")
    c1, c2 = st.columns([1, 2])
    with c1:
        with st.form("new_class"):
            st.markdown("**Nova Turma**")
            c_name = st.text_input("Nome da Turma (Ex: Terça Manhã)")
            c_sched = st.text_input("Horário (Ex: Terça 09:00 - 12:00)")
            c_notes = st.text_area("Notas")
            if st.form_submit_button("Criar Turma", type="primary"):
                if c_name:
                    try:
                        student_service.create_class(conn, c_name, c_sched, c_notes)
                        st.success("Turma criada!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
                else:
                    st.warning("Nome obrigatório.")
    
    with c2:
        classes = student_service.get_all_classes(conn)
        if not classes.empty:
            st.dataframe(
                classes[['id', 'name', 'schedule', 'student_count', 'notes']], 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "name": "Nome",
                    "schedule": "Horário",
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
                        ec_notes = st.text_area("Notas", value=row['notes'])
                        if st.form_submit_button("Salvar"):
                            student_service.update_class(conn, row['id'], ec_name, ec_sched, ec_notes)
                            st.success("Atualizado!")
                            st.rerun()

# ==============================================================================
# TAB 0: RESUMO
# ==============================================================================
with tab_summary:
    st.subheader("Visão Geral do Atelier")
    
    stats = student_service.get_module_summary_stats(conn)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Alunos Ativos", stats.get('total_students', 0))
    c2.metric("Receita Pendente", f"R$ {stats.get('pending_revenue', 0):.2f}")
    c3.metric("Receita Paga (Total)", f"R$ {stats.get('total_revenue_paid', 0):.2f}")
    
    st.divider()
    
    st.info("💡 Este painel mostra o resumo consolidado de alunos e mensalidades.")


# ==============================================================================
# TAB 1: ALUNOS
# ==============================================================================
with tab_students:
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
                        st.success(f"Aluno {name} cadastrado com ID {nid}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
                else:
                    st.warning("Nome obrigatório.")
    
    with c2:
        st.markdown("**Alunos Ativos**")
        
        # Filter View
        f_class = st.selectbox("Filtrar por Turma", ["Todas"] + list(class_opts.keys()), key="filter_st_class")
        
        show_all = True
        if f_class != "Todas":
            df_students = student_service.get_all_active_students(conn, class_id=class_opts[f_class])
        else:
            df_students = student_service.get_all_active_students(conn)
        if not df_students.empty:
            # Display readable
            st.dataframe(df_students[['id', 'name', 'phone', 'class_name', 'join_date']], hide_index=True, use_container_width=True)
            
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
                    
                    def on_class_change(k, sid):
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
                                st.toast(f"✅ Turma do Aluno {sid} alterada para: {sel_val} (ID Turma: {new_cid})", icon="💾")
                            finally:
                                conn_cb.close()
                                
                            st.cache_data.clear()
                    
                    st.selectbox(
                        "Turma", 
                        cls_names, 
                        index=curr_idx, 
                        key=f"class_sel_{row['id']}", 
                        on_change=on_class_change,
                        args=(f"class_sel_{row['id']}", row['id'])
                    )
                    
                    st.divider()
                    
                    # --- Other Details Form ---
                    with st.form(key=f"edit_student_details_{row['id']}"):
                        st.markdown("#### Editar Dados Pessoais")
                        en = st.text_input("Nome", value=row['name'], key=f"edit_name_{row['id']}")
                        ep = st.text_input("Telefone", value=row['phone'], key=f"edit_phone_{row['id']}")
                        ea = st.checkbox("Ativo", value=bool(row['active']), key=f"edit_active_{row['id']}")
                        
                        if st.form_submit_button("Salvar Dados Pessoais"):
                            try:
                                # Update only personal details. Class is handled by reactive widget above.
                                student_service.update_student(conn, row['id'], en, ep, ea)
                                st.success(f"Dados atualizados!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao atualizar: {e}")

# ==============================================================================
# TAB 2: LANÇAR CONSUMO
# ==============================================================================
with tab_consume:
    st.subheader("Lançar Consumo ou Aula Extra")
    
    # 1. Filter by Class
    classes_df = student_service.get_all_classes(conn)
    class_opts = {row['name']: row['id'] for _, row in classes_df.iterrows()} if not classes_df.empty else {}
    
    col_filter, col_res = st.columns([1, 2])
    with col_filter:
        filter_class = st.selectbox("Filtrar Alunos por Turma", ["Todos"] + list(class_opts.keys()), key="cons_filter_class")

    # 2. Select Student
    target_class_id = class_opts.get(filter_class) if filter_class != "Todos" else None
    students = student_service.get_all_active_students(conn, class_id=target_class_id)
    
    if students.empty:
        st.warning("Nenhum aluno encontrado.")
    else:
        s_dict = {f"{row['name']} ({row.get('class_name') or 'Sem Turma'})": row['id'] for _, row in students.iterrows()}
        # Ensure we reset or keep selection valid
        sel_student = st.selectbox("Selecione o Aluno", [""] + list(s_dict.keys()), key="cons_student_sel")
        
        if sel_student:
            st_id = s_dict[sel_student]
            
            # Type of Consumption
            c_type = st.radio("Tipo de Lançamento", ["Material (Baixa Estoque)", "Aula Extra / Serviço / Taxas"], horizontal=True)
            
            if c_type.startswith("Material"):
                # Category Filter Data
                cats = pd.read_sql("SELECT id, name FROM material_categories ORDER BY name", conn)
                cat_opts = {row['name']: row['id'] for _, row in cats.iterrows()}
                
                # Material Filters
                c_mf1, c_mf2 = st.columns([1, 1])
                cat_filter = c_mf1.selectbox("Filtrar Categoria", ["Todas"] + list(cat_opts.keys()))
                name_filter = c_mf2.text_input("🔍 Buscar Material", placeholder="Ex: Argila...")
                
                # Query Materials
                q_mat = "SELECT id, name, unit, price_per_unit, stock_level FROM materials WHERE type != 'Serviço'"
                if cat_filter != "Todas":
                    q_mat += f" AND category_id={cat_opts[cat_filter]}"
                if name_filter:
                    q_mat += f" AND name LIKE '%{name_filter}%'"
                q_mat += " ORDER BY name"
                
                mats = pd.read_sql(q_mat, conn)
                
                if mats.empty:
                    st.warning("Nenhum material encontrado com estes filtros.")
                else:
                    m_dict = {f"{r['name']} (R$ {r['price_per_unit']:.2f}/{r['unit']})": r['id'] for _, r in mats.iterrows()}
                    
                    with st.form("form_mat_consumption"):
                        target_mat = st.selectbox("Selecione Material", list(m_dict.keys()))
                        c_m1, c_m2 = st.columns(2)
                        qty = c_m1.number_input("Quantidade", min_value=0.01, step=0.1)
                        markup = c_m2.number_input("Markup (x Multiplicador)", min_value=1.0, value=2.0, step=0.1)
                        
                        date_cons = st.date_input("Data", value=datetime.today())
                        notes = st.text_input("Observações (Opcional)", key="cons_notes_mat")
                        
                        if st.form_submit_button("Lançar Consumo", type="primary", use_container_width=True):
                            mat_id = m_dict[target_mat]
                            try:
                                uid = st.session_state.current_user['id'] if 'current_user' in st.session_state else None
                                cid = student_service.process_material_consumption(conn, st_id, mat_id, qty, date_cons.strftime('%Y-%m-%d'), uid, notes, markup)
                                st.success("Consumo registrado com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {e}")
                            
            else:
                # Manual Extra/Service
                with st.form("form_extra"):
                    desc = st.text_input("Descrição (Ex: Queima Extra, Aula Avulsa)")
                    c_e1, c_e2, c_e3 = st.columns(3)
                    val_unit = c_e1.number_input("Valor Unitário (R$)", min_value=0.0)
                    qty = c_e2.number_input("Quantidade", value=1.0, min_value=0.1)
                    markup = c_e3.number_input("Markup (x Fator)", min_value=1.0, value=2.0, step=0.1)
                    
                    date_cons = st.date_input("Data", value=datetime.today())
                    notes = st.text_input("Observações (Opcional)", key="cons_notes_extra")
                    
                    if st.form_submit_button("Lançar", type="primary", use_container_width=True):
                        if desc and val_unit > 0:
                            # Apply markup factor to unit price
                            marked_up_price = val_unit * markup
                            total = marked_up_price * qty
                            student_service.add_consumption(conn, st_id, desc, qty, marked_up_price, total, date_cons.strftime('%Y-%m-%d'), notes=notes, markup=markup)
                            st.success(f"Lançamento realizado! Total: R$ {total:.2f}")
                            st.rerun()
                        else:
                            st.error("Preencha descrição e valor.")

# ==============================================================================
# TAB 3: FINANCEIRO
# ==============================================================================
with tab_finance:
    st.subheader("Controle Financeiro Mensal")
    
    # Global Actions (Generate Monthly Tuition)
    with st.expander("🛠️ Ferramentas em Massa (Gerar Mensalidades)"):
        c_gen1, c_gen2 = st.columns(2)
        month_ref = c_gen1.text_input("Mês/Ano Referência", value=datetime.now().strftime('%m/%Y'))
        default_val = c_gen2.number_input("Valor Mensalidade Padrão", value=350.00)
        
        if st.button("Gerar Mensalidades para TODOS Ativos"):
            students = student_service.get_all_active_students(conn)
            count = 0
            for _, s in students.iterrows():
                ok, msg = student_service.generate_tuition_record(conn, s['id'], month_ref, default_val)
                if ok: count += 1
            st.success(f"Geradas {count} mensalidades para {month_ref}.")
            st.rerun()

    st.divider()
    
    # --- FILTERS & LIST ---
    c_f1, c_f2, c_f3 = st.columns([2, 1, 1])
    search_fin = c_f1.text_input("🔍 Buscar Aluno", placeholder="Nome...", key="fin_search")
    
    classes_df = student_service.get_all_classes(conn)
    cls_opts = ["Todas"] + classes_df['name'].tolist() if not classes_df.empty else ["Todas"]
    filter_cls_fin = c_f2.selectbox("📚 Turma", cls_opts, key="fin_filter_cls")
    
    only_pending = c_f3.checkbox("⚠️ Apenas Pendentes", value=True, key="fin_only_pend")
    
    # Load and Filter Students
    students = student_service.get_all_active_students(conn)
    if not students.empty:
        # Pre-calculate totals for filtering
        students['total_due'] = students['id'].apply(lambda x: student_service.get_student_financial_summary(conn, x)[2])
        
        # Apply filters
        if search_fin:
            students = students[students['name'].str.contains(search_fin, case=False)]
        if filter_cls_fin != "Todas":
            students = students[students['class_name'] == filter_cls_fin]
        if only_pending:
            students = students[students['total_due'] > 0]
            
        if students.empty:
            st.info("Nenhum aluno encontrado com estes filtros.")
        else:
            # Selection Area
            st.markdown("---")
            sel_list = {f"{row['name']} (Pend: R$ {row['total_due']:.2f})": row['id'] for _, row in students.iterrows()}
            selected_label = st.selectbox("🎯 Selecione Aluno para Gerenciar", [""] + list(sel_list.keys()))
            
            if selected_label:
                sid = sel_list[selected_label]
                row = students[students['id'] == sid].iloc[0]
                sname = row['name']
                
                st.markdown(f"### 👤 Gestão: {sname}")
                tuit, cons, total = student_service.get_student_financial_summary(conn, sid)
                
                c_det, c_act = st.columns([3, 2], gap="medium")
                
                with c_det:
                    st.markdown("**Extrato de Pendências**")
                    # Details Table logic
                    items = []
                    for _, t in tuit.iterrows():
                        items.append({"date": t['month_year'], "description": f"Mensalidade {t['month_year']}", "quantity": 1, "value": t['amount'], "status": t['status']})
                    for _, c in cons.iterrows():
                        desc = c['description']
                        if c.get('notes'):
                            desc += f" ({c['notes']})"
                        items.append({"date": c['date'], "description": desc, "quantity": c['quantity'], "value": c['total_value'], "status": c['status']})
                    
                    if items:
                        df_items = pd.DataFrame(items)
                        st.dataframe(df_items, hide_index=True, use_container_width=True)
                    else:
                        st.success("Tudo pago! Nenhuma pendência encontrada. 🎉")

                with c_act:
                    if total > 0:
                        st.markdown("**Ações Rápidas**")
                        # Billing Text
                        bill_txt = (f"Olá {sname.split()[0]}! 🏺\n"
                                    f"Estou passando para enviar o resumo do atelier.\n\n"
                                    f"Total em aberto: R$ {total:.2f}\n"
                                    f"Referente a mensalidade e consumos extras.\n\n"
                                    f"Pode realizar o PIX para a chave: (xxx) \n"
                                    f"Obrigado!")
                        with st.expander("💬 Texto para WhatsApp", expanded=False):
                            st.text_area("Copiar", bill_txt, height=120, key=f"txt_{sid}")
                        
                        # Confirm Payment
                        if st.button("✅ Confirmar Pagamento Total", key=f"pay_{sid}", type="primary", use_container_width=True):
                            student_service.confirm_payment_all_pending(conn, sid)
                            st.toast(f"Pagamento de {sname} confirmado!", icon="💰")
                            time.sleep(1)
                            st.rerun()
                        
                        # PDF Download
                        st_data = {'name': sname, 'month': datetime.now().strftime('%m/%Y')}
                        pdf_bytes = reports.generate_student_statement(st_data, items, total)
                        
                        st.download_button(
                            "📄 Baixar Extrato PDF",
                            data=pdf_bytes,
                            file_name=f"extrato_{sname.replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            key=f"pdf_{sid}",
                            use_container_width=True
                        )
                    else:
                        st.info("Este aluno não possui débitos pendentes.")
    else:
        st.info("Sem alunos ativos cadastrados.")

