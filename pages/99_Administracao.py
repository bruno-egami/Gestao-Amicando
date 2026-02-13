import streamlit as st
import pandas as pd
import database
import admin_utils
import auth
import audit
import json
import os
import io

from datetime import datetime
import utils.backup_utils as backup_utils


st.set_page_config(page_title="Administração", page_icon="⚙️", layout="wide")

# Apply Global Styles
import utils.styles as styles
styles.apply_custom_style()

conn = database.get_connection()

# Ensure default admin exists
auth.create_default_admin(conn)

# Authentication & Authorization
if not auth.require_login(conn):
    st.stop()

if not auth.check_page_access('Administracao'):
    st.stop()

auth.render_custom_sidebar()
# Sidebar is already rendered above

admin_utils.render_header_logo()
st.title("⚙️ Administração")

# Create Tabs
tab_users, tab_audit, tab_db, tab_import, tab_export = st.tabs(["👥 Usuários", "📜 Auditoria", "💾 Banco de Dados", "📥 Importação", "📤 Exportação"])

# ==============================================================================
# TAB 4: IMPORT (Bulk Data Entry)
# ==============================================================================
with tab_import:
    st.header("📥 Importação de Dados em Massa")
    st.write("Utilize esta ferramenta para carregar dados de planilhas Excel.")
    
    # Select Import Type
    import_type = st.selectbox("O que você deseja importar?", ["Selecione...", "Insumos (Matérias-Primas)", "Produtos", "Vendas", "Despesas", "Fornecedores", "Clientes"])
    
    if import_type != "Selecione...":
        st.divider()
        
        # --- TEMPLATE DEFINITIONS ---
        # Define schemas
        schemas = {
            "Insumos (Matérias-Primas)": {
                "cols": ["Nome", "Preço", "Unidade", "Estoque", "Tipo", "Categoria", "Fornecedor"], 
                "example": [
                    ["Argila Branca", 15.50, "kg", 100, "Material", "Massas", "Fornecedor A"],
                    ["Esmalte Azul", 45.00, "L", 5, "Material", "Esmaltes", "Fornecedor B"]
                ],
                "table": "materials"
            },
            "Produtos": {
                "cols": ["Nome", "Preço Base", "Estoque", "Categoria", "Peso (g)"],
                "example": [
                    ["Caneca Café", 45.00, 10, "Utilitário", 350],
                    ["Vaso Decorativo", 120.00, 2, "Decorativo", 800]
                ],
                "table": "products"
            },
            "Vendas": {
                "cols": ["ID", "Data", "Produto", "Qtd", "Total", "Cliente", "Status"],
                "example": [
                    ["", datetime.now().strftime('%Y-%m-%d %H:%M'), "Caneca Café", 2, 90.00, "João da Silva", "Concluído"],
                    [101, datetime.now().strftime('%Y-%m-%d %H:%M'), "Vaso Decorativo", 1, 120.00, "Maria Souza", "Pendente"]
                ],
                "table": "sales"
            },
            "Despesas": {
                "cols": ["ID", "Data (AAAA-MM-DD)", "Descrição", "Valor", "Categoria"],
                "example": [
                    ["", datetime.now().strftime('%Y-%m-%d'), "Compra Esmalte", 150.00, "Compra de Insumo"],
                    [55, datetime.now().strftime('%Y-%m-%d'), "Conta de Luz", 300.00, "Energia"]
                ],
                "table": "expenses"
            },
            "Fornecedores": {
                "cols": ["Nome", "Email", "Telefone"],
                "example": [
                    ["Cerâmica ABC", "contato@cerabc.com", "1199999999"],
                    ["Massa Boa", "vendas@massaboa.com.br", "1188888888"]
                ],
                "table": "suppliers"
            },
            "Clientes": {
                "cols": ["Nome", "Telefone", "Email", "Data Nascimento"],
                "example": [
                    ["João da Silva", "11977777777", "joao@email.com", "1990-05-20"],
                    ["Maria Souza", "11966666666", "maria@email.com", ""]
                ],
                "table": "clients"
            }
        }
        
        curr_schema = schemas[import_type]
        
        c_step1, c_step2 = st.columns(2, gap="large")
        
        # --- STEP 1: DOWNLOAD TEMPLATE ---
        with c_step1:
            st.subheader("Passo 1: Baixar Modelo")
            st.write("Baixe a planilha modelo e preencha com seus dados.")
            
            # Generate Template DataFrame
            tmpl_df = pd.DataFrame(curr_schema['example'], columns=curr_schema['cols'])
            
            # Convert to Excel in memory
            # import io # Already imported globally
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                tmpl_df.to_excel(writer, index=False, sheet_name='Dados')
            
            st.download_button(
                f"⬇️ Baixar Modelo de {import_type} (.xlsx)",
                buffer.getvalue(),
                file_name=f"modelo_{import_type.split(' ')[0].lower()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
            with st.expander("Ver Colunas Obrigatórias"):
                st.write(curr_schema['cols'])

        # --- STEP 2: UPLOAD & PROCESS ---
        with c_step2:
            st.subheader("Passo 2: Enviar Arquivo")
            st.write("Faça upload da planilha preenchida.")
            
            up_file = st.file_uploader(f"Selecione arquivo para {import_type}", type=['xlsx', 'xls'])
            
            if up_file:
                try:
                    df_in = pd.read_excel(up_file)
                    admin_utils.show_feedback_dialog("Arquivo lido com sucesso!", level="success")
                    
                    # Validate Columns
                    missing_cols = [c for c in curr_schema['cols'] if c not in df_in.columns]
                    
                    if missing_cols:
                        admin_utils.show_feedback_dialog(f"Colunas faltando: {', '.join(missing_cols)}", level="error")
                        admin_utils.show_feedback_dialog("Por favor, use o modelo padrão.", level="warning")
                    else:
                        st.write(f"📝 **{len(df_in)} registros encontrados.**")
                        with st.expander("Pré-visualização (Primeiros 5)"):
                            st.dataframe(df_in.head())
                            
                        # Confirm Button
                        if st.button("🚀 IMPORTAR DADOS", type="primary"):
                            count_ok = 0
                            count_err = 0
                            cursor = conn.cursor()
                            
                            progress = st.progress(0)
                            
                            for idx, row in df_in.iterrows():
                                try:
                                    if import_type == "Insumos (Matérias-Primas)":
                                        # 1. Resolve Foreign Keys
                                        # Category
                                        cat_name = str(row['Categoria']).strip()
                                        cursor.execute("SELECT id FROM material_categories WHERE name=?", (cat_name,))
                                        res = cursor.fetchone()
                                        if res: cat_id = res[0]
                                        else:
                                            cursor.execute("INSERT INTO material_categories (name) VALUES (?)", (cat_name,))
                                            cat_id = cursor.lastrowid
                                            
                                        # Supplier
                                        sup_name = str(row['Fornecedor']).strip()
                                        cursor.execute("SELECT id FROM suppliers WHERE name=?", (sup_name,))
                                        res = cursor.fetchone()
                                        if res: sup_id = res[0]
                                        else:
                                            cursor.execute("INSERT INTO suppliers (name) VALUES (?)", (sup_name,))
                                            sup_id = cursor.lastrowid

                                        # 2. Check for Duplicate (Upsert)
                                        # Also fetch current stock for diff logging
                                        cursor.execute("SELECT id, stock_level FROM materials WHERE name=?", (row['Nome'],))
                                        mat_res = cursor.fetchone()
                                        
                                        if mat_res:
                                            # UPDATE
                                            target_id = mat_res[0]
                                            curr_stock = float(mat_res[1]) if mat_res[1] else 0.0
                                            new_stock = float(row['Estoque'])
                                            
                                            cursor.execute("""
                                                UPDATE materials 
                                                SET price_per_unit=?, unit=?, stock_level=?, type=?, category_id=?, supplier_id=?
                                                WHERE id=?
                                            """, (row['Preço'], row['Unidade'], new_stock, row['Tipo'], cat_id, sup_id, target_id))
                                            audit.log_action(conn, 'UPDATE', 'materials', target_id, None, row.to_dict())
                                            
                                            # LOG HISTORY (Diff)
                                            if abs(new_stock - curr_stock) > 0.001:
                                                diff = new_stock - curr_stock
                                                # Determine user
                                                current_u_id = 1 # Fallback
                                                if 'current_user' in st.session_state and st.session_state.current_user:
                                                    current_u_id = int(st.session_state.current_user['id'])
                                                
                                                cursor.execute("""
                                                    INSERT INTO inventory_transactions (material_id, date, type, quantity, cost, notes, user_id)
                                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                                """, (target_id, datetime.now().isoformat(), 'AJUSTE', abs(diff), 0.0, "Importação em Massa", current_u_id))
                                        else:
                                            # INSERT
                                            cursor.execute("""
                                                INSERT INTO materials (name, price_per_unit, unit, stock_level, type, category_id, supplier_id)
                                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                            """, (row['Nome'], row['Preço'], row['Unidade'], row['Estoque'], row['Tipo'], cat_id, sup_id))
                                            audit.log_action(conn, 'IMPORT', 'materials', cursor.lastrowid, None, row.to_dict())

                                    elif import_type == "Produtos":
                                        # 1. Product Categories (Text based in this schema version)
                                        # row['Categoria'] is used directly.
                                        
                                        # 2. Check for Duplicate (Upsert)
                                        cursor.execute("SELECT id, stock_quantity FROM products WHERE name=?", (row['Nome'],))
                                        prod_res = cursor.fetchone()
                                        
                                        if prod_res:
                                            # UPDATE
                                            target_id = prod_res[0]
                                            curr_stock = int(prod_res[1]) if prod_res[1] else 0
                                            new_stock = int(row['Estoque'])
                                            
                                            cursor.execute("""
                                                UPDATE products 
                                                SET base_price=?, stock_quantity=?, category=?, weight_g=?
                                                WHERE id=?
                                            """, (row['Preço Base'], new_stock, row['Categoria'], row['Peso (g)'], target_id))
                                            audit.log_action(conn, 'UPDATE', 'products', target_id, None, row.to_dict())
                                            
                                            # LOG HISTORY
                                            if new_stock != curr_stock:
                                                diff = new_stock - curr_stock
                                                # Determine user
                                                current_u_id = 1
                                                u_name = 'system'
                                                if 'current_user' in st.session_state and st.session_state.current_user:
                                                    current_u_id = int(st.session_state.current_user['id'])
                                                    u_name = st.session_state.current_user['username']
                                                
                                                cursor.execute("""
                                                    INSERT INTO production_history (timestamp, product_id, product_name, quantity, user_id, username, notes)
                                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                                """, (datetime.now().isoformat(), target_id, row['Nome'], diff, current_u_id, u_name, "Importação em Massa"))
                                        else:
                                            # INSERT
                                            cursor.execute("""
                                                INSERT INTO products (name, base_price, stock_quantity, category, weight_g)
                                                VALUES (?, ?, ?, ?, ?)
                                            """, (row['Nome'], row['Preço Base'], row['Estoque'], row['Categoria'], row['Peso (g)']))
                                            target_id = cursor.lastrowid
                                            audit.log_action(conn, 'IMPORT', 'products', target_id, None, row.to_dict())
                                        
                                        # 3. Handle Composition (Recipe/Kits)
                                        comp_str = str(row.get('Composição', '')).strip()
                                        if comp_str and target_id:
                                            try:
                                                # Clear existing (Safe Replace)
                                                cursor.execute("DELETE FROM product_recipes WHERE product_id=?", (target_id,))
                                                cursor.execute("DELETE FROM product_kits WHERE parent_product_id=?", (target_id,))
                                                
                                                # Format: TYPE: Name: Qty; Name: Qty
                                                parts = comp_str.split(':', 1)
                                                if len(parts) == 2:
                                                    ctype = parts[0].strip().upper()
                                                    items_str = parts[1].strip()
                                                    
                                                    items = [i.strip() for i in items_str.split(';') if i.strip()]
                                                    
                                                    if ctype == 'RECIPE':
                                                        for item in items:
                                                            # item = "Argila: 0.5"
                                                            iparts = item.rsplit(':', 1)
                                                            if len(iparts) == 2:
                                                                m_name = iparts[0].strip()
                                                                m_qty = float(iparts[1].strip())
                                                                
                                                                # Lookup Material by Name
                                                                cursor.execute("SELECT id FROM materials WHERE name=?", (m_name,))
                                                                m_res = cursor.fetchone()
                                                                if m_res:
                                                                    cursor.execute("INSERT INTO product_recipes (product_id, material_id, quantity) VALUES (?, ?, ?)", (target_id, m_res[0], m_qty))
                                                                else:
                                                                    print(f"Import Warning: Material '{m_name}' not found for product '{row['Nome']}'")

                                                    elif ctype == 'KIT':
                                                        for item in items:
                                                            iparts = item.rsplit(':', 1)
                                                            if len(iparts) == 2:
                                                                p_name = iparts[0].strip()
                                                                p_qty = int(float(iparts[1].strip())) # Allow float parsing but cast to int for kit qty
                                                                
                                                                # Lookup Product by Name
                                                                cursor.execute("SELECT id FROM products WHERE name=?", (p_name,))
                                                                p_res = cursor.fetchone()
                                                                if p_res:
                                                                    # Avoid self-reference loop?
                                                                    if p_res[0] != target_id:
                                                                        cursor.execute("INSERT INTO product_kits (parent_product_id, child_product_id, quantity) VALUES (?, ?, ?)", (target_id, p_res[0], p_qty))
                                                                else:
                                                                    print(f"Import Warning: Component '{p_name}' not found for kit '{row['Nome']}'")
                                            except Exception as e:
                                                print(f"Composition Parse Error for '{row['Nome']}': {e}")

                                    elif import_type == "Despesas":
                                        # Expenses - Upsert Logic
                                        # ID is optional. If present, Update. If empty, Insert.
                                        row_id = row.get('ID')
                                        target_id = None
                                        
                                        if pd.notna(row_id) and str(row_id).strip() != '':
                                             # Try to fetch existing
                                             try: 
                                                 tid = int(row_id)
                                                 cursor.execute("SELECT id FROM expenses WHERE id=?", (tid,))
                                                 if cursor.fetchone():
                                                     target_id = tid
                                             except Exception:
                                                 pass
                                        
                                        if target_id:
                                            # UPDATE
                                            cursor.execute("""
                                                UPDATE expenses SET date=?, description=?, amount=?, category=?
                                                WHERE id=?
                                            """, (row['Data (AAAA-MM-DD)'], row['Descrição'], row['Valor'], row['Categoria'], target_id))
                                            audit.log_action(conn, 'UPDATE', 'expenses', target_id, None, row.to_dict())
                                        else:
                                            # INSERT
                                            cursor.execute("""
                                                INSERT INTO expenses (date, description, amount, category)
                                                VALUES (?, ?, ?, ?)
                                            """, (row['Data (AAAA-MM-DD)'], row['Descrição'], row['Valor'], row['Categoria']))
                                            audit.log_action(conn, 'IMPORT', 'expenses', cursor.lastrowid, None, row.to_dict())

                                    elif import_type == "Vendas":
                                        # Sales - Upsert Logic
                                        
                                        # 1. Resolve Product ID
                                        prod_name = str(row['Produto']).strip()
                                        cursor.execute("SELECT id FROM products WHERE name=?", (prod_name,))
                                        pres = cursor.fetchone()
                                        prod_id = pres[0] if pres else None
                                        
                                        # 2. Resolve Client ID
                                        cli_name = str(row['Cliente']).strip()
                                        cursor.execute("SELECT id FROM clients WHERE name=?", (cli_name,))
                                        cres = cursor.fetchone()
                                        if cres:
                                            client_id = cres[0]
                                        else:
                                            # Auto-create Client
                                            cursor.execute("INSERT INTO clients (name, contact_info) VALUES (?, ?)", (cli_name, 'Importado'))
                                            client_id = cursor.lastrowid

                                        # 3. Check ID Upsert
                                        row_id = row.get('ID')
                                        target_id = None
                                        
                                        if pd.notna(row_id) and str(row_id).strip() != '':
                                             try: 
                                                 tid = int(row_id)
                                                 cursor.execute("SELECT id FROM sales WHERE id=?", (tid,))
                                                 if cursor.fetchone():
                                                     target_id = tid
                                             except Exception:
                                                 pass
                                        
                                        if target_id:
                                            # UPDATE
                                            cursor.execute("""
                                                UPDATE sales SET date=?, product_id=?, quantity=?, total_price=?, client_id=?, status=?
                                                WHERE id=?
                                            """, (row['Data'], prod_id, row['Qtd'], row['Total'], client_id, row['Status'], target_id))
                                            audit.log_action(conn, 'UPDATE', 'sales', target_id, None, row.to_dict())
                                        else:
                                            # INSERT
                                            cursor.execute("""
                                                INSERT INTO sales (date, product_id, quantity, total_price, client_id, status)
                                                VALUES (?, ?, ?, ?, ?, ?)
                                            """, (row['Data'], prod_id, row['Qtd'], row['Total'], client_id, row['Status']))
                                            audit.log_action(conn, 'IMPORT', 'sales', cursor.lastrowid, None, row.to_dict())

                                    elif import_type == "Fornecedores":
                                        # Suppliers - Upsert Logic (Match by Name)
                                        name = str(row['Nome']).strip()
                                        cursor.execute("SELECT id FROM suppliers WHERE name=?", (name,))
                                        res = cursor.fetchone()
                                        
                                        if res:
                                            # UPDATE
                                            target_id = res[0]
                                            cursor.execute("""
                                                UPDATE suppliers SET contact_info=?, email=?, phone=?
                                                WHERE id=?
                                            """, (f"{row['Telefone']} / {row['Email']}", row['Email'], row['Telefone'], target_id))
                                            audit.log_action(conn, 'UPDATE', 'suppliers', target_id, None, row.to_dict())
                                        else:
                                            # INSERT
                                            cursor.execute("""
                                                INSERT INTO suppliers (name, contact_info, email, phone)
                                                VALUES (?, ?, ?, ?)
                                            """, (name, f"{row['Telefone']} / {row['Email']}", row['Email'], row['Telefone']))
                                            audit.log_action(conn, 'IMPORT', 'suppliers', cursor.lastrowid, None, row.to_dict())

                                    elif import_type == "Clientes":
                                        # Clients - Upsert Logic (Match by Name)
                                        name = str(row['Nome']).strip()
                                        cursor.execute("SELECT id FROM clients WHERE name=?", (name,))
                                        res = cursor.fetchone()
                                        
                                        # Parse DOB
                                        dob = None
                                        if pd.notna(row['Data Nascimento']) and str(row['Data Nascimento']).strip():
                                            try:
                                                dob = pd.to_datetime(row['Data Nascimento']).strftime('%Y-%m-%d')
                                            except Exception:
                                                pass

                                        if res:
                                            # UPDATE
                                            target_id = res[0]
                                            cursor.execute("""
                                                UPDATE clients SET contact_info=?, email=?, phone=?, date_of_birth=?
                                                WHERE id=?
                                            """, (f"{row['Telefone']} / {row['Email']}", row['Email'], row['Telefone'], dob, target_id))
                                            audit.log_action(conn, 'UPDATE', 'clients', target_id, None, row.to_dict())
                                        else:
                                            # INSERT
                                            cursor.execute("""
                                                INSERT INTO clients (name, contact_info, email, phone, date_of_birth)
                                                VALUES (?, ?, ?, ?, ?)
                                            """, (name, f"{row['Telefone']} / {row['Email']}", row['Email'], row['Telefone'], dob))
                                            audit.log_action(conn, 'IMPORT', 'clients', cursor.lastrowid, None, row.to_dict())
                                    
                                    count_ok += 1
                                except Exception as e:
                                    count_err += 1
                                    print(f"Import Error row {idx}: {e}")

                                
                                progress.progress((idx + 1) / len(df_in))
                            
                            conn.commit()
                            admin_utils.show_feedback_dialog(f"Importação finalizada! {count_ok} sucessos, {count_err} erros.", level="success")
                            st.balloons()
                            st.rerun()

                except Exception as e:
                    admin_utils.show_feedback_dialog(f"Erro ao ler arquivo: {e}", level="error")

# ==============================================================================
# TAB 5: EXPORT (Data Dumping)
# ==============================================================================
with tab_export:
    st.header("📤 Exportação de Dados")
    st.write("Exporte seus dados para Excel para análise ou balanço de estoque.")
    
    export_type = st.selectbox("O que você deseja exportar?", ["Selecione...", "Insumos (Para Balanço/Contagem)", "Produtos", "Vendas", "Despesas", "Fornecedores", "Clientes"])
    
    if export_type != "Selecione...":
        st.divider()
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        
        if export_type == "Insumos (Para Balanço/Contagem)":
            st.info("💡 Esta planilha segue o mesmo formato da Importação. Você pode baixar, corrigir o estoque físico e importar de volta para atualizar o sistema.")
            
            # Fetch Data matching Import Schema: ["Nome", "Preço", "Unidade", "Estoque", "Tipo", "Categoria", "Fornecedor"]
            query = """
                SELECT 
                    m.name as Nome, 
                    m.price_per_unit as Preço, 
                    m.unit as Unidade, 
                    m.stock_level as Estoque, 
                    m.type as Tipo,
                    mc.name as Categoria,
                    s.name as Fornecedor
                FROM materials m
                LEFT JOIN material_categories mc ON m.category_id = mc.id
                LEFT JOIN suppliers s ON m.supplier_id = s.id
                ORDER BY m.name
            """
            df_exp = pd.read_sql(query, conn)
            
            # Generate Excel
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_exp.to_excel(writer, index=False, sheet_name='Dados')
            
            st.download_button(
                label=f"⬇️ Baixar Planilha de Insumos (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"insumos_balanco_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
            
            with st.expander("Pré-visualização"):
                st.dataframe(df_exp)

        elif export_type == "Produtos":
            # Match Import Schema: ["Nome", "Preço Base", "Estoque", "Categoria", "Peso (g)"]
            query = """
                SELECT 
                    p.id as ID_INTERNO,
                    p.name as "Nome", 
                    p.base_price as "Preço Base", 
                    p.stock_quantity as "Estoque", 
                    p.category as "Categoria",
                    p.weight_g as "Peso (g)"
                FROM products p
                ORDER BY p.name
            """
            products_df = pd.read_sql(query, conn)
            
            # --- BUILD COMPOSITION STRING ---
            comp_list = []
            for _, prow in products_df.iterrows():
                pid = prow['ID_INTERNO']
                comp_str = ""
                
                # 1. Check if Kit
                kits = pd.read_sql("""
                    SELECT pk.quantity, p.name 
                    FROM product_kits pk
                    JOIN products p ON pk.child_product_id = p.id
                    WHERE pk.parent_product_id = ?
                """, conn, params=(pid,))
                
                if not kits.empty:
                    # Format: KIT: Item1: Qtd; Item2: Qtd
                    # Sanitize name to avoid breaking the ';' delimiter
                    items = [f"{k['name'].replace(';', ',')}: {k['quantity']}" for _, k in kits.iterrows()]
                    comp_str = "KIT: " + "; ".join(items)
                else:
                    # 2. Check Recipe
                    recipes = pd.read_sql("""
                        SELECT m.name, pr.quantity
                        FROM product_recipes pr
                        JOIN materials m ON pr.material_id = m.id
                        WHERE pr.product_id = ?
                    """, conn, params=(pid,))
                    
                    if not recipes.empty:
                        # Format: RECIPE: Mat1: Qtd; Mat2: Qtd
                        items = [f"{r['name'].replace(';', ',')}: {r['quantity']}" for _, r in recipes.iterrows()]
                        comp_str = "RECIPE: " + "; ".join(items)
                
                comp_list.append(comp_str)
            
            products_df['Composição'] = comp_list
            # Remove internal ID before export
            del products_df['ID_INTERNO']
            
            df_exp = products_df
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_exp.to_excel(writer, index=False, sheet_name='Produtos')
            
            st.download_button(
                label=f"⬇️ Baixar Lista de Produtos (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"produtos_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

        elif export_type == "Vendas":
            query = """
                SELECT 
                    s.id as ID, 
                    s.date as Data, 
                    p.name as Produto, 
                    s.quantity as Qtd, 
                    s.total_price as Total, 
                    c.name as Cliente, 
                    s.status as Status
                FROM sales s
                LEFT JOIN products p ON s.product_id = p.id
                LEFT JOIN clients c ON s.client_id = c.id
                ORDER BY s.date DESC
            """
            df_exp = pd.read_sql(query, conn)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_exp.to_excel(writer, index=False, sheet_name='Vendas')

            st.download_button(
                label=f"⬇️ Baixar Relatório de Vendas (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"vendas_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

        elif export_type == "Despesas":
             # Match Import Schema: ["ID", "Data (AAAA-MM-DD)", "Descrição", "Valor", "Categoria"]
            query = """
                SELECT 
                    id as ID,
                    date as "Data (AAAA-MM-DD)", 
                    description as "Descrição", 
                    amount as "Valor", 
                    category as "Categoria"
                FROM expenses
                ORDER BY date DESC
            """
            df_exp = pd.read_sql(query, conn)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_exp.to_excel(writer, index=False, sheet_name='Despesas')
                
            st.download_button(
                label=f"⬇️ Baixar Relatório de Despesas (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"despesas_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

        elif export_type == "Fornecedores":
            # Match Import Schema: ["Nome", "Email", "Telefone"]
            query = """
                SELECT 
                    name as Nome,
                    email as Email,
                    phone as Telefone
                FROM suppliers
                ORDER BY name
            """
            df_exp = pd.read_sql(query, conn)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_exp.to_excel(writer, index=False, sheet_name='Fornecedores')
            
            st.download_button(
                label=f"⬇️ Baixar Lista de Fornecedores (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"fornecedores_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

        elif export_type == "Clientes":
            # Match Import Schema: ["Nome", "Telefone", "Email", "Data Nascimento"]
            query = """
                SELECT 
                    name as Nome,
                    phone as Telefone,
                    email as Email,
                    date_of_birth as "Data Nascimento"
                FROM clients
                ORDER BY name
            """
            df_exp = pd.read_sql(query, conn)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_exp.to_excel(writer, index=False, sheet_name='Clientes')
            
            st.download_button(
                label=f"⬇️ Baixar Lista de Clientes (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"clientes_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )


# ==============================================================================
# TAB 1: USERS (Adapted from 10_Usuarios.py)
# ==============================================================================
with tab_users:
    cursor = conn.cursor()

    # Session state for editing
    if "user_edit_id" not in st.session_state:
        st.session_state.user_edit_id = None

    # --- LAYOUT ---
    col_form, col_list = st.columns([1, 2], gap="large")

    # === LEFT: NEW/EDIT USER FORM ===
    with col_form:
        is_edit = st.session_state.user_edit_id is not None
        form_title = "✏️ Editar Usuário" if is_edit else "➕ Novo Usuário"
        st.subheader(form_title)
        
        # Defaults
        def_username, def_name, def_role = "", "", "vendedor"
        def_active = True
        
        if is_edit:
            try:
                edit_row = pd.read_sql("SELECT * FROM users WHERE id=?", conn, params=(st.session_state.user_edit_id,)).iloc[0]
                def_username = edit_row['username'] or ""
                def_name = edit_row['name'] or ""
                def_role = edit_row['role'] or "vendedor"
                def_active = bool(edit_row['active'])
            except Exception:
                st.session_state.user_edit_id = None
                st.rerun()
        
        if is_edit:
            if st.button("⬅️ Cancelar Edição"):
                st.session_state.user_edit_id = None
                st.rerun()
        
        with st.form("user_form", clear_on_submit=not is_edit):
            f_username = st.text_input("Usuário *", value=def_username, disabled=is_edit)
            f_name = st.text_input("Nome Completo", value=def_name)
            f_role = st.selectbox("Perfil", list(auth.ROLES.keys()), 
                                  format_func=lambda x: auth.ROLES[x],
                                  index=list(auth.ROLES.keys()).index(def_role) if def_role in auth.ROLES else 0)
            f_active = st.checkbox("Ativo", value=def_active)
            
            st.divider()
            st.caption("Senha" if not is_edit else "Nova Senha (deixe em branco para manter)")
            f_password = st.text_input("Senha", type="password")
            f_password_confirm = st.text_input("Confirmar Senha", type="password")
            
            btn_label = "💾 Salvar Alterações" if is_edit else "💾 Cadastrar"
            if st.form_submit_button(btn_label, type="primary", use_container_width=True):
                # Validation
                error = None
                
                if not is_edit and not f_username:
                    error = "Usuário é obrigatório."
                elif not is_edit and not f_password:
                    error = "Senha é obrigatória para novo usuário."
                elif f_password and f_password != f_password_confirm:
                    error = "As senhas não conferem."
                elif not is_edit:
                    # Check if username exists
                    existing = pd.read_sql("SELECT id FROM users WHERE username=?", conn, params=(f_username,))
                    if not existing.empty:
                        error = "Este usuário já existe."
                
                if error:
                    admin_utils.show_feedback_dialog(error, level="error")
                else:
                    if is_edit:
                        # Get old data for audit
                        old_user = pd.read_sql("SELECT username, name, role, active FROM users WHERE id=?", conn, params=(st.session_state.user_edit_id,))
                        old_data = old_user.iloc[0].to_dict() if not old_user.empty else {}
                        
                        # Update user
                        if f_password:
                            cursor.execute("""
                                UPDATE users SET name=?, role=?, active=?, password_hash=? WHERE id=?
                            """, (f_name, f_role, int(f_active), auth.hash_password(f_password), st.session_state.user_edit_id))
                        else:
                            cursor.execute("""
                                UPDATE users SET name=?, role=?, active=? WHERE id=?
                            """, (f_name, f_role, int(f_active), st.session_state.user_edit_id))
                        conn.commit()
                        audit.log_action(conn, 'UPDATE', 'users', st.session_state.user_edit_id, old_data,
                            {'name': f_name, 'role': f_role, 'active': f_active})
                        admin_utils.show_feedback_dialog("Usuário atualizado!", level="success")
                        st.session_state.user_edit_id = None
                    else:
                        # Create user
                        cursor.execute("""
                            INSERT INTO users (username, password_hash, role, name, active, created_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (f_username, auth.hash_password(f_password), f_role, f_name, int(f_active), datetime.now().isoformat()))
                        new_id = cursor.lastrowid
                        conn.commit()
                        audit.log_action(conn, 'CREATE', 'users', new_id, None,
                            {'username': f_username, 'name': f_name, 'role': f_role})
                        admin_utils.show_feedback_dialog("Usuário cadastrado!", level="success")
                    st.rerun()

    # === RIGHT: USER LIST ===
    with col_list:
        st.subheader("📋 Usuários Cadastrados")
        
        # Search
        search_user = st.text_input("🔍 Buscar", placeholder="Nome, usuário...")
        
        # Fetch Users
        users_df = pd.read_sql("SELECT id, username, name, role, active, created_at, last_login FROM users ORDER BY name", conn)
        
        # Apply filter
        if search_user and not users_df.empty:
            mask = users_df.apply(lambda row: search_user.lower() in str(row).lower(), axis=1)
            users_df = users_df[mask]
        
        st.caption(f"{len(users_df)} usuário(s)")
        
        if not users_df.empty:
            for _, row in users_df.iterrows():
                status_icon = "✅" if row['active'] else "❌"
                role_name = auth.ROLES.get(row['role'], row['role'])
                
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    
                    with c1:
                        st.markdown(f"### {status_icon} {row['name'] or row['username']}")
                        st.write(f"👤 @{row['username']} | 📋 {role_name}")
                        if row['last_login']:
                            st.caption(f"🕐 Último acesso: {row['last_login'][:16]}")
                    
                    with c2:
                        if st.button("✏️ Editar", key=f"edit_user_{row['id']}", use_container_width=True):
                            st.session_state.user_edit_id = row['id']
                            st.rerun()
                    
                    with c3:
                        # Prevent deleting yourself or last admin
                        current_user = auth.get_current_user()
                        is_self = current_user and current_user['id'] == row['id']
                        
                        if not is_self:
                            if st.button("🗑️", key=f"del_user_{row['id']}", use_container_width=True, help="Excluir"):
                                def do_del_user(uid=row['id'], uname=row['username']):
                                    cursor.execute("DELETE FROM users WHERE id=?", (uid,))
                                    conn.commit()
                                    audit.log_action(conn, 'DELETE', 'users', uid, {'username': uname}, None)

                                admin_utils.show_confirmation_dialog(
                                    f"Tem certeza que deseja excluir o usuário '{row['username']}'?",
                                    on_confirm=do_del_user
                                )
                        else:
                            st.caption("(você)")
        else:
            st.info("Nenhum usuário encontrado.")


# ==============================================================================
# TAB 2: AUDIT (Adapted from 11_Auditoria.py)
# ==============================================================================
with tab_audit:
    # --- FILTERS ---
    st.subheader("🔍 Filtros de Auditoria")
    
    f1, f2, f3, f4 = st.columns(4)
    
    with f1:
        tables = ["Todas", "products", "sales", "expenses", "materials", "clients", "suppliers", "commission_orders", "firings", "users"]
        sel_table = st.selectbox("Tabela", tables, format_func=lambda x: audit.format_table_name(x) if x != "Todas" else "Todas")
    
    with f2:
        actions = ["Todas", "CREATE", "UPDATE", "DELETE", "ROLLBACK"]
        sel_action = st.selectbox("Ação", actions, format_func=lambda x: audit.format_action(x) if x != "Todas" else "Todas")
    
    with f3:
        users_df = pd.read_sql("SELECT DISTINCT username FROM audit_log ORDER BY username", conn)
        user_opts = ["Todos"] + users_df['username'].tolist()
        sel_user = st.selectbox("Usuário", user_opts)
    
    with f4:
        limit = st.number_input("Limite", min_value=10, max_value=500, value=100, step=50)
    
    # Date filters
    d1, d2 = st.columns(2)
    with d1:
        start_date = st.date_input("De", value=None)
    with d2:
        end_date = st.date_input("Até", value=None)
    
    # Build filters
    filters = {}
    if sel_table != "Todas":
        filters['table_name'] = sel_table
    if sel_action != "Todas":
        filters['action'] = sel_action
    if sel_user != "Todos":
        filters['username'] = sel_user
    if start_date:
        filters['start_date'] = start_date.isoformat()
    if end_date:
        filters['end_date'] = end_date.isoformat() + "T23:59:59"
    
    st.divider()
    
    # --- AUDIT LOG TABLE ---
    log_df = audit.get_audit_log(conn, filters if filters else None, limit=limit)
    
    st.subheader(f"📋 Registros ({len(log_df)})")
    
    if log_df.empty:
        st.info("Nenhum registro encontrado com os filtros selecionados.")
    else:
        for _, row in log_df.iterrows():
            action_icon = audit.format_action(row['action'])
            table_icon = audit.format_table_name(row['table_name'])
            
            timestamp = row['timestamp'][:16].replace('T', ' ')
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                
                with c1:
                    st.markdown(f"**{action_icon}** em {table_icon} (ID: {row['record_id']})")
                    st.caption(f"🕐 {timestamp} | 👤 {row['username']}")
                
                with c2:
                    # Show details
                    with st.popover("📋 Detalhes"):
                        st.markdown("**Dados Anteriores:**")
                        if row['old_data']:
                            try:
                                old = json.loads(row['old_data'])
                                st.json(old)
                            except Exception:
                                st.code(row['old_data'])
                        else:
                            st.caption("N/A")
                        
                        st.markdown("**Dados Novos:**")
                        if row['new_data']:
                            try:
                                new = json.loads(row['new_data'])
                                st.json(new)
                            except Exception:
                                st.code(row['new_data'])
                        else:
                            st.caption("N/A")
                
                with c3:
                    # Rollback button (only for UPDATE and DELETE)
                    if row['action'] in ['UPDATE', 'DELETE'] and row['old_data']:
                        if st.button("↩️ Reverter", key=f"rb_{row['id']}", help="Restaurar dados anteriores"):
                            def do_rollback(rid=row['id']):
                                if audit.rollback_record(conn, rid):
                                    admin_utils.show_feedback_dialog("Dados restaurados com sucesso!", level="success")
                                else:
                                    admin_utils.show_feedback_dialog("Erro ao restaurar dados.", level="error")
                            
                            admin_utils.show_confirmation_dialog(
                                f"Deseja reverter esta alteração (ID Auditoria: {row['id']})?",
                                on_confirm=do_rollback
                            )

# ==============================================================================
# TAB 3: DATABASE (Maintenance)
# ==============================================================================
with tab_db:
    st.header("💾 Backup e Restauração")
    st.warning("Área sensível. Tenha cuidado ao realizar operações aqui.")
    
    col_bkp, col_rst = st.columns(2, gap="large")
    
    with col_bkp:
        st.subheader("⬇️ Backup (Download)")
        st.write("Baixe uma cópia completa do banco de dados atual.")
        
        db_path = database.DB_PATH
        if os.path.exists(db_path):
            with open(db_path, "rb") as f:
                st.download_button(
                    "💾 Baixar Banco de Dados (.db)",
                    f,
                    file_name=f"backup_manual_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                    mime="application/octet-stream",
                    use_container_width=True,
                    type="primary"
                )
        else:
            admin_utils.show_feedback_dialog("Arquivo de banco de dados não encontrado.", level="error")
        
        st.divider()
        st.subheader("⚙️ Backup Automático")
        bkp_settings = backup_utils.get_backup_settings(conn)
        
        freq_opts = ["Manual", "Diário", "Semanal", "Mensal"]
        curr_freq = bkp_settings['frequency']
        freq_idx = freq_opts.index(curr_freq) if curr_freq in freq_opts else 1
        
        new_freq = st.selectbox("Frequência de Backup", freq_opts, index=freq_idx, help="O backup será verificado sempre que o Dashboard for carregado.")
        
        if new_freq != curr_freq:
            backup_utils.save_backup_settings(conn, new_freq)
            st.success(f"Frequência alterada para: {new_freq}")
            
        last_run_dt = datetime.fromisoformat(bkp_settings['last_run']).strftime('%d/%m/%Y %H:%M')
        st.caption(f"📅 Último backup automático: {last_run_dt}")
        
        if st.button("🚀 Executar Backup Agora", use_container_width=True):
            if backup_utils.perform_backup(conn):
                admin_utils.show_feedback_dialog("Backup realizado com sucesso!", level="success")
                st.rerun()
            else:
                admin_utils.show_feedback_dialog("Erro ao realizar backup.", level="error")

    with col_rst:
        st.subheader("📋 Backups Recentes (Local)")
        backups = backup_utils.list_backups()
        
        if not backups:
            st.info("Nenhum backup local encontrado em `data/backups/`")
        else:
            for b_file in backups:
                with st.container(border=True):
                    bc1, bc2, bc3 = st.columns([3, 1, 1])
                    with bc1:
                        st.write(f"📄 {b_file}")
                        # Get size
                        b_path = os.path.join(backup_utils.BACKUP_FOLDER, b_file)
                        b_size = os.path.getsize(b_path) / (1024*1024)
                        st.caption(f"Tamanho: {b_size:.2f} MB")
                    
                    with bc2:
                        with open(b_path, "rb") as bf:
                            st.download_button("⬇️", bf, file_name=b_file, key=f"dl_{b_file}", help="Baixar")
                    
                    with bc3:
                        if st.button("🗑️", key=f"del_{b_file}", help="Excluir backup local"):
                            def do_del_bkp(fname=b_file):
                                if backup_utils.delete_backup(fname):
                                    st.rerun()
                            
                            admin_utils.show_confirmation_dialog(
                                f"Deseja excluir permanentemente o arquivo de backup {b_file}?",
                                on_confirm=do_del_bkp
                            )

        st.divider()
        st.subheader("⬆️ Restaurar (Upload)")
        st.write("Faça upload de um arquivo `.db` para restaurar o sistema.")
        
        uploaded_file = st.file_uploader("Selecione o arquivo de backup (.db)", type=['db'])
        
        if uploaded_file is not None:
            # 1. Save to temp for analysis
            temp_path = "temp_restore.db"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            try:
                # 2. Analysis
                st.info("Analisando arquivo...")
                
                # Get Current Stats
                curr_size = os.path.getsize(database.DB_PATH) / (1024*1024)
                curr_last_log = "N/A"
                try:
                    curr_log = pd.read_sql("SELECT timestamp FROM audit_log ORDER BY id DESC LIMIT 1", conn)
                    if not curr_log.empty:
                        curr_last_log = curr_log.iloc[0]['timestamp']
                except Exception:
                    pass

                # Get New (Backup) Stats
                import sqlite3
                conn_temp = sqlite3.connect(temp_path)
                new_size = os.path.getsize(temp_path) / (1024*1024)
                new_last_log = "N/A"
                try:
                    new_log = pd.read_sql("SELECT timestamp FROM audit_log ORDER BY id DESC LIMIT 1", conn_temp)
                    if not new_log.empty:
                        new_last_log = new_log.iloc[0]['timestamp']
                except Exception:
                    pass
                conn_temp.close()
                
                # 3. Display Comparison
                st.markdown("### 📊 Comparativo")
                
                res_col1, res_col2 = st.columns(2)
                
                # Timestamp Logic
                warn_time = False
                diff_msg = ""
                
                # Try parsing dates
                from datetime import datetime
                try:
                    curr_dt = datetime.fromisoformat(curr_last_log) if curr_last_log != "N/A" else datetime.min
                    new_dt = datetime.fromisoformat(new_last_log) if new_last_log != "N/A" else datetime.min
                    
                    if new_dt < curr_dt:
                        warn_time = True
                        diff = curr_dt - new_dt
                        diff_msg = f"⚠️ O backup é {diff.days} dias mais antigo que o atual!"
                    else:
                        diff_msg = "✅ O backup é mais recente ou igual."
                except Exception:
                    diff_msg = "Não foi possível comparar datas."

                with res_col1:
                    st.caption("🔴 Banco Atual (Será Substituído)")
                    st.metric("Tamanho", f"{curr_size:.2f} MB")
                    st.metric("Última Atividade", curr_last_log)
                    
                with res_col2:
                    st.caption("🟢 Novo Banco (Backup)")
                    st.metric("Tamanho", f"{new_size:.2f} MB", delta=f"{new_size - curr_size:.2f} MB")
                    st.metric("Última Atividade", new_last_log)
                
                if warn_time:
                    st.error(diff_msg)
                else:
                    st.success(diff_msg)
                    
                st.divider()
                
                # 4. Confirmation
                confirm = st.checkbox(f"ESTOU CIENTE DOS RISCOS. Entendo que substituirei o banco atual pelo arquivo enviado.", value=False)
                
                if confirm:
                    if st.button("🚨 SUBSTITUIR BANCO DE DADOS AGORA", type="primary", use_container_width=True):
                        def do_restore(t_path=temp_path):
                            try:
                                # Close connection before replacing file
                                conn.close()
                                # Replace
                                import shutil
                                shutil.copy(t_path, database.DB_PATH)
                                # Clean temp
                                os.remove(t_path)
                            except Exception as e:
                                st.error(f"Erro ao restaurar: {e}")

                        admin_utils.show_confirmation_dialog(
                            "PERIGO: Você está prestes a SUBSTITUIR COMPLETAMENTE o banco de dados atual. Esta ação é irreversível e o sistema será reiniciado. Deseja prosseguir?",
                            on_confirm=do_restore
                        )
                else:
                    st.button("🚨 SUBSTITUIR BANCO DE DADOS AGORA", disabled=True, use_container_width=True, help="Marque a caixa de confirmação acima.")

            except Exception as e:
                admin_utils.show_feedback_dialog(f"Arquivo inválido ou erro na análise: {e}", level="error")
                if os.path.exists(temp_path):
                    os.remove(temp_path)


conn.close()
