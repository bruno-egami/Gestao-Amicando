"""
Centralized CSS Styles for Gestão Amicando
Theme: Modern, Premium, Glassmorphism, Dark/Vibrant
"""
import streamlit as st

def apply_custom_style():
    st.markdown("""
        <style>
        /* --- GLOBAL VARIABLES --- */
        :root {
            --primary-color: #00d4ff; /* Cyan Neon */
            --secondary-color: #ff007f; /* Pink Neon */
            --bg-color: #0e1117; /* Dark Streamlit BG */
            --card-bg: rgba(255, 255, 255, 0.05);
            --card-border: rgba(255, 255, 255, 0.1);
            --text-color: #e0e0e0;
        }

        /* --- TYPOGRAPHY --- */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        
        html, body, [class*="css"]  {
            font-family: 'Inter', sans-serif;
        }
        
        h1, h2, h3 {
            font-weight: 800 !important;
            background: -webkit-linear-gradient(45deg, var(--primary-color), var(--secondary-color));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        /* --- SIDEBAR --- */
        [data-testid="stSidebar"] {
            background-color: #0b0e11;
            border-right: 1px solid rgba(255,255,255,0.05);
        }
        
        /* Hide default nav if customized */
        [data-testid="stSidebarNav"] {
            display: none;
        }

        /* --- CARDS (Containers) --- */
        [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
            /* Target generic containers if possible, or use specific classes */
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--card-bg);
            backdrop-filter: blur(10px);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 1rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
             border-color: var(--primary-color);
             box-shadow: 0 6px 12px rgba(0, 212, 255, 0.1);
        }

        /* --- METRICS --- */
        [data-testid="stMetric"] {
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            padding: 10px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        [data-testid="stMetricLabel"] {
            color: #aaa;
            font-size: 0.9em;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.8em;
            font-weight: 700;
            color: #fff;
        }

        /* --- BUTTONS --- */
        /* Primary */
        div.stButton > button[kind="primary"] {
            background: linear-gradient(90deg, var(--primary-color), #00aaff);
            border: none;
            color: #000;
            font-weight: 600;
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        div.stButton > button[kind="primary"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 212, 255, 0.4);
        }

        /* Secondary */
        div.stButton > button[kind="secondary"] {
            background: transparent;
            border: 1px solid var(--primary-color);
            color: var(--primary-color);
            border-radius: 8px;
        }
        div.stButton > button[kind="secondary"]:hover {
            background: rgba(0, 212, 255, 0.1);
        }
        
        /* Delete/Destructive (Custom mapping via helper might be needed, or standard if kind=secondary but red logic) */
        
        /* --- DATAFRAME / TABLE --- */
        [data-testid="stDataFrame"] {
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
        }

        /* --- ALERTS --- */
        .stAlert {
            border-radius: 8px;
            backdrop-filter: blur(5px);
        }

        </style>
    """, unsafe_allow_html=True)
