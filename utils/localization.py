# utils/localization.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.26-11-Langs-Titan
# Description: 
# 1. 新增簡體中文 (Simplified Chinese) 支援。
# 2. 註冊全 11 國語言。

import streamlit as st

# ==============================================================================
# 1. 匯入語言檔 (Import Locales)
# ==============================================================================
# [Tier 1] 核心語言
try:
    from .locales.zh_tw import STRINGS as zh_tw
    from .locales.en import STRINGS as en
    from .locales.ja import STRINGS as ja
    from .locales.fr import STRINGS as fr
except ImportError as e:
    print(f"Critical Locale Missing: {e}")
    zh_tw = {}
    en = {}
    ja = {}
    fr = {}

# [Tier 1.5] 中文圈擴充 (New)
try: from .locales.zh_cn import STRINGS as zh_cn
except ImportError: zh_cn = zh_tw

# [Tier 2] 亞洲擴充
try: from .locales.ko import STRINGS as ko
except ImportError: ko = en
try: from .locales.vi import STRINGS as vi
except ImportError: vi = en
try: from .locales.id import STRINGS as id_lang
except ImportError: id_lang = en

# [Tier 3] 全球擴充
try: from .locales.es import STRINGS as es
except ImportError: es = en
try: from .locales.pt import STRINGS as pt
except ImportError: pt = en
try: from .locales.tr import STRINGS as tr
except ImportError: tr = en

# ==============================================================================
# 2. 註冊語言包 (Register Bundles)
# ==============================================================================
LOCALES = {
    "zh_tw": zh_tw,
    "zh_cn": zh_cn, # New
    "en": en,
    "ja": ja,
    "fr": fr,
    "ko": ko,
    "vi": vi,
    "id": id_lang,
    "es": es,
    "pt": pt,
    "tr": tr
}

# ==============================================================================
# 3. 定義顯示名稱 (Display Names)
# ==============================================================================
LANGUAGE_OPTIONS = {
    "zh_tw": "🇹🇼 Traditional Chinese (繁體中文)",
    "zh_cn": "🇨🇳 Simplified Chinese (简体中文)", # New
    "en": "🇺🇸 English",
    "ja": "🇯🇵 Japanese (日本語)",
    "fr": "🇫🇷 French (Français)",
    "es": "🇪🇸 Spanish (Español)",
    "pt": "🇧🇷 Portuguese (Português do Brasil)",
    "tr": "🇹🇷 Turkish (Türkçe)",
    "ko": "🇰🇷 Korean (한국어)",
    "vi": "🇻🇳 Vietnamese (Tiếng Việt)",
    "id": "🇮🇩 Indonesian (Bahasa Indonesia)"
}

# ==============================================================================
# 4. 核心函式
# ==============================================================================
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
    
    # Fallback: 簡中缺字找繁中 -> 再找英文
    fallback_chain = ["en", "zh_tw"]
    if code == "zh_cn":
        fallback_chain.insert(0, "zh_tw")
    
    for fb in fallback_chain:
        fb_bundle = LOCALES.get(fb, {})
        if key in fb_bundle:
            return fb_bundle[key]
            
    return default if default is not None else key
