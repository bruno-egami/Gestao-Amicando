import streamlit as st
import pandas as pd
import time
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
tab_summary, tab_classes, tab_students, tab_finance, tab_history = st.tabs(["📊 Resumo", "🗓️ Turmas", "👥 Alunos", "💰 Gestão Financeira", "📜 Histórico Financeiro"])

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
                        admin_utils.show_feedback_dialog("Turma criada!", level="success")
                    except Exception as e:
                        admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")
                else:
                    admin_utils.show_feedback_dialog("Nome obrigatório.", level="warning")
    
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
                            admin_utils.show_feedback_dialog("Atualizado!", level="success")

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
                        admin_utils.show_feedback_dialog(f"Aluno {name} cadastrado com ID {nid}!", level="success")
                    except Exception as e:
                        admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")
                else:
                    admin_utils.show_feedback_dialog("Nome obrigatório.", level="warning")
    
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
                                # (Toasts are used for reactive background updates, but the user requested persistent. 
                                # However, show_feedback_dialog calls st.rerun which might be aggressive for a reactive dropdown. 
                                # Let's convert to dialog for full consistency as requested.)
                                admin_utils.show_feedback_dialog(f"Turma do Aluno {sid} alterada para: {sel_val}", level="success")
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
                                admin_utils.show_feedback_dialog("Dados atualizados!", level="success")
                                st.cache_data.clear()
                            except Exception as e:
                                admin_utils.show_feedback_dialog(f"Erro ao atualizar: {e}", level="error")

# ==============================================================================
# TAB 3: GESTÃO FINANCEIRA (UNIFIED)
# ==============================================================================
@st.dialog("✨ Registro Concluído")
def show_success_summary(item_name, qty, total, movement_type="Lançamento"):
    st.success(f"**{movement_type} realizado com sucesso!**")
    st.markdown(f"""
    ---
    **Resumo do Registro:**
    - **Item:** {item_name}
    - **Quantidade:** {qty}
    - **Valor Total:** R$ {total:.2f}
    ---
    """)
    if st.button("Fechar e Atualizar", type="primary", use_container_width=True):
        st.rerun()

@st.dialog("📝 Editar Mensalidade")
def edit_tuition_dialog(tid, sname, month, current_val):
    st.markdown(f"**Aluno:** {sname} | **Ref:** {month}")
    new_val = st.number_input("Novo Valor (R$)", value=float(current_val), min_value=0.0)
    if st.button("Salvar Alterações", type="primary", use_container_width=True):
        student_service.update_tuition(conn, tid, new_val)
        admin_utils.show_feedback_dialog("Valor da mensalidade atualizado!", level="success")
        st.rerun()

@st.dialog("📝 Editar Consumo")
def edit_consumption_dialog(cid, sname, current_desc, current_val):
    st.markdown(f"**Aluno:** {sname}")
    new_desc = st.text_input("Descrição", value=current_desc)
    new_val = st.number_input("Valor Total (R$)", value=float(current_val), min_value=0.0)
    if st.button("Salvar Alterações", type="primary", use_container_width=True):
        student_service.update_consumption(conn, cid, new_desc, new_val)
        admin_utils.show_feedback_dialog("Consumo atualizado!", level="success")
        st.rerun()

