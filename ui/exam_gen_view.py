# ui/exam_gen_view.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.23-Final-Sync-Fix
# Description: 
# 1. [Fix] 依據 2026 建議規範，將按鈕寬度參數統一修正為 width='stretch'。
# 2. [Security] 嚴格執行 PDF Magic Bytes 檢查並修正縮排與變數名。

import streamlit as st
import os
import time
import base64
import json
import ast
import hashlib
import re 
from datetime import datetime

# --- 核心服務 (容錯匯入) ---
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
    get_user_exams_unified, get_exam_by_id, create_exam, 
    check_user_quota, save_exam_draft_or_publish, get_all_questions
)
from utils.localization import t

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

def normalize_ai_data(ai_list):
    cleaned = []
    if not isinstance(ai_list, list): return []
    for item in ai_list:
        text = item.get('text') or item.get('question') or item.get('q_text') or item.get('content') or ""
        raw_opts = item.get('options') or item.get('choices') or []
        if isinstance(raw_opts, str): raw_opts = [raw_opts]
        ans = item.get('answer') or item.get('correct_option') or item.get('ans') or ""
        cleaned.append({
            "text": str(text),
            "options": raw_opts,
            "answer": str(ans),
            "solution": item.get('solution', ''),
            "type": item.get('type', '選擇題'),
            "score": int(item.get('score', 10)),
            "media": None,
            "sub_questions": [],
            "height": 6
        })
    return cleaned

# =============================================================================
# Main View
# =============================================================================

