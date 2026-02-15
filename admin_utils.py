import streamlit as st



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
        # Security: Unique filename
        import uuid
        ext = os.path.splitext(uploaded_file.name)[1]
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(folder, unique_name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    return None

@st.dialog("Notificação")
def show_feedback_dialog(message, level="success", sub_message=None, title=None):
    """
    Shows a persistent dialog for success, error, warning, or info messages.
    Requires user interaction to close and refresh the app.
    """
    icons = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️"
    }
    
    default_titles = {
        "success": "Operação Concluída",
        "error": "Erro ou Problema",
        "warning": "Atenção / Aviso",
        "info": "Informação"
    }
    
    display_title = title if title else default_titles.get(level, "Notificação")
    icon = icons.get(level, "🔔")
    
    st.markdown(f"### {icon} {display_title}")
    st.markdown(f"**{message}**")
    
    if sub_message:
        st.markdown("---")
        st.markdown(sub_message)
    
    st.divider()
    if st.button("Fechar e Atualizar", type="primary", use_container_width=True):
        st.rerun()

@st.dialog("Atenção: Confirmação")
def show_confirmation_dialog(message, action_label="Sim, continuar", on_confirm=None):
    """
    Standard confirmation dialog.
    """
    st.warning(f"**{message}**")
    st.write("Esta ação pode ser irreversível ou impactar outros registros.")
    
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", use_container_width=True):
        st.rerun()
    if c2.button(action_label, type="primary", use_container_width=True):
        if on_confirm:
            on_confirm()
        st.rerun()
