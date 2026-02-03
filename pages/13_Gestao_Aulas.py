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
            st.dataframe(classes, hide_index=True, use_container_width=True)
            
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
            
            # Edit Expander
            with st.expander("Editar / Desativar Aluno"):
                # Use ID-based mapping for uniqueness
                st_map = {f"{row['id']} - {row['name']}": row['id'] for _, row in df_students.iterrows()}
                sel_st_label = st.selectbox("Selecione para editar", [""] + list(st_map.keys()))
                
                if sel_st_label:
                    sid_target = st_map[sel_st_label]
                    # Filter by ID to be safe
                    row = df_students[df_students['id'] == sid_target].iloc[0]
                    
                    with st.form(key=f"edit_student_{row['id']}"):
                        en = st.text_input("Nome", value=row['name'], key=f"edit_name_{row['id']}")
                        ep = st.text_input("Telefone", value=row['phone'], key=f"edit_phone_{row['id']}")
                        
                        # Edit Class
                        e_curr_class_id = row['class_id']
                        # Find index
                        curr_idx = 0
                        cls_names = [""] + list(class_opts.keys())
                        
                        # Try to find current class name
                        curr_cls_name = ""
                        for name, cid in class_opts.items():
                             if cid == e_curr_class_id:
                                 curr_cls_name = name
                                 break
                        
                        try:
                            curr_idx = cls_names.index(curr_cls_name)
                        except: pass
                        
                        e_cl_name = st.selectbox("Turma", cls_names, index=curr_idx, key=f"edit_class_{row['id']}")
                        
                        ea = st.checkbox("Ativo", value=bool(row['active']), key=f"edit_active_{row['id']}")
                        
                        if st.form_submit_button("Salvar Alterações"):
                            try:
                                new_cid = class_opts.get(e_cl_name)
                                
                                # Explicitly casting/handling to ensure correct type passed
                                if new_cid is not None:
                                    new_cid = int(new_cid)
                                
                                student_service.update_student(conn, row['id'], en, ep, ea, class_id=new_cid)
                                st.success(f"Atualizado com sucesso!")
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
                # Category Filter
                cats = pd.read_sql("SELECT id, name FROM material_categories ORDER BY name", conn)
                cat_opts = {row['name']: row['id'] for _, row in cats.iterrows()}
                cat_filter = st.selectbox("Filtrar Categoria Material", ["Todas"] + list(cat_opts.keys()))
                
                # Query Materials
                q_mat = "SELECT id, name, unit, price_per_unit, stock_level FROM materials WHERE type != 'Serviço'"
                if cat_filter != "Todas":
                    q_mat += f" AND category_id={cat_opts[cat_filter]}"
                q_mat += " ORDER BY name"
                
                mats = pd.read_sql(q_mat, conn)
                
                if mats.empty:
                    st.warning("Nenhum material nesta categoria.")
                else:
                    m_dict = {f"{r['name']} (R$ {r['price_per_unit']:.2f}/{r['unit']})": r['id'] for _, r in mats.iterrows()}
                    
                    with st.form("form_mat_consumption"):
                        target_mat = st.selectbox("Selecione Material", list(m_dict.keys()))
                        qty = st.number_input("Quantidade", min_value=0.01, step=0.1)
                        date_cons = st.date_input("Data", value=datetime.today())
                        
                        if st.form_submit_button("Lançar Consumo"):
                            mat_id = m_dict[target_mat]
                            try:
                                uid = st.session_state.current_user['id'] if 'current_user' in st.session_state else None
                                cid = student_service.process_material_consumption(conn, st_id, mat_id, qty, date_cons.strftime('%Y-%m-%d'), uid)
                                st.success("Consumo registrado com sucesso!")
                            except Exception as e:
                                st.error(f"Erro: {e}")
                            
            else:
                # Manual Extra/Service
                with st.form("form_extra"):
                    desc = st.text_input("Descrição (Ex: Queima Extra, Aula Avulsa)")
                    val_unit = st.number_input("Valor Unitário (R$)", min_value=0.0)
                    qty = st.number_input("Quantidade", value=1.0, min_value=0.1)
                    date_cons = st.date_input("Data", value=datetime.today())
                    
                    if st.form_submit_button("Lançar"):
                        if desc and val_unit > 0:
                            total = val_unit * qty
                            student_service.add_consumption(conn, st_id, desc, qty, val_unit, total, date_cons.strftime('%Y-%m-%d'))
                            st.success("Lançamento realizado!")
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
    
    # Per Student View
    students = student_service.get_all_active_students(conn)
    if students.empty:
        st.info("Sem alunos.")
    else:
        for i, row in students.iterrows():
            sid = row['id']
            sname = row['name']
            
            # Fetch Financials
            tuit, cons, total = student_service.get_student_financial_summary(conn, sid)
            
            # Determine color based on debt
            status_color = "red" if total > 0 else "green"
            label = f"{sname} - Pendente: R$ {total:.2f}"
            
            with st.expander(f"🎓 {label}"):
                c_det, c_act = st.columns([2, 1])
                
                # Details Table logic
                items = []
                # Tuitions
                for _, t in tuit.iterrows():
                    items.append({
                        "date": t['month_year'], # Using month_year as date display for tuition
                        "description": f"Mensalidade {t['month_year']}",
                        "quantity": 1,
                        "value": t['amount'],
                        "status": t['status']
                    })
                # Consumptions
                for _, c in cons.iterrows():
                    items.append({
                        "date": c['date'],
                        "description": c['description'],
                        "quantity": c['quantity'],
                        "value": c['total_value'],
                        "status": c['status']
                    })
                
                with c_det:
                    if items:
                        df_items = pd.DataFrame(items)
                        st.dataframe(df_items, hide_index=True, use_container_width=True)
                    else:
                        st.info("Tudo pago!")
                        
                with c_act:
                    # Billing Text
                    if total > 0:
                        st.caption("Texto para Cobrança")
                        bill_txt = (f"Olá {sname.split()[0]}! 🏺\n"
                                    f"Estou passando para enviar o resumo do atelier.\n\n"
                                    f"Total em aberto: R$ {total:.2f}\n"
                                    f"Referente a mensalidade e consumos extras.\n\n"
                                    f"Pode realizar o PIX para a chave: (xxx) \n"
                                    f"Obrigado!")
                        st.text_area("Copiar", bill_txt, height=150, key=f"txt_{sid}")
                        
                        # Confirm Payment
                        if st.button("✅ Confirmar Pagamento Total", key=f"pay_{sid}", type="primary"):
                            student_service.confirm_payment_all_pending(conn, sid)
                            st.success("Baixa realizada!")
                            st.rerun()
                        
                        # PDF Download
                        st_data = {'name': sname, 'month': datetime.now().strftime('%m/%Y')}
                        pdf_bytes = reports.generate_student_statement(st_data, items, total)
                        
                        st.download_button(
                            "📄 Baixar Extrato PDF",
                            data=pdf_bytes,
                            file_name=f"extrato_{sname.replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            key=f"pdf_{sid}"
                        )
                    else:
                        st.success("Em dia! 🎉")

