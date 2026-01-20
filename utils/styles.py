# utils/styles.py
# -*- coding: utf-8 -*-
# Module-Version: 19.2.0 (Mac Native Style)

import streamlit as st

MAC_BASE_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", Helvetica, Arial, sans-serif !important;
        -webkit-font-smoothing: antialiased;
    }
    #MainMenu, footer, header {visibility: hidden;}
    .block-container { padding-top: 2rem !important; padding-bottom: 3rem !important; }
    
    /* Mac Buttons */
    .stButton > button {
        border-radius: 10px !important;
        border: none !important;
        padding: 0.4rem 1rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1) !important;
    }
    .stButton > button:hover { transform: translateY(-1px); }
    
    /* Inputs */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > div {
        border-radius: 8px !important;
        height: 38px !important;
    }
    
    /* Sidebar Footer */
    .sidebar-footer {
        position: fixed; bottom: 0; left: 0;
        width: 20rem; padding: 1rem;
        backdrop-filter: blur(10px);
        z-index: 999;
        border-top: 1px solid rgba(0,0,0,0.05);
        text-align: center;
    }
    .btn-support-mac {
        display: inline-block; width: 100%; padding: 8px 0;
        font-weight: 600; text-decoration: none !important;
        font-size: 13px; border-radius: 8px;
        transition: all 0.2s;
    }
</style>
"""

THEMES = {
    "專業商務 (Pro Blue)": """
    <style>
        .stApp { background-color: #FFFFFF !important; color: #1d1d1f !important; }
        section[data-testid="stSidebar"] { background-color: #F5F5F7 !important; border-right: 1px solid #d1d1d6; }
        .stButton > button { background-color: #007AFF !important; color: white !important; }
        .stButton > button:hover { background-color: #0062cc !important; }
        .stTextInput > div > div > input { background-color: #ffffff !important; border: 1px solid #d1d1d6 !important; color: #1d1d1f !important; }
        .sidebar-footer { background: rgba(245, 245, 247, 0.85); }
        .btn-support-mac { color: #007AFF !important; background: rgba(255,255,255,0.6); border: 1px solid rgba(0,0,0,0.05); }
        .btn-support-mac:hover { background: #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    </style>
    """,
    "暗夜極簡 (Dark Elegant)": """
    <style>
        .stApp { background-color: #1C1C1E !important; color: #F5F5F7 !important; }
        section[data-testid="stSidebar"] { background-color: #2C2C2E !important; border-right: 1px solid #3A3A3C; }
        .stButton > button { background-color: #0A84FF !important; color: white !important; }
        .stButton > button:hover { background-color: #409CFF !important; }
        .stTextInput > div > div > input, .stSelectbox > div > div > div { background-color: #2C2C2E !important; border: 1px solid #3A3A3C !important; color: #E0E0E0 !important; }
        div[data-testid="stExpander"] { background-color: #2C2C2E !important; border-color: #3A3A3C !important; }
        .streamlit-expanderHeader { color: #F5F5F7 !important; }
        .sidebar-footer { background: rgba(44, 44, 46, 0.85); border-top-color: #3A3A3C; }
        .btn-support-mac { color: #0A84FF !important; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); }
        .btn-support-mac:hover { background: rgba(255,255,255,0.1); color: #FFF !important; }
    </style>
    """,
    "溫暖紙張 (Warm Paper)": """
    <style>
        .stApp { background-color: #FAF7F2 !important; color: #4A3B32 !important; }
        section[data-testid="stSidebar"] { background-color: #F2EFE9 !important; border-right: 1px solid #E0D6CC; }
        .stButton > button { background-color: #8D6E63 !important; color: white !important; }
        .stTextInput > div > div > input { background-color: #FFFDF9 !important; border: 1px solid #D7CCC8 !important; color: #5D4037 !important; }
        .sidebar-footer { background: rgba(242, 239, 233, 0.9); border-top-color: #E0D6CC; }
        .btn-support-mac { color: #5D4037 !important; background: rgba(255,255,255,0.5); border: 1px solid rgba(93, 64, 55, 0.15); }
    </style>
    """
}

def apply_mac_style(theme_name="專業商務 (Pro Blue)"):
    # 注入基礎 CSS
    st.markdown(MAC_BASE_CSS, unsafe_allow_html=True)
    # 注入主題 CSS
    theme_css = THEMES.get(theme_name, THEMES["專業商務 (Pro Blue)"])
    st.markdown(theme_css, unsafe_allow_html=True)

def render_mac_sidebar_footer(url, text, tooltip):
    import html
    safe_url = html.escape(url)
    safe_text = html.escape(text)
    safe_tip = html.escape(tooltip)
    
    st.sidebar.markdown(f"""
        <div class="sidebar-footer" title="{safe_tip}">
            <a href="{safe_url}" target="_blank" class="btn-support-mac">
               ❤️ {safe_text}
            </a>
        </div>
    """, unsafe_allow_html=True)
