import streamlit as st
import pandas as pd
import database
import admin_utils
import auth
import audit
from datetime import datetime, date, timedelta
import plotly.express as px
import io

st.set_page_config(page_title="Gestão Financeira", page_icon="💰", layout="wide")

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

    # Fetch Categories
    cat_df = pd.read_sql("SELECT name FROM expense_categories ORDER BY name", conn)
    expense_categories = cat_df['name'].tolist()
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
    df_realized = pd.read_sql("""
        SELECT category, amount, date, description FROM expenses 
        WHERE date >= ? AND date < ?
    """, conn, params=(start_month, end_month))
    df_realized['type'] = 'Realizado'

    # 2. Fixed Costs (Definitions)
    df_fixed_def = pd.read_sql("SELECT category, value as amount, description FROM fixed_costs", conn)

    # Filter: Exclude definitions if already present in realized (by description)
    # This prevents double counting if the month was already consolidated
    realized_descs = set(df_realized['description'].tolist())
    df_fixed_pending = df_fixed_def[~df_fixed_def['description'].isin(realized_descs)].copy()
    df_fixed_pending['type'] = 'Fixo (Previsto)'

    # Combined Data
    df_final_chart = pd.concat([df_realized[['category', 'amount']], df_fixed_pending[['category', 'amount']]], ignore_index=True)

    col_d1, col_d2 = st.columns(2)

    with col_d1:
        st.write(f"**Gastos por Categoria ({sel_month}/{sel_year})**")
        
        if not df_final_chart.empty:
            total_period = df_final_chart['amount'].sum()
            
            # Breakdown
            tot_real = df_realized['amount'].sum()
            tot_fix_pending = df_fixed_pending['amount'].sum()
            
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
        
        df_hist_chart = pd.read_sql("SELECT date, amount FROM expenses", conn)
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
                        cursor.execute("INSERT INTO expense_categories (name) VALUES (?)", (new_cat,))
                        conn.commit()
                        st.success(f"Categoria '{new_cat}' adicionada!")
                        st.rerun()
                    except:
                        st.error("Categoria já existe.")
        with c_cat2:
            st.write("Categorias Existentes:")
            for cat in expense_categories:
                cc1, cc2 = st.columns([4, 1])
                cc1.text(cat)
                if cc2.button("🗑️", key=f"del_cat_{cat}"):
                    cursor.execute("DELETE FROM expense_categories WHERE name=?", (cat,))
                    conn.commit()
                    st.rerun()

    st.divider()

    # Nested Tabs for Expenses
    subtab1, subtab2 = st.tabs(["🛒 Despesas eventuais", "📌 Despesas recorrentes"])

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
                try:
                    row_edit = pd.read_sql("SELECT * FROM expenses WHERE id=?", conn, params=(st.session_state.exp_edit_id,)).iloc[0]
                    def_date = datetime.strptime(row_edit['date'], '%Y-%m-%d').date()
                    def_desc = row_edit['description']
                    def_val = float(row_edit['amount'])
                    if row_edit['category'] in expense_categories:
                        idx_cat = expense_categories.index(row_edit['category'])
                    if row_edit['supplier_id']:
                        s_name = next((k for k, v in sup_map.items() if v == row_edit['supplier_id']), None)
                        if s_name in sup_options: idx_sup = sup_options.index(s_name)
                except:
                    st.session_state.exp_edit_id = None
                    st.rerun()
                    
            if is_edit and st.button("⬅️ Cancelar", key="can_exp"):
                st.session_state.exp_edit_id = None
                st.rerun()
                
            with st.form("exp_form"):
                e_date = st.date_input("Data", def_date)
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
                        # Get old data for audit
                        old_exp = pd.read_sql("SELECT date, description, amount, category FROM expenses WHERE id=?", conn, params=(st.session_state.exp_edit_id,))
                        old_data = old_exp.iloc[0].to_dict() if not old_exp.empty else {}
                        
                        cursor.execute("UPDATE expenses SET date=?, description=?, amount=?, category=?, supplier_id=? WHERE id=?", (e_date, e_desc, e_val, e_cat, sup_id, st.session_state.exp_edit_id))
                        conn.commit()
                        audit.log_action(conn, 'UPDATE', 'expenses', st.session_state.exp_edit_id, old_data, 
                            {'date': str(e_date), 'description': e_desc, 'amount': e_val, 'category': e_cat})
                        st.success("Atualizado!")
                        st.session_state.exp_edit_id = None
                    else:
                        cursor.execute("INSERT INTO expenses (date, description, amount, category, supplier_id, linked_material_id) VALUES (?, ?, ?, ?, ?, ?)", (e_date, e_desc, e_val, e_cat, sup_id, material_to_stock))
                        new_id = cursor.lastrowid
                        if material_to_stock and qty_bought > 0:
                            cursor.execute("UPDATE materials SET stock_level = stock_level + ? WHERE id = ?", (qty_bought, material_to_stock))
                        conn.commit()
                        audit.log_action(conn, 'CREATE', 'expenses', new_id, None,
                            {'date': str(e_date), 'description': e_desc, 'amount': e_val, 'category': e_cat})
                        st.success("Salvo!")
                    st.rerun()

        with c_list:
            st.subheader("Histórico")
            
            # Filters
            f1, f2, f3 = st.columns(3)
            fil_cat = f1.selectbox("Filtrar Categoria", ["Todas"] + expense_categories)
            
            # Default to current month
            today = date.today()
            date_def = [today.replace(day=1), today]
            fil_date = f2.date_input("Intervalo", date_def, key="fil_d_exp")
            
            query = """
                SELECT e.id, e.date, e.description, e.amount, e.category, s.name as supplier
                FROM expenses e
                LEFT JOIN suppliers s ON e.supplier_id = s.id
                WHERE 1=1
            """
            params = []
            if fil_cat != "Todas":
                query += " AND e.category = ?"
                params.append(fil_cat)
            if len(fil_date) == 2:
                query += " AND e.date BETWEEN ? AND ?"
                params.append(fil_date[0])
                params.append(fil_date[1])
                
            query += " ORDER BY e.date DESC"
            
            df_hist = pd.read_sql(query, conn, params=params)
            
            # Search filter
            search_exp = st.text_input("🔍 Buscar", placeholder="Descrição, fornecedor...", key="search_exp")
            if search_exp and not df_hist.empty:
                mask = df_hist.apply(lambda row: search_exp.lower() in str(row).lower(), axis=1)
                df_hist = df_hist[mask]
            
            st.caption(f"{len(df_hist)} registro(s) | Total: R$ {df_hist['amount'].sum():.2f}")
            
            if not df_hist.empty:
                for i, row in df_hist.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        
                        with c1:
                            st.markdown(f"**{row['description']}**")
                            st.write(f"📅 {row['date']} | 📁 {row['category']}")
                            if row['supplier']:
                                st.caption(f"🏢 {row['supplier']}")
                        
                        with c2:
                            st.metric("Valor", f"R$ {row['amount']:.2f}")
                        
                        with c3:
                            if st.button("✏️", key=f"e_e_{row['id']}", help="Editar"):
                                st.session_state.exp_edit_id = row['id']
                                st.rerun()
                            if st.button("🗑️", key=f"d_e_{row['id']}", help="Excluir"):
                                old_data = {'description': row['description'], 'amount': row['amount'], 'category': row['category']}
                                cursor.execute("DELETE FROM expenses WHERE id=?", (row['id'],))
                                conn.commit()
                                audit.log_action(conn, 'DELETE', 'expenses', row['id'], old_data, None)
                                st.rerun()
            else:
                st.info("Sem lançamentos.")

    # ==========================================
    # AUTO-CONSOLIDATION LOGIC
    # ==========================================
    # Check if we need to generate fixed costs for THIS month
    today = date.today()
    curr_m = today.month
    curr_y = today.year
    start_m_date = date(curr_y, curr_m, 1)
    if curr_m == 12: end_m_date = date(curr_y + 1, 1, 1)
    else: end_m_date = date(curr_y, curr_m + 1, 1)

    fcs = pd.read_sql("SELECT * FROM fixed_costs", conn)
    if not fcs.empty:
        ex_month = pd.read_sql("""
            SELECT description FROM expenses 
            WHERE date >= ? AND date < ?
        """, conn, params=(start_m_date, end_m_date))
        existing_set = set(ex_month['description'].tolist())
        
        added_count = 0
        import calendar
        
        for _, fc in fcs.iterrows():
            if fc['description'] in existing_set:
                continue
                
            try:
                d_day = int(fc['due_day']) if fc['due_day'] else 1
                last_day = calendar.monthrange(curr_y, curr_m)[1]
                eff_day = min(d_day, last_day) 
                due_date_obj = date(curr_y, curr_m, eff_day)
                
                if today >= due_date_obj:
                    cursor.execute("""
                        INSERT INTO expenses (date, description, amount, category)
                        VALUES (?, ?, ?, ?)
                    """, (due_date_obj, fc['description'], fc['value'], fc['category']))
                    added_count += 1
            except:
                pass 
                
        if added_count > 0:
            conn.commit()
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
                try:
                    frow = pd.read_sql("SELECT * FROM fixed_costs WHERE id=?", conn, params=(st.session_state.fix_edit_id,)).iloc[0]
                    fd_desc = frow['description']
                    fd_val = float(frow['value'])
                    fd_day = int(frow['due_day']) if frow['due_day'] else 5
                    if frow['periodicity'] in periodicities: fd_per_idx = periodicities.index(frow['periodicity'])
                    if frow['category'] in expense_categories: fd_cat_idx = expense_categories.index(frow['category'])
                except:
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
                        old_fc = pd.read_sql("SELECT description, value, due_day, category FROM fixed_costs WHERE id=?", conn, params=(st.session_state.fix_edit_id,))
                        old_data = old_fc.iloc[0].to_dict() if not old_fc.empty else {}
                        cursor.execute("UPDATE fixed_costs SET description=?, value=?, due_day=?, periodicity=?, category=? WHERE id=?", (f_desc, f_val, f_day, f_per, f_cat, st.session_state.fix_edit_id))
                        conn.commit()
                        audit.log_action(conn, 'UPDATE', 'fixed_costs', st.session_state.fix_edit_id, old_data,
                            {'description': f_desc, 'value': f_val, 'due_day': f_day, 'category': f_cat})
                        st.success("Atualizado!")
                        st.session_state.fix_edit_id = None
                    else:
                        try:
                            cursor.execute("INSERT INTO fixed_costs (description, value, due_day, periodicity, category) VALUES (?, ?, ?, ?, ?)", (f_desc, f_val, f_day, f_per, f_cat))
                            new_id = cursor.lastrowid
                            conn.commit()
                            audit.log_action(conn, 'CREATE', 'fixed_costs', new_id, None,
                                {'description': f_desc, 'value': f_val, 'due_day': f_day, 'category': f_cat})
                            st.success("Criado!")
                        except:
                            st.error("Erro: Descrição deve ser única.")
                    st.rerun()
                    
        with fc_list:
            st.subheader("Despesas recorrentes cadastradas")
            
            ff1, ff2 = st.columns(2)
            fil_f_cat = ff1.selectbox("Filtrar Categoria", ["Todas"] + expense_categories, key="fil_f_cat")
            fil_f_per = ff2.selectbox("Filtrar Periodicidade", ["Todas", "Mensal", "Anual", "Semanal", "Trimestral"], key="fil_f_per")
            
            q_fix = "SELECT * FROM fixed_costs WHERE 1=1"
            p_fix = []
            
            if fil_f_cat != "Todas":
                q_fix += " AND category = ?"
                p_fix.append(fil_f_cat)
            
            if fil_f_per != "Todas":
                q_fix += " AND periodicity = ?"
                p_fix.append(fil_f_per)
                
            q_fix += " ORDER BY due_day"
            
            df_fix = pd.read_sql(q_fix, conn, params=p_fix)
            
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
                            old_data = {'description': row['description'], 'value': row['value'], 'category': row['category']}
                            cursor.execute("DELETE FROM fixed_costs WHERE id=?", (row['id'],))
                            conn.commit()
                            audit.log_action(conn, 'DELETE', 'fixed_costs', row['id'], old_data, None)
                            st.rerun()
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
            start_date = c_d1.date_input("Data Início", today.replace(day=1))
            end_date = c_d2.date_input("Data Fim", today)
    
    st.caption(f"Exibindo dados de **{start_date.strftime('%d/%m/%Y')}** até **{end_date.strftime('%d/%m/%Y')}**")
    st.divider()

    # --- DATA QUERIES ---
    # Sales
    sales_df = pd.read_sql("""
        SELECT s.id, s.date, s.total_price, s.discount, s.payment_method, s.salesperson,
               p.name as product_name, p.category as product_category, c.name as client_name
        FROM sales s
        JOIN products p ON s.product_id = p.id
        LEFT JOIN clients c ON s.client_id = c.id
        WHERE s.date BETWEEN ? AND ?
    """, conn, params=(start_date, end_date))

    # Expenses
    expenses_df = pd.read_sql("""
        SELECT e.id, e.date, e.description, e.amount, e.category, s.name as supplier_name
        FROM expenses e
        LEFT JOIN suppliers s ON e.supplier_id = s.id
        WHERE e.date BETWEEN ? AND ?
    """, conn, params=(start_date, end_date))

    # Commission Orders (Deposits)
    orders_df = pd.read_sql("""
        SELECT co.id, co.date_created, co.deposit_amount, co.total_price, co.status, c.name as client_name
        FROM commission_orders co
        LEFT JOIN clients c ON co.client_id = c.id
        WHERE co.date_created BETWEEN ? AND ?
    """, conn, params=(start_date, end_date))

    # --- CALCULATIONS ---
    total_sales = sales_df['total_price'].sum() if not sales_df.empty else 0.0
    total_discounts = sales_df['discount'].sum() if not sales_df.empty else 0.0
    total_expenses = expenses_df['amount'].sum() if not expenses_df.empty else 0.0
    total_deposits = orders_df['deposit_amount'].sum() if not orders_df.empty else 0.0

    gross_revenue = total_sales + total_deposits
    net_profit = gross_revenue - total_expenses

    # --- MAIN METRICS ---
    st.subheader("📊 Resumo do Período")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💵 Faturamento Bruto", f"R$ {gross_revenue:,.2f}", 
              help="Vendas finalizadas + Sinais de encomendas")
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
                    sales_df.to_excel(writer, sheet_name='Vendas', index=False)
                if not expenses_df.empty:
                    expenses_df.to_excel(writer, sheet_name='Despesas', index=False)
                if not orders_df.empty:
                    orders_df.to_excel(writer, sheet_name='Encomendas', index=False)
            st.download_button(
                "📥 Relatório Completo (Excel)",
                output_all.getvalue(),
                file_name=f"relatorio_financeiro_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    st.divider()

    # --- TABS FOR DETAILS ---
    subtab_sales, subtab_expenses, subtab_charts = st.tabs(["📈 Detalhe Vendas", "📉 Detalhe Despesas", "📊 Gráficos Avançados"])

    # ======================
    # SUBTAB: VENDAS
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
            
            if not sales_df.empty:
                sales_df['date'] = pd.to_datetime(sales_df['date'])
                daily_sales = sales_df.groupby(sales_df['date'].dt.date)['total_price'].sum().reset_index()
                daily_sales.columns = ['Data', 'Vendas']
            else:
                daily_sales = pd.DataFrame({'Data': [], 'Vendas': []})
            
            if not expenses_df.empty:
                expenses_df['date'] = pd.to_datetime(expenses_df['date'])
                daily_expenses = expenses_df.groupby(expenses_df['date'].dt.date)['amount'].sum().reset_index()
                daily_expenses.columns = ['Data', 'Despesas']
            else:
                daily_expenses = pd.DataFrame({'Data': [], 'Despesas': []})
            
            # Merge
            if not daily_sales.empty or not daily_expenses.empty:
                daily_all = pd.merge(daily_sales, daily_expenses, on='Data', how='outer').fillna(0)
                daily_all = daily_all.sort_values('Data')
                
                fig_line = px.line(daily_all, x='Data', y=['Vendas', 'Despesas'],
                                   labels={'value': 'Valor (R$)', 'variable': 'Tipo'},
                                   color_discrete_sequence=['#2ecc71', '#e74c3c'])
                fig_line.update_layout(margin=dict(t=20, b=0, l=0, r=0))
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.info("Sem dados para o gráfico de evolução.")
        
        # Monthly Trend (if enough data)
        st.markdown("### Tendência Mensal")
        
        # Sales Monthly
        if not sales_df.empty:
            sales_df['month'] = sales_df['date'].dt.to_period('M').astype(str)
            monthly_sales = sales_df.groupby('month')['total_price'].sum().reset_index()
            monthly_sales.columns = ['Mês', 'Vendas']
        else:
            monthly_sales = pd.DataFrame({'Mês': [], 'Vendas': []})
        
        # Expenses Monthly
        if not expenses_df.empty:
            expenses_df['month'] = expenses_df['date'].dt.to_period('M').astype(str)
            monthly_expenses = expenses_df.groupby('month')['amount'].sum().reset_index()
            monthly_expenses.columns = ['Mês', 'Despesas']
        else:
            monthly_expenses = pd.DataFrame({'Mês': [], 'Despesas': []})
        
        if not monthly_sales.empty or not monthly_expenses.empty:
            monthly_all = pd.merge(monthly_sales, monthly_expenses, on='Mês', how='outer').fillna(0)
            monthly_all = monthly_all.sort_values('Mês')
            monthly_all['Lucro'] = monthly_all['Vendas'] - monthly_all['Despesas']
            
            fig_bar = px.bar(monthly_all, x='Mês', y=['Vendas', 'Despesas', 'Lucro'],
                             barmode='group',
                             color_discrete_sequence=['#2ecc71', '#e74c3c', '#3498db'])
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Sem dados para a tendência mensal.")

conn.close()
