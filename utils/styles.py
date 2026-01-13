# utils/styles.py
# -*- coding: utf-8 -*-
# Module-Version: 19.2.0 (Retina Dark Mode Fixed)

import streamlit as st

# ==============================================================================
# 1. Mac 基礎構造 (Structure) - 骨架不變，保持圓潤與優雅
# ==============================================================================
MAC_BASE_CSS = """
<style>
    /* 全局字體：Mac 系統字體 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif !important;
        -webkit-font-smoothing: antialiased;
    }

    /* 隱藏 Streamlit 雜訊 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container { padding-top: 2rem !important; padding-bottom: 3rem !important; }

    /* 元件圓角化 (Squircle) */
    .stButton > button {
        border-radius: 10px !important;
        padding: 0.4rem 1rem !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        border: none !important;
        transition: all 0.2s cubic-bezier(0.25, 0.1, 0.25, 1);
        box-shadow: 0 1px 2px rgba(0,0,0,0.1) !important;
    }
    .stButton > button:hover { transform: translateY(-0.5px); }

    .stTextInput > div > div > input,
    .stSelectbox > div > div > div,
    .stNumberInput > div > div > input {
        border-radius: 8px !important;
        height: 38px !important;
        transition: all 0.2s ease;
    }

    div[data-testid="stExpander"] {
        border-radius: 12px !important;
        border-width: 1px !important;
    }

    /* 側邊欄 Footer (Sticky) */
    .sidebar-footer {
        position: fixed; bottom: 0; left: 0; width: 20rem; padding: 1rem;
        backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
        z-index: 999; border-top-width: 1px; border-top-style: solid;
        text-align: center;
    }
    .btn-support-mac {
        display: inline-block; width: 100%; padding: 8px 0;
        font-weight: 600; text-decoration: none !important; font-size: 13px;
        border-radius: 8px; transition: all 0.2s;
    }
</style>
"""

