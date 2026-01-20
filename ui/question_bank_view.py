# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# This software is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.

# ui/question_bank_view.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.22-Bank-UX-Success-Msg
# Description: 
# 1. [UX Fix] Implemented persistent Success Messages using Session State.
#    - Ensures "Add Success" or "Update Success" messages survive st.rerun().
#    - Prevents double-submission confusion.
# 2. [Feature] Retains all previous logic (Smart UI, 3-Level Taxonomy, Edit Mode).

import streamlit as st
import json
import time
import ast
import os
from utils.localization import t
from database.db_manager import (
    get_all_questions, save_question, update_question, delete_question,
    create_question_set, get_user_question_sets, 
    get_question_set_items, delete_question_set
)
from services.pdf_service import save_uploaded_file

# ------------------------------------------------------------------------------
# Constants & Helpers
# ------------------------------------------------------------------------------

def get_difficulty_options():
    return [
        t('diff_easy', "🟢 簡單 (Easy)"),
        t('diff_medium', "🟡 中等 (Medium)"),
        t('diff_hard', "🔴 困難 (Hard)")
    ]

def get_type_options():
    return [
        t('type_calc_normal', "計算題 (一般)"),
        t('type_calc_large', "計算題 (大格)"),
        t('type_choice', "選擇題 (Multiple Choice)"),
        t('type_proof', "證明題 (Proof)"),
        t('type_tf', "是非題 (True/False)"),
        t('type_fill', "填充題 (Fill-in)")
    ]

def build_taxonomy_tree(questions):
    """
    從現有題目中提取三層結構: Subject -> Chapter -> Section
    Returns: dict { subject: { chapter: set(sections) } }
    """
    tree = {}
    for q in questions:
        meta = q.get('meta', {})
        if isinstance(meta, str):
            try: meta = json.loads(meta)
            except: meta = {}
        
        s = meta.get('subject', '').strip()
        c = meta.get('chapter', '').strip()
        sec = meta.get('section', '').strip()
        
        if s:
            if s not in tree: tree[s] = {}
            if c:
                if c not in tree[s]: tree[s][c] = set()
                if sec:
                    tree[s][c].add(sec)
    return tree