with tab_finance:
    st.subheader("Controle Financeiro e Consumo")
    
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
            admin_utils.show_feedback_dialog(f"Geradas {count} mensalidades for {month_ref}.", level="success")

    st.divider()
    
    # --- FILTERS & LIST ---
    c_f1, c_f2, c_f3 = st.columns([2, 1, 1])
    search_fin = c_f1.text_input("🔍 Buscar Aluno", placeholder="Nome...", key="fin_search")
    
    classes_df = student_service.get_all_classes(conn)
    cls_opts = ["Todas"] + classes_df['name'].tolist() if not classes_df.empty else ["Todas"]
    filter_cls_fin = c_f2.selectbox("📚 Turma", cls_opts, key="fin_filter_cls")
    
    only_pending = c_f3.checkbox("⚠️ Apenas Pendentes", value=False, key="fin_only_pend")
    
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
                
                st.markdown(f"### 👤 Aluno: {sname}")
                
                # --- TWO COLUMN LAYOUT: ACTIONS/SUMMARY (Left) vs NEW CONSUMPTION (Right) ---
                col_fin_left, col_fin_right = st.columns([1, 1], gap="large")
                
                with col_fin_left:
                    st.markdown("#### 📊 Extrato e Pendências")
                    tuit, cons, total = student_service.get_student_financial_summary(conn, sid)
                    
                    if not tuit.empty or not cons.empty:
                        # Render Tuitions
                        for _, t in tuit.iterrows():
                            # Partial Logic
                            paid = t.get('amount_paid', 0) or 0
                            remaining = t['amount'] - paid
                            label = f"💰 Mensalidade {t['month_year']} - Restante: R$ {remaining:.2f}"
                            if paid > 0:
                                label += f" (Total: {t['amount']:.2f})"
                                
                            with st.expander(label, expanded=False):
                                ec1, ec2 = st.columns(2)
                                if ec1.button("📝 Editar", key=f"edit_t_{t['id']}"):
                                    edit_tuition_dialog(t['id'], sname, t['month_year'], t['amount'])
                                if ec2.button("🗑️ Cancelar", key=f"cancel_t_{t['id']}"):
                                    admin_utils.show_confirmation_dialog(
                                        f"Deseja cancelar a mensalidade de {t['month_year']}?",
                                        on_confirm=lambda tid=t['id']: student_service.cancel_tuition(conn, tid)
                                    )

                        # Render Consumptions
                        for _, c in cons.iterrows():
                            paid = c.get('amount_paid', 0) or 0
                            remaining = c['total_value'] - paid
                            
                            desc_label = c['description']
                            if c.get('notes'): desc_label += f" ({c['notes']})"
                            
                            label = f"📦 {desc_label} - Restante: R$ {remaining:.2f}"
                            if paid > 0:
                                label += f" (Total: {c['total_value']:.2f})"
                                
                            with st.expander(label, expanded=False):
                                ec1, ec2 = st.columns(2)
                                if ec1.button("📝 Editar", key=f"edit_c_{c['id']}"):
                                    edit_consumption_dialog(c['id'], sname, c['description'], c['total_value'])
                                if ec2.button("🗑️ Cancelar", key=f"cancel_c_{c['id']}"):
                                    admin_utils.show_confirmation_dialog(
                                        f"Deseja cancelar o lançamento: {c['description']}?",
                                        on_confirm=lambda cid=c['id']: student_service.cancel_consumption(conn, cid)
                                    )
                                    
                        st.divider()
                        st.metric("Total em Aberto", f"R$ {total:.2f}")

                        # Prepare list for PDF (unchanged logic for PDF generation)
                        items = []
                        for _, t in tuit.iterrows():
                            paid = t.get('amount_paid', 0) or 0
                            items.append({"date": t['month_year'], "description": f"Mensalidade {t['month_year']}", "quantity": 1, "value": t['amount'], "paid": paid, "status": t['status']})
                        for _, c in cons.iterrows():
                            desc = c['description']
                            if c.get('notes'): desc += f" ({c['notes']})"
                            paid = c.get('amount_paid', 0) or 0
                            items.append({"date": c['date'], "description": desc, "quantity": c['quantity'], "value": c['total_value'], "paid": paid, "status": c['status']})
                    else:
                        st.success("Tudo pago! Nenhuma pendência encontrada. 🎉")

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
                        
                        # Partial Payment Input
                        p_col1, p_col2 = st.columns([2, 1])
                        pay_val = p_col1.number_input("Valor Pagamento (R$)", min_value=0.01, max_value=float(total), value=float(total), step=10.0, key=f"pay_input_{sid}")
                        
                        if p_col2.button("✅ Pagar", key=f"pay_{sid}", type="primary", use_container_width=True):
                            admin_utils.show_confirmation_dialog(
                                f"Confirmar pagamento de R$ {pay_val:.2f} para {sname}?",
                                on_confirm=lambda s=sid, v=pay_val: student_service.process_partial_payment(conn, s, v)
                            )
                        
                        # PDF Download
                        st_data = {'name': sname, 'month': datetime.now().strftime('%m/%Y')}
                        pdf_bytes = reports.generate_student_statement(st_data, items, total)
                        st.download_button("📄 Baixar Extrato PDF", data=pdf_bytes, file_name=f"extrato_{sname.replace(' ', '_')}.pdf", mime="application/pdf", key=f"pdf_{sid}", use_container_width=True)

                with col_fin_right:
                    st.markdown("#### ✨ Lançar Novo Consumo")
                    c_type = st.radio("Tipo de Lançamento", ["Material (Baixa Estoque)", "Aula Extra / Serviço / Taxas"], horizontal=True, key=f"ctype_{sid}")
                    
                    if c_type.startswith("Material"):
                        # Category Filter Data
                        cats = pd.read_sql("SELECT id, name FROM material_categories ORDER BY name", conn)
                        cat_opts = {row['name']: row['id'] for _, row in cats.iterrows()}
                        
                        # Material Filters
                        c_mf1, c_mf2 = st.columns([1, 1])
                        cat_filter = c_mf1.selectbox("Filtrar Categoria", ["Todas"] + list(cat_opts.keys()), key=f"fcat_{sid}")
                        name_filter = c_mf2.text_input("🔍 Buscar Material", placeholder="Ex: Argila...", key=f"fmat_{sid}")
                        
                        # Query Materials
                        q_mat = "SELECT id, name, unit, price_per_unit, stock_level FROM materials WHERE type != 'Serviço'"
                        if cat_filter != "Todas":
                            q_mat += f" AND category_id={cat_opts[cat_filter]}"
                        if name_filter:
                            q_mat += f" AND name LIKE '%{name_filter}%'"
                        q_mat += " ORDER BY name"
                        
                        mats = pd.read_sql(q_mat, conn)
                        
                        if mats.empty:
                            st.warning("Nenhum material encontrado.")
                        else:
                            m_dict = {f"{r['name']} (R$ {r['price_per_unit']:.2f}/{r['unit']})": r['id'] for _, r in mats.iterrows()}
                            
                            with st.form(f"form_mat_consumption_{sid}"):
                                target_mat = st.selectbox("Selecione Material", list(m_dict.keys()))
                                cm1, cm2 = st.columns(2)
                                qty = cm1.number_input("Quantidade", min_value=0.01, step=0.1)
                                markup = cm2.number_input("Markup (x Multiplicador)", min_value=1.0, value=2.0, step=0.1)
                                
                                date_cons = st.date_input("Data", value=datetime.today())
                                notes = st.text_input("Observações (Opcional)", key=f"notes_mat_{sid}")
                                
                                if st.form_submit_button("Lançar Consumo", type="primary", use_container_width=True):
                                    mat_id = m_dict[target_mat]
                                    try:
                                        uid = st.session_state.current_user['id'] if 'current_user' in st.session_state else None
                                        cid = student_service.process_material_consumption(conn, sid, mat_id, qty, date_cons.strftime('%Y-%m-%d'), uid, notes, markup)
                                        mat_name_clean = target_mat.split(" (R$")[0]
                                        mat_price = float(mats[mats['id'] == mat_id]['price_per_unit'].iloc[0]) * markup
                                        show_success_summary(f"Material: {mat_name_clean}", qty, mat_price * qty)
                                    except Exception as e:
                                        admin_utils.show_feedback_dialog(f"Erro: {e}", level="error")
                    else:
                        # Manual Extra/Service
                        with st.form(f"form_extra_{sid}"):
                            desc = st.text_input("Descrição (Ex: Queima Extra, Aula Avulsa)")
                            ce1, ce2, ce3 = st.columns(3)
                            val_unit = ce1.number_input("Valor Unitário (R$)", min_value=0.0)
                            ext_qty = ce2.number_input("Quantidade", value=1.0, min_value=0.1)
                            markup = ce3.number_input("Markup (x Fator)", min_value=1.0, value=2.0, step=0.1)
                            
                            date_cons = st.date_input("Data", value=datetime.today())
                            notes = st.text_input("Observações (Opcional)", key=f"notes_extra_{sid}")
                            
                            if st.form_submit_button("Lançar", type="primary", use_container_width=True):
                                if desc and val_unit > 0:
                                    marked_up_price = val_unit * markup
                                    total_ext = marked_up_price * ext_qty
                                    student_service.add_consumption(conn, sid, desc, ext_qty, marked_up_price, total_ext, date_cons.strftime('%Y-%m-%d'), notes=notes, markup=markup)
                                    show_success_summary(desc, ext_qty, total_ext)
                                else:
                                    admin_utils.show_feedback_dialog("Preencha descrição e valor.", level="warning")
    else:
        st.info("Sem alunos ativos cadastrados.")

