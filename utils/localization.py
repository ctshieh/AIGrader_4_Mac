# utils/localization.py
# -*- coding: utf-8 -*-
# Module-Version: 19.0.0 (Synced with App v19.3)

import streamlit as st
from .locales.zh_tw import STRINGS as zh_tw
from .locales.en import STRINGS as en
from .locales.ja import STRINGS as ja
from .locales.fr import STRINGS as fr

# 1. 載入語言包
LOCALES = {
    "zh_tw": zh_tw, 
    "en": en, 
    "ja": ja, 
    "fr": fr
}

# 2. [關鍵新增] 定義語言選項 (Single Source of Truth)
# App v19.3.0 需要這個變數來產生側邊欄選單
LANGUAGE_OPTIONS = {
    "zh_tw": "🇹🇼 繁體中文",
    "en": "🇺🇸 English",
    "ja": "🇯🇵 日本語",
    "fr": "🇫🇷 Français"
}

def get_current_lang():
    if 'lang' not in st.session_state:
        st.session_state.lang = "zh_tw"
    return st.session_state.lang

def set_language(lang_code):
    if lang_code in LANGUAGE_OPTIONS:
        st.session_state.lang = lang_code
        st.session_state["language"] = LANGUAGE_OPTIONS[lang_code] # 相容舊版
    else:
        st.session_state.lang = "zh_tw"

def t(key, default=None):
    # 優先使用新的 lang code (zh_tw)
    code = get_current_lang()
    bundle = LOCALES.get(code, {})
    
    if key in bundle:
        return bundle[key]
    
    # Fallback
    for fb in ["zh_tw", "en"]:
        fb_bundle = LOCALES.get(fb, {})
        if key in fb_bundle:
            return fb_bundle[key]
            
    return default if default is not None else key
