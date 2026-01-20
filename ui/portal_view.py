# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# ui/portal_view.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.22-Portal-i18n-Features
# Description: 
# 1. [i18n] Full multilingual support for Portal.
# 2. [UI] Split layout (Creator vs Grader) with specific feature descriptions.
# 3. [Feature] Highlights "AI RAG Generation" as a Business feature.

import streamlit as st
from utils.localization import t

def render_portal(user):
    # 1. Welcome Header
    st.title(t("portal_header", "歡迎回來").format(user.real_name or user.username) + " 👋")
    st.write(t("portal_sub", "請選擇您的工作區："))
    
    st.divider()

    # 2. Dual Mode Selection (Cards)
    col_creator, col_grader = st.columns(2)

    # --- 左側：出卷中心 ---
    with col_creator:
        st.subheader(f"📝 {t('mode_creator_title', '出卷中心')}")
        
        # 特色描述 (支援 Markdown)
        desc_creator = t('mode_creator_desc', 
            "設計試卷、排版 LaTeX、編寫解答與評分標準。\n"
            "支援 **AI 輔助出題 (Business)** 與歷年試卷管理。"
        )
        st.info(desc_creator)
        
        if st.button(t('btn_enter_creator', '進入出卷模式'), use_container_width=True, type="primary"):
            st.session_state["app_mode"] = "creator"
            st.rerun()

    # --- 右側：閱卷中心 ---
    with col_grader:
        st.subheader(f"⚖️ {t('mode_grader_title', '閱卷中心')}")
        
        # 特色描述
        desc_grader = t('mode_grader_desc',
            "上傳掃描考卷、執行 AI 批改、生成統計報表。\n"
            "支援高精準度水平閱卷與班級分析。"
        )
        st.info(desc_grader)
        
        if st.button(t('btn_enter_grader', '進入閱卷模式'), use_container_width=True, type="primary"):
            st.session_state["app_mode"] = "grader"
            st.rerun()

    st.divider()
    
    # 3. Footer Info
    plan_display = user.plan.title() if user.plan else "Free"
    st.caption(f"{t('plan_label', '方案等級')}: **{plan_display}** | System Ready")
