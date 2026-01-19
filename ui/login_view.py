# ui/login_view.py
# -*- coding: utf-8 -*-
# Version: v2026.01.20-Full-Sync-I18n

import streamlit as st
import time
import uuid

from database.db_manager import login_user
from utils.localization import t, LANGUAGE_OPTIONS, set_language # 引用語系組件

# 修正認證服務匯入路徑，確保與 app.py 一致
try:
    from services.auth_service import create_session as _create_session
except ImportError:
    try:
        from auth_service import create_session as _create_session
    except Exception:
        _create_session = None

# 品牌標籤常數
BRAND_MAIN = "AI Grader for STEM"
BRAND_SUB = "Powered by @2026 Nexora Systems"

def render_login_sidebar():
    """在登入頁面的側邊欄提供語言切換功能，解決登入前無法選語言的問題"""
    with st.sidebar:
        st.subheader("Language / 語言")
        
        # 動態載入四國語言選項
        lang_names = list(LANGUAGE_OPTIONS.values())
        curr_lang_name = st.session_state.get("language", lang_names[0])
        
        # 確保當前語言在選項中的正確索引
        try:
            curr_idx = lang_names.index(curr_lang_name)
        except ValueError:
            curr_idx = 0

        sel_lang = st.selectbox(
            "Select Language",
            lang_names,
            index=curr_idx,
            label_visibility="collapsed",
            key="login_lang_selector"
        )
        
        # 切換語言並即時整理頁面
        reverse_map = {v: k for k, v in LANGUAGE_OPTIONS.items()}
        target_code = reverse_map.get(sel_lang)
        if target_code and target_code != st.session_state.get("lang"):
            set_language(target_code)
            st.rerun()
            
        st.markdown("---")
        # 側邊欄品牌標記 (兩行格式)
        st.markdown(f"""
            <div style="text-align: center; margin-top: 20px;">
                <div style="font-size: 14px; color: #0066cc; font-weight: bold; white-space: nowrap;">{BRAND_MAIN}</div>
                <div style="font-size: 10px; color: #718096; margin-top: 2px;">{BRAND_SUB}</div>
            </div>
        """, unsafe_allow_html=True)

def render_login():
    """
    渲染完整登入頁面，包含四國語系切換與品牌視覺。
    """
    # 呼叫側邊欄渲染 (確保未登入時側邊欄仍有語系選單)
    render_login_sidebar()

    # 品牌視覺區
    st.markdown("<br>", unsafe_allow_html=True)
    _, col_brand, _ = st.columns([1, 2.5, 1])
    with col_brand:
        # 強制標題不換行 (white-space: nowrap) 並套用多國語系標語
        st.markdown(
            f"""
            <div style='text-align: center;'>
                <h1 style='font-family: serif; color: #1A365D; margin: 0; font-size: 2.5em; white-space: nowrap;'>{BRAND_MAIN}</h1>
                <p style='color: #2D3748; font-size: 1.25em; font-weight: 500; margin-top: 10px;'>{t('desc_secure_grading', 'K-16 STEM AI 智慧命題、自動閱卷與學力診斷系統')}</p>
                <div style='color: #718096; font-size: 0.85em; letter-spacing: 3px; margin-top: 5px;'>
                    UNIVERSITY │ SENIOR HIGH │ JUNIOR HIGH
                </div>
                <hr style="border: 0; height: 1px; background-image: linear-gradient(to right, rgba(0,0,0,0), rgba(0,0,0,0.15), rgba(0,0,0,0)); margin: 20px 0;">
                <p style='color: #A0AEC0; font-size: 0.8em;'>{BRAND_SUB}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # 傳統登入表單
    _, mid_col, _ = st.columns([1.2, 1.5, 1.2])
    with mid_col:
        with st.form("traditional_login_form"):
            st.subheader(t("tab_login", "登入"))
            u_name = st.text_input(t("lbl_username", "帳號"), placeholder="Username")
            u_pwd = st.text_input(t("lbl_password", "密碼"), type="password", placeholder="Password")

            submit_btn = st.form_submit_button(
                t("btn_signin", "登入"),
                type="primary",
                use_container_width=True,
            )

            if submit_btn:
                # 直接調用既有的 login_user
                user = login_user(u_name, u_pwd)
                if user:
                    st.session_state["is_authenticated"] = True
                    st.session_state["user"] = user

                    # 建立 DB session token 以支援 app.py 的 logout_user()
                    if callable(_create_session):
                        try:
                            token = str(uuid.uuid4())
                            uid = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
                            if uid is not None:
                                _create_session(uid, token)
                                st.session_state["session_token"] = token
                        except Exception:
                            # 不中斷登入流程
                            pass

                    st.success(t("msg_login_success", "登入成功"))
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(t("err_login_fail", "帳號或密碼錯誤"))
