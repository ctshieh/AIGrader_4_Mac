# ui/exam_gen_view.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.26-Reorder-Added
# Description: 
# 1. [Feat] 新增「上移/下移」按鈕，解決題目排序問題 (Reordering)。
# 2. [Core] 保留所有資料庫載入與 I18n 邏輯。

import streamlit as st
import os
import time
import base64
import json
import ast
import hashlib
import re 
from datetime import datetime

# --- 核心服務 ---
try:
    from services.exam_gen_service import ExamBuilder
except ImportError:
    class ExamBuilder:
        def generate_tex_source(self, *args, **kwargs): return ""
        def compile_tex_to_pdf(self, *args, **kwargs): return None
        def generate_pdf(self, *args, **kwargs): return None, "error.pdf"

try:
    from services.pdf_service import save_uploaded_file
except ImportError:
    def save_uploaded_file(f, uid): return f"temp/{f.name}"

# AI 服務
try:
    from services.ai_generator import extract_text_from_pdf, generate_questions_from_material
except ImportError:
    def extract_text_from_pdf(x): return ""
    def generate_questions_from_material(k, c, cfg): return {"success": False, "error": "AI Module Missing"}

from services.plans import get_plan_config
from database.db_manager import (
    get_user_exams_unified, save_exam_draft_or_publish, check_user_quota
)
from utils.localization import t, LANGUAGE_OPTIONS

# =============================================================================
# Helpers 
# =============================================================================
def sanitize_content(text):
    if not text: return ""
    text = str(text).replace('\u00A0', ' ')
    text = re.sub(r'[\u200b-\u200f\u202a-\u202e\ufeff]', '', text)
    return text

def normalize_math_delimiters(text):
    if not text: return ""
    text = str(text)
    def _blk(m: re.Match) -> str: return f"$$\n{m.group(1).strip()}\n$$"
    def _inl(m: re.Match) -> str: return f"${m.group(1).strip()}$"
    _INLINE_MATH_RE = re.compile(r"\\\(\s*(.*?)\s*\\\)", flags=re.DOTALL)
    _BLOCK_MATH_RE = re.compile(r"\\\[\s*(.*?)\s*\\\]", flags=re.DOTALL)
    text = _BLOCK_MATH_RE.sub(_blk, text)
    text = _INLINE_MATH_RE.sub(_inl, text)
    return text

def render_text_with_math(container, text: str):
    if not text: return
    container.markdown(normalize_math_delimiters(sanitize_content(text)))

def normalize_ai_data(ai_list):
    cleaned = []
    if not isinstance(ai_list, list): return []
    for item in ai_list:
        text = item.get('text') or item.get('question') or ""
        raw_opts = item.get('options') or []
        if isinstance(raw_opts, str): raw_opts = [raw_opts]
        cleaned.append({
            "text": str(text),
            "options": raw_opts,
            "answer": str(item.get('answer', '')),
            "type": item.get('type', 'Multiple Choice'),
            "score": int(item.get('score', 10)),
            "sub_questions": [],
            "height": 6
        })
    return cleaned

# [NEW] 排序輔助函式
def move_question(index, direction):
    """
    交換題目順序
    """
    qs = st.session_state.exam_questions
    if direction == 'up' and index > 0:
        qs[index], qs[index-1] = qs[index-1], qs[index]
    elif direction == 'down' and index < len(qs) - 1:
        qs[index], qs[index+1] = qs[index+1], qs[index]
    # 觸發重繪
    st.rerun()

# =============================================================================
# Main View
# =============================================================================

