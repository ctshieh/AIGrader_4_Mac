# utils/localization.py
import streamlit as st
from .locales.zh_tw import STRINGS as zh_tw
from .locales.en import STRINGS as en
from .locales.ja import STRINGS as ja
from .locales.fr import STRINGS as fr

LOCALES = {"zh_tw": zh_tw, "en": en, "ja": ja, "fr": fr}
LANG_CODE_MAP = {"繁體中文": "zh_tw", "English": "en", "日本語": "ja", "Français": "fr"}

def t(key, default=None):
    current_lang_label = st.session_state.get("language", "繁體中文")
    lang_code = LANG_CODE_MAP.get(current_lang_label, "zh_tw")
    bundle = LOCALES.get(lang_code, {})
    if key in bundle: return bundle[key]
    # Fallback 1: zh_tw -> Fallback 2: en
    for fb in ["zh_tw", "en"]:
        fb_bundle = LOCALES.get(fb, {})
        if key in fb_bundle: return fb_bundle[key]
    return default if default is not None else key
