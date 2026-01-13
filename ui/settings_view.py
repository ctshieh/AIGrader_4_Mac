# ui/settings_view.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.12-Settings-Maintenance-Added

from __future__ import annotations
__version__ = "5.3.0"

import streamlit as st
from typing import Any, Dict, List
import pytz 
import os

import database.db_manager as db_manager
from services.auth_service import update_user_profile, update_user_password
from database.db_manager import get_ai_memory_rules, update_ai_memory_rules, cleanup_old_data, get_user_by_id
from utils.localization import t
from services.plans import get_plan_config  # [New]

TIMEZONES = pytz.common_timezones

def render_settings(user: Any):
    st.title(t("settings_title"))
    
    # 取得方案權限
    plan_conf = get_plan_config(user.plan)
    
    # 根據權限決定 Tab 內容
    # 1. 基本資料 & Key (所有人都需要)
    # 2. AI 記憶 (所有人都需要)
    # 3. 品牌設定 (只有 branding=True 的方案顯示)
    # 4. 資料維護 (取代 Admin 功能，讓單機版用戶清理硬碟)
    # 5. 關於
    
    tabs_labels = [
        t("settings_profile_header"), 
        t("settings_memory_header")
    ]
    
    has_branding = plan_conf.get("branding", False)
    if has_branding:
        tabs_labels.append(t("settings_branding_header"))
        
    tabs_labels.append("資料維護 (Data)")
    tabs_labels.append("關於 (About)")
    
    tabs = st.tabs(tabs_labels)
    
    # --- Tab 1: Profile & Keys ---
    with tabs[0]:
        st.subheader(t("keys_header"))
        with st.form("api_key_form"):
            st.caption("請輸入您的 API Key (BYOK 模式)")
            new_google_key = st.text_input(t("google_key"), value=user.google_key, type="password")
            new_openai_key = st.text_input(t("openai_key"), value=user.openai_key, type="password")
            
            if st.form_submit_button(t("save_profile")):
                if db_manager.update_user(user.id, google_key=new_google_key, openai_key=new_openai_key):
                    st.success(t("profile_update_ok"))
                    st.session_state["user"] = get_user_by_id(user.id)
                    st.rerun()
                else:
                    st.error(t("profile_update_fail"))
        
        st.markdown("---")
        st.subheader(t("change_pw_header"))
        with st.form("pwd_form"):
            old_pw = st.text_input(t("old_password"), type="password")
            new_pw = st.text_input(t("new_password"), type="password")
            cfm_pw = st.text_input(t("new_password2"), type="password")
            
            if st.form_submit_button(t("change_password_btn")):
                if not update_user_password(user.id, old_pw, new_pw):
                    st.error(t("pw_update_fail")) # 密碼錯誤
                elif new_pw != cfm_pw:
                    st.error(t("pw_not_match"))
                else:
                    st.success(t("pw_update_ok"))

    # --- Tab 2: AI Memory ---
    with tabs[1]:
        st.subheader(t("ai_memory_header"))
        rules = get_ai_memory_rules(user.id)
        if rules:
            for i, r in enumerate(rules):
                c1, c2 = st.columns([5,1])
                c1.text(f"• {r}")
                if c2.button(t("delete"), key=f"del_rule_{i}"):
                    rules.pop(i)
                    update_ai_memory_rules(user.id, rules)
                    st.rerun()
        
        st.markdown("---")
        new_rule = st.text_input(t("mem_new_label"), placeholder=t("settings_new_rule_placeholder"))
        if st.button(t("add_rule")):
            if new_rule:
                rules.append(new_rule)
                update_ai_memory_rules(user.id, rules)
                st.success(t("add_ok"))
                st.rerun()

    # --- Tab 3: Branding (Conditional) ---
    current_tab_idx = 2
    if has_branding:
        with tabs[current_tab_idx]:
            st.subheader(t("settings_branding_header"))
            st.info("此處上傳的 Logo 將顯示於試卷左上角 (僅限機構版)。")
            # (這裡保留您原有的 Logo 上傳邏輯)
            uploaded_logo = st.file_uploader(t("upload_logo_label"), type=["png", "jpg", "jpeg"])
            if uploaded_logo:
                # 儲存邏輯...
                st.success("Logo uploaded (Mock)")
        current_tab_idx += 1

    # --- Tab 4: Data Maintenance (Crucial for Standalone) ---
    with tabs[current_tab_idx]:
        st.header("🧹 資料維護 (Data Maintenance)")
        st.info("此功能協助您清理過期的閱卷圖片與暫存檔，釋放硬碟空間。")
        
        c1, c2 = st.columns([2, 1])
        with c1:
            days_to_keep = st.slider("保留最近幾天的資料？", 7, 365, 30)
        with c2:
            st.write("") # Spacer
            if st.button("立即執行清理", type="primary"):
                try:
                    count = cleanup_old_data(days_to_keep)
                    st.success(f"✅ 清理完成！共移除了 {count} 筆過期批次資料。")
                except Exception as e:
                    st.error(f"清理失敗: {e}")
        current_tab_idx += 1

    # --- Tab 5: About ---
    with tabs[current_tab_idx]:
        st.caption(f"App Version: v2026.01.12 | Plan: {user.plan.title()}")
        if user.plan == "personal":
            st.caption("🔒 Personal Edition (Standalone)")
        elif user.plan == "business":
            st.caption("🏢 Business Edition (Site License)")
