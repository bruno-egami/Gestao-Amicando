
"""
UI Components Utility
Standardized UI elements for the application.
"""
import streamlit as st
import pandas as pd

def render_product_grid(df, selection_mode='single'):
    """
    Renders a standardized product grid with search.
    Expects df to have columns: id, name, thumb_path, base_price, stock_quantity
    """
    st.dataframe(
        df,
        column_config={
            "thumb_path": st.column_config.ImageColumn("Img", width="small"),
            "name": st.column_config.TextColumn("Produto", width="medium"),
            "base_price": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
            "stock_quantity": st.column_config.NumberColumn("Est.", format="%d"),
            "id": None # Hide ID
        },
        use_container_width=True,
        hide_index=True,
        selection_mode=selection_mode,
        on_select="rerun"
    )

def render_styled_dataframe(df, column_config=None, key=None):
    """
    Renders a consistently styled dataframe.
    """
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
        key=key
    )