def render_question_editor(user, questions, taxonomy_tree, sorted_subjects, q_id=None, on_success=None, on_cancel=None):
    """
    共用編輯器邏輯 (用於 新增 與 修改)
    """
    is_edit = (q_id is not None)
    target_q = None
    default_meta = {}
    
    if is_edit:
        target_q = next((q for q in questions if q['id'] == q_id), None)
        if target_q:
            raw_meta = target_q.get('meta', {})
            if isinstance(raw_meta, str):
                try: default_meta = json.loads(raw_meta)
                except: default_meta = {}
            else: default_meta = raw_meta

    # Key prefix to avoid collisions
    k_pfx = f"edit_{q_id}" if is_edit else "add_new"
    
    # Header
    if is_edit:
        st.subheader(f"✏️ {t('header_edit_q', '編輯題目')} #{q_id}")
    else:
        st.subheader(f"➕ {t('header_add_q', '新增題目')}")

    # 1. Classification
    st.markdown(f"##### 1. {t('lbl_classification', '分類設定')}")
    c_meta1, c_meta2, c_meta3 = st.columns(3)
    
    create_new_label = f"✏️ {t('opt_create_new', '自訂新項目...')}"

    # -- Subject --
    def_subj = default_meta.get('subject', 'All')
    subj_opts = sorted_subjects + [create_new_label]
    
    idx_s = 0
    if def_subj in subj_opts: idx_s = subj_opts.index(def_subj)
    
    sel_subj = c_meta1.selectbox(f"📚 {t('lbl_subject', '科目')}", subj_opts, index=idx_s, key=f"{k_pfx}_subj")
    
    final_subj = sel_subj
    is_new_subj = (sel_subj == create_new_label)
    if is_new_subj:
        final_subj = c_meta1.text_input(f"↳ {t('lbl_new_subj', '輸入新科目')}", key=f"{k_pfx}_new_subj")

    # -- Chapter --
    existing_chaps = []
    if not is_new_subj and final_subj in taxonomy_tree:
        existing_chaps = sorted(list(taxonomy_tree[final_subj].keys()))
        
    def_chap = default_meta.get('chapter', '')
    
    if is_new_subj or not existing_chaps:
        final_chap = c_meta2.text_input(f"📑 {t('lbl_chapter', '章節')}", value=def_chap, key=f"{k_pfx}_chap_txt")
        is_new_chap = True
    else:
        chap_opts = existing_chaps + [create_new_label]
        idx_c = 0
        if def_chap in chap_opts: idx_c = chap_opts.index(def_chap)
        
        sel_chap = c_meta2.selectbox(f"📑 {t('lbl_chapter', '章節')}", chap_opts, index=idx_c, key=f"{k_pfx}_chap_sel")
        final_chap = sel_chap
        is_new_chap = (sel_chap == create_new_label)
        if is_new_chap:
            final_chap = c_meta2.text_input(f"↳ {t('lbl_new_chap', '輸入新章節')}", key=f"{k_pfx}_new_chap")

    # -- Section --
    def_sec = default_meta.get('section', '')
    existing_secs = []
    if not is_new_subj and not is_new_chap and final_subj in taxonomy_tree and final_chap in taxonomy_tree[final_subj]:
        existing_secs = sorted(list(taxonomy_tree[final_subj][final_chap]))
        
    if is_new_subj or is_new_chap or not existing_secs:
        final_sec = c_meta3.text_input(f"📍 {t('lbl_section', '小節')}", value=def_sec, key=f"{k_pfx}_sec_txt")
    else:
        sec_opts = existing_secs + [create_new_label]
        idx_sec = 0
        if def_sec in sec_opts: idx_sec = sec_opts.index(def_sec)
        
        sel_sec = c_meta3.selectbox(f"📍 {t('lbl_section', '小節')}", sec_opts, index=idx_sec, key=f"{k_pfx}_sec_sel")
        final_sec = sel_sec
        if sel_sec == create_new_label:
            final_sec = c_meta3.text_input(f"↳ {t('lbl_new_sec', '輸入新小節')}", key=f"{k_pfx}_new_sec")

    # -- Diff --
    def_diff = default_meta.get('difficulty', get_difficulty_options()[0])
    diff_opts = get_difficulty_options()
    idx_d = 0
    if def_diff in diff_opts: idx_d = diff_opts.index(def_diff)
    final_diff = c_meta1.selectbox(f"📊 {t('lbl_difficulty', '難易度')}", diff_opts, index=idx_d, key=f"{k_pfx}_diff")

    st.markdown("---")

    # 2. Content
    st.markdown(f"##### 2. {t('lbl_content', '題目詳細內容')}")
    
    def_content = target_q['content'] if target_q else ""
    q_text = st.text_area(t('lbl_q_text', '題目敘述 (支援 LaTeX)'), height=100, value=def_content, key=f"{k_pfx}_content")
    
    c_p1, c_p2, c_p3 = st.columns(3)
    
    def_type = default_meta.get('type', get_type_options()[0])
    type_opts = get_type_options()
    idx_t = 0
    if def_type in type_opts: idx_t = type_opts.index(def_type)
    q_type = c_p1.selectbox(t('gen_type_label', '題型'), type_opts, index=idx_t, key=f"{k_pfx}_type")
    
    def_h = default_meta.get('height', 6)
    q_height = c_p3.number_input(t('gen_height_label', '作答區高度 (cm)'), 2, 25, value=int(def_h), key=f"{k_pfx}_h")
    
    options = []
    sub_questions = []
    parent_score = 0
    layout_cols = 1
    
    # 判斷邏輯
    if "選擇題" in q_type or "Choice" in q_type:
        st.info(f"🔹 {t('mode_choice', '選擇題模式')}")
        def_opts = default_meta.get('options', [])
        opts_val = "\n".join(def_opts) if def_opts else ""
        opts_text = st.text_area(t('lbl_options', '選項 (每行一個)'), height=80, value=opts_val, key=f"{k_pfx}_opts")
        if opts_text: options = [o.strip() for o in opts_text.split('\n') if o.strip()]
        
        def_score = target_q.get('score', 10) if target_q else 10
        parent_score = c_p2.number_input(t('lbl_score', '分數'), 1, 100, value=int(def_score), key=f"{k_pfx}_sc")
    else:
        # Load sub questions
        def_subs = []
        if target_q:
            raw_subs = target_q.get('sub_questions')
            if isinstance(raw_subs, str):
                try: def_subs = json.loads(raw_subs)
                except: pass
            elif isinstance(raw_subs, list): def_subs = raw_subs
        
        has_subs_def = len(def_subs) > 0
        has_subs = st.checkbox(t('gen_subs_check', '包含子題'), value=has_subs_def, key=f"{k_pfx}_has_subs")
        
        if has_subs:
            st.info(f"🔹 {t('mode_composite', '子題模式')}")
            def_cols = int(default_meta.get('layout_cols', 1))
            layout_cols = st.radio(t('lbl_layout_cols', '子題排列'), [1, 2], horizontal=True, index=(0 if def_cols==1 else 1), format_func=lambda x: f"{x} 欄", key=f"{k_pfx}_layout")
            
            ss_key_num = f"{k_pfx}_num_subs"
            if ss_key_num not in st.session_state:
                st.session_state[ss_key_num] = len(def_subs) if def_subs else 1
            
            num_subs = st.number_input(t('lbl_sub_count', '子題數量'), 1, 10, key=ss_key_num)
            
            for i in range(num_subs):
                ex_txt = def_subs[i].get('text','') if i < len(def_subs) else ""
                ex_sc = def_subs[i].get('score', 5) if i < len(def_subs) else 5
                
                sc1, sc2 = st.columns([4, 1])
                s_txt = sc1.text_input(f"{t('lbl_sub_q', '子題')} ({i+1})", value=ex_txt, key=f"{k_pfx}_sq_t_{i}")
                s_score = sc2.number_input(f"{t('lbl_score', '分數')}", 1, 100, value=int(ex_sc), key=f"{k_pfx}_sq_s_{i}")
                sub_questions.append({"text": s_txt, "score": s_score})
            
            parent_score = sum(float(s['score']) for s in sub_questions)
            st.caption(f"總分: {parent_score}")
        else:
            def_score = target_q.get('score', 10) if target_q else 10
            parent_score = c_p2.number_input(t('lbl_score', '分數'), 1, 100, value=int(def_score), key=f"{k_pfx}_sc_norm")

    # 3. Media
    st.write(f"🖼️ {t('lbl_media', '媒體附件')}")
    mt1, mt2 = st.tabs([t('tab_upload_img', '上傳圖片'), t('tab_tikz', 'TikZ 代碼')])
    current_media = default_meta.get('media')
    
    with mt1:
        if current_media and current_media.get('type') == 'image':
            if os.path.exists(current_media['content']):
                st.image(current_media['content'], width=150, caption="Current Image")
        
        uploaded_img = st.file_uploader(t('lbl_img_file', '更換/上傳圖片'), type=['png', 'jpg', 'jpeg'], key=f"{k_pfx}_img")
    
    with mt2:
        def_tikz = ""
        if current_media and current_media.get('type') == 'tikz':
            def_tikz = current_media['content']
        tikz_code = st.text_area(t('lbl_tikz_code', '輸入 TikZ Code'), height=100, value=def_tikz, key=f"{k_pfx}_tikz")

    # Actions
    st.markdown("---")
    b_col1, b_col2 = st.columns([1, 1])
    
    # Label Switch based on mode
    save_label = t('btn_save_changes', '💾 儲存修改') if is_edit else t('btn_add_confirm', '💾 確認新增')
    
    if b_col1.button(save_label, type="primary", width='stretch'):
        # Validation
        if not q_text:
            st.error(t('err_empty_content', '題目內容不能為空'))
        elif not final_subj or not final_chap or not final_sec:
            st.error(t('err_missing_meta', '請完整填寫 科目、章節 與 小節'))
        else:
            if uploaded_img:
                img_path = save_uploaded_file(uploaded_img, user.id)
                current_media = {"type": "image", "content": img_path}
            elif tikz_code and r"\begin{tikzpicture}" in tikz_code:
                current_media = {"type": "tikz", "content": tikz_code}
            
            meta_data = {
                "subject": final_subj,
                "chapter": final_chap,
                "section": final_sec,
                "difficulty": final_diff,
                "type": q_type,
                "height": q_height,
                "options": options,
                "layout_cols": layout_cols,
                "media": current_media
            }
            meta_json = json.dumps(meta_data, ensure_ascii=False)
            subs_json = json.dumps(sub_questions, ensure_ascii=False)
            
            try:
                if is_edit:
                    update_question(q_id, q_text, parent_score, meta=meta_json, sub_questions=subs_json)
                else:
                    save_question(q_text, parent_score, "LOC-NEW", meta=meta_json, sub_questions=subs_json)
                
                if on_success: on_success()
                
            except Exception as e:
                st.error(f"Save Failed: {e}")

    if is_edit and b_col2.button(f"❌ {t('btn_cancel', '取消')}", width='stretch'):
        if on_cancel: on_cancel()


