
import streamlit as st
import pandas as pd
from datetime import datetime
import io
import zipfile
import database
import admin_utils
import services.reporting as reports
from services import student_service
from utils.logging_config import get_logger

logger = get_logger(__name__)

# ==============================================================================
# DIALOGS & HELPERS
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
def edit_tuition_dialog(tid, sname, month, current_val, current_count=None, current_unit_price=None):
    st.markdown(f"**Aluno:** {sname} | **Ref:** {month}")
    
    # Mode: Automatic vs Manual
    st.caption("Ajuste os valores quantitativos. O total será recalculado.")
    
    c1, c2 = st.columns(2)
    new_count = c1.number_input("Qtd Aulas", value=int(current_count) if current_count else 0, min_value=0, step=1)
    new_unit = c2.number_input("Valor Unitário (R$)", value=float(current_unit_price) if current_unit_price else 0.0, min_value=0.0, step=0.5)
    
    msg_total = new_count * new_unit
    st.metric("Total Recalculado", f"R$ {msg_total:.2f}")
    
    # Manual override option (legacy support)
    manual_total = st.number_input("Valor Manual (Total)", value=float(current_val), min_value=0.0, help="Caso queira definir um valor fixo diferente do cálculo.")
    
    final_val = manual_total if manual_total != current_val else msg_total
    
    if st.button("Salvar Alterações", type="primary", use_container_width=True):
        try:
            with database.db_session() as conn:
                student_service.update_tuition(conn, tid, final_val)
                st.success("Valor da mensalidade atualizado!")
                if st.button("Concluir", type="primary", use_container_width=True):
                    st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

@st.dialog("📝 Editar Consumo")
def edit_consumption_dialog(cid, sname, current_desc, current_val, current_qty=1.0, current_markup=1.0):
    st.markdown(f"**Aluno:** {sname}")
    
    st.caption("Ajuste a quantidade e markup. O valor total será recalculado.")
    
    col_d1, col_d2 = st.columns([3, 1])
    new_desc = col_d1.text_input("Descrição", value=current_desc)
    
    try:
        inferred_unit_price = float(current_val) / (float(current_qty) * float(current_markup)) if float(current_qty) > 0 and float(current_markup) > 0 else 0.0
    except Exception:
        inferred_unit_price = 0.0
        
    c1, c2, c3 = st.columns(3)
    new_qty = c1.number_input("Quantidade", value=float(current_qty), min_value=0.01, step=1.0)
    new_markup = c2.number_input("Markup", value=float(current_markup), min_value=1.0, step=0.1)
    
    calc_total = inferred_unit_price * new_qty * new_markup
    
    c3.metric("Valor Unit. (Est.)", f"R$ {inferred_unit_price:.2f}")
    
    st.divider()
    
    new_val = st.number_input("Valor Total (R$)", value=float(calc_total), min_value=0.0, step=0.5, help="Calculado: Qtd * Markup * Unitário. Ajuste se necessário.")
    
    if st.button("Salvar Alterações", type="primary", use_container_width=True):
        try:
            with database.db_session() as conn:
                student_service.update_consumption(conn, cid, new_desc, new_qty, new_markup, new_val)
                st.success("Consumo atualizado!")
                if st.button("Concluir", type="primary", use_container_width=True):
                    st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

# ==============================================================================
# MAIN VIEWS
# ==============================================================================