def render_exam_generator(user):
    st.title(f"📝 {t('menu_exam_gen', '智慧出卷中心')}")

    # Session 初始化
    if 'exam_questions' not in st.session_state: st.session_state.exam_questions = []
    if 'editing_index' not in st.session_state: st.session_state.editing_index = -1
    
    defaults = {
        'e_title': "", 'e_sub': "", 'e_subject': "", 'e_dept': "", 'e_note': "",
        'e_category': "General", 'e_compact': False, 'e_layout': "combined",
        'e_ay': str(datetime.now().year - 1911), 'e_sem': "上學期", 'e_type': "期中考"
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

    license_data = st.session_state.get("license_data", {})
    plan_cfg = get_plan_config(getattr(user, 'plan', 'free'), license_data.get("features", []))

    # 1. AI 智慧出題
    with st.expander(t('expander_ai_gen', '🤖 AI 智慧出題 (AI Generator)'), expanded=False):
        if not plan_cfg.get("ai_gen_enabled", False):
            st.warning(f"🔒 {t('msg_feature_locked', '此功能僅限付費版使用')}")
        else:
            c1, c2 = st.columns([1, 1])
            ai_content = None 
            with c1:
                ai_src = st.radio(t('lbl_ai_source', '教材來源'), [t('opt_text', '文字'), "PDF"], horizontal=True)
                if ai_src == t('opt_text', '文字'):
                    text_input = st.text_area(t('lbl_ai_input_range', '輸入範圍'), height=100, key="ai_in_text")
                    if text_input: ai_content = text_input
                else:
                    pdf_file = st.file_uploader(t('lbl_upload_pdf', '上傳 PDF'), type=None, key="ai_in_pdf")
            
            with c2:
                limit = plan_cfg.get("ai_gen_batch_limit", 10)
                ai_num = st.number_input(f"{t('lbl_amount', '數量')} (Max {limit})", 1, max(1, limit), 5)
                ai_type_display = [t("type_choice"), t("type_calc_normal"), t("type_fill")]
                ai_type_keys = ["Multiple Choice", "Calculation", "Fill-in"]
                ai_type_idx = st.selectbox(t('lbl_q_type', '題型'), range(len(ai_type_display)), format_func=lambda x: ai_type_display[x], key="ai_in_type")
                ai_type = ai_type_keys[ai_type_idx] 
                ai_diff = st.select_slider(t('lbl_difficulty', '難度'), ["Easy", "Medium", "Hard"], value="Medium")
                
                lang_opts = list(LANGUAGE_OPTIONS.values())
                curr_lang_name = st.session_state.get("language", lang_opts[0])
                default_idx = lang_opts.index(curr_lang_name) if curr_lang_name in lang_opts else 0
                ai_out_lang = st.selectbox(t('lbl_ai_out_lang', '生成語言'), lang_opts, index=default_idx, label_visibility="collapsed", key="ai_out_lang")

                api_key = getattr(user, 'google_key', None) or getattr(user, 'google_api_key', None)
                btn_disabled = not api_key or (ai_src == "PDF" and not pdf_file) or (ai_src != "PDF" and not ai_content)
                
                if st.button(t('btn_ai_generate', '✨ 生成試題'), disabled=btn_disabled):
                    status_box = st.empty()
                    try:
                        if ai_src == "PDF" and pdf_file:
                            status_box.info("📄 正在讀取與解析 PDF 文件，請稍候...")
                            if not pdf_file.getvalue().startswith(b"%PDF-"):
                                st.error("❌ " + t("err_invalid_format", "Invalid format."))
                                st.stop()
                            ai_content = extract_text_from_pdf(pdf_file.getvalue())
                            if not ai_content or len(ai_content) < 10:
                                status_box.error("⚠️ PDF 無法讀取文字 (可能是純圖片掃描檔)。")
                                st.stop()

                        status_box.info(f"🤖 AI ({ai_out_lang}) 正在生成 {ai_num} 道題目，這通常需要 10-30 秒...")
                        start_time = time.time()
                        res = generate_questions_from_material(api_key, ai_content, {
                            "q_type": ai_type, "count": ai_num, "difficulty": ai_diff, "language": ai_out_lang 
                        })
                        duration = time.time() - start_time

                        if res.get("success"):
                            clean_qs = normalize_ai_data(res["data"])
                            st.session_state.exam_questions.extend(clean_qs)
                            st.session_state.last_data_hash = str(time.time())
                            status_box.success(f"✅ {t('msg_ai_success', '生成成功！')} (耗時 {duration:.1f}s)")
                            time.sleep(1.5); status_box.empty(); st.rerun()
                        else: status_box.error(f"❌ 生成失敗: {res.get('error')}")
                    except Exception as e: status_box.error(f"❌ 系統錯誤: {str(e)}")

    # 2. 試卷設定與載入 (含修復)
    if 'loader_selected_id' in st.session_state:
        target_id = st.session_state.pop('loader_selected_id')
        try:
            all_exams = get_user_exams_unified(user.id)
            found = next((e for e in all_exams if str(e['id']) == str(target_id)), None)
            if found:
                content = found.get('content', {})
                header = content.get('header', {})
                st.session_state.e_title = header.get('title', found['title'])
                st.session_state.e_subject = header.get('subject', found['subject'])
                st.session_state.e_sub = header.get('subtitle', "")
                st.session_state.e_dept = header.get('department', "")
                st.session_state.e_note = header.get('note', "")
                st.session_state.e_category = header.get('category', "General")
                st.session_state.e_compact = header.get('is_compact', False)
                st.session_state.e_layout = header.get('layout_mode', "combined")
                st.session_state.e_ay = found.get('academic_year') or "114"
                st.session_state.e_sem = found.get('semester') or "上學期"
                st.session_state.e_type = found.get('exam_type') or "期中考"
                st.session_state.exam_questions = content.get('questions_cache', [])
                st.toast(f"✅ {t('msg_draft_loaded', '試卷已成功載入！')}")
                time.sleep(0.5); st.rerun()
            else: st.error("❌ 找不到該試卷 (ID Mismatch)。")
        except Exception as e: st.error(f"載入失敗: {str(e)}")

    with st.expander(f"⚙️ {t('expander_header_settings', '試卷表頭設定')}", expanded=True):
        c1, c2 = st.columns([3, 1])
        st.session_state.e_title = c1.text_input(t('gen_exam_title', '主標題'), value=st.session_state.e_title)
        st.session_state.e_subject = c2.text_input(t('gen_subject', '科目'), value=st.session_state.e_subject)
        cm1, cm2, cm3 = st.columns(3)
        st.session_state.e_ay = cm1.text_input(t('lbl_academic_year', '學年度'), value=st.session_state.e_ay)
        st.session_state.e_sem = cm2.selectbox(t('lbl_semester', '學期'), ["上學期", "下學期"], index=0 if st.session_state.e_sem=="上學期" else 1)
        st.session_state.e_type = cm3.selectbox(t('lbl_exam_type', '考試別'), ["期中考", "期末考", "小考"], index=0)
        st.text_input(f"{t('gen_exam_subtitle', '副標題')}", key="e_sub")
        st.text_input(f"{t('gen_dept', '系級/班級')}", key="e_dept")
        c_time, c_compact = st.columns([1, 1])
        with c_time: st.text_input(t('lbl_time', '考試時間'), key="e_time", placeholder="100 min")
        with c_compact:
            st.write(""); st.write("")
            st.checkbox(t('lbl_compact_header', 'Compact Header'), key="e_compact", help=t('help_compact', '縮減高度'))
        st.write(f"📄 {t('lbl_layout_mode', '排版模式')}")
        st.radio(t('lbl_output_format', '格式：'), options=["combined", "separate"], 
            format_func=lambda x: t('opt_layout_combined', "標準合併") if x == "combined" else t('opt_layout_sep', "卷卡分離"),
            key="e_layout", horizontal=True)
        st.text_area(f"{t('gen_exam_note', '注意事項')}", key="e_note", height=68)

    col_save, col_load = st.columns([1, 1])
    with col_save:
        if st.button(f"💾 {t('btn_save_draft', '儲存草稿')}", type="primary", width='stretch'):
            can_save, msg = check_user_quota(user.id, getattr(user, 'plan', 'free'), "exam_gen")
            if not can_save: st.error(msg)
            else:
                save_data = {
                    "header": {
                        "title": st.session_state.e_title, "subject": st.session_state.e_subject,
                        "subtitle": st.session_state.e_sub, "department": st.session_state.e_dept,
                        "note": st.session_state.e_note, "category": st.session_state.e_category,
                        "is_compact": st.session_state.e_compact, "layout_mode": st.session_state.e_layout
                    },
                    "questions_cache": st.session_state.exam_questions,
                    "question_count": len(st.session_state.exam_questions)
                }
                try:
                    save_exam_draft_or_publish(user.id, st.session_state.e_title, st.session_state.e_subject, save_data, False, academic_year=st.session_state.e_ay, semester=st.session_state.e_sem, exam_type=st.session_state.e_type)
                    st.toast(t('msg_draft_saved', '草稿已儲存！')); st.success(f"{t('msg_save_success', '存檔成功')}。{msg}")
                except Exception as e: st.error(f"{t('msg_save_failed', '存檔失敗')}: {e}")
            
    with col_load: st.button(f"📥 {t('btn_load_draft', '載入最新草稿')}", width='stretch')

    # 3. 題目列表 (新增排序按鈕)
    st.write(f"### {t('gen_q_list', '試題列表')} ({len(st.session_state.exam_questions)})")
    if st.session_state.exam_questions:
        for i, q in enumerate(st.session_state.exam_questions):
            with st.container():
                # [Layout Fix] 將按鈕區稍微加寬，容納上下移按鈕
                c_idx, c_content, c_info, c_ops = st.columns([0.5, 4, 1.5, 1.2])
                c_idx.markdown(f"**Q{i+1}.**")
                
                subs = q.get('sub_questions', [])
                total_s = q.get('score', 0)
                if subs:
                    try: total_s = sum([float(sq.get('score', 0)) for sq in subs])
                    except: pass
                
                main_text = q.get('text', '') or f"*({t('lbl_no_content', '無內容')})*"
                render_text_with_math(c_content, main_text)
                if subs:
                    with c_content.expander(t('expander_show_subs', '{count} 小題').format(count=len(subs))):
                        for sub_i, sub_q in enumerate(subs):
                            sub_txt = sub_q.get('text', '')
                            st.markdown(f"↳ **({sub_i+1})** *({sub_q.get('score',0)} pts)*")
                            render_text_with_math(st.container(), sub_txt)
                
                c_info.caption(f"Score: {total_s} | H: {q.get('height', 6)}cm")
                
                # [NEW] 操作區：加入排序
                with c_ops:
                    r1, r2 = st.columns(2) # 第一行按鈕
                    r3, r4 = st.columns(2) # 第二行按鈕
                    
                    if r1.button("✏️", key=f"ed_{i}", help="Edit"):
                        st.session_state.editing_index = i; st.rerun()
                    if r2.button("🗑️", key=f"dl_{i}", help="Delete"):
                        st.session_state.exam_questions.pop(i)
                        st.session_state.editing_index = -1; st.rerun()
                    
                    # 排序按鈕 (第一題不能上移，最後一題不能下移)
                    if i > 0:
                        if r3.button("⬆️", key=f"up_{i}", help="Move Up"):
                            move_question(i, 'up')
                    if i < len(st.session_state.exam_questions) - 1:
                        if r4.button("⬇️", key=f"dn_{i}", help="Move Down"):
                            move_question(i, 'down')
                            
                st.divider()

    # 4. 編輯器
    edit_idx = st.session_state.editing_index
    is_edit_mode = edit_idx >= 0
    form_title = f"✏️ {t('header_edit', '編輯')} Q{edit_idx+1}" if is_edit_mode else f"➕ {t('header_add_new_q', '新增題目')}"
    form_bg = "background-color: #f8f9fa; padding: 20px; border-radius: 10px; border: 1px solid #ddd;" if is_edit_mode else ""
    with st.container():
        st.markdown(f"<div style='{form_bg}'><h4>{form_title}</h4>", unsafe_allow_html=True)
        curr_q = st.session_state.exam_questions[edit_idx] if is_edit_mode else {}
        def_txt = curr_q.get('text', '')
        def_score = curr_q.get('score', 10)
        def_h = curr_q.get('height', 6)
        def_type = curr_q.get('type', 'Calculation')
        
        q_text = st.text_area(f"{t('gen_content_label', '內容')} (LaTeX)", height=80, key="new_q_text", value=def_txt)
        
        c1, c2, c3 = st.columns(3)
        q_type_keys = ["Calculation", "Calculation Large", "Multiple Choice", "Proof", "True/False", "Fill-in"]
        q_type_vals = [t("type_calc_normal"), t("type_calc_large"), t("type_choice"), t("type_proof"), t("type_tf"), t("type_fill")]
        try: current_key_idx = q_type_keys.index(def_type)
        except: current_key_idx = 0
        q_type_idx = c1.selectbox(t('gen_type_label', '分類'), range(len(q_type_keys)), format_func=lambda x: q_type_vals[x], index=current_key_idx, key="new_q_type")
        selected_type_key = q_type_keys[q_type_idx]
        q_height = c3.number_input(f"{t('gen_height_label', '高度')} (cm)", 2, 25, value=int(def_h), key="new_q_height")
        
        options = []; sub_questions = []; has_subs = False; parent_score = 0
        if "Choice" in selected_type_key:
            def_opts = "\n".join(curr_q.get('options', []))
            opts_text = st.text_area(f"{t('lbl_options', '選項')} ({t('lbl_one_per_line', '一行一個')})", height=100, key="new_q_opts", value=def_opts)
            if opts_text: options = [o.strip() for o in opts_text.split('\n') if o.strip()]
            parent_score = c2.number_input(t('gen_score_label', '配分'), 1, 100, value=int(def_score), key="new_q_score_choice")
        else:
            def_subs = curr_q.get('sub_questions', [])
            has_subs = st.checkbox(t('gen_subs_check', '包含子題'), value=bool(def_subs), key="new_q_has_subs")
            if has_subs:
                st.radio(t('lbl_layout_cols', '排列'), [1, 2], horizontal=True, key="new_q_layout")
                num_subs = len(def_subs) if def_subs else 3
                st.caption(t('msg_edit_sub', '編輯 {n} 子題').format(n=num_subs))
                for i in range(num_subs):
                    sq = def_subs[i] if i < len(def_subs) else {}
                    sc1, sc2 = st.columns([4, 1])
                    s_txt = sc1.text_input(f"{t('lbl_sub_q', '子題')} ({i+1})", value=sq.get('text', ''), key=f"sq_txt_{i}")
                    s_score = sc2.number_input(t('lbl_score_unit', '分'), 1, 100, value=int(sq.get('score', 5)), key=f"sq_sc_{i}")
                    if s_txt: sub_questions.append({"text": s_txt, "score": s_score})
                parent_score = sum(s['score'] for s in sub_questions)
                st.caption(f"{t('lbl_total_score', '總分')}: {parent_score}")
            else:
                parent_score = c2.number_input(t('gen_score_label', '配分'), 1, 100, value=int(def_score), key="new_q_score_norm")
        
        st.write(f"🖼️ {t('lbl_media', '媒體')}")
        mt1, mt2 = st.tabs([t('tab_upload_img', '圖片'), t('tab_tikz', 'TikZ')])
        with mt1: up_img = st.file_uploader(t('lbl_img_file', '選擇圖片'), type=['png', 'jpg'], key="new_q_img_up")
        with mt2:
            def_tikz = ""
            if curr_q.get('media') and curr_q['media'].get('type') == 'tikz': def_tikz = curr_q['media']['content']
            tikz_code = st.text_area(t('lbl_tikz_code', 'TikZ Code'), value=def_tikz, height=100, key="new_q_tikz")
        
        b_col1, b_col2 = st.columns([1, 1])
        btn_label = f"💾 {t('btn_update_q', '更新')}" if is_edit_mode else f"➕ {t('btn_add_q', '新增')}"
        if b_col1.button(btn_label, type="primary", width='stretch'):
            media_obj = None
            if tikz_code: media_obj = {"type": "tikz", "content": tikz_code}
            elif up_img:
                path = save_uploaded_file(up_img, user.id)
                media_obj = {"type": "image", "content": path}
            new_q = {
                "text": normalize_math_delimiters(sanitize_content(q_text)),
                "score": parent_score, "height": q_height, "type": selected_type_key,
                "media": media_obj, "options": options, "sub_questions": sub_questions, "layout_cols": 1
            }
            if is_edit_mode:
                st.session_state.exam_questions[edit_idx] = new_q
                st.session_state.editing_index = -1; st.toast(t('msg_q_updated', 'Updated'))
            else:
                st.session_state.exam_questions.append(new_q); st.toast(t('msg_q_added', 'Added'))
            st.rerun()
        if is_edit_mode:
            if b_col2.button(f"❌ {t('btn_cancel_edit', '取消')}", width='stretch'):
                st.session_state.editing_index = -1; st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # 5. PDF Preview
    st.markdown("---")
    st.write(f"### 3. {t('header_gen_pdf', 'PDF 預覽')}")
    exam_data = {
        "title": st.session_state.e_title, "subtitle": st.session_state.e_sub,
        "subject": st.session_state.e_subject, "dept": st.session_state.e_dept, 
        "note": st.session_state.e_note, "exam_time": st.session_state.get("e_time", ""),
        "is_compact": st.session_state.e_compact, "layout_mode": st.session_state.get("e_layout", "combined")
    }
    data_str = json.dumps({'h': exam_data, 'q': st.session_state.exam_questions}, sort_keys=True, default=str)
    current_hash = hashlib.md5(data_str.encode()).hexdigest()
    builder = ExamBuilder()
    if 'last_data_hash' not in st.session_state: st.session_state.last_data_hash = ""
    if 'raw_tex_source' not in st.session_state: st.session_state.raw_tex_source = ""
    if current_hash != st.session_state.last_data_hash:
        st.session_state.raw_tex_source = builder.generate_tex_source(exam_data, st.session_state.exam_questions)
        st.session_state.last_data_hash = current_hash

    with st.expander(f"{t('expander_latex_preview', 'LaTeX 原始碼')}", expanded=False):
        edited_source = st.text_area(t('lbl_source_code', '編輯器'), value=st.session_state.raw_tex_source, height=300)
        if edited_source != st.session_state.raw_tex_source: st.session_state.raw_tex_source = edited_source
        if st.button(f"🔧 {t('btn_compile_manual', '手動編譯')}", key="btn_man_compile"):
            with st.spinner(t('msg_compiling', '編譯中...')):
                pdf_bytes = builder.compile_tex_to_pdf(
                    tex_source=st.session_state.raw_tex_source, 
                    exam_id="manual", system_qr_content="MANUAL", marketing_url=None
                )
                if pdf_bytes:
                    st.session_state.generated_pdf = pdf_bytes
                    st.session_state.pdf_filename = "manual_preview.pdf"
                    st.success(t('msg_compile_success', '成功')); st.rerun()
                else: st.error(t('err_compile_failed', '失敗'))

    if st.button(f"🚀 {t('btn_gen_pdf', '生成 PDF')}", type="primary", width='stretch', disabled=not st.session_state.exam_questions):
        with st.spinner(t('msg_generating_pdf', '生成中...')):
            pdf_res = builder.generate_pdf(exam_data, st.session_state.exam_questions, user=user)
            if pdf_res and pdf_res[0]:
                st.session_state.generated_pdf = pdf_res[0]
                st.session_state.pdf_filename = pdf_res[1] 
                st.success(t('msg_gen_success', '成功')); st.rerun()
            else: st.error(t('err_gen_fail', '失敗'))

    if 'generated_pdf' in st.session_state and st.session_state.generated_pdf:
        b64_pdf = base64.b64encode(st.session_state.generated_pdf).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800px" style="border:none;"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
        fname = st.session_state.get('pdf_filename', "exam.pdf")
        st.download_button(f"📥 {t('btn_download_pdf', '下載')}", st.session_state.generated_pdf, fname, "application/pdf", width='stretch')