# ==============================================================================
# TAB 4: HISTÓRICO FINANCEIRO (Refined)
# ==============================================================================
with tab_history:
    st.subheader("Histórico de Movimentações")
    
    # --- FILTERS ---
    with st.expander("🔍 Filtros de Visualização", expanded=False):
        f_c1, f_c2 = st.columns(2)
        
        # Period
        today = datetime.today()
        start_date = f_c1.date_input("De", value=today.replace(day=1))
        end_date = f_c2.date_input("Até", value=today)
        
        f_c3, f_c4, f_c5, f_c6 = st.columns(4)
        
        # Student
        students_all = student_service.get_all_active_students(conn)
        st_opts = {"Todos": "Todos"}
        if not students_all.empty:
            for _, s in students_all.iterrows():
                st_opts[s['name']] = s['id']
        
        sel_st_name = f_c3.selectbox("Aluno", list(st_opts.keys()), key="hist_student_sel")
        sel_st_id = st_opts[sel_st_name]
        
        # Class (Turma)
        classes_df = student_service.get_all_classes(conn)
        cls_opts = {"Todas": "Todas"}
        if not classes_df.empty:
            for _, c in classes_df.iterrows():
                cls_opts[c['name']] = c['id']
        
        sel_cls_name = f_c4.selectbox("Turma", list(cls_opts.keys()), key="hist_cls_sel")
        sel_cls_id = cls_opts[sel_cls_name]
        
        # Type
        type_opts = ["Todos", "Mensalidade", "Consumo"]
        sel_type = f_c5.selectbox("Tipo Lançamento", type_opts, key="hist_type_sel")
        
        # Status
        status_opts = ["Todos", "Pago", "Pendente"]
        sel_status = f_c6.selectbox("Status Fatura", status_opts, key="hist_status_sel")
        
    st.divider()
    
    # Fetch Data
    history_df = student_service.get_payment_history(
        conn, 
        start_date=start_date.strftime('%Y-%m-%d'), 
        end_date=end_date.strftime('%Y-%m-%d'),
        student_id=sel_st_id,
        payment_type=sel_type,
        class_id=sel_cls_id,
        status_filter=sel_status
    )
    
    if not history_df.empty:
        # Summary Metrics
        m1, m2 = st.columns(2)
        total_rec = history_df[history_df['status'] == 'Pago']['amount'].sum()
        total_pend = history_df[history_df['status'] == 'Pendente']['amount'].sum()
        m1.metric("Total Recebido (Pago)", f"R$ {total_rec:,.2f}")
        m2.metric("Total Aberto (Pendente)", f"R$ {total_pend:,.2f}")
        
        st.markdown("---")
        
        # Table
        # Columns in DF: date, amount, student_name, student_id, description, cat, movement_type, status
        st.dataframe(
            history_df[['date', 'student_name', 'movement_type', 'description', 'amount', 'status']],
            hide_index=True,
            use_container_width=True,
            column_config={
                "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "student_name": "Aluno",
                "movement_type": "Movimentação",
                "description": "Descrição",
                "amount": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                "status": "Status"
            }
        )
        
        st.divider()
        st.subheader("📄 Gerar Extrato Individual")
        st.info("Selecione um aluno filtrado acima para gerar o PDF consolidado do período selecionado.")
        
        if sel_st_id != "Todos":
            # Generate Statement for this student and period
            st_items = []
            for _, row in history_df[history_df['student_id'] == sel_st_id].iterrows():
                st_items.append({
                    "date": row['date'].strftime('%Y-%m-%d'),
                    "description": row['description'],
                    "quantity": 1,
                    "value": row['amount'],
                    "paid": row.get('amount_paid', 0) or (row['amount'] if row['status'] == 'Pago' else 0), # Fallback if col missing in history view
                    "status": row['status']
                })
            
            if st_items:
                st_data = {'name': sel_st_name, 'month': f"{start_date.strftime('%d/%m/%y')} - {end_date.strftime('%d/%m/%y')}"}
                pdf_bytes = reports.generate_student_statement(st_data, st_items)
                
                st.download_button(
                    f"Baixar PDF de {sel_st_name}",
                    data=pdf_bytes,
                    file_name=f"extrato_{sel_st_name.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    key=f"pdf_hist_{sel_st_id}",
                    use_container_width=True
                )
        else:
            st.warning("Selecione um aluno específico no filtro para habilitar o download do PDF.")
            
    else:
        st.info("Nenhuma movimentação encontrada com os filtros selecionados.")

