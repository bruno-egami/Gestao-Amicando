
import streamlit as st
from services import product_service

def render_catalog(conn, products_df):
    st.subheader("📦 Catálogo de Produtos")
    
    # Grid Layout
    if products_df.empty:
        st.warning("Nenhum produto encontrado.")
    else:
        # Grid Layout
        cols_per_row = 3
        with st.container(height=800): # Scrollable Catalog
            rows = [products_df.iloc[i:i+cols_per_row] for i in range(0, len(products_df), cols_per_row)]
            
            for row_chunk in rows:
                cols = st.columns(cols_per_row)
                for idx, (c, product) in enumerate(zip(cols, row_chunk.itertuples())):
                    with c:
                        with st.container(border=True):
                            # Image Logic (Handle Kits)
                            display_thumbs = product_service.get_product_images(conn, product.id)
                            
                            if display_thumbs:
                                st.image(display_thumbs[:3], use_container_width=True)
                            else:
                                st.markdown("🖼️ *Sem Foto*")
                            
                            # Stock Logic (Handle Kits)
                            display_stock = product.stock_quantity
                            is_kit, kit_stock = product_service.get_kit_stock_status(conn, product.id)
                            
                            if is_kit:
                                display_stock = kit_stock
                            st.markdown(f"**{product.name}**")
                            
                            # Variant Logic (Visual Badges)
                            vars_df = product_service.get_product_variants(conn, product.id)
                            if not vars_df.empty:
                                vars_in_stock = vars_df[vars_df['stock_quantity'] > 0]
                                if not vars_in_stock.empty:
                                    st.markdown("<div style='margin-top: 5px; margin-bottom: 5px; font-size: 0.8em; color: #aaa;'>Esmaltes em Estoque:</div>", unsafe_allow_html=True)
                                    badges = ""
                                    for _, vr in vars_in_stock.iterrows():
                                        s_qty = vr['stock_quantity']
                                        badges += f"<div style='display: flex; justify-content: space-between; background-color: rgba(255,255,255,0.08); padding: 2px 6px; border-radius: 4px; margin-bottom: 2px; align-items: center; font-size: 0.8em;'><span style='color: #e0e0e0;'>{vr['variant_name']}</span><span style='font-weight: bold; color: #66ff66; font-family: monospace;'>{s_qty}</span></div>"
                                    st.markdown(badges, unsafe_allow_html=True)
                                else:
                                    st.caption(f"🎨 {len(vars_df)} esmaltes — sem estoque")

                            stock_txt = f"📦 Kit: {display_stock}" if is_kit else f"Est. Base: {product.stock_quantity}"
                            st.caption(f"ID: {product.id} | {stock_txt}")
                            st.markdown(f"**R$ {product.base_price:.2f}**")
                            
                            # Selection Logic
                            is_selected = (st.session_state.get('selected_product_id') == product.id)
                            if st.button("Selecionar", key=f"btn_sel_{product.id}", 
                                         type="primary" if is_selected else "secondary",
                                         use_container_width=True):
                                st.session_state['selected_product_id'] = product.id
                                st.rerun()
