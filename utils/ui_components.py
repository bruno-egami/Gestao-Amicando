"""
Reusable UI Components conforming to the new Design System.
"""
import streamlit as st

def card_metric(label, value, delta=None, icon=None, help_text=None, color=None):
    """
    Renders a styled metric card.
    Note: Standard st.metric is already styled by styles.py, but this allows custom HTML if needed.
    """
    st.metric(label=label, value=value, delta=delta, help=help_text)

def section_header(title, subtitle=None):
    """
    Renders a standard section header with gradient text.
    """
    st.markdown(f"## {title}")
    if subtitle:
        st.caption(subtitle)
    st.markdown("---")

def status_badge(status):
    """
    Returns HTML for a status badge.
    """
    colors = {
        "Pendente": "#f59e0b", # Amber
        "Aprovado": "#10b981", # Emerald
        "Finalizada": "#3b82f6", # Blue
        "Cancelado": "#ef4444", # Red
        "Entregue": "#8b5cf6" # Violet
    }
    c = colors.get(status, "#6b7280")
    return f"<span style='background-color: {c}33; color: {c}; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; font-weight: 600; border: 1px solid {c}'>{status}</span>"
