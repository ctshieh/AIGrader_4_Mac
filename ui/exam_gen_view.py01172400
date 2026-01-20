# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# This software is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.

# ui/exam_gen_view.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.13-TagPosFix-Plan-Merged
# Description: 
# 1. [Synced] Retained Tag Position Fix & Layout Mode from your version.
# 2. [Merged] Integrated 'services.plans' for Standalone/Business quota logic.

import streamlit as st
import os
import time
import base64
import json
import ast
import hashlib
import re 
from services.exam_gen_service import ExamBuilder
from services.pdf_service import save_uploaded_file 

from config import DATA_DIR
from utils.localization import t
from database.db_manager import (
    get_user_exams, get_exam_by_id, create_exam, 
    get_all_questions, get_user_weekly_exam_gen_count, get_sys_conf, User,
    get_user_by_id
)
from services.plans import get_plan_config  # [New] 引入方案規則

# =============================================================================
# Helpers
# =============================================================================

def sanitize_content(text):
    if not text: return ""
    text = str(text).replace('\u00A0', ' ')
    text = re.sub(r'[\u200b-\u200f\u202a-\u202e\ufeff]', '', text)
    return text

def get_safe_filename(title, subject, suffix=""):
    base = f"{title}_{subject}"
    safe_base = re.sub(r'[\\/*?:"<>|]', "", base).strip()
    if not safe_base: safe_base = "Exam_Paper"
    return f"{safe_base}{suffix}.pdf"

_INLINE_MATH_RE = re.compile(r"\\\(\s*(.*?)\s*\\\)", flags=re.DOTALL)
_BLOCK_MATH_RE = re.compile(r"\\\[\s*(.*?)\s*\\\]", flags=re.DOTALL)

def normalize_math_delimiters(text):
    if not text: return ""
    text = str(text)
    def _blk(m: re.Match) -> str: return f"$$\n{m.group(1).strip()}\n$$"
    def _inl(m: re.Match) -> str: return f"${m.group(1).strip()}$"
    text = _BLOCK_MATH_RE.sub(_blk, text)
    text = _INLINE_MATH_RE.sub(_inl, text)
    return text

def split_text_math_segments(text: str):
    if text is None: return []
    s = str(text); out = []; i = 0; n = len(s)
    def emit(kind, buf_str):
        if buf_str: out.append((kind, buf_str))
    buf = []
    while i < n:
        ch = s[i]
        if ch == "\\" and i + 1 < n and s[i + 1] == "$":
            buf.append("$"); i += 2; continue
        if ch == "$":
            emit("text", "".join(buf)); buf = []
            is_display = (i + 1 < n and s[i + 1] == "$")
            i += 2 if is_display else 1
            math_buf = []
            while i < n:
                if s[i] == "\\" and i + 1 < n and s[i + 1] == "$":
                    math_buf.append("$"); i += 2; continue
                if (not is_display) and s[i] == "$": i += 1; break
                if is_display and s[i] == "$" and i + 1 < n and s[i + 1] == "$": i += 2; break
                math_buf.append(s[i]); i += 1
            math_content = "".join(math_buf).strip()
            if math_content: out.append(("display_math" if is_display else "math", math_content))
            else: out.append(("text", "$$" if is_display else "$"))
            continue
        buf.append(ch); i += 1
    emit("text", "".join(buf))
    return out

def render_text_with_math(container, text: str):
    if not text: return
    text = sanitize_content(text)
    text = normalize_math_delimiters(text)
    segments = split_text_math_segments(text)
    for kind, content in segments:
        if not content: continue
        if kind == "text": container.markdown(content)
        else: container.latex(content)

# =============================================================================
# Main View
# =============================================================================

