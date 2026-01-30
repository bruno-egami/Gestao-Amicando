"""
Authentication and Authorization Module for CeramicAdmin OS
Handles user login, password hashing, session management, and role-based access control.
"""
import streamlit as st
import hashlib
import time
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
    'Despesas': ['admin'],
    'Financeiro': ['admin'],
    'Queimas': ['admin'],
    'Produtos': ['admin', 'vendedor'],
    'Vendas': ['admin', 'vendedor'],
    'Fornecedores': ['admin'],
    'Clientes': ['admin', 'vendedor'],
    'Encomendas': ['admin', 'vendedor'],
    'Usuarios': ['admin']
}

def hash_password(password: str) -> str:
    """Hash password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(password) == password_hash

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
                'id': user['id'],
                'username': user['username'],
                'role': user['role'],
                'name': user['name'] or user['username']
            }
        
        return None
    except Exception as e:
        st.error(f"Erro de login: {e}")
        return None

def get_current_user() -> dict | None:
    """Get the currently logged-in user from session state."""
    if 'current_user' in st.session_state and st.session_state.current_user:
        # Check session timeout (30 minutes)
        if 'last_activity' in st.session_state:
            if (time.time() - st.session_state.last_activity) > 1800:  # 30 min
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
        return True
    
    # Show login form
    st.subheader("🔐 Login")
    
    with st.form("login_form"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        
        if st.form_submit_button("Entrar", type="primary"):
            user = login(conn, username, password)
            if user:
                set_current_user(user)
                st.success(f"Bem-vindo(a), {user['name']}!")
                time.sleep(0.5)
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

def render_user_info():
    """Render current user info in sidebar."""
    user = get_current_user()
    if user:
        with st.sidebar:
            st.divider()
            st.caption(f"👤 {user['name']}")
            st.caption(f"📋 {ROLES.get(user['role'], user['role'])}")
            if st.button("🚪 Sair", use_container_width=True):
                logout()
                st.rerun()

def create_default_admin(conn):
    """Create default admin user if no users exist."""
    import pandas as pd
    
    cursor = conn.cursor()
    
    # Check if any users exist
    count = pd.read_sql("SELECT count(*) as c FROM users", conn).iloc[0]['c']
    
    if count == 0:
        # Create default admin
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, name, active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, ('admin', hash_password('admin'), 'admin', 'Administrador', datetime.now().isoformat()))
        conn.commit()
        return True
    return False
