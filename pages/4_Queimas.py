import streamlit as st
import pandas as pd
import database
import admin_utils
import auth
from datetime import datetime
import os
from services import firing_service

st.set_page_config(page_title="Queimas", page_icon="🔥", layout="wide")

# Apply Global Styles
import utils.styles as styles
styles.apply_custom_style()

admin_utils.render_sidebar_logo()

conn = database.get_connection()

if not auth.require_login(conn):
    st.stop()

if not auth.check_page_access("Queimas"):
    st.stop()

auth.render_custom_sidebar()
st.title("Gestão de Queimas e Manutenção de Fornos")

# Fetch Kilns
kiln_map = firing_service.get_kilns(conn)
kiln_options = list(kiln_map.keys())

# Fetch Categories for Maintenance
maint_categories = ["Resistência", "Termopar", "Estrutura", "Elétrica", "Outro"]

# Session State for Editing
if "firing_edit_id" not in st.session_state:
    st.session_state.firing_edit_id = None

tab1, tab2 = st.tabs(["🔥 Queimas", "🛠️ Manutenção do Forno"])

# ==========================================
# TAB 1: QUEIMAS (Firings)
# ==========================================
with tab1:
    col_new, col_hist = st.columns([1, 2])
    
    # --- Nova / Editar Queima ---
    with col_new:
        is_edit = st.session_state.firing_edit_id is not None
        form_title = "Editar Queima" if is_edit else "Registrar Nova Queima"
        
        st.subheader(form_title)
        
        # Load data if editing
        default_data = {}
        if is_edit:
            try:
                row_edit = firing_service.get_firing_by_id(conn, st.session_state.firing_edit_id)
                if row_edit is not None:
                    default_data = row_edit
                else:
                    raise ValueError("Queima não encontrada")
            except Exception:
                admin_utils.show_feedback_dialog("Erro ao carregar dados.", level="error")
                st.session_state.firing_edit_id = None
                st.rerun()
                
        if is_edit and st.button("⬅️ Cancelar Edição"):
            st.session_state.firing_edit_id = None
            st.rerun()

        with st.form("firing_form"):
            # Defaults
            d_date = datetime.strptime(default_data['date'], '%Y-%m-%d').date() if is_edit and default_data.get('date') else datetime.now()
            
            # Kiln Index
            d_kiln_idx = 0
            if is_edit and default_data.get('kiln_id'):
                k_name = next((k for k, v in kiln_map.items() if v == default_data['kiln_id']), None)
                if k_name in kiln_options:
                    d_kiln_idx = kiln_options.index(k_name)

            # Type Index
            types = ["Biscoito", "Esmalte", "Outro"]
            d_type_idx = types.index(default_data['type']) if is_edit and default_data.get('type') in types else 0
            
            # Values
            d_cons = float(default_data['power_consumption_kwh']) if is_edit else 0.0
            d_cost = float(default_data['cost']) if is_edit else 0.0
            
            date = st.date_input("Data", d_date, format="DD/MM/YYYY")
            sel_kiln = st.selectbox("Forno Utilizado", kiln_options, index=d_kiln_idx)
            f_type = st.selectbox("Tipo de Queima", types, index=d_type_idx)
            
            st.markdown("#### Energia")
            
            if not is_edit:
                 c1, c2 = st.columns(2)
                 start_kwh = c1.number_input("Leitura Inicial", min_value=0.0, step=0.1, format="%.1f")
                 end_kwh = c2.number_input("Leitura Final", min_value=0.0, step=0.1, format="%.1f")
                 calc_cons = max(0.0, end_kwh - start_kwh)
                 if calc_cons > 0: d_cons = calc_cons
            
            consumption = st.number_input("Consumo (kWh)", min_value=0.0, step=0.1, value=d_cons, format="%.1f")
            kwh_price = st.number_input("Preço kWh (R$)", min_value=0.0, step=0.01, value=0.80)
            
            cost_calc = consumption * kwh_price
            cost = st.number_input("Custo Total (R$)", min_value=0.0, step=0.01, value=cost_calc if not is_edit else d_cost)

            obs = st.text_area("Observações / Peças", placeholder="Descreva as peças...", value=default_data.get('observation', '') if is_edit else "")
            
            # Image
            if is_edit and default_data.get('image_path'):
                 st.write("Imagem Atual:")
                 if os.path.exists(default_data['image_path']):
                     st.image(default_data['image_path'], width=100)
            
            img_file = st.file_uploader("Foto da Fornada", type=["jpg", "png", "jpeg", "webp"])
            
            btn_txt = "Salvar Alterações" if is_edit else "Registrar Queima"
            submitted = st.form_submit_button(btn_txt)
            
            if submitted:
                # Image Logic
                final_img_path = default_data.get('image_path')
                if img_file:
                    final_img_path = admin_utils.save_image(img_file, "assets/firing_images")
                
                k_id = kiln_map[sel_kiln]
                
                firing_data = {
                    'date': date,
                    'type': f_type,
                    'power_consumption_kwh': consumption,
                    'cost': cost,
                    'kiln_id': k_id,
                    'observation': obs,
                    'image_path': final_img_path
                }

                try:
                    if is_edit:
                        firing_service.update_firing(conn, st.session_state.firing_edit_id, firing_data)
                        admin_utils.show_feedback_dialog("Queima atualizada!", level="success")
                        st.session_state.firing_edit_id = None
                    else:
                        firing_service.create_firing(conn, firing_data)
                        admin_utils.show_feedback_dialog("Queima registrada!", level="success")
                    
                    st.rerun()
                except Exception as e:
                    admin_utils.show_feedback_dialog(f"Erro ao salvar: {e}", level="error")

    # --- Histórico Queimas ---
    with col_hist:
        st.subheader("Histórico de Queimas")
        
        # Filters
        fc1, fc2, fc3 = st.columns(3)
        fil_kiln = fc1.selectbox("Filtrar Forno", ["Todos"] + kiln_options)
        fil_type = fc2.selectbox("Filtrar Tipo", ["Todos", "Biscoito", "Esmalte", "Outro"])
        fil_date = fc3.date_input("Intervalo Data", [], format="DD/MM/YYYY") 

        # Using Service
        filters = {
            'kiln_name': fil_kiln,
            'type': fil_type,
            'start_date': fil_date[0] if len(fil_date) == 2 else None,
            'end_date': fil_date[1] if len(fil_date) == 2 else None
        }
        
        df_firings = firing_service.get_firings(conn, filters)
        
        if not df_firings.empty:
            for i, row in df_firings.iterrows():
                # Title with kWh
                exp_title = f"{row['date']} | {row['forno']} | {row['type']} | {row['power_consumption_kwh']:.1f} kWh | R$ {row['cost']:.2f}"
                with st.expander(exp_title):
                    c_info, c_img = st.columns([2, 1])
                    with c_info:
                        st.write(f"**Consumo:** {row['power_consumption_kwh']:.1f} kWh")
                        st.write(f"**Observações:** {row['observation']}")
                        
                        c_edit, c_del = st.columns(2)
                        
                        if c_edit.button("✏️ Editar", key=f"ed_f_{row['id']}"):
                            st.session_state.firing_edit_id = row['id']
                            st.rerun()
                            
                        if c_del.button("🗑️ Excluir", key=f"del_f_{row['id']}"):
                            firing_service.delete_firing(conn, row['id'])
                            st.rerun()
                            
                    with c_img:
                        if row['image_path'] and os.path.exists(row['image_path']):
                            st.image(row['image_path'], caption="Fornada")
                        else:
                            st.write("Sem foto")
        else:
            st.info("Nenhuma queima registrada.")