# ------------------------------------------------------------------------------
# Main View
# ------------------------------------------------------------------------------

def render_question_bank(user):
    st.title(f"📚 {t('menu_bank', '題庫中心')}")

    # [UX Fix] 檢查是否有「成功訊息」待顯示
    if 'bank_msg' in st.session_state:
        st.toast(st.session_state.bank_msg) # 彈出 Toast (Modern)
        st.success(st.session_state.bank_msg) # 頂部橫幅 (Traditional, very clear)
        del st.session_state.bank_msg # 顯示後刪除，避免重複

    if 'bank_cart' not in st.session_state: st.session_state.bank_cart = set()
    if 'bk_edit_mode' not in st.session_state: st.session_state.bk_edit_mode = False
    if 'bk_edit_id' not in st.session_state: st.session_state.bk_edit_id = None
    if 'bk_form_ver' not in st.session_state: st.session_state.bk_form_ver = 0

    # Tabs
    tab_list, tab_sets, tab_add = st.tabs([
        f"📖 {t('tab_q_list', '題目列表')}", 
        f"📂 {t('tab_q_sets', '題組管理')}", 
        f"➕ {t('tab_q_add', '新增題目')}"
    ])

    all_qs = get_all_questions() 
    taxonomy_tree = build_taxonomy_tree(all_qs)
    sorted_subjects = sorted(list(taxonomy_tree.keys()))

    # ==========================================================================
    # Tab 1: 題目列表 OR 編輯器
    # ==========================================================================
    with tab_list:
        
        # --- Edit Mode ---
        if st.session_state.bk_edit_mode and st.session_state.bk_edit_id:
            def on_save_success():
                st.session_state.bk_edit_mode = False
                st.session_state.bk_edit_id = None
                # [UX Fix] 設置成功訊息，供重整後顯示
                st.session_state.bank_msg = t('msg_update_success', "✅ 修改成功！")
                st.rerun()
            
            def on_cancel_edit():
                st.session_state.bk_edit_mode = False
                st.session_state.bk_edit_id = None
                st.rerun()

            render_question_editor(
                user, all_qs, taxonomy_tree, sorted_subjects, 
                q_id=st.session_state.bk_edit_id, 
                on_success=on_save_success, 
                on_cancel=on_cancel_edit
            )
        
        # --- List Mode ---
        else:
            col_filter, col_list = st.columns([1, 3])
            
            with col_filter:
                st.subheader(f"🔍 {t('lbl_filter', '條件篩選')}")
                
                subj_opts = ["All"] + sorted_subjects
                sel_subj = st.selectbox(f"📚 {t('lbl_subject', '科目')}", subj_opts, key="filter_subj")
                
                chap_opts = ["All"]
                if sel_subj != "All":
                    chap_opts += sorted(list(taxonomy_tree.get(sel_subj, {}).keys()))
                sel_chap = st.selectbox(f"📑 {t('lbl_chapter', '章節')}", chap_opts, key="filter_chap")
                
                sec_opts = ["All"]
                if sel_subj != "All" and sel_chap != "All":
                    sec_opts += sorted(list(taxonomy_tree[sel_subj].get(sel_chap, set())))
                sel_sec = st.selectbox(f"📍 {t('lbl_section', '小節')}", sec_opts, key="filter_sec")
                
                diff_opts = ["All"] + get_difficulty_options()
                sel_diff = st.selectbox(f"📊 {t('lbl_difficulty', '難易度')}", diff_opts, key="filter_diff")
                
                st.divider()
                search_kw = st.text_input(t('lbl_keyword', '關鍵字搜尋'), placeholder="e.g. Matrix...")
                
                st.markdown("---")
                if st.session_state.bank_cart:
                    cart_len = len(st.session_state.bank_cart)
                    st.info(f"🛒 {t('lbl_cart', '已選題目')}: {cart_len}")
                    with st.expander(f"💾 {t('btn_save_set', '存為題組')}", expanded=True):
                        set_title = st.text_input(t('lbl_set_name', '題組名稱'), key="local_set_title")
                        set_desc = st.text_area(t('lbl_desc', '描述'), key="local_set_desc", height=60)
                        if st.button(t('btn_confirm_save', '儲存'), key="save_set_local", width='stretch'):
                            if not set_title: st.error(t('err_no_title', '請輸入名稱'))
                            else:
                                create_question_set(user.id, set_title, set_desc, list(st.session_state.bank_cart))
                                st.session_state.bank_msg = f"{t('msg_saved', '已儲存')}: {set_title}"
                                st.session_state.bank_cart = set(); st.rerun()
                    if st.button(t('btn_clear', '清除選擇'), key="clr_cart_local", width='stretch'):
                        st.session_state.bank_cart = set(); st.rerun()
                else:
                    st.caption(t('msg_cart_empty', '尚未選擇題目'))

            with col_list:
                filtered = []
                for q in all_qs:
                    meta = q.get('meta', {})
                    if isinstance(meta, str):
                        try: meta = json.loads(meta)
                        except: meta = {}
                    
                    if sel_subj != "All" and meta.get('subject') != sel_subj: continue
                    if sel_chap != "All" and meta.get('chapter') != sel_chap: continue
                    if sel_sec != "All" and meta.get('section') != sel_sec: continue
                    if sel_diff != "All" and meta.get('difficulty') != sel_diff: continue
                    if search_kw and search_kw.lower() not in q['content'].lower(): continue
                    filtered.append(q)

                st.caption(f"{t('lbl_showing', '顯示')} {len(filtered)} {t('lbl_items', '筆題目')}")
                
                if not filtered:
                    st.info(t('msg_no_result', '沒有找到符合條件的題目。'))
                else:
                    for q in filtered:
                        qid = q['id']
                        in_cart = qid in st.session_state.bank_cart
                        
                        m = q.get('meta', {})
                        if isinstance(m, str):
                            try: m = json.loads(m)
                            except: m = {}
                        
                        tags = [m.get('subject'), m.get('chapter'), m.get('section'), m.get('difficulty'), m.get('type')]
                        tags = [t for t in tags if t]
                        
                        border = "#28a745" if in_cart else "#e0e0e0"
                        bg = "#f0fff4" if in_cart else "#ffffff"
                        
                        with st.container():
                            st.markdown(f'<div style="border:1px solid {border}; border-left:5px solid {border}; padding:15px; margin-bottom:10px; border-radius:5px; background:{bg};">', unsafe_allow_html=True)
                            
                            c1, c2 = st.columns([0.85, 0.15])
                            with c1:
                                if tags: st.caption(" • ".join(tags))
                                st.markdown(q['content'])
                                
                                if m.get('media'):
                                    media_content = m['media'].get('content')
                                    if m['media']['type'] == 'image' and os.path.exists(media_content):
                                        st.image(media_content, width=200)
                                    elif m['media']['type'] == 'tikz':
                                        st.code(media_content, language='latex')

                                subs = q.get('sub_questions', [])
                                if isinstance(subs, str):
                                    try: subs = json.loads(subs)
                                    except: subs = []
                                
                                if subs:
                                    with st.expander(f"{t('lbl_subs_count', '包含小題')}: {len(subs)}"):
                                        for idx, sq in enumerate(subs):
                                            st.markdown(f"↳ **({idx+1})** {sq.get('text','')} *({sq.get('score',0)} pts)*")

                            with c2:
                                st.write(f"**{q.get('score',0)} pt**")
                                
                                if in_cart:
                                    if st.button("➖ Cart", key=f"rm_{qid}"):
                                        st.session_state.bank_cart.remove(qid); st.rerun()
                                else:
                                    if st.button("➕ Cart", key=f"add_{qid}"):
                                        st.session_state.bank_cart.add(qid); st.rerun()
                                
                                # Edit Button
                                if st.button("✏️ Edit", key=f"btn_edit_{qid}"):
                                    st.session_state.bk_edit_mode = True
                                    st.session_state.bk_edit_id = qid
                                    st.rerun()
                                    
                                # Delete Button
                                if st.button("🗑️ Del", key=f"btn_del_{qid}"):
                                    delete_question(qid)
                                    st.toast("Deleted")
                                    time.sleep(0.5)
                                    st.rerun()

                            st.markdown('</div>', unsafe_allow_html=True)

    # ==========================================================================
    # Tab 2: 題組管理
    # ==========================================================================
    with tab_sets:
        st.subheader(f"📂 {t('header_my_sets', '我的題組')}")
        my_sets = get_user_question_sets(user.id)
        if not my_sets:
            st.info(t('msg_no_sets', '您尚未建立任何題組。'))
        else:
            c_list, c_detail = st.columns([1, 2])
            with c_list:
                sel_set_id = st.radio(t('lbl_select_set', '選擇題組'), [s['id'] for s in my_sets], 
                    format_func=lambda x: next((s['title'] for s in my_sets if s['id']==x), str(x)), label_visibility="collapsed")
            with c_detail:
                if sel_set_id:
                    curr = next((s for s in my_sets if s['id'] == sel_set_id), None)
                    if curr:
                        st.markdown(f"### 📄 {curr['title']}")
                        st.write(f"_{curr.get('description','')}_")
                        item_ids = get_question_set_items(sel_set_id)
                        st.success(f"{t('lbl_contains', '包含')} {len(item_ids)} {t('lbl_qs', '題')}")
                        ac1, ac2 = st.columns(2)
                        if ac1.button(f"📥 {t('btn_load_cart', '載入暫存')}", width='stretch'):
                            for qid in item_ids: st.session_state.bank_cart.add(qid)
                            st.session_state.bank_msg = t('msg_loaded', '已載入！'); st.rerun()
                        if ac2.button(f"🗑️ {t('btn_del_set', '刪除題組')}", type="primary", width='stretch'):
                            delete_question_set(sel_set_id); st.session_state.bank_msg = t('msg_deleted', '已刪除'); st.rerun()

    # ==========================================================================
    # Tab 3: 新增題目
    # ==========================================================================
    with tab_add:
        def on_add_success():
            st.session_state.bk_form_ver += 1
            # [UX Fix] 新增成功訊息
            st.session_state.bank_msg = t('msg_add_success', "✅ 新增題目成功！")
            st.rerun()

        render_question_editor(
            user, all_qs, taxonomy_tree, sorted_subjects, 
            q_id=None, 
            on_success=on_add_success
        )
