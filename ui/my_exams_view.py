# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# ui/my_exams_view.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.22-Callback-Fix
# Description: 
# [Fix] Solved StreamlitAPIException by using on_click callback for page navigation.

import streamlit as st
import json
import time
from database.db_manager import get_user_exams_unified, get_exam_by_id
from utils.localization import t

def load_exam_to_editor(exam_id):
    """
    [Callback Function]
    這會在按鈕按下後、頁面重繪前執行。
    此時修改 page_selection 是安全的。
    """
    st.session_state['loader_selected_id'] = exam_id # 標記要載入的試卷 ID
    st.session_state.page_selection = "menu_exam_gen" # 切換頁面

def render_my_exams_view(user):
    st.title(f"🗂️ {t('menu_my_exams', '我的試卷庫')}")

    # 1. 取得所有試卷
    all_exams = get_user_exams_unified(user.id)

    if not all_exams:
        st.info("尚無試卷存檔。請前往「試卷生成」建立第一份試卷！")
        return

    # 2. 建立樹狀結構
    tree = {}
    for e in all_exams:
        subj = e.get('subject') or "未分類科目"
        year = e.get('academic_year')
        if not year:
            try: year = e['content']['meta']['year']
            except: year = "未分類年份"
            
        sem = e.get('semester') or "未分類學期"
        etype = e.get('exam_type') or "未分類型態"
        
        if subj not in tree: tree[subj] = {}
        if year not in tree[subj]: tree[subj][year] = {}
        if sem not in tree[subj][year]: tree[subj][year][sem] = {}
        if etype not in tree[subj][year][sem]: tree[subj][year][sem][etype] = []
        
        tree[subj][year][sem][etype].append(e)

    # 3. 渲染視圖
    for subj, years in sorted(tree.items()):
        with st.expander(f"📚 {subj}", expanded=True):
            for year, sems in sorted(years.items(), reverse=True):
                st.markdown(f"### 📅 {year} 學年度")
                for sem, types in sorted(sems.items()):
                    st.markdown(f"**🔹 {sem}**")
                    for etype, exams in sorted(types.items()):
                        st.caption(f"📝 {etype}")
                        
                        for exam in exams:
                            with st.container():
                                col_info, col_act = st.columns([3, 1])
                                
                                with col_info:
                                    status_icon = "🟢" if exam.get('source') == "legacy" else "🟡"
                                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{status_icon} **{exam['title']}**")
                                    st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;最後更新: {exam['updated_at']}")
                                
                                with col_act:
                                    # [FIX] 改用 on_click 機制
                                    # 注意：args 必須是 tuple，所以單一參數後面要加逗號 (exam['id'],)
                                    st.button(
                                        "♻️ 導入編輯", 
                                        key=f"clone_{exam['id']}",
                                        on_click=load_exam_to_editor,
                                        args=(exam['id'],)
                                    )
                        st.markdown("---")
