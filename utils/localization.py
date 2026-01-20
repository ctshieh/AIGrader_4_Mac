# utils/localization.py
# -*- coding: utf-8 -*-
# Module-Version: 19.0.0 (Fixes Import Error)

import streamlit as st
from .locales.zh_tw import STRINGS as zh_tw
from .locales.en import STRINGS as en
from .locales.ja import STRINGS as ja
from .locales.fr import STRINGS as fr

LOCALES = {"zh_tw": zh_tw, "en": en, "ja": ja, "fr": fr}

# [關鍵] 這裡就是 app.py 找不到會閃退的原因
LANGUAGE_OPTIONS = {
    "zh_tw": "🇹🇼 繁體中文",
    "en": "🇺🇸 English",
    "ja": "🇯🇵 日本語",
    "fr": "🇫🇷 Français"
}

def set_language(lang_code):
    if lang_code in LANGUAGE_OPTIONS:
        st.session_state.lang = lang_code
        st.session_state["language"] = LANGUAGE_OPTIONS[lang_code]
    else:
        st.session_state.lang = "zh_tw"

def t(key, default=None):
    code = st.session_state.get("lang", "zh_tw")
    bundle = LOCALES.get(code, {})
    if key in bundle:
        return bundle[key]
    
    # Fallback
    for fb in ["zh_tw", "en"]:
        if key in LOCALES.get(fb, {}):
            return LOCALES[fb][key]
            
    return default if default is not None else key
