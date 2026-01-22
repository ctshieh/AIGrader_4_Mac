# ui/my_exams_view.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.26-Fix-Nav-Delete
# Description: 
# 1. [Fix] 修復「導入編輯」無法跳轉的問題 (修正 Session 變數名稱)。
# 2. [Feat] 新增「刪除」按鈕，支援舊版與新版草稿刪除。

import streamlit as st
import time
from database.db_manager import get_user_exams_unified, delete_unified_exam
from utils.localization import t

def load_exam_to_editor(exam_id):
    """
    [Callback] 觸發導入編輯
    """
    # 1. 設定要載入的 ID
    st.session_state['loader_selected_id'] = exam_id
    
    # 2. [CRITICAL FIX] 強制切換頁面
    # 必須使用 page_selection_clean 並且值必須等於選單上的顯示名稱 (翻譯後)
    # 這樣 app_core.py 才會偵測到變化並切換
    target_page_name = t("menu_exam_gen") 
    st.session_state.page_selection_clean = target_page_name

def handle_delete(exam_id, user_id):
    """
    [Callback] 執行刪除
    """
    success = delete_unified_exam(exam_id, user_id)
    if success:
        st.toast(f"✅ {t('msg_deleted', '已刪除')}", icon="🗑️")
        time.sleep(0.5) # 稍作停頓讓 Toast 顯示
    else:
        st.toast(f"❌ {t('err_save_failed', '刪除失敗')}", icon="⚠️")

def render_my_exams_view(user):
    st.title(f"🗂️ {t('menu_my_exams', '我的試卷庫')}")

    # 1. 取得所有試卷
    all_exams = get_user_exams_unified(user.id)

    if not all_exams:
        st.info(t('msg_no_sets', "尚無試卷存檔。"))
        return

    # 2. 建立分類樹 (科目 -> 年份 -> 學期 -> 類型)
    tree = {}
    for e in all_exams:
        # 處理資料欄位可能的缺失
        header = e.get('content', {}).get('header', {})
        
        subj = e.get('subject') or header.get('subject') or "未分類科目"
        
        # 優先使用外層欄位，若無則找 content 內層
        year = e.get('academic_year') or header.get('academic_year') or "未分類年份"
        sem = e.get('semester') or header.get('semester') or "未分類學期"
        etype = e.get('exam_type') or header.get('exam_type') or "未分類型態"
        
        if subj not in tree: tree[subj] = {}
        if year not in tree[subj]: tree[subj][year] = {}
        if sem not in tree[subj][year]: tree[subj][year][sem] = {}
        if etype not in tree[subj][year][sem]: tree[subj][year][sem][etype] = []
        
        tree[subj][year][sem][etype].append(e)

    # 3. 渲染視圖
    for subj, years in sorted(tree.items()):
        with st.expander(f"📚 {subj}", expanded=True):
            for year, sems in sorted(years.items(), reverse=True):
                st.markdown(f"### 📅 {year}")
                for sem, types in sorted(sems.items()):
                    st.markdown(f"**🔹 {sem}**")
                    for etype, exams in sorted(types.items()):
                        st.caption(f"📝 {etype}")
                        
                        for exam in exams:
                            with st.container():
                                c_info, c_edit, c_del = st.columns([6, 2, 1])
                                
                                # A. 資訊欄
                                with c_info:
                                    is_legacy = exam.get('source') == "legacy"
                                    icon = "🔒" if is_legacy else "📄"
                                    source_text = "(舊版存檔)" if is_legacy else ""
                                    
                                    st.markdown(f"#### {icon} {exam['title']} {source_text}")
                                    st.caption(f"Update: {exam['updated_at']}")
                                
                                # B. 導入編輯按鈕
                                with c_edit:
                                    st.button(
                                        f"✏️ {t('lbl_select_edit', '導入編輯')}", 
                                        key=f"edit_{exam['id']}",
                                        on_click=load_exam_to_editor,
                                        args=(exam['id'],),
                                        use_container_width=True,
                                        type="primary"
                                    )
                                
                                # C. 刪除按鈕 (本次新增)
                                with c_del:
                                    st.button(
                                        "🗑️", 
                                        key=f"del_{exam['id']}",
                                        on_click=handle_delete,
                                        args=(exam['id'], user.id),
                                        type="secondary",
                                        help="刪除此試卷"
                                    )
                        st.markdown("---")