def render_financial_management(conn):
    st.subheader("Controle Financeiro e Consumo")
    
    # Global Settings
    with st.expander("⚙️ Configurações Gerais"):
        curr_global = student_service.get_global_price_per_class(conn)
        new_global = st.number_input("Valor Global da Aula (R$)", value=float(curr_global), min_value=0.0, step=0.50, help="Valor usado para o cálculo de TODAS as mensalidades.")
        if st.button("Salvar Configuração Global"):
             if student_service.set_global_price_per_class(conn, new_global):
                 admin_utils.show_feedback_dialog("Valor global atualizado!", level="success")
                 st.rerun()
             else:
                 st.error("Erro ao salvar.")
    
    WEEKDAYS = {
        "Segunda-feira": 0, "Terça-feira": 1, "Quarta-feira": 2, 
        "Quinta-feira": 3, "Sexta-feira": 4, "Sábado": 5, "Domingo": 6
    }
    WEEKDAYS_REV = {v: k for k, v in WEEKDAYS.items()}

    # Calendar & Cancellations Visualization
    with st.expander("📅 Calendário de Aulas (Simulação & Cancelamentos)", expanded=True):
        st.markdown(f"**Verifique a quantidade de aulas calculada para cada turma no mês.**")
        
        c_cal1, c_cal2 = st.columns([1, 2])
        sim_month = c_cal1.text_input("Mês/Ano para Simulação", value=datetime.now().strftime('%m/%Y'), key="sim_month_ref")
        
        # Calculate for all classes
        classes_sim = student_service.get_all_classes(conn)
        if not classes_sim.empty:
            sim_data = []
            for _, c_row in classes_sim.iterrows():
                metrics = student_service.calculate_class_monthly_metrics(conn, c_row['id'], sim_month)
                
                if metrics:
                    sim_data.append({
                        "_wd_idx": metrics['weekday_idx'],
                        "Turma": c_row['name'],
                        "Dia Semana": WEEKDAYS_REV.get(metrics['weekday_idx'], "-"),
                        "Aulas Totais": metrics['total_days'],
                        "Cancelamentos": metrics['canc_count'],
                        "Aulas Líquidas": metrics['net_days'],
                        "Mensalidade Est. (R$)": metrics['estimated_tuition']
                    })

            if sim_data:
                sim_data.sort(key=lambda x: x['_wd_idx'])
                df_sim = pd.DataFrame(sim_data)
                df_sim_disp = df_sim.drop(columns=['_wd_idx'])
                st.dataframe(df_sim_disp, hide_index=True, use_container_width=True)
            else:
                st.info("Nenhuma turma com dia da semana configurado ou erro na data.")
        
        st.markdown("---")
        st.markdown("**Registrar Cancelamento / Feriado Rapidamente:**")
        c_q1, c_q2, c_q3, c_q4 = st.columns([1, 2, 2, 1])
        
        # 1. Date Input First
        qa_date = c_q1.date_input("Data Cancelamento", value=datetime.today(), key="qa_date")
        
        # 2. Determine Pre-selection based on Date
        pre_sel_index = 0
        qa_classes = classes_sim['name'].tolist() if not classes_sim.empty else []
        
        if not classes_sim.empty and qa_date:
            wd = qa_date.weekday()
            try:
                valid_wd = classes_sim['weekday'].fillna(-1).astype(int)
                match = classes_sim[valid_wd == wd]
                if not match.empty:
                    match_name = match.iloc[0]['name']
                    if match_name in qa_classes:
                        pre_sel_index = qa_classes.index(match_name)
            except Exception as e:
                logger.debug(f"Error pre-selecting class for cancellation: {e}")

        qa_cls_sel = c_q2.selectbox("Turma", qa_classes, index=pre_sel_index, key=f"qa_cls_{qa_date}")
        qa_reason = c_q3.text_input("Motivo", placeholder="Feriado...", key="qa_reason")
        
        if c_q4.button("Adicionar", type="primary", key="qa_btn"):
             if qa_cls_sel and qa_reason:
                 cid_target = int(classes_sim[classes_sim['name'] == qa_cls_sel].iloc[0]['id'])
                 if student_service.add_class_cancellation(conn, cid_target, qa_date.strftime('%Y-%m-%d'), qa_reason):
                     admin_utils.show_feedback_dialog("Cancelamento registrado com sucesso!", level="success")
                     st.rerun()
             else:
                 st.warning("Preencha Turma e Motivo.")

        # List Cancellations
        st.markdown("---")
        st.markdown(f"**📋 Cancelamentos Registrados em {sim_month}**")
        
        try:
            m_sim, y_sim = map(int, sim_month.split('/'))
            all_cancs = []
            for _, c_row in classes_sim.iterrows():
                c_cancs = student_service.get_class_cancellations(conn, c_row['id'])
                if not c_cancs.empty:
                    c_cancs['date_dt'] = pd.to_datetime(c_cancs['date'])
                    mask = (c_cancs['date_dt'].dt.month == m_sim) & (c_cancs['date_dt'].dt.year == y_sim)
                    filtered = c_cancs[mask]
                    
                    for _, fr in filtered.iterrows():
                        all_cancs.append({
                            "id": fr['id'],
                            "Turma": c_row['name'],
                            "Data": fr['date_dt'].strftime('%d/%m/%Y'),
                            "Motivo": fr['reason']
                        })
            
            if all_cancs:
                df_cancs = pd.DataFrame(all_cancs)
                for i, row in df_cancs.iterrows():
                    cc1, cc2, cc3, cc4 = st.columns([2, 2, 3, 1])
                    cc1.text(row['Turma'])
                    cc2.text(row['Data'])
                    cc3.text(row['Motivo'])
                    if cc4.button("🗑️", key=f"del_fin_canc_{row['id']}"):
                        student_service.delete_class_cancellation(conn, row['id'])
                        st.rerun()
            else:
                st.info(f"Nenhum cancelamento encontrado em {sim_month}.")
        except Exception as e:
            st.error(f"Erro ao listar cancelamentos: {e}")

    with st.expander("🛠️ Ferramentas em Massa (Gerar Mensalidades)"):
        st.info("O sistema calculará o valor automaticamente: (Qtd Aulas no Mês - Cancelamentos) x (Valor Global).")
        
        c_gen1, c_gen2 = st.columns([1, 2])
        month_ref = c_gen1.text_input("Mês/Ano Referência", value=datetime.now().strftime('%m/%Y'))
        
        if st.button("Gerar Mensalidades para TODOS Ativos"):
            students = student_service.get_all_active_students(conn)
            count = 0
            
            progress_bar = st.progress(0)
            st_len = len(students)
            
            for idx, (_, s) in enumerate(students.iterrows()):
                days_count, unit_price, total_calc, final_dates = student_service.calculate_tuition(conn, s['id'], month_ref)
                
                final_amt = total_calc
                u_p = unit_price
                c_c = days_count
                
                ok, msg = student_service.generate_tuition_record(conn, s['id'], month_ref, final_amt, class_count=c_c, unit_price=u_p, class_dates=final_dates)
                if ok: count += 1
                
                progress_bar.progress((idx + 1) / st_len)
                
            admin_utils.show_feedback_dialog(f"Processo concluído! {count} mensalidades processadas.", level="success")

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
        students['total_due'] = students['id'].apply(lambda x: student_service.get_student_financial_summary(conn, x)[2])
        
        if search_fin:
            students = students[students['name'].str.contains(search_fin, case=False)]
        if filter_cls_fin != "Todas":
            students = students[students['class_name'] == filter_cls_fin]
        if only_pending:
            students = students[students['total_due'] > 0]
            
        if students.empty:
            st.info("Nenhum aluno encontrado com estes filtros.")
        else:
            # --- BATCH DOWNLOAD (ZIP) ---
            with st.expander("📥 Baixar Relatórios em Massa (ZIP)", expanded=False):
                st.info("Gera um arquivo ZIP contendo os extratos PDF de todos os alunos listados abaixo (filtrados).")
                c_zip1, c_zip2 = st.columns([1, 2])
                zip_filename_input = c_zip1.text_input("Nome do Arquivo (.zip)", value=datetime.now().strftime('%m-%Y'))
                
                if c_zip2.button("📦 Gerar ZIP", key="btn_gen_zip"):
                    zip_buffer = io.BytesIO()
                    
                    with st.spinner("Gerando relatórios..."):
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                            progress_zip = st.progress(0)
                            total_zip = len(students)
                            count_zip = 0
                            
                            for idx, (_, s_row) in enumerate(students.iterrows()):
                                sid_z = s_row['id']
                                sname_z = s_row['name']
                                
                                items_z, cancs_list_z, total_z, st_class_name_z = student_service.get_student_statement_items(conn, sid_z)

                                if items_z:
                                    month_header = zip_filename_input.replace('-', '/')
                                    st_data_z = {'name': sname_z, 'month': month_header, 'class_name': st_class_name_z}
                                    pdf_out = reports.generate_student_statement(st_data_z, items_z, total_z, cancellations=cancs_list_z)
                                    
                                    pdf_bytes = pdf_out.getvalue() if hasattr(pdf_out, 'getvalue') else pdf_out
                                    zf.writestr(f"{sname_z}_Extrato.pdf", pdf_bytes)
                                    count_zip += 1
                                
                                progress_zip.progress((idx + 1) / total_zip)
                        
                        st.session_state['zip_data'] = zip_buffer.getvalue()
                        st.session_state['zip_name'] = f"{zip_filename_input}.zip"
                        st.success(f"{count_zip} relatórios gerados com sucesso! Clique abaixo para baixar.")

                if 'zip_data' in st.session_state:
                     st.download_button(
                        label="⬇️ Clique para Baixar o Arquivo ZIP",
                        data=st.session_state['zip_data'],
                        file_name=st.session_state['zip_name'],
                        mime="application/zip",
                        key="btn_download_zip_final"
                    )

            st.markdown("---")
            sel_list = {f"{row['name']} (Pend: R$ {row['total_due']:.2f})": row['id'] for _, row in students.iterrows()}
            selected_label = st.selectbox("🎯 Selecione Aluno para Gerenciar", [""] + list(sel_list.keys()))
            
            if selected_label:
                sid = sel_list[selected_label]
                row = students[students['id'] == sid].iloc[0]
                sname = row['name']
                
                st.markdown(f"### 👤 Aluno: {sname}")
                
                col_fin_left, col_fin_right = st.columns([1, 1], gap="large")
                
                with col_fin_left:
                    st.markdown("#### 📊 Extrato e Pendências")
                    tuit, cons, total = student_service.get_student_financial_summary(conn, sid)
                    
                    # Fetch detailed items for ALL states (Paid or Pending) to ensure PDF generation works
                    items, cancellations_list, _, st_class_name = student_service.get_student_statement_items(conn, sid)
                    
                    if not tuit.empty or not cons.empty:
                        for _, t in tuit.iterrows():
                            paid = t.get('amount_paid', 0) or 0
                            remaining = t['amount'] - paid
                            label = f"💰 Mensalidade {t['month_year']} - Restante: R$ {remaining:.2f}"
                            if paid > 0: label += f" (Total: {t['amount']:.2f})"
                                
                            with st.expander(label, expanded=False):
                                ec1, ec2 = st.columns(2)
                                if ec1.button("📝 Editar", key=f"edit_t_{t['id']}"):
                                    edit_tuition_dialog(
                                        t['id'], 
                                        sname, 
                                        t['month_year'], 
                                        t['amount'],
                                        current_count=t['class_count'],
                                        current_unit_price=t['unit_price']
                                    )
                                if ec2.button("🗑️ Cancelar", key=f"cancel_t_{t['id']}"):
                                    def do_cancel_tuition(tid=t['id']):
                                        with database.db_session() as ctx_conn:
                                            student_service.cancel_tuition(ctx_conn, tid)
                                    admin_utils.show_confirmation_dialog(f"Deseja cancelar a mensalidade de {t['month_year']}?", on_confirm=do_cancel_tuition)

                        for _, c in cons.iterrows():
                            paid = c.get('amount_paid', 0) or 0
                            remaining = c['total_value'] - paid
                            
                            desc_label = c['description']
                            if c.get('notes'): desc_label += f" ({c['notes']})"
                            
                            label = f"📦 {desc_label} - Restante: R$ {remaining:.2f}"
                            if paid > 0: label += f" (Total: {c['total_value']:.2f})"
                                
                            with st.expander(label, expanded=False):
                                ec1, ec2 = st.columns(2)
                                if ec1.button("📝 Editar", key=f"edit_c_{c['id']}"):
                                    edit_consumption_dialog(
                                        c['id'], 
                                        sname, 
                                        c['description'], 
                                        c['total_value'],
                                        current_qty=c['quantity'] if pd.notnull(c['quantity']) else 1.0,
                                        current_markup=c['markup'] if pd.notnull(c.get('markup')) and c['markup'] > 0 else 1.0
                                    )
                                if ec2.button("🗑️ Cancelar", key=f"cancel_c_{c['id']}"):
                                    def do_cancel_consumption(cid=c['id']):
                                        with database.db_session() as ctx_conn:
                                            student_service.cancel_consumption(ctx_conn, cid)
                                    admin_utils.show_confirmation_dialog(f"Deseja cancelar o lançamento: {c['description']}?", on_confirm=do_cancel_consumption)
                                    
                        st.divider()
                        st.metric("Total em Aberto", f"R$ {total:.2f}")
                    else:
                        st.success("Tudo pago! Nenhuma pendência encontrada. 🎉")

                    # Always show Statement details (History)
                    # Always show Statement details (History)
                    if items:
                        st.markdown("##### 📜 Extrato Detalhado")
                        
                        # Headers
                        c1, c2, c3, c4, c5 = st.columns([1.5, 3, 1.5, 1.5, 1])
                        c1.markdown("**Data**")
                        c2.markdown("**Descrição**")
                        c3.markdown("**Valor**")
                        c4.markdown("**Status**")
                        c5.markdown("**Ações**")
                        
                        for item in items:
                            with st.container():
                                c1, c2, c3, c4, c5 = st.columns([1.5, 3, 1.5, 1.5, 1])
                                c1.write(pd.to_datetime(item['date']).strftime('%d/%m/%Y') if pd.notnull(item.get('date')) else '-')
                                c2.write(item['description'])
                                c3.write(f"R$ {item['value']:.2f}")
                                
                                status = item['status']
                                if status == 'Pago':
                                    c4.success(status)
                                    # Undo Button
                                    # Only if ID and Type are present (added in service)
                                    if item.get('id') and item.get('type'):
                                        if c5.button("↩️", key=f"undo_{item['type']}_{item['id']}", help="Desfazer Pagamento (Estornar)"):
                                            def undo_payment():
                                                student_service.revert_payment(conn, item['id'], item['type'])
                                                st.toast("Pagamento estornado com sucesso!", icon='🔄')
                                                
                                            admin_utils.show_confirmation_dialog(
                                                "Deseja realmente desfazer este pagamento? O item voltará para 'Pendente'.",
                                                action_label="Sim, Desfazer",
                                                on_confirm=undo_payment
                                            )
                                else:
                                    c4.warning(status)
                                
                                st.divider()

                    if total > 0:
                        st.markdown("**Ações Rápidas**")
                        bill_txt = (f"Olá {sname.split()[0]}! 🏺\n"
                                    f"Estou passando para enviar o resumo do atelier.\n\n"
                                    f"Total em aberto: R$ {total:.2f}\n"
                                    f"Referente a mensalidade e consumos extras.\n\n"
                                    f"Pode realizar o PIX para a chave: (xxx) \n"
                                    f"Obrigado!")
                        with st.expander("💬 Texto para WhatsApp", expanded=False):
                            st.text_area("Copiar", bill_txt, height=120, key=f"txt_{sid}")
                        
                        p_col1, p_col2 = st.columns([2, 1])
                        pay_val = p_col1.number_input("Valor Pagamento (R$)", min_value=0.01, max_value=float(total), value=float(total), step=10.0, key=f"pay_input_{sid}")
                        
                        if p_col2.button("✅ Pagar", key=f"pay_{sid}", type="primary", use_container_width=True):
                            def do_process_payment(s=sid, v=pay_val):
                                with database.db_session() as ctx_conn:
                                    student_service.process_partial_payment(ctx_conn, s, v)
                            admin_utils.show_confirmation_dialog(f"Confirmar pagamento de R$ {pay_val:.2f} para {sname}?", on_confirm=do_process_payment)
                        
                    # PDF Download - ALWAYS Available
                    st_data = {'name': sname, 'month': datetime.now().strftime('%m/%Y'), 'class_name': st_class_name}
                    pdf_bytes = reports.generate_student_statement(st_data, items, total, cancellations=cancellations_list)
                    st.download_button("📄 Baixar Extrato PDF", data=pdf_bytes, file_name=f"extrato_{sname.replace(' ', '_')}.pdf", mime="application/pdf", key=f"pdf_{sid}", use_container_width=True)

                with col_fin_right:
                    st.markdown("#### ✨ Lançar Novo Consumo")
                    c_type = st.radio("Tipo de Lançamento", ["Material (Baixa Estoque)", "Aula Extra / Serviço / Taxas"], horizontal=True, key=f"ctype_{sid}")
                    
                    if c_type.startswith("Material"):
                        from services import material_service
                        cats = material_service.get_all_categories(conn)
                        cat_opts = {row['name']: row['id'] for _, row in cats.iterrows()}
                        
                        c_mf1, c_mf2 = st.columns([1, 1])
                        cat_filter = c_mf1.selectbox("Filtrar Categoria", ["Todas"] + list(cat_opts.keys()), key=f"fcat_{sid}")
                        name_filter = c_mf2.text_input("🔍 Buscar Material", placeholder="Ex: Argila...", key=f"fmat_{sid}")
                        
                        mats = material_service.get_all_materials(conn)
                        mats = mats[mats['type'] != 'Serviço']
                        
                        if cat_filter != "Todas":
                            mats = mats[mats['category_id'] == cat_opts[cat_filter]]
                        if name_filter:
                            mats = mats[mats['name'].str.contains(name_filter, case=False)]
                        
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

