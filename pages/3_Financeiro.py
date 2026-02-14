import streamlit as st
import pandas as pd
import database
import admin_utils
import auth
import audit
from datetime import datetime, date, timedelta
import plotly.express as px
import io
import services.finance_service as finance_service

st.set_page_config(page_title="Gestão Financeira", page_icon="💰", layout="wide")

# Apply Global Styles
import utils.styles as styles
styles.apply_custom_style()

admin_utils.render_sidebar_logo()
conn = database.get_connection()
cursor = conn.cursor()

# Authentication
if not auth.require_login(conn):
    st.stop()

auth.render_custom_sidebar()

# Role check - admin only (Both pages were Admin only or restricted)
# Assuming 'Financeiro' encompasses both.
if not auth.check_page_access('Financeiro'):
    st.stop()

admin_utils.render_header_logo()
st.title("Gestão Financeira")

# --- GLOBAL TABS ---
tab_gestao, tab_relatorios = st.tabs(["📝 Gestão de Despesas", "📊 Relatórios & Fluxo"])

# ==============================================================================
# TAB 1: GESTÃO DE DESPESAS (Former pages/2_Despesas.py)
# ==============================================================================
with tab_gestao:
    # Session for Editing
    if "exp_edit_id" not in st.session_state:
        st.session_state.exp_edit_id = None
    if "fix_edit_id" not in st.session_state:
        st.session_state.fix_edit_id = None

    # Helper to fetch suppliers
    suppliers = pd.read_sql("SELECT id, name FROM suppliers", conn)
    sup_map = {row['name']: row['id'] for _, row in suppliers.iterrows()}
    sup_options = [""] + list(sup_map.keys())

    # Fetch Categories via Service
    expense_categories = finance_service.get_expense_categories(conn)
    periodicities = ["Mensal", "Anual", "Semanal", "Trimestral"]

    # Ensure critical categories exist in list even if DB is empty (fallback)
    if "Compra de Insumo" not in expense_categories: expense_categories.append("Compra de Insumo")

    # --- DASHBOARD SUMMARY ---
    st.subheader("Resumo Mensal")

    # Month Selection approach
    col_m, col_y = st.columns([1, 1])
    with col_m:
        sel_month = st.selectbox("Mês", range(1, 13), index=date.today().month - 1)
    with col_y:
        sel_year = st.number_input("Ano", min_value=2020, max_value=2030, value=date.today().year)

    start_month = date(sel_year, sel_month, 1)
    if sel_month == 12:
        end_month = date(sel_year + 1, 1, 1)
    else:
        end_month = date(sel_year, sel_month + 1, 1)

    # 1. Realized Expenses (Lançamentos)
    filters_realized = {
        'start_date': start_month,
        'end_date': end_month
    }
    df_realized = finance_service.get_expenses(conn, filters_realized)
    if not df_realized.empty:
        df_realized['type'] = 'Realizado'

    # 2. Fixed Costs (Definitions)
    df_fixed_def = finance_service.get_fixed_costs(conn)
    df_fixed_def.rename(columns={'value': 'amount'}, inplace=True)

    # Filter: Exclude definitions if already present in realized (by description)
    # This prevents double counting if the month was already consolidated
    realized_descs = set(df_realized['description'].tolist()) if not df_realized.empty else set()
    df_fixed_pending = df_fixed_def[~df_fixed_def['description'].isin(realized_descs)].copy()
    df_fixed_pending['type'] = 'Fixo (Previsto)'

    # Combined Data
    to_concat = []
    if not df_realized.empty: to_concat.append(df_realized[['category', 'amount']])
    if not df_fixed_pending.empty: to_concat.append(df_fixed_pending[['category', 'amount']])
    
    df_final_chart = pd.concat(to_concat, ignore_index=True) if to_concat else pd.DataFrame()

    col_d1, col_d2 = st.columns(2)

    with col_d1:
        st.write(f"**Gastos por Categoria ({sel_month}/{sel_year})**")
        
        if not df_final_chart.empty:
            total_period = df_final_chart['amount'].sum()
            
            # Breakdown
            tot_real = df_realized['amount'].sum() if not df_realized.empty else 0.0
            tot_fix_pending = df_fixed_pending['amount'].sum() if not df_fixed_pending.empty else 0.0
            
            st.metric("Total Geral (Realizado + Pendente)", f"R$ {total_period:.2f}", 
                     help=f"Realizado: R$ {tot_real:.2f} | Fixo Pendente: R$ {tot_fix_pending:.2f}")
            
            # Chart with Colors
            chart_data = df_final_chart.groupby('category')['amount'].sum().reset_index()
            st.bar_chart(chart_data, x="category", y="amount", color="category")
        else:
            st.info("Sem dados.")

    with col_d2:
        st.write("**Evolução dos Lançamentos (Últimos 12 meses)**")
        st.caption("*Considera apenas despesas lançadas/pagas")
        
        # We can implement a specific history summary in service later, 
        # for now let's reuse get_expenses generally or use direct SQL for just this chart optimization?
        # Let's use get_expenses for last 12 months.
        last_year_start = date.today() - timedelta(days=365)
        df_hist_chart = finance_service.get_expenses(conn, {'start_date': last_year_start, 'end_date': date.today()})
        
        if not df_hist_chart.empty:
            df_hist_chart['date'] = pd.to_datetime(df_hist_chart['date'])
            df_hist_chart['month'] = df_hist_chart['date'].dt.strftime('%Y-%m')
            chart_bar = df_hist_chart.groupby('month')['amount'].sum().reset_index().sort_values('month').tail(12)
            
            total_hist = chart_bar['amount'].sum()
            st.metric("Total Lançado (12 Meses)", f"R$ {total_hist:.2f}")
            
            st.bar_chart(chart_bar, x="month", y="amount", color="month")
        else:
            st.info("Sem histórico de lançamentos.")

    st.divider()

    # --- CATEGORY MANAGEMENT ---
    with st.expander("⚙️ Gerenciar Categorias de Despesas"):
        c_cat1, c_cat2 = st.columns([1, 2])
        with c_cat1:
            new_cat = st.text_input("Nova Categoria")
            if st.button("Adicionar Categoria"):
                if new_cat:
                    try:
                        finance_service.create_expense_category(conn, new_cat)
                        admin_utils.show_feedback_dialog(f"Categoria '{new_cat}' adicionada!", level="success")
                        st.rerun()
                    except Exception:
                        admin_utils.show_feedback_dialog("Categoria já existe.", level="error")
        with c_cat2:
            st.write("Categorias Existentes:")
            for cat in expense_categories:
                cc1, cc2 = st.columns([4, 1])
                cc1.text(cat)
                if cc2.button("🗑️", key=f"del_cat_{cat}"):
                    def do_del_cat(name=cat):
                        with database.db_session() as ctx_conn:
                            finance_service.delete_expense_category(ctx_conn, name)
                        st.rerun()
                    
                    admin_utils.show_confirmation_dialog(
                        f"Deseja excluir a categoria de despesa '{cat}'?",
                        on_confirm=do_del_cat
                    )

    st.divider()

    # Nested Tabs for Expenses
    subtab1, subtab2 = st.tabs(["🛒 Despesas eventuais", "📌 Despesas recorrentes"])

    # ==========================================
    # SUBTAB 1: Despesas
    # ==========================================
    # ==========================================
    # SUBTAB 1: Despesas
    # ==========================================
    with subtab1:
        c_new, c_list = st.columns([1, 2])
        
        with c_new:
            is_edit = st.session_state.exp_edit_id is not None
            t_title = "Editar Despesa" if is_edit else "Lançar Nova Despesa"
            st.subheader(t_title)
            
            # Load Defaults
            idx_cat = 0
            idx_sup = 0
            def_date = date.today()
            def_desc = ""
            def_val = 0.0
            
            if is_edit:
                target_data = finance_service.get_expense_by_id(conn, st.session_state.exp_edit_id)
                if target_data:
                    def_date = datetime.strptime(target_data['date'], '%Y-%m-%d').date()
                    def_desc = target_data['description']
                    def_val = float(target_data['amount'])
                    if target_data['category'] in expense_categories:
                        idx_cat = expense_categories.index(target_data['category'])
                    if target_data['supplier_id']:
                        s_name = next((k for k, v in sup_map.items() if v == target_data['supplier_id']), None)
                        if s_name in sup_options: idx_sup = sup_options.index(s_name)
                else:
                    st.session_state.exp_edit_id = None
                    st.rerun()
                    
            if is_edit and st.button("⬅️ Cancelar", key="can_exp"):
                st.session_state.exp_edit_id = None
                st.rerun()
                
            with st.form("exp_form"):
                e_date = st.date_input("Data", def_date, format="DD/MM/YYYY")
                e_desc = st.text_input("Descrição", def_desc)
                e_val = st.number_input("Valor (R$)", min_value=0.0, step=0.01, value=def_val)
                e_cat = st.selectbox("Categoria", expense_categories, index=idx_cat)
                e_sup = st.selectbox("Fornecedor", sup_options, index=idx_sup)
                
                # Stock Logic Only on New
                material_to_stock = None
                qty_bought = 0.0
                if not is_edit and e_cat == "Compra de Insumo":
                    st.info("Adicionar ao estoque?")
                    materials = pd.read_sql("SELECT id, name, unit FROM materials WHERE type != 'Labor'", conn)
                    mat_dict = {f"{row['name']} ({row['unit']})": row['id'] for _, row in materials.iterrows()}
                    mat_choice = st.selectbox("Insumo", ["(Nenhum)"] + list(mat_dict.keys()))
                    if mat_choice != "(Nenhum)":
                        qty_bought = st.number_input("Qtd.", min_value=0.0, step=0.1)
                        material_to_stock = mat_dict[mat_choice]

                if st.form_submit_button("Salvar Despesa"):
                    sup_id = sup_map[e_sup] if e_sup else None
                    if is_edit:
                        try:
                            old_data = finance_service.update_expense(
                                conn, st.session_state.exp_edit_id, e_date, e_desc, e_val, e_cat, sup_id
                            )
                            audit.log_action(conn, 'UPDATE', 'expenses', st.session_state.exp_edit_id, old_data, 
                                {'date': str(e_date), 'description': e_desc, 'amount': e_val, 'category': e_cat})
                            st.session_state.exp_edit_id = None
                            admin_utils.show_feedback_dialog("Atualizado!", level="success")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar: {e}")
                    else:
                        try:
                            new_id = finance_service.create_expense(
                                conn, e_date, e_desc, e_val, e_cat, sup_id, material_to_stock, qty_bought
                            )
                            audit.log_action(conn, 'CREATE', 'expenses', new_id, None,
                                {'date': str(e_date), 'description': e_desc, 'amount': e_val, 'category': e_cat})
                            admin_utils.show_feedback_dialog("Salvo!", level="success")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao criar: {e}")

        with c_list:
            st.subheader("Histórico")
            
            # Filters
            f1, f2, f3 = st.columns(3)
            fil_cat = f1.selectbox("Filtrar Categoria", ["Todas"] + expense_categories)
            
            # Default to current month
            today = date.today()
            date_def = [today.replace(day=1), today]
            fil_date = f2.date_input("Intervalo", date_def, key="fil_d_exp", format="DD/MM/YYYY")
            
            # Search filter
            search_exp = st.text_input("🔍 Buscar", placeholder="Descrição, fornecedor...", key="search_exp")
            
            filters = {
                'category': fil_cat,
                'search_term': search_exp
            }
            if len(fil_date) == 2:
                filters['start_date'] = fil_date[0]
                filters['end_date'] = fil_date[1]
            
            df_hist = finance_service.get_expenses(conn, filters)
            
            st.caption(f"{len(df_hist)} registro(s) | Total: R$ {df_hist['amount'].sum():.2f}")
            
            if not df_hist.empty:
                for i, row in df_hist.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        
                        with c1:
                            st.markdown(f"**{row['description']}**")
                            # Handle date which might be string or datetime depending on pandas version/sqlite
                            d_str = row['date']
                            if isinstance(d_str, (pd.Timestamp, datetime)):
                                d_str = d_str.strftime('%d/%m/%Y')
                            st.write(f"📅 {d_str} | 📁 {row['category']}")
                            if row['supplier_name']:
                                st.caption(f"🏢 {row['supplier_name']}")
                        
                        with c2:
                            st.metric("Valor", f"R$ {row['amount']:.2f}")
                        
                        with c3:
                            if st.button("✏️", key=f"e_e_{row['id']}", help="Editar"):
                                st.session_state.exp_edit_id = row['id']
                                st.rerun()
                            if st.button("🗑️", key=f"d_e_{row['id']}", help="Excluir"):
                                def do_del_exp(eid=row['id']):
                                    with database.db_session() as ctx_conn:
                                        old_data = finance_service.delete_expense(ctx_conn, eid)
                                        audit.log_action(ctx_conn, 'DELETE', 'expenses', eid, old_data, None)
                                    st.rerun()

                                admin_utils.show_confirmation_dialog(
                                    f"Excluir a despesa '{row['description']}' de R$ {row['amount']:.2f}?",
                                    on_confirm=do_del_exp
                                )
            else:
                st.info("Sem lançamentos.")

    # ==========================================
    # AUTO-CONSOLIDATION LOGIC
    # ==========================================
    # Check if we need to generate fixed costs for THIS month
    added_count = finance_service.auto_process_monthly_fixed_costs(conn)
    if added_count > 0:
        st.toast(f"✅ {added_count} custos fixos do mês foram lançados automaticamente!", icon="🤖")
        st.rerun()

    # ==========================================
    # SUBTAB 2: Gastos Recorrentes
    # ==========================================
    with subtab2:
        st.divider()
        
        fc_new, fc_list = st.columns([1, 2])
        
        with fc_new:
            is_f_edit = st.session_state.fix_edit_id is not None
            f_title = "Editar Despesa Recorrente" if is_f_edit else "Nova despesa recorrente"
            st.subheader(f_title)
            
            fd_desc = ""
            fd_val = 0.0
            fd_day = 5
            fd_per_idx = 0
            fd_cat_idx = 0
            
            if is_f_edit:
                frow = finance_service.get_fixed_cost_by_id(conn, st.session_state.fix_edit_id)
                if frow:
                    fd_desc = frow['description']
                    fd_val = float(frow['value'])
                    fd_day = int(frow['due_day']) if frow['due_day'] else 5
                    if frow['periodicity'] in periodicities: fd_per_idx = periodicities.index(frow['periodicity'])
                    if frow['category'] in expense_categories: fd_cat_idx = expense_categories.index(frow['category'])
                else:
                    st.session_state.fix_edit_id = None
                    st.rerun()
            
            if is_f_edit and st.button("⬅️ Cancelar", key="can_fix"):
                st.session_state.fix_edit_id = None
                st.rerun()

            with st.form("fix_form"):
                f_desc = st.text_input("Descrição (Ex: Aluguel)", fd_desc)
                f_val = st.number_input("Valor Estimado (R$)", min_value=0.0, step=0.1, value=fd_val)
                f_day = st.number_input("Dia Vencimento", min_value=1, max_value=31, value=fd_day)
                f_per = st.selectbox("Periodicidade", periodicities, index=fd_per_idx)
                f_cat = st.selectbox("Categoria", expense_categories, index=fd_cat_idx)
                
                if st.form_submit_button("Salvar Definição"):
                    if is_f_edit:
                        try:
                            old_data = finance_service.update_fixed_cost(
                                conn, st.session_state.fix_edit_id, f_desc, f_val, f_day, f_per, f_cat
                            )
                            audit.log_action(conn, 'UPDATE', 'fixed_costs', st.session_state.fix_edit_id, old_data,
                                {'description': f_desc, 'value': f_val, 'due_day': f_day, 'category': f_cat})
                            st.session_state.fix_edit_id = None
                            admin_utils.show_feedback_dialog("Atualizado!", level="success")
                            st.rerun()
                        except Exception as e:
                             st.error(f"Erro ao atualizar: {e}")
                    else:
                        try:
                            new_id = finance_service.create_fixed_cost(
                                conn, f_desc, f_val, f_day, f_per, f_cat
                            )
                            audit.log_action(conn, 'CREATE', 'fixed_costs', new_id, None,
                                {'description': f_desc, 'value': f_val, 'due_day': f_day, 'category': f_cat})
                            admin_utils.show_feedback_dialog("Criado!", level="success")
                            st.rerun()
                        except Exception:
                            admin_utils.show_feedback_dialog("Erro: Descrição deve ser única.", level="error")
                    
        with fc_list:
            st.subheader("Despesas recorrentes cadastradas")
            
            ff1, ff2 = st.columns(2)
            fil_f_cat = ff1.selectbox("Filtrar Categoria", ["Todas"] + expense_categories, key="fil_f_cat")
            fil_f_per = ff2.selectbox("Filtrar Periodicidade", ["Todas", "Mensal", "Anual", "Semanal", "Trimestral"], key="fil_f_per")
            
            filters_fc = {
                'category': fil_f_cat,
                'periodicity': fil_f_per
            }
            
            df_fix = finance_service.get_fixed_costs(conn, filters_fc)
            
            if not df_fix.empty:
                st.metric("Total Estimado (Mensal)", f"R$ {df_fix['value'].sum():.2f}")
                for i, row in df_fix.iterrows():
                    with st.expander(f"Dia {row['due_day']} | {row['description']} | R$ {row['value']:.2f}"):
                        st.write(f"**Categoria:** {row['category']} | **Freq:** {row['periodicity']}")
                        fc_ed, fc_del = st.columns(2)
                        if fc_ed.button("✏️ Editar", key=f"e_f_{row['id']}"):
                            st.session_state.fix_edit_id = row['id']
                            st.rerun()
                        if fc_del.button("🗑️ Excluir", key=f"d_f_{row['id']}"):
                            def do_del_fix(fid=row['id']):
                                with database.db_session() as ctx_conn:
                                    old_data = finance_service.delete_fixed_cost(ctx_conn, fid)
                                    audit.log_action(ctx_conn, 'DELETE', 'fixed_costs', fid, old_data, None)
                                st.rerun()

                            admin_utils.show_confirmation_dialog(
                                f"Excluir a definição de custo fixo: '{row['description']}'?",
                                on_confirm=do_del_fix
                            )
            else:
                st.info("Nenhum custo fixo definido.")

