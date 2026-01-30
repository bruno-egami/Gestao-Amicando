import streamlit as st
import pandas as pd
import database
import admin_utils
from datetime import datetime, date

st.set_page_config(page_title="Despesas", page_icon="💸", layout="wide")

admin_utils.render_sidebar_logo()

if not admin_utils.check_password():
    st.stop()

st.title("Gestão de Despesas")

conn = database.get_connection()
cursor = conn.cursor()

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
        
        # We can't easily color by category here unless we stack it. Let's keep simple blue or color by month?? 
        # User asked for "Alocar cores diferentes para cada item".
        # Let's pivot to show categories stacked if possible, or just color by month (rainbow).
        # Better: Stacked bar by category for history?
        # Let's try simple colorful bars for now using 'month' as color or just single color.
        # Stacking by category in history is better but more complex query.
        # Let's stick to the current view but add color="month" just to have colors as requested.
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

tab1, tab2 = st.tabs(["🛒 Despesas", "📌 Gastos Recorrentes"])

# ==========================================
# TAB 1: Despesas
# ==========================================
with tab1:
    c_new, c_list = st.columns([1, 2])
    
    # ... (Edit Form Logic stays mostly same) ...
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
                row_edit = pd.read_sql(f"SELECT * FROM expenses WHERE id={st.session_state.exp_edit_id}", conn).iloc[0]
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
                    cursor.execute("UPDATE expenses SET date=?, description=?, amount=?, category=?, supplier_id=? WHERE id=?", (e_date, e_desc, e_val, e_cat, sup_id, st.session_state.exp_edit_id))
                    st.success("Atualizado!")
                    st.session_state.exp_edit_id = None
                else:
                    cursor.execute("INSERT INTO expenses (date, description, amount, category, supplier_id, linked_material_id) VALUES (?, ?, ?, ?, ?, ?)", (e_date, e_desc, e_val, e_cat, sup_id, material_to_stock))
                    if material_to_stock and qty_bought > 0:
                        cursor.execute("UPDATE materials SET stock_level = stock_level + ? WHERE id = ?", (qty_bought, material_to_stock))
                    st.success("Salvo!")
                conn.commit()
                st.rerun()

    with c_list:
        st.subheader("Histórico")
        # ... (keep existing history code)
        
        # Filters (Keep existing)
        f1, f2, f3 = st.columns(3)
        fil_cat = f1.selectbox("Filtrar Categoria", ["Todas"] + expense_categories)
        fil_date = f2.date_input("Intervalo", [], key="fil_d_exp")
        
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
        
        if not df_hist.empty:
            st.metric("Total Filtrado", f"R$ {df_hist['amount'].sum():.2f}")
            for i, row in df_hist.iterrows():
                sup_txt = f" | {row['supplier']}" if row['supplier'] else ""
                with st.expander(f"{row['date']} | {row['description']} | R$ {row['amount']:.2f}{sup_txt}"):
                    st.write(f"**Categoria:** {row['category']}")
                    c_ed, c_del = st.columns(2)
                    if c_ed.button("✏️ Editar", key=f"e_e_{row['id']}"):
                        st.session_state.exp_edit_id = row['id']
                        st.rerun()
                    if c_del.button("🗑️ Excluir", key=f"d_e_{row['id']}"):
                        cursor.execute("DELETE FROM expenses WHERE id=?", (row['id'],))
                        conn.commit()
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

# Get active fixed costs
fcs = pd.read_sql("SELECT * FROM fixed_costs", conn)
if not fcs.empty:
    # Get existing expenses for this month to check dupes
    ex_month = pd.read_sql("""
        SELECT description FROM expenses 
        WHERE date >= ? AND date < ?
    """, conn, params=(start_m_date, end_m_date))
    existing_set = set(ex_month['description'].tolist())
    
    added_count = 0
    import calendar
    
    for _, fc in fcs.iterrows():
        # Check Recurrence Strategy (MVP: Monthly only or handled simply)
        # If duplicated in same month, skip
        if fc['description'] in existing_set:
            continue
            
        # Check Due Date
        try:
            d_day = int(fc['due_day']) if fc['due_day'] else 1
            last_day = calendar.monthrange(curr_y, curr_m)[1]
            eff_day = min(d_day, last_day) # Clamp to month end
            
            due_date_obj = date(curr_y, curr_m, eff_day)
            
            # If today >= due_date, we launch it!
            if today >= due_date_obj:
                cursor.execute("""
                    INSERT INTO expenses (date, description, amount, category)
                    VALUES (?, ?, ?, ?)
                """, (due_date_obj, fc['description'], fc['value'], fc['category']))
                added_count += 1
        except:
            pass # Skip invalid dates
            
    if added_count > 0:
        conn.commit()
        st.toast(f"✅ {added_count} custos fixos do mês foram lançados automaticamente!", icon="🤖")
        st.rerun()

# ==========================================
# TAB 2: Gastos Recorrentes
# ==========================================
with tab2:
    st.divider()
    
    fc_new, fc_list = st.columns([1, 2])
    
    with fc_new:
        is_f_edit = st.session_state.fix_edit_id is not None
        f_title = "Editar Custo Recorrente" if is_f_edit else "Novo Custo Recorrente"
        st.subheader(f_title)
        
        # Defaults
        fd_desc = ""
        fd_val = 0.0
        fd_day = 5
        fd_per_idx = 0
        fd_cat_idx = 0
        
        if is_f_edit:
            try:
                frow = pd.read_sql(f"SELECT * FROM fixed_costs WHERE id={st.session_state.fix_edit_id}", conn).iloc[0]
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
                    cursor.execute("UPDATE fixed_costs SET description=?, value=?, due_day=?, periodicity=?, category=? WHERE id=?", (f_desc, f_val, f_day, f_per, f_cat, st.session_state.fix_edit_id))
                    st.success("Atualizado!")
                    st.session_state.fix_edit_id = None
                else:
                    try:
                        cursor.execute("INSERT INTO fixed_costs (description, value, due_day, periodicity, category) VALUES (?, ?, ?, ?, ?)", (f_desc, f_val, f_day, f_per, f_cat))
                        st.success("Criado!")
                    except:
                        st.error("Erro: Descrição deve ser única.")
                conn.commit()
                st.rerun()
                
    with fc_list:
        st.subheader("Custos Recorrentes Definidos")
        
        # Filters
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
                        cursor.execute("DELETE FROM fixed_costs WHERE id=?", (row['id'],))
                        conn.commit()
                        st.rerun()
        else:
            st.info("Nenhum custo fixo definido.")

conn.close()
