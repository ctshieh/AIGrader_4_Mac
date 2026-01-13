# utils/localization.py
# -*- coding: utf-8 -*-
# Module-Version: 18.0.3 (Architecture Optimized)

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

# 2. 定義語言選項 (Single Source of Truth)
# 這是全系統唯一的語言清單定義點
# Key = 語言代碼 (存入 Session)
# Value = 顯示名稱 (UI 選單用)
LANGUAGE_OPTIONS = {
    "zh_tw": "🇹🇼 繁體中文",
    "en": "🇺🇸 English",
    "ja": "🇯🇵 日本語",
    "fr": "🇫🇷 Français"
}

# 3. 核心函式
def get_current_lang():
    """取得當前語言代碼，預設為 zh_tw"""
    if 'lang' not in st.session_state:
        st.session_state.lang = "zh_tw"
    return st.session_state.lang

def set_language(lang_code):
    """設定語言並寫入 Session"""
    if lang_code in LANGUAGE_OPTIONS:
        st.session_state.lang = lang_code
    else:
        st.session_state.lang = "zh_tw"

def t(key, default=None):
    """
    翻譯函式
    依照 Session 中的 'lang' 代碼來查找對應字串
    """
    # 1. 取得當前語言代碼 (例如 'en')
    code = get_current_lang()
    
    # 2. 取得該語言的字典
    bundle = LOCALES.get(code, {})
    
    # 3. 查找 Key
    if key in bundle:
        return bundle[key]
    
    # 4. Fallback (如果找不到，依序找 zh_tw -> en)
    # 這是為了防止某些新 Key 尚未翻譯導致空白
    for fb in ["zh_tw", "en"]:
        fb_bundle = LOCALES.get(fb, {})
        if key in fb_bundle:
            return fb_bundle[key]
            
    # 5. 真的找不到，回傳預設值或 Key 本身
    return default if default is not None else key
