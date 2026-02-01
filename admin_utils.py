import streamlit as st

import time

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == "admin":
            st.session_state["password_correct"] = True
            st.session_state["last_active"] = time.time() # Init timer
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Senha de Administrador", type="password", on_change=password_entered, key="password"
        )
        return False
        
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "Senha de Administrador", type="password", on_change=password_entered, key="password"
        )
        st.error("Senha incorreta")
        return False
        
    else:
        # Password is correct, check timeout
        if "last_active" in st.session_state:
            if (time.time() - st.session_state["last_active"]) > 300: # 5 minutes = 300s
                # Timed out
                del st.session_state["password_correct"]
                del st.session_state["last_active"]
                st.error("Sessão expirada por inatividade (5 min). Faça login novamente.")
                st.text_input(
                    "Senha de Administrador", type="password", on_change=password_entered, key="password"
                )
                return False
            else:
                # Active -> Reset timer
                st.session_state["last_active"] = time.time()
                return True
        else:
            # Fallback if variable missing
            st.session_state["last_active"] = time.time()
            return True

def render_sidebar_logo():
    """Renders the logo in the sidebar if available."""
    try:
        st.sidebar.image("Logo amicando.png", use_container_width=True)
    except Exception:
        pass  # Logo missing or error

def render_header_logo():
    """Renders a smaller logo in the main content header."""
    try:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            st.image("Logo amicando.png", width=200)
    except Exception:
        pass  # Logo missing or error

def save_image(uploaded_file, folder):
    """Saves an uploaded file to the specified folder. Returns the file path."""
    import os
    if uploaded_file:
        if not os.path.exists(folder):
            os.makedirs(folder)
        file_path = os.path.join(folder, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    return None
