
import streamlit as st
import database
import admin_utils
import auth
import utils.styles as styles
from services import order_service, product_service
from views import sales_catalog, sales_cart, sales_quotes, sales_history

st.set_page_config(page_title="Vendas", page_icon="💰", layout="wide")

# Apply Global Styles
styles.apply_custom_style()

admin_utils.render_sidebar_logo()

# Database Connection
with database.db_session() as conn:

    if not auth.require_login(conn):
        st.stop()

    if not auth.check_page_access("Vendas"):
        st.stop()

    auth.render_custom_sidebar()
    st.title("Frente de Vendas")

    # --- Application State ---
    if 'cart' not in st.session_state:
        st.session_state['cart'] = []

    if 'selected_product_id' not in st.session_state:
        st.session_state['selected_product_id'] = None

    # --- Receipt Dialog ---
    if 'last_order' in st.session_state:
        sales_cart.show_receipt_dialog(st.session_state['last_order'])

    # --- Prepare Data ---
    # 1. Select Client (Global fetch for Form and History)
    clients_df = order_service.get_all_clients(conn)
    client_dict = {row['name']: row['id'] for _, row in clients_df.iterrows()}
    client_opts = [""] + list(client_dict.keys())

    # 2. Select Product (Visual Catalog)
    # Full list for Cart lookup (Cached)
    all_products_df = product_service.get_all_products(conn)

    # --- Tabs Structure ---
    tab_pos, tab_quotes = st.tabs(["🛒 Nova Venda / Cotação", "📄 Orçamentos Salvos"])

    # ==============================================================================
    # TAB 1: POS (Catalog + Cart)
    # ==============================================================================
    with tab_pos:
        # --- Layout: 2 Columns (Catalog vs Cart/Checkout) ---
        col_catalog, col_cart = st.columns([1.1, 0.9], gap="large")

        # ==========================
        # LEFT COL: CATALOG
        # ==========================
        with col_catalog:
            # --- Filters (SQL Optimized) ---
            c_filt1, c_filt2 = st.columns([1, 1])
            search_term = c_filt1.text_input("🔍 Buscar Produto", placeholder="Nome do produto...")
        
            # Get Categories (from full list or DB)
            all_cats = product_service.get_categories(conn, all_products_df)
            sel_cats = c_filt2.multiselect("📂 Filtrar Categoria", options=all_cats, placeholder="Todas")
        
            # Fetch Filtered Data (SQL)
            catalog_df = product_service.get_all_products(conn, search_term=search_term, category=sel_cats if sel_cats else None)
        
            sales_catalog.render_catalog(conn, catalog_df)

        # ==========================
        # RIGHT COL: CART & ACTION
        # ==========================
        with col_cart:
            sales_cart.render_cart_section(conn, all_products_df, client_opts, client_dict)

    # ==============================================================================
    # TAB 2: QUOTES MANAGEMENT
    # ==============================================================================
    with tab_quotes:
        sales_quotes.render_quotes_management(conn)

    # ==============================================================================
    # HISTORY SECTION
    # ==============================================================================
    st.divider()
    sales_history.render_sales_history(conn, client_opts)