# Session State for Editing Maintenance
if "maint_edit_id" not in st.session_state:
    st.session_state.maint_edit_id = None

with tab2:
    col_m_new, col_m_hist = st.columns([1, 2])
    
    # --- Nova / Editar Manutenção ---
    with col_m_new:
        is_m_edit = st.session_state.maint_edit_id is not None
        m_title = "Editar Manutenção" if is_m_edit else "Registrar Manutenção"
        st.subheader(m_title)
        
        # Load Defaults
        m_default = {}
        if is_m_edit:
            try:
                m_row = firing_service.get_maintenance_by_id(conn, st.session_state.maint_edit_id)
                if m_row is not None:
                    m_default = m_row
                else:
                    raise ValueError("Manutenção não encontrada")
            except Exception:
                admin_utils.show_feedback_dialog("Erro ao carregar dados.", level="error")
                st.session_state.maint_edit_id = None
                st.rerun()
        
        if is_m_edit and st.button("⬅️ Cancelar Edição", key="cancel_m_edit"):
             st.session_state.maint_edit_id = None
             st.rerun()

        with st.form("new_maint"):
            d_m_date = datetime.strptime(m_default['date'], '%Y-%m-%d').date() if is_m_edit and m_default.get('date') else datetime.now()
            
            # Kiln Index
            d_mkiln_idx = 0
            if is_m_edit and m_default.get('kiln_id'):
                kname = next((k for k, v in kiln_map.items() if v == m_default['kiln_id']), None)
                if kname in kiln_options: d_mkiln_idx = kiln_options.index(kname)

            # Cat Index
            d_cat_idx = maint_categories.index(m_default['category']) if is_m_edit and m_default.get('category') in maint_categories else 0

            m_date = st.date_input("Data", d_m_date)
            m_kiln = st.selectbox("Forno", kiln_options, index=d_mkiln_idx, key="m_kiln_sel")
            m_cat = st.selectbox("Categoria", maint_categories, index=d_cat_idx)
            
            m_desc = st.text_input("Descrição Curta", placeholder="Ex: Troca de resistência", value=m_default.get('description', '') if is_m_edit else "")
            m_obs = st.text_area("Observações Detalhadas", value=m_default.get('observation', '') if is_m_edit else "")
            
            # Image
            if is_m_edit and m_default.get('image_path'):
                 st.write("Imagem Atual:")
                 if os.path.exists(m_default['image_path']):
                     st.image(m_default['image_path'], width=100)
            
            m_img = st.file_uploader("Foto da Manutenção", type=["jpg", "png", "jpeg", "webp"], key="m_img_upl")
            
            btn_mtxt = "Salvar Alterações" if is_m_edit else "Salvar Manutenção"
            if st.form_submit_button(btn_mtxt):
                # Image
                final_m_img = m_default.get('image_path')
                if m_img:
                    final_m_img = admin_utils.save_image(m_img, "assets/maintenance_images")
                
                mk_id = kiln_map[m_kiln]
                
                maint_data = {
                    'kiln_id': mk_id,
                    'date': m_date,
                    'category': m_cat,
                    'description': m_desc,
                    'observation': m_obs,
                    'image_path': final_m_img
                }
                
                try:
                    if is_m_edit:
                        firing_service.update_maintenance(conn, st.session_state.maint_edit_id, maint_data)
                        admin_utils.show_feedback_dialog("Manutenção Atualizada!", level="success")
                        st.session_state.maint_edit_id = None
                    else:
                        firing_service.create_maintenance(conn, maint_data)
                        admin_utils.show_feedback_dialog("Manutenção Registrada!", level="success")
                    
                    st.rerun()
                except Exception as e:
                    admin_utils.show_feedback_dialog(f"Erro ao salvar: {e}", level="error")
                
    # --- Histórico Manutenção ---
    with col_m_hist:
        st.subheader("Histórico de Manutenções")
        
        # Filters
        mf1, mf2, mf3 = st.columns(3)
        mfil_kiln = mf1.selectbox("Filtrar Forno", ["Todos"] + kiln_options, key="mfil_kiln")
        mfil_cat = mf2.selectbox("Filtrar Categoria", ["Todas"] + maint_categories, key="mfil_cat")
        mfil_date = mf3.date_input("Intervalo Data", [], key="mfil_date")

        # Using Service
        m_filters = {
            'kiln_name': mfil_kiln,
            'category': mfil_cat,
            'start_date': mfil_date[0] if len(mfil_date) == 2 else None,
            'end_date': mfil_date[1] if len(mfil_date) == 2 else None
        }
        
        df_maint = firing_service.get_maintenance_records(conn, m_filters)
        
        if not df_maint.empty:
            for i, row in df_maint.iterrows():
                with st.expander(f"{row['date']} - {row['forno']} [{row['category']}]"):
                    c_minfo, c_mimg = st.columns([2, 1])
                    with c_minfo:
                        st.markdown(f"**{row['description']}**")
                        st.write(row['observation'])
                        
                        c_medit, c_mdel = st.columns(2)
                        
                        if c_medit.button("✏️ Editar", key=f"ed_m_{row['id']}"):
                            st.session_state.maint_edit_id = row['id']
                            st.rerun()
                            
                        if c_mdel.button("🗑️ Excluir", key=f"del_m_{row['id']}"):
                             firing_service.delete_maintenance(conn, row['id'])
                             st.rerun()
                    with c_mimg:
                        if row['image_path'] and os.path.exists(row['image_path']):
                            st.image(row['image_path'])
        else:
            st.info("Nenhuma manutenção registrada.")

conn.close()