# ==============================================================================
# 2. 主題配色 (Color Skins) - 像素級復刻 macOS
# ==============================================================================
THEMES = {
    # --------------------------------------------------------------------------
    # 🔵 Light Mode: macOS Big Sur / Monterey 風格 (乾淨、白底、藍按鈕)
    # --------------------------------------------------------------------------
    "專業商務 (Pro Blue)": """
    <style>
        .stApp { background-color: #FFFFFF !important; color: #1d1d1f !important; }
        
        /* 側邊欄：Finder 淺灰 */
        section[data-testid="stSidebar"] {
            background-color: #F5F5F7 !important;
            border-right: 1px solid #d1d1d6;
        }
        
        /* 按鈕：Standard Apple Blue */
        .stButton > button {
            background-color: #007AFF !important;
            color: white !important;
        }
        .stButton > button:hover {
            background-color: #0062cc !important;
            box-shadow: 0 4px 12px rgba(0,122,255,0.3) !important;
        }

        /* 輸入框 */
        .stTextInput > div > div > input, .stSelectbox > div > div > div {
            background-color: #FFFFFF !important;
            border: 1px solid #D1D1D6 !important;
            color: #1D1D1F !important;
        }
        .stTextInput > div > div > input:focus {
            border-color: #007AFF !important;
            box-shadow: 0 0 0 3px rgba(0,122,255,0.15) !important;
        }
        
        /* Expander */
        div[data-testid="stExpander"] {
            background-color: #FFFFFF !important;
            border-color: #E5E5EA !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.02) !important;
        }

        /* Footer */
        .sidebar-footer { background: rgba(245, 245, 247, 0.85); border-top-color: #D1D1D6; }
        .btn-support-mac {
            color: #007AFF !important;
            background: rgba(255,255,255,0.6);
            border: 1px solid rgba(0,0,0,0.05);
        }
        .btn-support-mac:hover { background: #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    </style>
    """,

    # --------------------------------------------------------------------------
    # 🌑 Dark Mode: macOS Native Dark (深灰層次、柔和藍光、不刺眼)
    # --------------------------------------------------------------------------
    "暗夜極簡 (Dark Elegant)": """
    <style>
        /* 背景：不是純黑，而是 macOS 視窗背景色 #1C1C1E */
        .stApp { background-color: #1C1C1E !important; color: #F5F5F7 !important; }
        
        /* 側邊欄：macOS 側邊欄深色 #2C2C2E (比背景稍亮) */
        section[data-testid="stSidebar"] {
            background-color: #2C2C2E !important;
            border-right: 1px solid #3A3A3C;
        }
        
        /* 按鈕：macOS Dark Blue #0A84FF (比淺色版稍亮，增加對比) */
        .stButton > button {
            background-color: #0A84FF !important; 
            color: white !important;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2) !important;
        }
        .stButton > button:hover {
            background-color: #409CFF !important;
            box-shadow: 0 0 15px rgba(10, 132, 255, 0.4) !important;
        }

        /* 輸入框：深灰底 + 邊框 */
        .stTextInput > div > div > input, .stSelectbox > div > div > div {
            background-color: #2C2C2E !important;
            border: 1px solid #3A3A3C !important;
            color: #E0E0E0 !important;
        }
        .stTextInput > div > div > input:focus {
            border-color: #0A84FF !important;
            box-shadow: 0 0 0 2px rgba(10, 132, 255, 0.25) !important;
        }
        
        /* 下拉選單文字 */
        div[data-baseweb="select"] span { color: #E0E0E0 !important; }

        /* Expander 卡片 */
        div[data-testid="stExpander"] {
            background-color: #2C2C2E !important;
            border-color: #3A3A3C !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
        }
        .streamlit-expanderHeader { color: #F5F5F7 !important; }

        /* Toast 訊息 */
        div[data-testid="stToast"] {
            background-color: #2C2C2E !important;
            color: #F5F5F7 !important;
            border: 1px solid #3A3A3C !important;
        }

        /* Footer */
        .sidebar-footer { background: rgba(44, 44, 46, 0.85); border-top-color: #3A3A3C; }
        .btn-support-mac {
            color: #0A84FF !important;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
        }
        .btn-support-mac:hover { background: rgba(255,255,255,0.1); color: #FFF !important; }
    </style>
    """,

    # --------------------------------------------------------------------------
    # 📜 Warm Mode: 類似 macOS "True Tone" 或閱讀模式 (護眼米黃)
    # --------------------------------------------------------------------------
    "溫暖紙張 (Warm Paper)": """
    <style>
        .stApp { background-color: #FAF7F2 !important; color: #4A3B32 !important; }
        
        /* 側邊欄 */
        section[data-testid="stSidebar"] {
            background-color: #F2EFE9 !important;
            border-right: 1px solid #E0D6CC;
        }
        
        /* 按鈕：大地色系 */
        .stButton > button {
            background-color: #8D6E63 !important;
            color: white !important;
        }
        .stButton > button:hover {
            background-color: #795548 !important;
            box-shadow: 0 3px 8px rgba(141, 110, 99, 0.3) !important;
        }
        
        /* 輸入框 */
        .stTextInput > div > div > input, .stSelectbox > div > div > div {
            background-color: #FFFDF9 !important;
            border: 1px solid #D7CCC8 !important;
            color: #5D4037 !important;
        }
        .stTextInput > div > div > input:focus {
            border-color: #8D6E63 !important;
            box-shadow: 0 0 0 2px rgba(141, 110, 99, 0.2) !important;
        }

        /* Footer */
        .sidebar-footer { background: rgba(242, 239, 233, 0.9); border-top-color: #E0D6CC; }
        .btn-support-mac {
            color: #5D4037 !important;
            background: rgba(255,255,255,0.5);
            border: 1px solid rgba(93, 64, 55, 0.15);
        }
        .btn-support-mac:hover { background: #fff; }
    </style>
    """
}

def apply_mac_style(theme_name="專業商務 (Pro Blue)"):
    """
    應用 Mac 風格 + 指定的配色主題
    """
    # 1. 注入基礎構造 (圓角、字體)
    st.markdown(MAC_BASE_CSS, unsafe_allow_html=True)
    
    # 2. 注入配色主題 (Fallback 到 Pro Blue)
    theme_css = THEMES.get(theme_name, THEMES["專業商務 (Pro Blue)"])
    st.markdown(theme_css, unsafe_allow_html=True)

def render_mac_sidebar_footer(url, text, tooltip):
    """
    渲染側邊欄底部 (CSS 已在 MAC_BASE_CSS 定義)
    """
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
