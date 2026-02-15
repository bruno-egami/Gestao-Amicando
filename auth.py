"""
Authentication and Authorization Module for CeramicAdmin OS
Handles user login, password hashing, session management, and role-based access control.
"""
import streamlit as st
import bcrypt
import time
import pandas as pd
import sqlite3
from datetime import datetime

# Role definitions
ROLES = {
    'admin': 'Administrador',
    'vendedor': 'Vendedor(a)',
    'visualizador': 'Visualizador'
}

# Page access control - which roles can access which pages
PAGE_ACCESS = {
    'Dashboard': ['admin', 'vendedor', 'visualizador'],
    'Insumos': ['admin', 'vendedor'],
    'Financeiro': ['admin', 'vendedor'],
    'Queimas': ['admin', 'vendedor'],
    'Produtos': ['admin', 'vendedor'],
    'Vendas': ['admin', 'vendedor'],
    'Orcamentos': ['admin', 'vendedor'],
    'Fornecedores': ['admin', 'vendedor'],
    'Clientes': ['admin', 'vendedor'],
    'Encomendas': ['admin', 'vendedor'],
    'Producao': ['admin', 'vendedor'],
    'Relatorios': ['admin', 'vendedor'],
    'Administracao': ['admin'],
    'Gestao_Aulas': ['admin', 'vendedor']
}

# Navigation Menu Configuration
# (Label, Icon, Page File)
NAV_MENU = {
    'admin': [
        ("Dashboard", "📊", "Dashboard.py"),
        ("Vendas", "🛒", "pages/6_Vendas.py"),
        ("Encomendas", "📦", "pages/9_Encomendas.py"),
        ("Produção", "🏭", "pages/11_Producao.py"),
        ("Aulas & Alunos", "🎓", "pages/13_Gestao_Aulas.py"),
        ("Queimas", "🔥", "pages/4_Queimas.py"),
        ("Produtos", "🏺", "pages/5_Produtos.py"),
        ("Insumos", "🧪", "pages/1_Insumos.py"),
        ("Financeiro", "💰", "pages/3_Financeiro.py"),
        ("Relatórios", "📈", "pages/10_Relatorios.py"),
        ("Clientes", "🤝", "pages/8_Clientes.py"),
        ("Fornecedores", "🚚", "pages/7_Fornecedores.py"),
        ("Administração", "⚙️", "pages/99_Administracao.py"),
    ],
    'vendedor': [
        ("Dashboard", "📊", "Dashboard.py"),
        ("Vendas", "🛒", "pages/6_Vendas.py"),
        ("Encomendas", "📦", "pages/9_Encomendas.py"),
        ("Produção", "🏭", "pages/11_Producao.py"),
        ("Aulas & Alunos", "🎓", "pages/13_Gestao_Aulas.py"),
        ("Queimas", "🔥", "pages/4_Queimas.py"),
        ("Produtos", "🏺", "pages/5_Produtos.py"),
        ("Insumos", "🧪", "pages/1_Insumos.py"),
        ("Financeiro", "💰", "pages/3_Financeiro.py"),
        ("Relatórios", "📈", "pages/10_Relatorios.py"),
        ("Clientes", "🤝", "pages/8_Clientes.py"),
        ("Fornecedores", "🚚", "pages/7_Fornecedores.py"),
    ],
    'visualizador': [
        ("Dashboard", "📊", "Dashboard.py"),
    ]
}

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    # bcrypt requires bytes, returns bytes. We store as string.
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        # Fallback for old SHA256 hashes (optional, but requested to reset admin anyway)
        # If we wanted to support legacy hashes we would check len or prefix.
        # For now, we assume all valid passwords will be bcrypt after migration.
        return False

def login(conn, username: str, password: str) -> dict | None:
    """
    Attempt to login a user. Returns user dict if successful, None otherwise.
    """
    import pandas as pd
    
    try:
        user_df = pd.read_sql(
            "SELECT * FROM users WHERE username=? AND active=1", 
            conn, 
            params=(username,)
        )
        
        if user_df.empty:
            return None
        
        user = user_df.iloc[0]
        
        if verify_password(password, user['password_hash']):
            # Update last login
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET last_login=? WHERE id=?", 
                (datetime.now().isoformat(), user['id'])
            )
            conn.commit()
            
            return {
                'id': int(user['id']),
                'username': user['username'],
                'role': user['role'],
                'name': user['name'] or user['username'],
                'force_password_change': int(user.get('force_password_change', 0))
            }
        
        return None
    except Exception as e:
        st.error(f"Erro de login: {e}")
        return None

def verify_admin_authorization(conn, password: str) -> bool:
    """
    Verify if a given password belongs to an active admin user.
    Useful for overriding restricted areas.
    """
    try:
        # Check against specific 'admin' user or ANY admin? 
        # Requirement usually implies the 'admin' superuser or any admin. 
        # Let's check against the specific 'admin' user first for simplicity, 
        # or iterate all admins? 'admin' user is guaranteed by create_default_admin.
        # Let's use the 'admin' username for the override.
        
        user_df = pd.read_sql(
            "SELECT password_hash FROM users WHERE username='admin' AND active=1", 
            conn
        )
        
        if user_df.empty:
            return False
            
        return verify_password(password, user_df.iloc[0]['password_hash'])
    except Exception as e:
        print(f"Auth Check Error: {e}")
        return False

