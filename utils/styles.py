# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# This software is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.

# utils/styles.py
# -*- coding: utf-8 -*-
import streamlit as st

# ==========================
# 主題定義 (Themes)
# ==========================
THEMES = {
    "專業商務 (Pro Blue)": """
        <style>
            .stApp { background-color: #f4f6f9; }
            .stSidebar { background-color: #ffffff; border-right: 1px solid #e0e0e0; }
            .stButton>button { 
                background: linear-gradient(135deg, #4B7BEC, #3867d6); 
                color: white; border: none; border-radius: 8px; font-weight: 500;
            }
            .stButton>button:hover { transform: translateY(-1px); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            /* 主題顏色變數 */
            :root { --primary-color-custom: #4B7BEC; --text-color-custom: #212121; }
        </style>
    """,
    "暗夜極簡 (Dark Elegant)": """
        <style>
            .stApp { background-color: #121212; color: #e0e0e0; }
            .stSidebar { background-color: #1E1E1E; border-right: 1px solid #333; }
            .stButton>button { 
                border: 1px solid #BB86FC; background-color: #1f1f1f; color: #BB86FC; border-radius: 8px;
            }
            .stButton>button:hover { background-color: #BB86FC; color: #121212; }
            /* 主題顏色變數 */
            :root { --primary-color-custom: #BB86FC; --text-color-custom: #e0e0e0; }
        </style>
    """,
    "溫暖紙張 (Warm Paper)": """
        <style>
            .stApp { background-color: #faf7f2; color: #5d4037; }
            .stSidebar { background-color: #f0ebe5; border-right: 1px solid #d7ccc8; }
            .stButton>button { 
                background-color: #8d6e63; color: #fff; border: none; border-radius: 8px;
            }
            .stButton>button:hover { background-color: #795548; box-shadow: 0 3px 5px rgba(0,0,0,0.1); }
            /* 主題顏色變數 */
            :root { --primary-color-custom: #8d6e63; --text-color-custom: #5d4037; }
        </style>
    """
}

# ==========================
# 側邊欄底部按鈕 & Tooltip CSS
# ==========================
SIDEBAR_FOOTER_CSS = """
<style>
    .sidebar-footer { 
        position: fixed; bottom: 10px; left: 10px; z-index: 100;
        width: 280px; 
    }
    
    .btn-sup { 
        display: flex; align-items: center; justify-content: center; gap: 8px; 
        padding: 8px 16px; 
        background: white; color: #555 !important; border: 1px solid #ccc; 
        border-radius: 20px; font-weight: 600; font-size: 14px; 
        text-decoration: none !important; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); transition: all 0.2s;
        width: 100%;
    }
    .btn-sup:hover { 
        background-color: #f8f9fa; color: var(--primary-color-custom) !important; 
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        text-decoration: none !important;
    }
    .btn-sup svg { 
        fill: var(--primary-color-custom); width: 16px; height: 16px; 
    }

    .tooltip-wrapper {
        position: relative;
        display: block; 
    }

    .tooltip-content {
        visibility: hidden;
        width: 280px; 
        background-color: #fff;
        color: #333;
        text-align: left;
        border-radius: 8px;
        padding: 15px;
        position: absolute;
        z-index: 1000;
        bottom: 110%; 
        left: 0;
        opacity: 0;
        transition: opacity 0.3s;
        box-shadow: 0 0 10px rgba(0,0,0,0.1);
        border: 1px solid #e0e0e0;
        font-size: 0.9em;
    }
    .tooltip-content h3 {
        margin-top: 0;
        font-size: 1.1em;
        color: var(--primary-color-custom);
    }
    .tooltip-content p {
        margin-bottom: 0;
        line-height: 1.4;
    }

    .tooltip-wrapper:hover .tooltip-content {
        visibility: visible;
        opacity: 1;
    }
    
    .tooltip-content::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -8px; 
        border-width: 8px;
        border-style: solid;
        border-color: #fff transparent transparent transparent;
    }
</style>
"""

def apply_theme(theme_name):
    """應用主題樣式與 Footer CSS"""
    base_css = THEMES.get(theme_name, THEMES["專業商務 (Pro Blue)"])
    st.markdown(base_css + SIDEBAR_FOOTER_CSS, unsafe_allow_html=True)