def render_financial_history(conn):
    st.subheader("Histórico de Movimentações")
    
    with st.expander("🔍 Filtros de Visualização", expanded=False):
        f_c1, f_c2 = st.columns(2)
        
        today = datetime.today()
        start_date = f_c1.date_input("De", value=today.replace(day=1))
        end_date = f_c2.date_input("Até", value=today)
        
        f_c3, f_c4, f_c5, f_c6 = st.columns(4)
        
        students_all = student_service.get_all_active_students(conn)
        st_opts = {"Todos": "Todos"}
        if not students_all.empty:
            for _, s in students_all.iterrows():
                st_opts[s['name']] = s['id']
        
        sel_st_name = f_c3.selectbox("Aluno", list(st_opts.keys()), key="hist_student_sel")
        sel_st_id = st_opts[sel_st_name]
        
        classes_df = student_service.get_all_classes(conn)
        cls_opts = {"Todas": "Todas"}
        if not classes_df.empty:
            for _, c in classes_df.iterrows():
                cls_opts[c['name']] = c['id']
        
        sel_cls_name = f_c4.selectbox("Turma", list(cls_opts.keys()), key="hist_cls_sel")
        sel_cls_id = cls_opts[sel_cls_name]
        
        type_opts = ["Todos", "Mensalidade", "Consumo"]
        sel_type = f_c5.selectbox("Tipo Lançamento", type_opts, key="hist_type_sel")
        
        status_opts = ["Todos", "Pago", "Pendente"]
        sel_status = f_c6.selectbox("Status Fatura", status_opts, key="hist_status_sel")
        
    st.divider()
    
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
        m1, m2 = st.columns(2)
        total_rec = history_df[history_df['status'] == 'Pago']['amount'].sum()
        total_pend = history_df[history_df['status'] == 'Pendente']['amount'].sum()
        m1.metric("Total Recebido (Pago)", f"R$ {total_rec:,.2f}")
        m2.metric("Total Aberto (Pendente)", f"R$ {total_pend:,.2f}")
        
        st.markdown("---")
        
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
            st_items = []
            involved_months_hist = set()
            st_class_name_hist = "---"
            
            for _, row in history_df[history_df['student_id'] == sel_st_id].iterrows():
                desc = row['description']
                if 'class_count' in row and pd.notnull(row['class_count']):
                     try:
                         desc += f" ({int(row['class_count'])} aulas)"
                     except Exception as e:
                         logger.debug(f"Error formatting class count: {e}")
                
                if "Mensalidade" in str(row.get('cat', '')):
                     try:
                         parts = row['description'].split(' ')
                         if len(parts) >= 2:
                             involved_months_hist.add(parts[-1])
                     except Exception as e:
                         logger.debug(f"Error parsing month from description: {e}")
                
                paid_val = row.get('amount_paid', 0)
                if not paid_val and row['status'] == 'Pago': paid_val = row['amount']
                
                st_items.append({
                    "date": row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
                    "description": desc,
                    "quantity": 1,
                    "value": row['amount'],
                    "paid": paid_val,
                    "status": row['status'],
                    "class_dates": row.get('class_dates')
                })
                
                if row.get('class_name'): st_class_name_hist = row['class_name']
            
            cancellations_hist = []
            if involved_months_hist:
                 try:
                     curr_class_res = conn.execute("SELECT class_id FROM students WHERE id=?", (sel_st_id,)).fetchone()
                     if curr_class_res and curr_class_res[0]:
                         cid_hist = curr_class_res[0]
                         all_cancs_h = student_service.get_class_cancellations(conn, cid_hist)
                         
                         if not all_cancs_h.empty:
                             all_cancs_h['mm_yyyy'] = pd.to_datetime(all_cancs_h['date']).dt.strftime('%m/%Y')
                             filtered_cancs_h = all_cancs_h[all_cancs_h['mm_yyyy'].isin(involved_months_hist)]
                             
                             for _, cr in filtered_cancs_h.iterrows():
                                 cancellations_hist.append({
                                     'date': cr['date'],
                                     'reason': cr['reason']
                                 })
                 except Exception as e:
                     print(f"Error fetching cancellations for history report: {e}")

            if st_items:
                st_data = {
                    'name': sel_st_name, 
                    'month': f"{start_date.strftime('%d/%m/%y')} - {end_date.strftime('%d/%m/%y')}",
                    'class_name': st_class_name_hist
                }
                pdf_bytes = reports.generate_student_statement(st_data, st_items, cancellations=cancellations_hist)
                
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
