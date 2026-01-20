# ui/settings_view.py
# -*- coding: utf-8 -*-
# Version: 19.9.22 (Strict Sync Edition)

import streamlit as st
import time
from database.db_manager import update_user, hash_password, login_user
from utils.localization import t, LANGUAGE_OPTIONS
from services.security import get_fingerprint_for_ui

def render_settings(user):
    """
    Nexora 系統設定頁面：確保 API 金鑰與語系偏好 100% 同步。
    """
    # 內部輔助函數：相容字典與物件格式
    def get_attr(obj, key, default=""):
        val = getattr(obj, key, None)
        if val is None and isinstance(obj, dict):
            val = obj.get(key)
        return val if val is not None else default

    st.markdown(f"## {t('settings_title', '⚙️ 系統設定')}")
    
    # 建立三個功能頁籤
    tab_keys, tab_profile, tab_sys = st.tabs([
        t("keys_header", "🔑 API 引擎配置"),
        t("settings_profile_header", "👤 個人偏好"),
        t("lbl_sys_info", "🖥️ 診斷資訊")
    ])

    # --- TAB 1: API 引擎配置 (修復金鑰消失 Bug) ---
    with tab_keys:
        st.markdown(f"### {t('keys_header')}")
        st.info("💡 建議使用 **Gemini 2.5** 系列模型以獲取最佳閱卷性能。")
        
        with st.form("newera_engine_form"):
            # 讀取當前儲存的金鑰
            current_google_key = get_attr(user, "google_key")
            new_key = st.text_input(
                "Google Gemini API Key", 
                value=current_google_key, 
                type="password",
                help="金鑰將加密儲存於本地資料庫"
            )
            
            # 模型選擇 (2026 旗艦模型)
            model_list = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-8b"]
            current_model = get_attr(user, "model_name", "gemini-2.5-pro")
            new_model = st.selectbox(
                t("lbl_model", "AI 核心模型"), 
                options=model_list,
                index=model_list.index(current_model) if current_model in model_list else 0
            )
            
            if st.form_submit_button("儲存並啟動引擎", type="primary"):
                uid = get_attr(user, "id")
                # 1. 寫入資料庫
                if update_user(uid, google_key=new_key.strip(), model_name=new_model):
                    # 2. 【核心修正】同步更新全域 Session 變數，解決閱卷功能讀不到金鑰的問題
                    if isinstance(st.session_state["user"], dict):
                        st.session_state["user"]["google_key"] = new_key.strip()
                        st.session_state["user"]["model_name"] = new_model
                    else:
                        st.session_state["user"].google_key = new_key.strip()
                        st.session_state["user"].model_name = new_model
                    
                    st.success("✅ Nexora  引擎已完成同步更新！")
                    time.sleep(0.5)
                    st.rerun()

    # --- TAB 2: 個人偏好 (多語系與安全) ---
    with tab_profile:
        st.markdown(f"### {t('settings_profile_header')}")
        
        # 語言偏好設定
        st.write("🌍 **語言設定 / Language Settings**")
        selected_lang = st.selectbox(
            "選擇介面語言",
            options=list(LANGUAGE_OPTIONS.keys()),
            format_func=lambda x: LANGUAGE_OPTIONS[x],
            index=list(LANGUAGE_OPTIONS.keys()).index(st.session_state.get("lang", "zh_tw"))
        )
        
        if st.button("更新語言 / Update Language"):
            st.session_state["lang"] = selected_lang
            # 同步至資料庫 (假設 update_user 支援 language 欄位)
            update_user(get_attr(user, "id"), language=selected_lang)
            st.success("語言設定已更新！")
            time.sleep(0.3)
            st.rerun()

        st.divider()
        st.text_input("Username", value=get_attr(user, "username"), disabled=True)
        st.text_input("Account Plan", value="Nexora Professional", disabled=True)

    # --- TAB 3: 系統診斷 (Machine ID 與版本控制) ---
    with tab_sys:
        st.markdown(f"### {t('lbl_sys_info')}")
        diag_data = [
            ("Nexora Core Version", "2026.1.14-Stable"),
            ("Active Engine", get_attr(user, "model_name")),
            ("API Connectivity", "Active" if len(get_attr(user, "google_key")) > 10 else "Inactive"),
            ("Device Fingerprint", get_fingerprint_for_ui())
        ]
        
        with st.container(border=True):
            for label, value in diag_data:
                c1, c2 = st.columns([1, 2])
                c1.markdown(f"**{label}**")
                c2.code(value, language=None)
        
        st.markdown("<br><div style='text-align:center; opacity:0.3;'>Next-Gen tools for Education powered by Nexora</div>", unsafe_allow_html=True)