# ==============================================================================
# TAB 2: RELATÓRIOS & FLUXO (Former pages/3_Financeiro.py)
# ==============================================================================
with tab_relatorios:
    # --- SIDEBAR FILTERS (Moved to Main Area or Top of Tab, because Sidebar is Global) ---
    # Since we are in a tab, putting filters in sidebar is confusing if they only apply to this tab.
    # But Streamlit sidebar is shared. 
    # Let's put them in an expander or top section of the tab.
    
    st.subheader("📅 Filtros do Relatório")
    
    col_fil1, col_fil2 = st.columns([1, 2])
    
    with col_fil1:
        quick_period = st.radio("Período Rápido", 
                                ["Mês Atual", "Mês Anterior", "Último Trimestre", "Ano Atual", "Personalizado"],
                                index=0, horizontal=True)
    
    today = date.today()
    start_date = today.replace(day=1)
    end_date = today

    if quick_period == "Mês Atual":
        start_date = today.replace(day=1)
        end_date = today
    elif quick_period == "Mês Anterior":
        first_this_month = today.replace(day=1)
        end_date = first_this_month - timedelta(days=1)
        start_date = end_date.replace(day=1)
    elif quick_period == "Último Trimestre":
        start_date = today - timedelta(days=90)
        end_date = today
    elif quick_period == "Ano Atual":
        start_date = today.replace(month=1, day=1)
        end_date = today
    else:  # Personalizado
        with col_fil2:
            c_d1, c_d2 = st.columns(2)
            start_date = c_d1.date_input("Data Início", today.replace(day=1), format="DD/MM/YYYY")
            end_date = c_d2.date_input("Data Fim", today, format="DD/MM/YYYY")
    
    st.caption(f"Exibindo dados de **{start_date.strftime('%d/%m/%Y')}** até **{end_date.strftime('%d/%m/%Y')}**")
    st.divider()

    # --- DETAILED DATA QUERIES (Used for Excel & Details) ---
    # Use centralized finance_service for all data
    fin_data = finance_service.get_financial_summary(conn, start_date, end_date)
    
    # Extract DataFrames from service result
    sales_df = fin_data['revenue_details']
    expenses_df = fin_data['expense_details']
    
    # Metrics
    gross_revenue = fin_data['gross_revenue']
    total_expenses = fin_data['total_expenses']
    net_profit = fin_data['net_profit']
    total_discounts = fin_data['total_discounts']
    
    # NOTE: The service returns 'revenue_details' and 'expense_details'. 
    # The original code expected 'sales_df' and 'expenses_df' with specific columns.
    # The service ensures these columns exist.
    
    # --- MAIN METRICS ---
    st.subheader("📊 Resumo do Período")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💵 Faturamento Bruto", f"R$ {gross_revenue:,.2f}", 
              help="Vendas + Sinais de Encomenda + Mensalidades + Extras (Pagos)")
    c2.metric("📤 Despesas", f"R$ {total_expenses:,.2f}")
    c3.metric("📉 Descontos Concedidos", f"R$ {total_discounts:,.2f}")
    c4.metric("💰 Lucro Líquido", f"R$ {net_profit:,.2f}", 
              delta=f"R$ {net_profit:,.2f}", delta_color="normal" if net_profit >= 0 else "inverse")

    st.divider()

    # --- EXCEL EXPORT ---
    exp_col1, exp_col2, exp_col3 = st.columns(3)

    with exp_col1:
        if not sales_df.empty:
            output_sales = io.BytesIO()
            # Drop the 'source' column added by service if not needed for specific export
            # but it is fine to keep.
            sales_df.to_excel(output_sales, index=False, engine='openpyxl')
            st.download_button(
                "📥 Exportar Vendas (Excel)",
                output_sales.getvalue(),
                file_name=f"vendas_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with exp_col2:
        if not expenses_df.empty:
            output_exp = io.BytesIO()
            expenses_df.to_excel(output_exp, index=False, engine='openpyxl')
            st.download_button(
                "📥 Exportar Despesas (Excel)",
                output_exp.getvalue(),
                file_name=f"despesas_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with exp_col3:
        # Combined Report
        if not sales_df.empty or not expenses_df.empty:
            output_all = io.BytesIO()
            with pd.ExcelWriter(output_all, engine='openpyxl') as writer:
                if not sales_df.empty:
                    sales_df.to_excel(writer, sheet_name='Receitas_Unificadas', index=False)
                if not expenses_df.empty:
                    expenses_df.to_excel(writer, sheet_name='Despesas', index=False)
                # Keep original sales/orders sheets if they have data for backward compatibility or detail
                if not sales_df.empty:
                    sales_df.to_excel(writer, sheet_name='Vendas_Detalhe', index=False)
            st.download_button(
                "📥 Relatório Completo (Excel)",
                output_all.getvalue(),
                file_name=f"relatorio_financeiro_unificado_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    st.divider()

    # --- TABS FOR DETAILS ---
    subtab_sales, subtab_expenses, subtab_charts = st.tabs(["📈 Detalhe Vendas", "📉 Detalhe Despesas", "📊 Gráficos Avançados"])

    # ======================
    # SUBTAB: VENDAS (Details from Sales Table)
    # ======================
    with subtab_sales:
        if not sales_df.empty:
            # Filters
            f1, f2, f3 = st.columns(3)
            
            payment_opts = ["Todos"] + sales_df['payment_method'].dropna().unique().tolist()
            sel_payment = f1.selectbox("Forma de Pagamento", payment_opts)
            
            seller_opts = ["Todos"] + sales_df['salesperson'].dropna().unique().tolist()
            sel_seller = f2.selectbox("Vendedora", seller_opts)
            
            cat_opts = ["Todos"] + sales_df['product_category'].dropna().unique().tolist()
            sel_cat = f3.selectbox("Categoria do Produto", cat_opts)
            
            # Apply Filters
            filtered_sales = sales_df.copy()
            if sel_payment != "Todos":
                filtered_sales = filtered_sales[filtered_sales['payment_method'] == sel_payment]
            if sel_seller != "Todos":
                filtered_sales = filtered_sales[filtered_sales['salesperson'] == sel_seller]
            if sel_cat != "Todos":
                filtered_sales = filtered_sales[filtered_sales['product_category'] == sel_cat]
            
            # Summary
            st.metric("Total Filtrado", f"R$ {filtered_sales['total_price'].sum():,.2f}")
            
            # Table
            st.dataframe(
                filtered_sales[['date', 'product_name', 'client_name', 'total_price', 'discount', 'payment_method', 'salesperson']],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "product_name": "Produto",
                    "client_name": "Cliente",
                    "total_price": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                    "discount": st.column_config.NumberColumn("Desconto", format="R$ %.2f"),
                    "payment_method": "Pagamento",
                    "salesperson": "Vendedora"
                }
            )
            
            # Breakdown by Payment Method
            st.subheader("Por Forma de Pagamento")
            pay_breakdown = filtered_sales.groupby('payment_method')['total_price'].sum().reset_index()
            st.bar_chart(pay_breakdown, x='payment_method', y='total_price', color='payment_method')
            
            # Breakdown by Salesperson
            st.subheader("Por Vendedora")
            seller_breakdown = filtered_sales.groupby('salesperson')['total_price'].sum().reset_index()
            st.bar_chart(seller_breakdown, x='salesperson', y='total_price', color='salesperson')
            
        else:
            st.info("Nenhuma venda registrada no período.")

    # ======================
    # SUBTAB: DESPESAS
    # ======================
    with subtab_expenses:
        # Actually, let's just use the detailed query here for the subtab to keep supplier name.
        if not expenses_df.empty:
            # Filters
            e1, e2 = st.columns(2)
            
            exp_cat_opts = ["Todos"] + expenses_df['category'].dropna().unique().tolist()
            sel_exp_cat = e1.selectbox("Categoria", exp_cat_opts)
            
            sup_opts = ["Todos"] + expenses_df['supplier_name'].dropna().unique().tolist()
            sel_sup = e2.selectbox("Fornecedor", sup_opts)
            
            # Apply Filters
            filtered_expenses = expenses_df.copy()
            if sel_exp_cat != "Todos":
                filtered_expenses = filtered_expenses[filtered_expenses['category'] == sel_exp_cat]
            if sel_sup != "Todos":
                filtered_expenses = filtered_expenses[filtered_expenses['supplier_name'] == sel_sup]
            
            # Summary
            st.metric("Total Filtrado", f"R$ {filtered_expenses['amount'].sum():,.2f}")
            
            # Table
            st.dataframe(
                filtered_expenses[['date', 'description', 'amount', 'category', 'supplier_name']],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "date": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "description": "Descrição",
                    "amount": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                    "category": "Categoria",
                    "supplier_name": "Fornecedor"
                }
            )
            
            # Breakdown by Category
            st.subheader("Por Categoria")
            cat_breakdown = filtered_expenses.groupby('category')['amount'].sum().reset_index()
            st.bar_chart(cat_breakdown, x='category', y='amount', color='category')
            
        else:
            st.info("Nenhuma despesa registrada no período.")

    # ======================
    # SUBTAB: GRÁFICOS
    # ======================
    # ======================
    # SUBTAB: GRÁFICOS
    # ======================
    with subtab_charts:
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.markdown("### Receita vs Despesa")
            
            summary_data = pd.DataFrame({
                'Tipo': ['Receita', 'Despesas'],
                'Valor': [gross_revenue, total_expenses]
            })
            
            fig_pie = px.pie(summary_data, values='Valor', names='Tipo', 
                             color_discrete_sequence=['#2ecc71', '#e74c3c'],
                             hole=0.4)
            fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with chart_col2:
            st.markdown("### Evolução Diária")
            
            # Use sales_df and expenses_df from service
            if not sales_df.empty:
                daily_sales = sales_df.groupby(sales_df['date'].dt.date)['amount'].sum().reset_index()
                daily_sales.columns = ['Data', 'Receita']
            else:
                daily_sales = pd.DataFrame({'Data': [], 'Receita': []})
            
            if not expenses_df.empty:
                daily_expenses = expenses_df.groupby(expenses_df['date'].dt.date)['amount'].sum().reset_index()
                daily_expenses.columns = ['Data', 'Despesas']
            else:
                daily_expenses = pd.DataFrame({'Data': [], 'Despesas': []})
            
            # Merge
            if not daily_sales.empty or not daily_expenses.empty:
                daily_all = pd.merge(daily_sales, daily_expenses, on='Data', how='outer').fillna(0)
                daily_all = daily_all.sort_values('Data')
                
                fig_line = px.line(daily_all, x='Data', y=['Receita', 'Despesas'],
                                   labels={'value': 'Valor (R$)', 'variable': 'Tipo'},
                                   color_discrete_sequence=['#2ecc71', '#e74c3c'])
                fig_line.update_layout(margin=dict(t=20, b=0, l=0, r=0))
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.info("Sem dados para o gráfico de evolução.")
        
        # Monthly Trend (if enough data)
        st.markdown("### Tendência Mensal")
        
        if not sales_df.empty or not expenses_df.empty:
            # Monthly Trend
            # Need to copy to avoid SettingWithCopy if slice
            rev_c = sales_df.copy() if not sales_df.empty else pd.DataFrame(columns=['date', 'amount'])
            exp_c = expenses_df.copy() if not expenses_df.empty else pd.DataFrame(columns=['date', 'amount'])
            
            if not rev_c.empty:
                rev_c['month'] = rev_c['date'].dt.to_period('M').astype(str)
                monthly_sales = rev_c.groupby('month')['amount'].sum().reset_index()
                monthly_sales.columns = ['Mês', 'Receita']
            else:
                monthly_sales = pd.DataFrame(columns=['Mês', 'Receita'])
            
            if not exp_c.empty:
                exp_c['month'] = exp_c['date'].dt.to_period('M').astype(str)
                monthly_expenses = exp_c.groupby('month')['amount'].sum().reset_index()
                monthly_expenses.columns = ['Mês', 'Despesas']
            else:
                monthly_expenses = pd.DataFrame(columns=['Mês', 'Despesas'])
            
            monthly_all = pd.merge(monthly_sales, monthly_expenses, on='Mês', how='outer').fillna(0)
            monthly_all = monthly_all.sort_values('Mês')
            monthly_all['Lucro'] = monthly_all['Receita'] - monthly_all['Despesas']
            
            fig_bar = px.bar(monthly_all, x='Mês', y=['Receita', 'Despesas', 'Lucro'],
                             barmode='group',
                             color_discrete_sequence=['#2ecc71', '#e74c3c', '#3498db'])
            st.plotly_chart(fig_bar, use_container_width=True)
            
            # Additional Breakdown: Revenue by Source
            if 'source' in sales_df.columns:
                 st.markdown("### Composição do Faturamento")
                 source_breakdown = sales_df.groupby('source')['amount'].sum().reset_index()
                 fig_source = px.bar(source_breakdown, x='source', y='amount', color='source',
                                     labels={'amount': 'Total (R$)', 'source': 'Origem'})
                 st.plotly_chart(fig_source, use_container_width=True)
        else:
            st.info("Sem dados para a tendência mensal.")

conn.close()