def get_current_user() -> dict | None:
    """Get the currently logged-in user from session state."""
    if 'current_user' in st.session_state and st.session_state.current_user:
        # Check session timeout (60 minutes)
        SESSION_TIMEOUT_SECONDS = 3600
        if 'last_activity' in st.session_state:
            if (time.time() - st.session_state.last_activity) > SESSION_TIMEOUT_SECONDS:
                logout()
                return None
        st.session_state.last_activity = time.time()
        return st.session_state.current_user
    return None

def set_current_user(user: dict):
    """Set the current user in session state."""
    st.session_state.current_user = user
    st.session_state.last_activity = time.time()

def logout():
    """Logout the current user."""
    if 'current_user' in st.session_state:
        del st.session_state.current_user
    if 'last_activity' in st.session_state:
        del st.session_state.last_activity

def require_login(conn):
    """
    Require user to be logged in. Shows login form if not.
    Returns True if user is logged in, False otherwise.
    """
    user = get_current_user()
    
    if user:
        # Check for Forced Password Change
        if user.get('force_password_change', 0) == 1:
            # Hide sidebar
            st.markdown("""
                <style>
                [data-testid="stSidebarNav"] {display: none;}
                section[data-testid="stSidebar"] {display: none;}
                </style>
            """, unsafe_allow_html=True)
            
            st.warning("⚠️ Por segurança, você deve alterar sua senha antes de continuar.")
            
            with st.container(border=True):
                st.subheader("🔄 Trocar Senha")
                with st.form("force_pass_change_form"):
                    new_pass = st.text_input("Nova Senha", type="password")
                    conf_pass = st.text_input("Confirmar Nova Senha", type="password")
                    
                    if st.form_submit_button("Salvar Nova Senha", type="primary"):
                            if new_pass != conf_pass:
                                st.error("As senhas não coincidem.")
                            elif len(new_pass) < 6:
                                st.error("A senha deve ter pelo menos 6 caracteres.")
                            else:
                                try:
                                    cursor = conn.cursor()
                                    new_hash = hash_password(new_pass)
                                    # Ensure ID is native int
                                    uid = int(user['id'])
                                    cursor.execute("UPDATE users SET password_hash=?, force_password_change=0 WHERE id=?", (new_hash, uid))
                                    conn.commit()
                                    
                                    # Update session
                                    user['force_password_change'] = 0
                                    set_current_user(user)
                                    
                                    st.success("Senha alterada com sucesso! Redirecionando...")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao salvar: {e}")
                                    print(f"Password Update Error: {e}")
            return False

        return True
    
    # Hide sidebar if not logged in (Unified Login View)
    st.markdown("""
        <style>
        [data-testid="stSidebarNav"] {display: none;}
        section[data-testid="stSidebar"] {display: none;}
        </style>
    """, unsafe_allow_html=True)
    
    # Show login form
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("🔐 Gestão Amicando - Login")
        
        with st.form("login_form"):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            
            if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                user = login(conn, username, password)
                if user:
                    set_current_user(user)
                    st.success(f"Bem-vindo(a), {user['name']}!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    
    return False

def require_role(allowed_roles: list, page_name: str = None):
    """
    Check if current user has one of the allowed roles.
    Returns True if authorized, False otherwise.
    """
    user = get_current_user()
    
    if not user:
        return False
    
    if user['role'] in allowed_roles:
        return True
    
    st.error(f"⛔ Acesso negado. Seu perfil ({ROLES.get(user['role'], user['role'])}) não tem permissão para esta área.")
    return False

def check_page_access(page_name: str) -> bool:
    """
    Check if current user can access a specific page.
    """
    allowed_roles = PAGE_ACCESS.get(page_name, ['admin'])
    return require_role(allowed_roles, page_name)

def render_custom_sidebar():
    """Render the custom sidebar with role-based navigation."""
    
    # Hide default sidebar nav
    st.markdown("""
        <style>
        [data-testid="stSidebarNav"] {display: none;}
        </style>
    """, unsafe_allow_html=True)

    user = get_current_user()
    if not user:
        return

    with st.sidebar:
        st.divider()
        role = user['role']
        menu_items = NAV_MENU.get(role, NAV_MENU['visualizador'])
        
        for label, icon, file_path in menu_items:
            st.page_link(file_path, label=label, icon=icon)
            
        st.divider()
        st.caption(f"👤 {user['name']}")
        st.caption(f"📋 {ROLES.get(user['role'], user['role'])}")
        
        if st.button("🚪 Sair", use_container_width=True, key="sidebar_logout_btn"):
            logout()
            st.rerun()

def render_user_info():
    # Deprecated in favor of render_custom_sidebar but kept for backward compatibility during refactor
    render_custom_sidebar()

def create_default_admin(conn):
    """Create default admin user if no users exist."""
    import pandas as pd
    
    cursor = conn.cursor()
    
    # Check if any users exist
    count = pd.read_sql("SELECT count(*) as c FROM users", conn).iloc[0]['c']
    
    if count == 0:
        # Create default admin with forced password change
        try:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, name, active, created_at, force_password_change)
                VALUES (?, ?, ?, ?, 1, ?, 1)
            """, ('admin', hash_password('admin'), 'admin', 'Administrador', datetime.now().isoformat()))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Race condition or user already exists despite count=0 check
            pass
    return False