def render_exam_generator(user: User):
    st.title(f"📝 {t('menu_exam_gen')}")

    # ==========================================================
    # [CRITICAL FIX] User Refresh Logic
    # ==========================================================
    try:
        latest_user = get_user_by_id(user.id)
        if latest_user:
            user = latest_user
    except Exception as e:
        print(f"User refresh failed: {e}")
    # ==========================================================

    if 'exam_questions' not in st.session_state: st.session_state.exam_questions = []
    if 'editing_index' not in st.session_state: st.session_state.editing_index = -1
    
    if 'e_title' not in st.session_state: st.session_state.e_title = t('default_exam_title')
    if 'e_sub' not in st.session_state: st.session_state.e_sub = ""
    if 'e_subject' not in st.session_state: st.session_state.e_subject = ""
    if 'e_dept' not in st.session_state: st.session_state.e_dept = ""
    if 'e_note' not in st.session_state: st.session_state.e_note = ""
    if 'e_category' not in st.session_state: st.session_state.e_category = "General"
    if 'e_compact' not in st.session_state: st.session_state.e_compact = False 
    if 'e_layout' not in st.session_state: st.session_state.e_layout = "combined"

    if st.session_state.get('toast_message'):
        st.toast(t(st.session_state['toast_message']))
        del st.session_state['toast_message']

    def apply_loaded_exam(draft):
        if not draft: return False
        try:
            raw_c = draft.get('content') or draft.get('content_json') or {}
            c = raw_c
            if not isinstance(c, dict):
                try: c = json.loads(str(c))
                except: 
                    try: c = ast.literal_eval(str(c))
                    except: c = {}

            st.session_state.e_title = sanitize_content(draft.get('title', ''))
            st.session_state.e_subject = sanitize_content(draft.get('subject', ''))
            
            header = c.get('header', {}) if 'header' in c else c
            st.session_state.e_sub = sanitize_content(header.get('subtitle', ''))
            st.session_state.e_dept = sanitize_content(header.get('department', ''))
            st.session_state.e_note = sanitize_content(header.get('note', ''))
            st.session_state.e_category = sanitize_content(header.get('category', 'General'))
            st.session_state.e_compact = bool(header.get('is_compact', False))
            st.session_state.e_layout = header.get('layout_mode', 'combined')

            raw_qs = c.get('questions_cache', []) or c.get('questions', [])
            parsed_qs = []
            for q in raw_qs:
                q_text = (q.get('text', '') or '').replace(r'\_', '_')
                q_text = normalize_math_delimiters(q_text)
                q['text'] = sanitize_content(q_text)
                subs = q.get('sub_questions')
                if subs and isinstance(subs, str):
                    try: subs = json.loads(subs)
                    except: 
                        try: subs = ast.literal_eval(subs)
                        except: subs = []
                if isinstance(subs, list):
                    for sub in subs:
                        sub_text = (sub.get('text', '') or '').replace(r'\_', '_')
                        sub_text = normalize_math_delimiters(sub_text)
                        sub['text'] = sanitize_content(sub_text)
                q['sub_questions'] = subs if isinstance(subs, list) else []
                parsed_qs.append(q)
            st.session_state.exam_questions = parsed_qs
            st.session_state.editing_index = -1
            st.session_state['last_data_hash'] = ""
            return True
        except Exception as e:
            print(f"Load Error: {e}")
            return False

    def cb_load_selected():
        eid = st.session_state.get('loader_selected_id')
        if eid:
            actual_id = str(eid).replace("LEGACY_", "") if isinstance(eid, str) else eid
            draft = get_exam_by_id(actual_id)
            if apply_loaded_exam(draft): st.session_state['toast_message'] = 'msg_draft_loaded'

    def cb_load_latest():
        u_exams = get_user_exams(user.id)
        if u_exams:
            if apply_loaded_exam(u_exams[0]): st.session_state['toast_message'] = 'msg_draft_loaded'

    def clear_form_state():
        keys_to_del = [k for k in st.session_state.keys() if k.startswith('sq_txt_') or k.startswith('sq_sc_')]
        for k in keys_to_del: del st.session_state[k]
        st.session_state['new_q_text'] = ""
        st.session_state['new_q_height'] = 6
        st.session_state['new_q_has_subs'] = False
        st.session_state['new_q_opts'] = ""
        st.session_state['new_q_tikz'] = ""
        if 'uploader_key' not in st.session_state: st.session_state['uploader_key'] = 0
        st.session_state['uploader_key'] += 1

    if st.session_state.get('trigger_clear_form', False):
        clear_form_state()
        st.session_state['trigger_clear_form'] = False

    def load_question_into_form(idx):
        if 0 <= idx < len(st.session_state.exam_questions):
            q = st.session_state.exam_questions[idx]
            st.session_state['new_q_text'] = q.get('text', '')
            st.session_state['new_q_type'] = q.get('type', t('type_calc_normal'))
            st.session_state['new_q_height'] = q.get('height', 6)
            if q.get('options'):
                st.session_state['new_q_opts'] = "\n".join(q['options'])
                st.session_state['new_q_score_choice'] = q.get('score', 5)
            subs = q.get('sub_questions', [])
            if isinstance(subs, str):
                try: subs = json.loads(subs)
                except:
                    try: subs = ast.literal_eval(subs)
                    except: subs = []
            if subs:
                st.session_state['new_q_has_subs'] = True
                st.session_state['new_q_num_subs'] = len(subs)
                st.session_state['new_q_layout'] = q.get('layout_cols', 2)
                for i, sq in enumerate(subs):
                    st.session_state[f'sq_txt_{i}'] = sq.get('text', '')
                    st.session_state[f'sq_sc_{i}'] = sq.get('score', 5)
            else:
                st.session_state['new_q_has_subs'] = False
                st.session_state['new_q_score_norm'] = q.get('score', 10)
            if q.get('media') and q['media'].get('type') == 'tikz':
                st.session_state['new_q_tikz'] = q['media'].get('content', '')
            else:
                st.session_state['new_q_tikz'] = ""

    user_exams_list = get_user_exams(user.id)
    cats = set()
    if user_exams_list:
        for e in user_exams_list:
            try:
                raw_c = e.get('content') or e.get('content_json')
                c = json.loads(raw_c) if isinstance(raw_c, str) else raw_c
                header = c.get('header', {}) if isinstance(c, dict) and 'header' in c else (c if isinstance(c, dict) else {})
                if header.get('category'): cats.add(header['category'])
            except: pass

    with st.expander(t('btn_load_draft'), expanded=False): 
        if not user_exams_list: st.info(t('msg_no_drafts'))
        else:
            def fmt(eid):
                e = next((x for x in user_exams_list if x['id'] == eid), None)
                if not e: return str(eid)
                try:
                    raw_c = e.get('content') or e.get('content_json')
                    c = json.loads(raw_c) if isinstance(raw_c, str) else raw_c
                    if not isinstance(c, dict): c = {}
                except: c = {}
                
                header = c.get('header', {}) if 'header' in c else c
                title = e.get('title', '')
                dept = header.get('department', '')
                subject = e.get('subject', '')
                parts = [p for p in [title, dept, subject] if p]
                display_name = " - ".join(parts)
                
                return f"[{header.get('category','Gen')}] {e['updated_at'].strftime('%m-%d %H:%M')} | {display_name}"

            st.selectbox(t('lbl_select_exam'), [e['id'] for e in user_exams_list], format_func=fmt, key="loader_selected_id")
            st.button(t('btn_confirm_load'), on_click=cb_load_selected)

    with st.expander(t('gen_header_info'), expanded=True):
        c_cat1, c_cat2 = st.columns(2)
        exist_cats = sorted(list(cats))
        cat_opts = exist_cats + ["(Create New...)"]
        if "e_category" not in st.session_state: st.session_state.e_category = "General"
        curr_cat = st.session_state.e_category
        idx = cat_opts.index(curr_cat) if curr_cat in cat_opts else 0
        sel_cat = c_cat1.selectbox(t('lbl_category'), cat_opts, index=idx)
        if sel_cat == "(Create New...)":
            new_cat = c_cat2.text_input(t('lbl_new_cat_name'))
            if new_cat: st.session_state.e_category = new_cat
        else: st.session_state.e_category = sel_cat
        st.divider()
        st.text_input(t('gen_exam_title'), key="e_title")
        st.text_input(t('gen_exam_subtitle'), key="e_sub")
        st.text_input(t('gen_subject'), key="e_subject")
        st.text_input(t('gen_dept'), key="e_dept")
        
        c_time, c_compact = st.columns([1, 1])
        with c_time:
            st.text_input(t('lbl_time'), key="e_time", placeholder="100 min")
        with c_compact:
            st.write("")
            st.write("")
            st.checkbox("Compact Header (精簡標頭)", key="e_compact", help="Reduce header size to save space.")

        st.write("📄 Layout Mode (排版模式)")
        st.radio(
            "選擇輸出格式：", 
            options=["combined", "separate"], 
            format_func=lambda x: "標準合併 (題目+作答格)" if x == "combined" else "卷卡分離 (試題卷 + 答題卷)",
            key="e_layout",
            horizontal=True
        )

        st.text_area(t('gen_exam_note'), key="e_note", height=68)

    col_help, col_save, col_load = st.columns([2, 1, 1])
    with col_save:
        if st.button(t('btn_save_draft'), type="primary", width='stretch'):
            save_data = {
                "header": {
                    "subtitle": st.session_state.e_sub, 
                    "department": st.session_state.e_dept,
                    "note": st.session_state.e_note, 
                    "category": st.session_state.e_category,
                    "is_compact": st.session_state.e_compact,
                    "layout_mode": st.session_state.e_layout
                },
                "questions_cache": st.session_state.exam_questions,
                "question_count": len(st.session_state.exam_questions)
            }
            payload_json = json.dumps(save_data, default=str, ensure_ascii=False)
            try:
                create_exam(user.id, st.session_state.e_title, st.session_state.e_subject, payload_json)
                st.toast(t('msg_draft_saved'))
            except Exception as e: st.error(f"{t('msg_save_failed')}: {e}")
    with col_load:
        st.button(f"📥 {t('btn_load_draft')} ({t('lbl_latest')})", width='stretch', on_click=cb_load_latest)

    st.write(f"### 2. {t('gen_q_list')}")
    with st.expander(t('expander_import_bank'), expanded=False):
        all_qs = get_all_questions()
        if not all_qs: st.warning(t('msg_bank_empty'))
        else:
            q_map = {q['id']: f"[{q.get('question_no','-')}] {sanitize_content(q['content'])[:50]}..." for q in all_qs}
            sel_db_ids = st.multiselect(t('lbl_select_questions'), list(q_map.keys()), format_func=lambda x: q_map[x])
            if st.button(t('btn_add_selected_q')):
                for qid in sel_db_ids:
                    db_q = next((q for q in all_qs if q['id'] == qid), None)
                    if db_q:
                        subs = []
                        raw_s = db_q.get('sub_questions')
                        if raw_s:
                            if isinstance(raw_s, str):
                                try: subs = json.loads(raw_s)
                                except: 
                                    try: subs = ast.literal_eval(raw_s)
                                    except: subs = []
                            elif isinstance(raw_s, list): subs = raw_s
                        view_q = {
                            "text": normalize_math_delimiters(sanitize_content(db_q.get('content', ''))),
                            "score": db_q.get('score', 0), "type": t('type_calc_normal'), "height": 6,
                            "sub_questions": [{"text": normalize_math_delimiters(sanitize_content(s.get('content', '') or s.get('text', ''))), "score": s.get('score', 0)} for s in subs],
                            "media": None, "options": []
                        }
                        st.session_state.exam_questions.append(view_q)
                st.session_state.last_data_hash = ""
                st.rerun()

    if st.session_state.exam_questions:
        for i, q in enumerate(st.session_state.exam_questions):
            with st.container():
                c_idx, c_content, c_info, c_ops = st.columns([0.5, 4, 1.5, 1])
                c_idx.markdown(f"**Q{i+1}.**")
                subs = q.get('sub_questions', [])
                if isinstance(subs, str):
                    try: subs = json.loads(subs)
                    except: 
                        try: subs = ast.literal_eval(subs)
                        except: subs = []
                total_s = q.get('score', 0)
                if subs:
                    try: total_s = sum([float(sq.get('score', 0)) for sq in subs])
                    except: pass
                main_text = q.get('text', '')
                if not main_text: main_text = f"*({t('lbl_no_content')})*"
                render_text_with_math(c_content, main_text)
                if subs:
                    with c_content.expander(t('expander_show_subs').format(count=len(subs))):
                        for sub_i, sub_q in enumerate(subs):
                            sub_txt = sub_q.get('text', '')
                            sub_sc = sub_q.get('score', 0)
                            st.markdown(f"↳ **({sub_i+1})** *({sub_sc} pts)*")
                            render_text_with_math(st.container(), sub_txt)
                c_info.caption(f"{t('lbl_total_score')}: {total_s} | H: {q.get('height', 6)}cm")
                with c_ops:
                    bc1, bc2 = st.columns(2)
                    if bc1.button("✏️", key=f"ed_{i}"):
                        st.session_state.editing_index = i
                        load_question_into_form(i)
                        st.rerun()
                    if bc2.button("🗑️", key=f"dl_{i}"):
                        st.session_state.exam_questions.pop(i)
                        st.session_state.editing_index = -1
                        st.session_state['trigger_clear_form'] = True
                        st.session_state.last_data_hash = ""
                        st.rerun()
                st.divider()
    else: st.info(t('msg_no_questions'))

    edit_idx = st.session_state.editing_index
    is_edit_mode = edit_idx >= 0
    form_bg = "background-color: #f0f2f6; padding: 20px; border-radius: 10px;" if is_edit_mode else ""
    with st.container():
        if is_edit_mode: st.markdown(f"<div style='{form_bg}'><h4>✏️ {t('lbl_editing')} Q{edit_idx+1}</h4>", unsafe_allow_html=True)
        else: st.write(f"#### {t('gen_add_title')}")
        q_text = st.text_area(t('gen_content_label'), height=80, key="new_q_text", placeholder=t('placeholder_q_content'))
        c1, c2, c3 = st.columns(3)
        q_type_opts = [t('type_calc_normal'), t('type_calc_large'), t('type_choice'), t('type_proof'), t('type_tf'), t('type_fill')]
        q_type = c1.selectbox(t('gen_type_label'), q_type_opts, key="new_q_type")
        q_height = c3.number_input(t('gen_height_label'), min_value=2, max_value=25, key="new_q_height")
        options = []; sub_questions = []; parent_score = 0; layout_cols = 1; has_subs = False
        if q_type == t('type_choice'):
            st.info(f"🔹 {t('mode_choice')}")
            opts_text = st.text_area(t('lbl_options'), height=100, key="new_q_opts", placeholder=t('placeholder_options'))
            if opts_text: options = [o.strip() for o in opts_text.split('\n') if o.strip()]
            parent_score = c2.number_input(t('gen_score_label'), 1, 100, key="new_q_score_choice")
        else:
            has_subs = st.checkbox(t('gen_subs_check'), key="new_q_has_subs")
            if has_subs:
                st.info(f"🔹 {t('mode_composite')}")
                layout_cols = st.radio(t('lbl_layout_cols'), [1, 2], horizontal=True, key="new_q_layout")
                num_subs = st.number_input(t('lbl_sub_count'), 1, 10, key="new_q_num_subs")
                for i in range(num_subs):
                    sc1, sc2 = st.columns([4, 1])
                    s_txt = sc1.text_input(f"{t('lbl_sub_q')} ({i+1})", key=f"sq_txt_{i}")
                    s_score = sc2.number_input(t('lbl_score'), 1, 100, key=f"sq_sc_{i}")
                    sub_questions.append({"text": s_txt, "score": s_score})
                parent_score = sum(float(s['score']) for s in sub_questions)
            else:
                parent_score = c2.number_input(t('gen_score_label'), 1, 100, key="new_q_score_norm")
        st.write(f"🖼️ {t('lbl_media')}")
        mt1, mt2 = st.tabs([t('tab_upload_img'), t('tab_tikz')])
        with mt1:
            uploaded_img = st.file_uploader(t('lbl_img_file'), type=['png', 'jpg', 'jpeg'], key=f"new_q_img_{st.session_state.get('uploader_key', 0)}")
        with mt2:
            tikz_code = st.text_area(t('lbl_tikz_code'), height=100, key="new_q_tikz")
        b_col1, b_col2 = st.columns([1, 1])
        btn_label = t('btn_update_q') if is_edit_mode else t('btn_add_q')
        if b_col1.button(btn_label, type="primary", width='stretch'):
            current_media = st.session_state.exam_questions[edit_idx].get('media') if is_edit_mode else None
            if uploaded_img:
                img_path = save_uploaded_file(uploaded_img, user.id)
                current_media = {"type": "image", "content": img_path}
            elif tikz_code and r"\begin{tikzpicture}" in tikz_code:
                current_media = {"type": "tikz", "content": tikz_code}
            new_q = {
                "text": normalize_math_delimiters(sanitize_content(q_text)),
                "score": parent_score, "height": q_height, "type": q_type, "media": current_media,
                "options": options, "sub_questions": sub_questions if has_subs else [],
                "layout_cols": layout_cols if has_subs else 1
            }
            if is_edit_mode:
                st.session_state.exam_questions[edit_idx] = new_q
                st.session_state.editing_index = -1
                st.toast(t('msg_q_updated'))
            else:
                st.session_state.exam_questions.append(new_q)
                st.toast(t('msg_q_added'))
            st.session_state['trigger_clear_form'] = True
            st.session_state.last_data_hash = ""
            time.sleep(0.5); st.rerun()
        if is_edit_mode and b_col2.button(t('btn_cancel_edit'), width='stretch'):
            st.session_state.editing_index = -1
            st.session_state['trigger_clear_form'] = True
            st.rerun()
        if is_edit_mode: st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.write(f"### 3. {t('header_gen_pdf')}")
    exam_data = {
        "title": st.session_state.e_title, 
        "subtitle": st.session_state.e_sub,
        "subject": st.session_state.e_subject, 
        "dept": st.session_state.e_dept, 
        "note": st.session_state.e_note,
        "exam_time": st.session_state.get("e_time", ""),
        "is_compact": st.session_state.e_compact,
        "layout_mode": st.session_state.get("e_layout", "combined")
    }
    data_str = json.dumps({'h': exam_data, 'q': st.session_state.exam_questions}, sort_keys=True, default=str)
    current_hash = hashlib.md5(data_str.encode()).hexdigest()
    builder = ExamBuilder()
    if 'last_data_hash' not in st.session_state: st.session_state.last_data_hash = ""
    if current_hash != st.session_state.last_data_hash:
        st.session_state.raw_tex_source = builder.generate_tex_source(exam_data, st.session_state.exam_questions)
        st.session_state.current_preview_source = st.session_state.raw_tex_source
        st.session_state.last_data_hash = current_hash

    # [Fix] LaTeX Preview
    with st.expander(t('expander_latex_preview'), expanded=False):
        if st.session_state.exam_questions:
            edited_source = st.text_area(t('lbl_source_code'), value=st.session_state.current_preview_source, height=300)
            if edited_source != st.session_state.current_preview_source: st.session_state.current_preview_source = edited_source
            if st.button(t('btn_compile_manual')):
                with st.spinner(t('msg_compiling')):
                    pdf_bytes = builder.compile_tex_to_pdf(
                        tex_source=edited_source, 
                        exam_id="manual_preview", 
                        system_qr_content="PREVIEW",
                        marketing_url=None,
                        user=user
                    )
                    if pdf_bytes:
                        st.session_state.generated_pdf = pdf_bytes
                        st.session_state.pdf_filename = get_safe_filename(st.session_state.e_title, st.session_state.e_subject, "_preview")
                        st.success(t('msg_compile_success'))
        else: st.info(t('msg_add_q_first'))

    # ==========================================================
    # [NEW] QUOTA CHECK (Replaced System Conf with Plans.py)
    # ==========================================================
    current_exams = get_user_weekly_exam_gen_count(user.id)
    
    # 1. 讀取方案設定 (Plans.py)
    plan_conf = get_plan_config(user.plan)
    default_limit = plan_conf.get("exam_gen", 0)
    
    # 2. 機構版客製化 (Business Only)
    limit = default_limit
    if user.plan == "business":
        custom = int(getattr(user, 'custom_exam_limit', 0) or 0)
        if custom > 0: limit = custom
    # ==========================================================

    remaining = max(0, limit - current_exams)
    if remaining <= 0:
        st.error(f"❌ {t('quota_exceeded_msg')} ({current_exams}/{limit})")
    else:
        st.info(f"💡 {t('remaining_quota_label')}: {remaining}")

    if st.button(t('btn_gen_pdf'), type="primary", width='stretch', disabled=(remaining <= 0 or not st.session_state.exam_questions)):
        with st.spinner(t('msg_generating_pdf')):
            pdf_res = builder.generate_pdf(exam_data, st.session_state.exam_questions, user=user)
            if pdf_res and pdf_res[0]:
               st.session_state.generated_pdf = pdf_res[0]
               st.session_state.pdf_filename = pdf_res[1] 
               st.success(t('msg_gen_success'))
               st.rerun()
            else:
               st.error(t('msg_gen_fail'))

    if 'generated_pdf' in st.session_state and st.session_state.generated_pdf:
        b64_pdf = base64.b64encode(st.session_state.generated_pdf).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800px" style="border:none;"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
        fname = st.session_state.get('pdf_filename', "exam.pdf")
        st.download_button(t('btn_download_pdf'), st.session_state.generated_pdf, fname, "application/pdf", width='stretch')