def render_exam_generator(user):
    st.title(f"📝 {t('menu_exam_gen', '智慧出卷中心')}")

    # Session 初始化
    if 'exam_questions' not in st.session_state: st.session_state.exam_questions = []
    if 'editing_index' not in st.session_state: st.session_state.editing_index = -1
    if 'e_title' not in st.session_state: st.session_state.e_title = ""
    if 'e_sub' not in st.session_state: st.session_state.e_sub = ""
    if 'e_subject' not in st.session_state: st.session_state.e_subject = ""
    if 'e_dept' not in st.session_state: st.session_state.e_dept = ""
    if 'e_note' not in st.session_state: st.session_state.e_note = ""
    if 'e_category' not in st.session_state: st.session_state.e_category = "General"
    if 'e_compact' not in st.session_state: st.session_state.e_compact = False 
    if 'e_layout' not in st.session_state: st.session_state.e_layout = "combined"
    if 'e_ay' not in st.session_state: st.session_state.e_ay = str(datetime.now().year - 1911)
    if 'e_sem' not in st.session_state: st.session_state.e_sem = "上學期"
    if 'e_type' not in st.session_state: st.session_state.e_type = "期中考"

    # 權限
    license_data = st.session_state.get("license_data", {})
    plan_cfg = get_plan_config(getattr(user, 'plan', 'free'), license_data.get("features", []))

    # 1. AI 智慧出題
    with st.expander("🤖 AI 智慧出題 (AI Generator)", expanded=False):
        if not plan_cfg.get("ai_gen_enabled", False):
            st.warning("🔒 此功能僅限付費版使用")
        else:
            c1, c2 = st.columns([1, 1])
            with c1:
                ai_src = st.radio("教材來源", ["文字", "PDF"], horizontal=True)
                ai_content = ""
                if ai_src == "文字":
                    ai_content = st.text_area("輸入範圍", height=100, key="ai_in_text")
                else:
                    pdf = st.file_uploader("上傳 PDF", type=None, key="ai_in_pdf")
                    if pdf:
                        # [Security Fix] 縮排對齊 24 空格，變數名 pdf
                        if not pdf.getvalue().startswith(b"%PDF-"):
                            st.error("❌ " + t("err_invalid_format", "Invalid format: Please upload a PDF file."))
                            st.stop()
                    if pdf: ai_content = extract_text_from_pdf(pdf.getvalue())
            with c2:
                limit = plan_cfg.get("ai_gen_batch_limit", 10)
                ai_num = st.number_input(f"數量 (Max {limit})", 1, max(1, limit), 5)
                ai_type = st.selectbox("題型", ["選擇題", "計算題", "填充題"], key="ai_in_type")
                ai_diff = st.select_slider("難度", ["Easy", "Medium", "Hard"], value="Medium")
                api_key = getattr(user, 'google_key', None) or getattr(user, 'google_api_key', None)
                if st.button("✨ 生成試題", disabled=not (ai_content and api_key)):
                    with st.spinner("AI 運算中..."):
                        res = generate_questions_from_material(api_key, ai_content, {
                            "q_type": ai_type, "count": ai_num, "difficulty": ai_diff
                        })
                        if res.get("success"):
                            clean_qs = normalize_ai_data(res["data"])
                            st.session_state.exam_questions.extend(clean_qs)
                            st.session_state.last_data_hash = str(time.time())
                            st.success(f"已加入 {len(clean_qs)} 題")
                            time.sleep(1)
                            st.rerun()
                        else: st.error(res.get("error"))

    # 2. 試卷設定
    if 'loader_selected_id' in st.session_state:
        st.session_state.pop('loader_selected_id')
        st.toast("已載入試卷草稿")

    with st.expander("⚙️ 試卷表頭與排版設定", expanded=True):
        c_cat1, c_cat2 = st.columns(2)
        exist_cats = ["General", "Midterm", "Final"]
        cat_opts = exist_cats + ["(Create New...)"]
        curr_cat = st.session_state.e_category
        idx = cat_opts.index(curr_cat) if curr_cat in cat_opts else 0
        sel_cat = c_cat1.selectbox("分類", cat_opts, index=idx)
        if sel_cat == "(Create New...)":
            new_cat = c_cat2.text_input("新分類名稱")
            if new_cat: st.session_state.e_category = new_cat
        else: st.session_state.e_category = sel_cat
        st.divider()
        c_h1, c_h2 = st.columns([3, 1])
        st.session_state.e_title = c_h1.text_input("主標題 (Title)", value=st.session_state.e_title)
        st.session_state.e_subject = c_h2.text_input("科目 (Subject)", value=st.session_state.e_subject)
        cm1, cm2, cm3 = st.columns(3)
        st.session_state.e_ay = cm1.text_input("學年度", value=st.session_state.e_ay)
        st.session_state.e_sem = cm2.selectbox("學期", ["上學期", "下學期"], index=0 if st.session_state.e_sem=="上學期" else 1)
        st.session_state.e_type = cm3.selectbox("考試別", ["期中考", "期末考", "小考"], index=0)
        st.text_input("副標題 (Subtitle)", key="e_sub")
        st.text_input("系級/班級 (Dept)", key="e_dept")
        c_time, c_compact = st.columns([1, 1])
        with c_time: st.text_input("考試時間", key="e_time", placeholder="100 min")
        with c_compact:
            st.write(""); st.write("")
            st.checkbox("Compact Header (精簡標頭)", key="e_compact", help="縮減表頭高度")
        st.write("📄 排版模式 (Layout Mode)")
        st.radio("選擇輸出格式：", options=["combined", "separate"], 
            format_func=lambda x: "標準合併 (題目+作答格)" if x == "combined" else "卷卡分離 (試題卷 + 答題卷)",
            key="e_layout", horizontal=True)
        st.text_area("試卷注意事項 (Note)", key="e_note", height=68)

    col_save, col_load = st.columns([1, 1])
    with col_save:
        # [Fix] 修正縮排並依據教授建議使用 width='stretch'
        if st.button("💾 儲存草稿 (Save Draft)", type="primary", width='stretch'):
            can_save, msg = check_user_quota(user.id, getattr(user, 'plan', 'free'), "exam_gen")
            if not can_save: 
                st.error(msg)
            else:
                save_data = {
                    "header": {
                        "title": st.session_state.e_title, 
                        "subject": st.session_state.e_subject,
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
                    save_exam_draft_or_publish(
                        user.id, st.session_state.e_title, st.session_state.e_subject,
                        save_data, False,
                        academic_year=st.session_state.e_ay,
                        semester=st.session_state.e_sem,
                        exam_type=st.session_state.e_type
                    )
                    st.toast("草稿已儲存！")
                    st.success(f"存檔成功。{msg}")
                except Exception as e: st.error(f"存檔失敗: {e}")
    with col_load: st.button("📥 載入最新草稿", width='stretch')

    # 3. 題目列表
    st.write(f"### 試題列表 ({len(st.session_state.exam_questions)})")
    if st.session_state.exam_questions:
        for i, q in enumerate(st.session_state.exam_questions):
            with st.container():
                c_idx, c_content, c_info, c_ops = st.columns([0.5, 4, 1.5, 1])
                c_idx.markdown(f"**Q{i+1}.**")
                subs = q.get('sub_questions', [])
                total_s = q.get('score', 0)
                if subs:
                    try: total_s = sum([float(sq.get('score', 0)) for sq in subs])
                    except: pass
                main_text = q.get('text', '') or f"*({t('lbl_no_content')})*"
                render_text_with_math(c_content, main_text)
                if subs:
                    with c_content.expander(f"包含 {len(subs)} 小題"):
                        for sub_i, sub_q in enumerate(subs):
                            sub_txt = sub_q.get('text', '')
                            st.markdown(f"↳ **({sub_i+1})** *({sub_q.get('score',0)} pts)*")
                            render_text_with_math(st.container(), sub_txt)
                c_info.caption(f"Score: {total_s} | H: {q.get('height', 6)}cm")
                with c_ops:
                    b1, b2 = st.columns(2)
                    if b1.button("✏️", key=f"ed_{i}"):
                        st.session_state.editing_index = i; st.rerun()
                    if b2.button("🗑️", key=f"dl_{i}"):
                        st.session_state.exam_questions.pop(i)
                        st.session_state.editing_index = -1; st.rerun()
                st.divider()

    # 4. 編輯器
    edit_idx = st.session_state.editing_index
    is_edit_mode = edit_idx >= 0
    form_title = f"✏️ 編輯 Q{edit_idx+1}" if is_edit_mode else "➕ 新增題目"
    form_bg = "background-color: #f8f9fa; padding: 20px; border-radius: 10px; border: 1px solid #ddd;" if is_edit_mode else ""
    with st.container():
        st.markdown(f"<div style='{form_bg}'><h4>{form_title}</h4>", unsafe_allow_html=True)
        curr_q = st.session_state.exam_questions[edit_idx] if is_edit_mode else {}
        def_txt = curr_q.get('text', '')
        def_score = curr_q.get('score', 10)
        def_h = curr_q.get('height', 6)
        def_type = curr_q.get('type', '計算題 (一般)')
        q_text = st.text_area("題目內容 (支援 LaTeX)", height=80, key="new_q_text", value=def_txt)
        c1, c2, c3 = st.columns(3)
        q_type_opts = ["計算題 (一般)", "計算題 (大格)", "選擇題", "證明題", "是非題", "填充題"]
        type_idx = q_type_opts.index(def_type) if def_type in q_type_opts else 0
        q_type = c1.selectbox("題型", q_type_opts, index=type_idx, key="new_q_type")
        q_height = c3.number_input("高度 (cm)", 2, 25, value=int(def_h), key="new_q_height")
        options = []; sub_questions = []; has_subs = False; parent_score = 0
        if "選擇" in q_type:
            def_opts = "\n".join(curr_q.get('options', []))
            opts_text = st.text_area("選項 (每行一個)", height=100, key="new_q_opts", value=def_opts)
            if opts_text: options = [o.strip() for o in opts_text.split('\n') if o.strip()]
            parent_score = c2.number_input("配分", 1, 100, value=int(def_score), key="new_q_score_choice")
        else:
            def_subs = curr_q.get('sub_questions', [])
            has_subs = st.checkbox("包含子題", value=bool(def_subs), key="new_q_has_subs")
            if has_subs:
                layout_cols = st.radio("子題排列", [1, 2], horizontal=True, key="new_q_layout")
                num_subs = len(def_subs) if def_subs else 3
                st.caption(f"編輯 {num_subs} 個子題 (如需增減請直接編輯內容)")
                for i in range(num_subs):
                    sq = def_subs[i] if i < len(def_subs) else {}
                    sc1, sc2 = st.columns([4, 1])
                    s_txt = sc1.text_input(f"子題 ({i+1})", value=sq.get('text', ''), key=f"sq_txt_{i}")
                    s_score = sc2.number_input("分", 1, 100, value=int(sq.get('score', 5)), key=f"sq_sc_{i}")
                    if s_txt: sub_questions.append({"text": s_txt, "score": s_score})
                parent_score = sum(s['score'] for s in sub_questions)
                st.caption(f"總分: {parent_score}")
            else:
                parent_score = c2.number_input("配分", 1, 100, value=int(def_score), key="new_q_score_norm")
        st.write("🖼️ 媒體附件 (Media)")
        mt1, mt2 = st.tabs(["上傳圖片", "TikZ 代碼"])
        with mt1: up_img = st.file_uploader("更換圖片", type=['png', 'jpg'], key="new_q_img_up")
        with mt2:
            def_tikz = ""
            if curr_q.get('media') and curr_q['media'].get('type') == 'tikz': def_tikz = curr_q['media']['content']
            tikz_code = st.text_area("TikZ Code", value=def_tikz, height=100, key="new_q_tikz")
        b_col1, b_col2 = st.columns([1, 1])
        btn_label = "💾 更新題目" if is_edit_mode else "➕ 新增題目"
        if b_col1.button(btn_label, type="primary", width='stretch'):
            media_obj = None
            if tikz_code: media_obj = {"type": "tikz", "content": tikz_code}
            elif up_img:
                path = save_uploaded_file(up_img, user.id)
                media_obj = {"type": "image", "content": path}
            new_q = {
                "text": normalize_math_delimiters(sanitize_content(q_text)),
                "score": parent_score, "height": q_height, "type": q_type,
                "media": media_obj, "options": options, "sub_questions": sub_questions, "layout_cols": 1
            }
            if is_edit_mode:
                st.session_state.exam_questions[edit_idx] = new_q
                st.session_state.editing_index = -1; st.toast("題目已更新")
            else:
                st.session_state.exam_questions.append(new_q); st.toast("題目已新增")
            st.rerun()
        if is_edit_mode:
            if b_col2.button("❌ 取消編輯", width='stretch'):
                st.session_state.editing_index = -1; st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # 5. PDF 生成與預覽 (包含手動編譯)
    st.markdown("---")
    st.write("### 3. PDF 生成與預覽")
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

    # [RESTORED] 手動編譯功能
    with st.expander("LaTeX 原始碼預覽 (可手動修改)", expanded=False):
        edited_source = st.text_area("Source Code", value=st.session_state.raw_tex_source, height=300)
        # 如果用戶修改了內容，更新 session state 供按鈕使用
        if edited_source != st.session_state.raw_tex_source:
             st.session_state.raw_tex_source = edited_source

        if st.button("🔧 手動編譯 (Manual Compile)", key="btn_man_compile"):
            with st.spinner("Compiling custom LaTeX..."):
                pdf_bytes = builder.compile_tex_to_pdf(
                    tex_source=st.session_state.raw_tex_source, 
                    exam_id="manual", system_qr_content="MANUAL",
                    marketing_url=None
                )
                if pdf_bytes:
                    st.session_state.generated_pdf = pdf_bytes
                    st.session_state.pdf_filename = "manual_preview.pdf"
                    st.success("手動編譯成功！")
                    st.rerun()
                else:
                    st.error("編譯失敗，請檢查 LaTeX 語法。")

    if st.button("🚀 生成 PDF 試卷", type="primary", width='stretch', disabled=not st.session_state.exam_questions):
        with st.spinner("正在編譯 PDF... (這可能需要幾秒鐘)"):
            pdf_res = builder.generate_pdf(exam_data, st.session_state.exam_questions, user=user)
            if pdf_res and pdf_res[0]:
                st.session_state.generated_pdf = pdf_res[0]
                st.session_state.pdf_filename = pdf_res[1] 
                st.success("PDF 生成成功！")
                st.rerun()
            else: st.error("PDF 生成失敗 (可能是 LaTeX 語法錯誤或缺少字型)")

    if 'generated_pdf' in st.session_state and st.session_state.generated_pdf:
        b64_pdf = base64.b64encode(st.session_state.generated_pdf).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800px" style="border:none;"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
        fname = st.session_state.get('pdf_filename', "exam.pdf")
        st.download_button("📥 下載 PDF", st.session_state.generated_pdf, fname, "application/pdf", width='stretch')
