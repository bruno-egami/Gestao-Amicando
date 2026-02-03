import streamlit as st

import time

def check_password():
    # DEPRECATED: Use auth.require_role instead
    st.error("Function check_password is deprecated and insecure. Use auth.py.")
    return False

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
