# ui/settings_view.py
# -*- coding: utf-8 -*-
# Version: 19.9.25 (Nexora Full Engine Sync)

import streamlit as st
import time
from database.db_manager import update_user, hash_password, login_user
from utils.localization import t
from services.security import get_fingerprint_for_ui

def render_settings(user):
    """
    Nexora 系統設定頁面：管理 API 金鑰、模型選擇與多語系偏好。
    確保資料庫寫入與 Session 記憶體 100% 同步。
    """
    
    # 安全獲取使用者屬性的內部函數 (相容 Row 物件與字典)
    def get_user_val(attr, default=""):
        val = getattr(user, attr, None)
        if val is None and isinstance(user, dict):
            val = user.get(attr)
        return val if val is not None else default

    st.markdown(f"## {t('settings_title', '⚙️ 個人設定')}")
    
    # 建立功能頁籤
    tab_keys, tab_profile, tab_sys = st.tabs([
        t("keys_header", "🔑 API 引擎配置"),
        t("settings_profile_header", "👤 個人帳戶"),
        t("lbl_sys_info", "🖥️ 診斷資訊")
    ])

    # --- TAB 1: API 引擎配置 ---
    with tab_keys:
        st.markdown(f"### {t('keys_header')}")
        st.markdown(f"> 🔗 **{t('boyk_link_text', '獲取金鑰')}**: [Google AI Studio (2026)](https://aistudio.google.com/app/apikey)")
        
        with st.form("newera_api_config_form"):
            # 【關鍵】讀取目前儲存的金鑰，解決存完變空白的問題
            current_google_key = get_user_val("google_key")
            new_key = st.text_input(
                t("google_key", "Google Gemini API Key"), 
                value=current_google_key, 
                type="password",
                help="請貼入以 AIza 開頭的金鑰"
            )
            
            # 鎖定 2026 年旗艦模型：Gemini 2.5 系列
            model_options = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-8b"]
            current_model = get_user_val("model_name", "gemini-2.5-pro")
            
            # 防呆：如果資料庫裡的模型名不在選單內，預設選第一個
            default_index = 0
            if current_model in model_options:
                default_index = model_options.index(current_model)
                
            new_model = st.selectbox(
                t("lbl_model", "預設 AI 閱卷模型"), 
                options=model_options,
                index=default_index
            )
            
            save_btn = st.form_submit_button(t("save_profile", "更新 Nexora 引擎設定"), type="primary")
            
            if save_btn:
                uid = get_user_val("id")
                # 1. 寫入資料庫
                if update_user(uid, google_key=new_key.strip(), model_name=new_model):
                    # 2. 【核心同步】解決金鑰存完讀不到的 Bug：強制更新當前 Session 物件
                    if isinstance(st.session_state["user"], dict):
                        st.session_state["user"]["google_key"] = new_key.strip()
                        st.session_state["user"]["model_name"] = new_model
                    else:
                        st.session_state["user"].google_key = new_key.strip()
                        st.session_state["user"].model_name = new_model
                    
                    st.success("✅ " + t("msg_save_success", "設定已儲存並立即生效！"))
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("❌ 儲存失敗，請檢查資料庫連線。")

    # --- TAB 2: 個人資料與偏好 ---
    with tab_profile:
        st.markdown(f"### {t('settings_profile_header')}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.text_input(t("lbl_username"), value=get_user_val("username"), disabled=True)
            st.text_input(t("real_name"), value=get_user_val("real_name"), disabled=True)
        with col2:
            st.text_input(t("col_plan", "授權方案"), value="Nexora Professional (2026)", disabled=True)
            
        st.divider()
        st.markdown("#### 🔒 修改登入密碼")
        with st.expander("點擊展開密碼變更表單"):
            with st.form("pwd_form"):
                old_p = st.text_input("舊密碼", type="password")
                new_p = st.text_input("新密碼", type="password")
                if st.form_submit_button("變更密碼"):
                    if login_user(get_user_val("username"), old_p):
                        update_user(get_user_val("id"), password_hash=hash_password(new_p))
                        st.success("密碼修改成功！")
                    else:
                        st.error("舊密碼驗證錯誤。")

    # --- TAB 3: 系統診斷資訊 ---
    with tab_sys:
        st.markdown(f"### {t('lbl_sys_info')}")
        
        # 顯示硬體指紋與軟體版本
        diag_info = [
            ("系統架構", "Nexora Intelligent Education Engine"),
            ("當前模型", get_user_val("model_name")),
            ("API 狀態", "已就緒 (Active)" if len(get_user_val("google_key")) > 10 else "未設定 (Inactive)"),
            ("裝置指紋 (Machine ID)", get_fingerprint_for_ui()),
            ("系統語系", st.session_state.get("lang", "zh_tw"))
        ]
        
        with st.container(border=True):
            for label, val in diag_info:
                cl, cr = st.columns([1, 2])
                cl.markdown(f"**{label}**")
                cr.code(val, language=None)
        
        st.markdown("""
            <div style='text-align:center; margin-top: 30px; opacity: 0.3;'>
                Nexora Tools for Education © 2026 | Bridging Academic Heritage with Intelligent Technology
            </div>
        """, unsafe_allow_html=True)
