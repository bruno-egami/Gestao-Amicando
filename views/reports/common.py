import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
from datetime import datetime

def render_report_result():
    """Renders the standard report result based on session_state.report_data."""
    if 'report_data' not in st.session_state:
        return

    data = st.session_state.report_data
    if not data:
        return

    st.divider()
    
    # 1. Title and Info
    st.subheader(data.get('title', 'Relatório'))
    
    info = data.get('info', {})
    if info:
        cols = st.columns(len(info))
        for idx, (k, v) in enumerate(info.items()):
            cols[idx].metric(k, v)
    
    st.markdown("---")
    
    # 2. Totals/Metrics
    totals = data.get('totals', [])
    if totals:
        # Create rows of metrics (max 4 per row)
        for i in range(0, len(totals), 4):
            batch = totals[i:i+4]
            cols = st.columns(len(batch))
            for idx, (label, value) in enumerate(batch):
                cols[idx].metric(label, value)
        st.markdown("---")
    
    # 3. Charts
    # Handle both 'chart' (single) and 'charts' (list) keys
    charts = data.get('charts', [])
    if data.get('chart'):
        charts.insert(0, data['chart'])
    
    if charts:
        for chart in charts:
            if not chart: continue
            
            c_type = chart.get('type')
            c_df = chart.get('df')
            c_title = chart.get('title', '')
            
            st.markdown(f"#### {c_title}")
            
            if c_type == 'bar':
                fig = px.bar(c_df, x=chart['x'], y=chart['y'], text=chart['y'], title=c_title)
            elif c_type == 'bar_h':
                fig = px.bar(c_df, x=chart['x'], y=chart['y'], orientation='h', text=chart['x'], title=c_title)
                fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            elif c_type == 'pie':
                fig = px.pie(c_df, names=chart['names'], values=chart['values'], title=c_title)
            elif c_type == 'line':
                fig = px.line(c_df, x=chart['x'], y=chart['y'], title=c_title, markers=True)
            elif c_type == 'grouped_bar':
                fig = px.bar(c_df, x=chart['x'], y=chart['y'], color=chart['color'], barmode='group', title=c_title)
            else:
                fig = None
            
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")
    
    # 4. Data Table
    df = data.get('df')
    headers = data.get('headers', [])
    
    if df is not None and not df.empty:
        st.markdown("#### Detalhamento")
        
        # Filter columns if headers provided
        display_df = df[headers] if headers else df
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Export buttons
        c1, c2 = st.columns(2)
        
        # Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            display_df.to_excel(writer, sheet_name='Relatorio', index=False)
        
        c1.download_button(
            label="📥 Baixar em Excel",
            data=buffer.getvalue(),
            file_name=f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.ms-excel"
        )
        
        # CSV
        csv = display_df.to_csv(index=False).encode('utf-8')
        c2.download_button(
            label="📄 Baixar em CSV",
            data=csv,
            file_name=f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    elif df is not None and df.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")
