# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# This software is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.

# ui/dashboard_view.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.12-UI-I18n-Selector
# Description: 
# 1. [I18n] Integrated new PromptService selector with localization support.
# 2. [UX] Split Subject selection into Level -> Subject hierarchy.

from __future__ import annotations
import matplotlib
matplotlib.use('Agg')

import pandas as pd
import zipfile
import logging
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import streamlit as st
import pandas as pd
import json, os, re, time, cv2, datetime, numpy as np
import uuid
import tempfile
import base64
import pytz
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

from google import genai
from google.genai import types

import config
from database.db_manager import (
    get_sys_conf, get_today_batch_count, save_batch_results,
    get_user_weekly_page_count, User
)
from utils.localization import t
from utils.helpers import pdf_to_images, split_pdf_by_pages
from services.grading_service import GradingService
from services.vision_service import VisionService
from services.ai_service import generate_rubric, generate_class_analysis
from services.report_service import (
    merge_and_calculate_data, 
    create_advanced_zip_report, 
    generate_question_analysis_chart, 
    generate_score_distribution_chart, 
    analyze_questions_performance
)
from services.pdf_report_worker import PdfReportWorker
from services.prompt_service import PromptService # [NEW] Import
from services.plans import get_plan_config  # [New] Use centralized config
# [新增] 引入我們剛寫好的方案規則

# ==============================================================================
#  Global Helpers
# ==============================================================================

def render_subject_selector(key_prefix: str):
    """
    [NEW] Multi-level Subject Selector with I18n Support
    Returns: internal_subject_key (str)
    """
    c1, c2 = st.columns(2)
    
    with c1:
        # 1. Get Levels (Key, Display Label)
        levels_data = PromptService.get_levels() 
        level_map = {label: key for key, label in levels_data}
        level_display_list = list(level_map.keys())

        # Select Level
        selected_level_label = st.selectbox(
            t("lbl_grade_level", "Education Level"), 
            level_display_list, 
            index=0, 
            key=f"{key_prefix}_level_ui"
        )
        internal_level_key = level_map[selected_level_label]
    
    with c2:
        # 2. Get Subjects based on Level
        subjects_data = PromptService.get_subjects_by_level(internal_level_key)
        subj_map = {label: key for key, label in subjects_data}
        subj_display_list = list(subj_map.keys())
        
        # Select Subject
        selected_subj_label = st.selectbox(
            t("subject_select"), 
            subj_display_list, 
            index=0, 
            key=f"{key_prefix}_subj_ui"
        )
        internal_subject_key = subj_map[selected_subj_label]
        
    return internal_subject_key

def _calculate_flash_cost(usage_metadata, model="gemini-2.5-flash"):
    if not usage_metadata: return 0.0
    rate_input = 0.075; rate_output = 0.30
    if "pro" in model: rate_input = 1.25; rate_output = 5.00
    in_t = getattr(usage_metadata, 'prompt_token_count', 0) or 0
    out_t = getattr(usage_metadata, 'candidates_token_count', 0) or 0
    return (in_t / 1_000_000 * rate_input) + (out_t / 1_000_000 * rate_output)

def _safe_float(value, default=0.0):
    if value is None: return default
    try: return float(value)
    except: return default

def _normalize_id_ui(raw_id: str) -> str:
    s = str(raw_id).strip().lower()
    return re.sub(r'[^a-z0-9]', '', s)

def _safe_json_loads(text: str):
    if not isinstance(text, str) or not text.strip(): return None
    try: return json.loads(text.strip())
    except: pass
    if m := re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE):
        try: return json.loads(m.group(1))
        except: pass
    s_idx = text.find('{'); e_idx = text.rfind('}')
    if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
        try: return json.loads(text[s_idx:e_idx+1])
        except: pass
    return None

def _map_rubric_to_labels(rubric_json: dict) -> list[str]:
    labels = []
    if not rubric_json or "questions" not in rubric_json: return []
    for q in rubric_json["questions"]:
        pid = str(q.get("id", "Q?")).strip()
        if "sub_questions" in q and isinstance(q["sub_questions"], list) and len(q["sub_questions"]) > 0:
            for i, sub in enumerate(q["sub_questions"]):
                sid = str(sub.get("id", "")).strip()
                if sid.startswith(pid): labels.append(sid)
                else:
                    clean_sid = re.sub(r"[^0-9a-zA-Z]", "", sid)
                    if not clean_sid: clean_sid = str(i+1)
                    labels.append(f"{pid}-{clean_sid}")
        else: labels.append(pid)
    return labels

def _generate_meaningful_batch_id(user) -> str:
    clean_name = re.sub(r"[^a-zA-Z0-9]", "", user.username)
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    target_tz_str = getattr(user, 'timezone', 'Asia/Taipei')
    if not target_tz_str: target_tz_str = 'Asia/Taipei'
    try: user_tz = pytz.timezone(target_tz_str)
    except: user_tz = pytz.timezone('Asia/Taipei')
    local_now = utc_now.astimezone(user_tz)
    today_str = local_now.strftime("%Y%m%d")
    count = get_today_batch_count(user.id)
    return f"report_{clean_name}_{today_str}_{count + 1:02d}"

def _save_student_pdf(batch_id: str, student_id: str, pdf_chunk) -> str:
    path = os.path.join(config.SPLITS_DIR, batch_id)
    os.makedirs(path, exist_ok=True)
    safe_id = re.sub(r'[^a-zA-Z0-9\-_]', '', str(student_id))
    if not safe_id: safe_id = "unknown"
    f_path = os.path.join(path, f"{safe_id}.pdf")
    with open(f_path, "wb") as f:
        if hasattr(pdf_chunk, "getvalue"): f.write(pdf_chunk.getvalue())
        else: f.write(pdf_chunk)
    return f_path

def _get_max_workers(user=None):
    plan = "free"
    if user and hasattr(user, 'plan') and user.plan:
        plan = user.plan.lower().strip()
    db_key = f"MAX_WORKERS_{plan.upper()}"
    try:
        db_val = get_sys_conf(db_key)
        if db_val and str(db_val).isdigit(): return int(db_val)
    except: pass
    if hasattr(config, 'PLAN_MAX_WORKERS') and isinstance(config.PLAN_MAX_WORKERS, dict):
        config_val = config.PLAN_MAX_WORKERS.get(plan)
        if config_val: return int(config_val)
    return getattr(config, 'DEFAULT_MAX_WORKERS', 3)

def _identify_student_info(user, img_pil, ratio):
    if not user.google_api_key: return None, None, 0.0
    try:
        if isinstance(img_pil, Image.Image): cv_img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        else: cv_img = img_pil
        aligned = VisionService.align_document(cv_img)
        crop = VisionService.extract_header_image(aligned, True, ratio)
        cost = 0.0
        if crop is not None and crop.size > 0:
            pil_crop = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            img_byte_arr = BytesIO(); pil_crop.save(img_byte_arr, format='PNG')
            client = genai.Client(api_key=user.google_api_key)
            prompt = """
            Identify the **Handwritten Name** (姓名) and **Student ID** (學號).
            Output JSON: {"Student ID": "...", "Name": "..."}
            If text is unclear or missing, use "Unknown".
            """
            resp = client.models.generate_content(
                model='gemini-2.5-pro', 
                contents=[prompt, types.Part.from_bytes(data=img_byte_arr.getvalue(), mime_type='image/png')], 
                config={'response_mime_type': 'application/json'}
            )
            cost = _calculate_flash_cost(resp.usage_metadata, 'gemini-2.5-pro')
            try:
                text = resp.text.strip()
                if text.startswith("```json"): text = text[7:-3]
                d = json.loads(text)
                sid = str(d.get("Student ID", "")).strip()
                name = str(d.get("Name", "")).strip()
                if sid.lower() in ["unknown", "none", "null"]: sid = ""
                if name.lower() in ["unknown", "none", "null"]: name = ""
                if not sid and not name: return None, None, cost
                return sid, name, cost
            except: pass
    except Exception as e:
        print(f"[Dashboard] Identity OCR Error: {e}")
        return None, None, 0.0
    return None, None, 0.0

def display_pdf(pdf_input, height=600):
    try:
        if isinstance(pdf_input, bytes): base64_pdf = base64.b64encode(pdf_input).decode('utf-8')
        elif isinstance(pdf_input, BytesIO): base64_pdf = base64.b64encode(pdf_input.getvalue()).decode('utf-8')
        elif hasattr(pdf_input, "read"): base64_pdf = base64.b64encode(pdf_input.read()).decode('utf-8')
        else: return
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="{height}px" type="application/pdf" style="min-width: 400px; max-width: 100%; border: 1px solid #ddd; border-radius: 5px;"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e: st.error(f"{t('err_pdf_preview')}: {e}")

def _find_max_score_in_rubric_json(rubric_json, q_id):
    if not rubric_json or "questions" not in rubric_json: return None
    target_norm = _normalize_id_ui(q_id)
    for q in rubric_json["questions"]:
        q_norm = _normalize_id_ui(q.get("id", ""))
        if q_norm == target_norm:
            return float(q.get("points", q.get("score", 0)))
        if "sub_questions" in q:
            for sub in q["sub_questions"]:
                sub_norm = _normalize_id_ui(sub.get("id", ""))
                def get_val(item): return float(item.get("points", item.get("score", 0)))
                if sub_norm == target_norm: return get_val(sub)
                if (q_norm + sub_norm) == target_norm: return get_val(sub)
    return None

def render_step_indicator(step):
    steps = [t("step_1"), t("step_2"), t("step_3")]
    html = '<div style="display: flex; justify-content: space-between; margin-bottom: 25px;">'
    for i, name in enumerate(steps):
        step_num = i + 1
        is_finished = (step_num < step) or (step == 3 and step_num == 3)
        is_active = (step_num == step)
        if is_finished: color = "#28a745"; icon = "✓"; font_weight = "bold"
        elif is_active: color = "#4B7BEC"; icon = str(step_num); font_weight = "bold"
        else: color = "#999"; icon = str(step_num); font_weight = "normal"
        html += f'''
        <div style="text-align: center; color: {color}; font-weight: {font_weight};">
            <div style="width: 32px; height: 32px; border-radius: 50%; background: {color}; color: #fff; display: flex; align-items: center; justify-content: center; margin: 0 auto 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">{icon}</div>
            <div>{name}</div>
        </div>'''
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# ==============================================================================
#  STEP 1
# ==============================================================================

def render_step_1_rubric(user):
    st.header(t("step_1"))
    ss = st.session_state
    editor_key = "rubric_editor_fixed"
    if editor_key not in ss: ss[editor_key] = ""
    
    # [FIXED] Using new subject selector
    internal_subject = render_subject_selector(key_prefix="rubric_gen")
    
    c1, c2 = st.columns(2)
    with c1:
        up = st.file_uploader(t("upload_rubric_label"), type=["pdf"], key="rub_up")
        if up and st.button(t("ai_gen_rubric"), type="primary"):
            with st.spinner(t("analyzing")):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
                    tf.write(up.getvalue()); tpath = tf.name
                lang = ss.get("language", "繁體中文")
                try:
                    res = generate_rubric(tpath, user.model_name, user.google_api_key, subject=internal_subject, language=lang)
                    if res: ss[editor_key] = res; st.rerun()
                finally:
                    if os.path.exists(tpath): os.unlink(tpath)
    with c2:
        st.subheader(t("edit_rubric_header"))
        r_txt = st.text_area(t("rubric_area_label"), height=500, key=editor_key)
        ss["rubric_content"] = r_txt
        if _safe_json_loads(r_txt) and st.button(t("save_next") + " ➡️", type="primary"):
            ss["rubric_json"] = _safe_json_loads(r_txt); ss["current_step"] = 2; st.rerun()

# ==============================================================================
#  STEP 2 (Grading)
# ==============================================================================

def render_step_2_grading(user):
    st.header(t("step_2"))
    ss = st.session_state
    rub_json = ss.get("rubric_json", {})
    
    if st.button("⬅️ " + t("prepare_rubric"), type="secondary"):
        ss["current_step"] = 1
        st.rerun()

    col_conf, col_file = st.columns([1, 2])
    with col_conf:
        st.subheader("⚙️ " + t("grading_settings"))
        
        # [FIXED] Using new subject selector
        internal_subject = render_subject_selector(key_prefix="grading_exec")
        st.caption(f"🔧 System Key: `{internal_subject}`") 
        
        # [MODIFIED] Logic Preservation with Localization
        strat_opts = ["Vertical (Full Page)", "Collage (Fast Grid)"]
        strat_map = {"Vertical (Full Page)": t("strat_vertical", "Vertical"), "Collage (Fast Grid)": t("strat_collage", "Collage")}
        
        strategy_raw = st.radio(
            t("grading_strategy"), 
            strat_opts, 
            index=1,
            format_func=lambda x: strat_map.get(x, x)
        )

        mode = st.select_slider(t("mode_label"), ["Standard", "Strict"])
        report_mode = st.radio(t("report_mode"), options=["simple", "full"], index=0)
        ss["report_mode"] = report_mode
        temp_val = st.slider(t("lbl_temperature", "Temperature"), 0.0, 1.0, 0.0, 0.05)
        st.markdown("---")
        with st.expander(f"📐 {t('lbl_vision_settings', 'Vision')}", expanded=True):
            man_ratio = st.slider(t("lbl_header_ratio", "Header Ratio"), 0.10, 0.70, 0.25, 0.01)
            ignore_first = st.checkbox(t("lbl_ignore_first", "Ignore 1st Box"), help=t("help_ignore_first", "Skip box 1"))

    with col_file:
        up_pdf = st.file_uploader(t("upload_exam_label"), type=["pdf"], key="exam_up")
        if up_pdf:
            pps = st.number_input(t("pps_label"), 1, 10, 2)
            if st.button(f"✂️ {t('split_btn')}", type="primary"):
                with st.spinner(t("splitting")):
                    ss["exam_chunks"] = split_pdf_by_pages(up_pdf, pps); st.rerun()
            
            if ss.get("exam_chunks"):
                chunks = ss["exam_chunks"]
                st.info(f"📚 {len(chunks)} {t('msg_students_loaded', 'Students')}")
                
                # Check raw value for logic
                if "Collage" in strategy_raw:
                    st.markdown(f"#### 🖼️ {t('hdr_layout_analysis', 'Layout Analysis')}")
                    c_btn_1, c_btn_2 = st.columns([1, 1])
                    trigger_analysis = False
                    with c_btn_1:
                        if st.button(f"🔍 {t('btn_detect_layout', 'Detect Layout')}", type="secondary"): trigger_analysis = True
                    with c_btn_2:
                         if st.button(f"❌ {t('btn_reset_layout', 'Reset')}"): ss.pop("layout_map", None); st.rerun()

                    if trigger_analysis:
                        with st.spinner(t("msg_analyzing_layout", "Analyzing...")):
                            imgs = pdf_to_images(chunks[0])
                            rubric_json = ss.get("rubric_json", {})
                            all_labels = _map_rubric_to_labels(rubric_json)
                            if not all_labels: st.warning(f"⚠️ {t('warn_no_rubric_detected', 'No Rubric')}")
                            
                            label_cursor = 0 
                            full_layout_list = []
                            for page_idx, page_img in enumerate(imgs):
                                cv_img = cv2.cvtColor(np.array(page_img), cv2.COLOR_RGB2BGR)
                                aligned = VisionService.align_document(cv_img)
                                is_p1 = (page_idx == 0)
                                boxes, cutoff = VisionService.detect_answer_areas(aligned, is_first_page=is_p1, manual_p1_ratio=man_ratio)
                                if ignore_first and is_p1 and boxes: boxes.pop(0)

                                current_page_labels = []
                                if all_labels:
                                    count = len(boxes)
                                    current_page_labels = all_labels[label_cursor : label_cursor + count]
                                    label_cursor += count
                                
                                debug_img = VisionService.draw_debug_boxes(aligned, boxes, labels=current_page_labels, actual_cutoff=cutoff)
                                full_layout_list.append({"page": page_idx, "boxes": boxes, "vis_img": debug_img})
                            ss["layout_map"] = full_layout_list

                    if ss.get("layout_map"):
                        st.success(f"✅ {t('msg_layout_analyzed', 'Done')}: {len(ss['layout_map'])} Pages")
                        for p_data in ss["layout_map"]:
                            st.image(cv2.cvtColor(p_data['vis_img'], cv2.COLOR_BGR2RGB), caption=f"Page {p_data['page']+1}", width='stretch')

                with st.expander(f"👀 {t('preview_chunks')}", expanded=True):
                    num_chunks = len(chunks)
                    idx = st.slider("Student", 0, num_chunks - 1, 0) if num_chunks > 1 else 0
                    st.markdown("### 📄 PDF Preview")
                    if idx < len(chunks): display_pdf(chunks[idx], height=600) 
                
                if st.button(t("start_grading_btn"), type="primary"):
                    user_plan = user.plan
                    current_weekly_usage = get_user_weekly_page_count(user.id)
                    custom_page = int(getattr(user, 'custom_page_limit', 0) or 0)
                    if custom_page > 0: max_limit = custom_page
                    else:
                        plan_key = f"QUOTA_{user.plan.upper()}_WEEKLY_PAGES"
                        fallback = {"free": 70, "pro": 500, "premium": 1000, "enterprise": 5000}.get(user.plan, 70)
                        max_limit = int(get_sys_conf(plan_key) or fallback)

                    incoming_pages = len(chunks) * pps
                    if (current_weekly_usage + incoming_pages) > max_limit:
                        st.error(f"❌ {t('quota_exceeded_msg')}")
                    else: 
                        rubric_content = ss.get("rubric_content", "")
                        if "Collage" in strategy_raw:
                            _run_collage_batch(user, chunks, rubric_content, rub_json, man_ratio, temp_val, mode, internal_subject, ignore_first=ignore_first)
                        else:
                            _run_vertical_batch(user, chunks, mode, man_ratio, temp_val, internal_subject, rub_json)

def _update_status(status_container, start_time, done, total, current_task):
    elapsed = time.time() - start_time
    rate = done / elapsed if elapsed > 0 and done > 0 else 0.0
    remaining = total - done
    eta_str = f"{(remaining / rate):.1f}s" if rate > 0 else t("calc_eta", "Calculating...")
    prog = min(1.0, done / total) if total > 0 else 0
    html = f"""
    <div style="border:1px solid #ddd; padding:12px; border-radius:10px; background-color:#f9f9f9; margin-bottom:15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="color:#2c3e50; font-weight:600; font-size:15px;">🔄 {current_task}</span>
            <span style="color:#e67e22; font-weight:bold; font-size:16px;">{int(prog*100)}%</span>
        </div>
        <div style="width:100%; background-color:#e0e0e0; height:100%; border-radius:5px; overflow:hidden;">
            <div style="width:{prog*100}%; background-color:#4B7BEC; height:100%; border-radius:5px; transition: width 0.5s ease;"></div>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:13px; margin-top:8px; color:#555;">
            <span>⏱️ Elapsed: <b>{elapsed:.1f}s</b></span>
            <span>🚀 Speed: <b>{rate:.2f} it/s</b></span>
            <span>🏁 ETA: <b>{eta_str}</b></span>
        </div>
    </div>
    """
    status_container.markdown(html, unsafe_allow_html=True)

class AtomicBatchProcessor:
    def __init__(self, batch_size=9, grid_cols=3):
        self.batch_size = batch_size
        self.grid_cols = grid_cols

    def create_batches(self, items, unit_size=(1024, 600)):
        batches_result = []
        for i in range(0, len(items), self.batch_size):
            chunk = items[i : i + self.batch_size]
            batches_result.append(self._create_single_batch(chunk, unit_size))
        return batches_result

    def _create_single_batch(self, items, unit_size):
        unit_w, unit_h = unit_size
        grid_rows = (self.batch_size + self.grid_cols - 1) // self.grid_cols
        canvas = np.full((grid_rows * unit_h, self.grid_cols * unit_w, 3), 255, dtype=np.uint8)
        batch_uuid = str(uuid.uuid4())[:8]
        manifest = {"batch_id": batch_uuid, "cells": []}
        for idx in range(self.batch_size):
            r = idx // self.grid_cols; c = idx % self.grid_cols
            x_start = c * unit_w; y_start = r * unit_h
            cell_data = {"index": idx, "is_empty": True, "sid": None}
            if idx < len(items):
                item = items[idx]; src_img = item['img']
                resized_img = cv2.resize(src_img, (unit_w, unit_h), interpolation=cv2.INTER_LANCZOS4)
                canvas[y_start : y_start+unit_h, x_start : x_start+unit_w] = resized_img
                cell_data["is_empty"] = False; cell_data["sid"] = item['sid']
            manifest["cells"].append(cell_data)
        return {"image": canvas, "manifest": manifest, "batch_id": batch_uuid}

def _run_vertical_batch(user, chunks, mode, ratio, temp, subject, rubric_json):
    ss = st.session_state
    status_box = st.empty()
    bid = _generate_meaningful_batch_id(user)
    ss["current_batch_id"] = bid
    workers = _get_max_workers(user) 
    start_t = time.time()
    total = len(chunks)
    results = []
    
    allowed_labels = _map_rubric_to_labels(rubric_json)
    current_lang = ss.get("language", "繁體中文")

    _update_status(status_box, start_t, 0, total, f"{t('status_init_ai', 'Init AI')} ({subject} Mode)...")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(
            _process_single_student_vert, 
            user, i, ck, ss.get("rubric_content", ""), bid, mode, ratio, temp, allowed_labels, current_lang, subject, rubric_json
        ): i for i, ck in enumerate(chunks)}
        
        for i, f in enumerate(as_completed(futures)):
            try:
                res = f.result()
                results.append(res)
                _update_status(status_box, start_t, i + 1, total, f"{t('status_grading_student', 'Grading')} {i+1}/{total}")
            except Exception as e:
                print(f"Error: {e}")

    if results:
        save_batch_results(user.id, bid, results)
        ss["grading_results"] = results
        ss["current_step"] = 3
        st.rerun()
    else:
        st.error(t("err_grading_failed"))

def _process_single_student_vert(user, idx, ck, rubric, bid, mode, ratio, temp, allowed_labels, lang, subject, rubric_json):
    imgs = pdf_to_images(ck)
    rid, rname, cost_ocr = _identify_student_info(user, imgs[0], ratio)
    
    res = GradingService.grade_submission(
        images=imgs, rubric_text=rubric, user=user, batch_id=bid, student_idx=idx+1, 
        mode=mode, subject=subject, ai_memory="", temperature=temp, 
        allowed_labels=allowed_labels, language=lang
    )
    
    recalc_total = 0.0
    if "questions" in res and rubric_json:
        for q in res["questions"]:
            q_id = q.get("id")
            score = float(q.get("score", 0))
            max_val = _find_max_score_in_rubric_json(rubric_json, q_id)
            if max_val is not None:
                q["max_score"] = max_val 
                if score > max_val:
                    q["original_ai_score"] = score
                    q["score"] = max_val
                    score = max_val
                    q["reasoning"] += f"\n[System Correction] Score capped at {max_val}."
            recalc_total += score
        res["total_score"] = recalc_total

    score = _safe_float(res.get("total_score") if res.get("total_score") is not None else res.get("score"), 0.0)
    cost_grading = _safe_float(res.get("cost_usd"), 0.0)
    total_cost = cost_ocr + cost_grading
    sid = rid if rid else f"S{idx+1:03d}"
    file_path = _save_student_pdf(bid, sid, ck)
    res["rubric"] = rubric_json 
    res.update({
        "Student ID": sid, "Name": rname or "Unknown", 
        "total_score": score, "cost_usd": total_cost, 
        "cost_breakdown": {"flash_ocr": cost_ocr, "pro_grading": cost_grading},
        "file_path": file_path, "page_count": len(imgs)
    })
    return res

def _run_collage_batch(user, chunks, rubric_text, rubric_json, ratio, temp, mode, subject, ignore_first=False):
    ss = st.session_state
    status_box = st.empty()
    start_t = time.time()
    bid = _generate_meaningful_batch_id(user)
    ss["current_batch_id"] = bid
    current_lang = ss.get("language", "繁體中文")
    workers = _get_max_workers(user)
    
    total_chunks = len(chunks)
    student_map = [] 
    
    _update_status(status_box, start_t, 0, total_chunks * 3, t("status_phase_1", "Phase 1"))
    for i, ck in enumerate(chunks):
        imgs = pdf_to_images(ck)
        sid, name, cost = _identify_student_info(user, imgs[0], ratio)
        display_sid = sid if sid else f"S{i+1:03d}"
        f_path = _save_student_pdf(bid, display_sid, ck)
        cv_imgs = [cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR) for img in imgs]
        student_map.append({
            "idx": i, "sid": display_sid, "name": name, "cv_imgs": cv_imgs, 
            "cost_ocr": cost, "file_path": f_path, "page_count": len(imgs)
        })
        _update_status(status_box, start_t, i+1, total_chunks * 3, f"{t('status_scanning', 'Scan')}: {display_sid}")

    _update_status(status_box, start_t, total_chunks, total_chunks * 3, t("status_phase_2", "Phase 2"))
    q_labels = _map_rubric_to_labels(rubric_json)
    
    if ss.get("layout_map") and isinstance(ss["layout_map"], list):
        template_meta = []
        box_ptr = 0
        expected_count = len(q_labels)
        for page_data in ss["layout_map"]:
            p_idx = page_data["page"]
            boxes = page_data["boxes"]
            for b in boxes:
                 lbl = q_labels[box_ptr] if box_ptr < expected_count else f"Extra_{box_ptr}"
                 template_meta.append({"page": p_idx, "box": b, "label": lbl})
                 box_ptr += 1
    else:
        template_meta = None
        expected_count = len(q_labels)
        scan_limit = 20
        checked_count = 0
        for s in student_map:
            if checked_count >= scan_limit: break
            checked_count += 1
            if len(s["cv_imgs"]) < 1: continue
            detected_meta = []
            total_boxes = 0
            for p_idx, img in enumerate(s["cv_imgs"]):
                aligned = VisionService.align_document(img)
                boxes, _ = VisionService.detect_answer_areas(aligned, is_first_page=(p_idx==0), manual_p1_ratio=ratio)
                if ignore_first and (p_idx == 0) and boxes: boxes.pop(0)
                for b in boxes: detected_meta.append({"page": p_idx, "box": b})
                total_boxes += len(boxes)
            
            if total_boxes == expected_count:
                final_meta = []
                for idx, item in enumerate(detected_meta):
                    lbl = q_labels[idx] if idx < expected_count else f"Extra_{idx}"
                    item["label"] = lbl
                    final_meta.append(item)
                template_meta = final_meta
                break

        if template_meta is None:
            s = student_map[0]
            detected_meta = []
            box_ptr = 0
            for p_idx, img in enumerate(s["cv_imgs"]):
                aligned = VisionService.align_document(img)
                boxes, _ = VisionService.detect_answer_areas(aligned, is_first_page=(p_idx==0), manual_p1_ratio=ratio)
                if ignore_first and (p_idx == 0) and boxes: boxes.pop(0)
                for b in boxes:
                    lbl = q_labels[box_ptr] if box_ptr < expected_count else f"Extra_{box_ptr}"
                    detected_meta.append({"page": p_idx, "box": b, "label": lbl})
                    box_ptr += 1
            template_meta = detected_meta
    
    question_batches = {lbl: [] for lbl in q_labels}
    for stu in student_map:
        for meta in template_meta:
            lbl = meta["label"]
            if lbl not in question_batches: continue
            if meta["page"] < len(stu["cv_imgs"]):
                raw_img = stu["cv_imgs"][meta["page"]]
                aligned = VisionService.align_document(raw_img)
                crops = VisionService.crop_images_by_layout(aligned, [meta["box"]])
                if crops: question_batches[lbl].append({"sid": stu["sid"], "img": crops[0]})

    final_grades = {}
    for s in student_map:
        final_grades[s["sid"]] = {
            "Student ID": s["sid"], "Name": s["name"] or "Unknown", "questions": [], 
            "total_score": 0, "cost_usd": s["cost_ocr"], "file_path": s["file_path"], 
            "cost_breakdown": {"flash_ocr": s["cost_ocr"], "pro_grading": 0.0},
            "rubric": rubric_json, "page_count": s.get("page_count", 1)
        }
        
    BATCH_SIZE = 9; GRID_COLS = 3
    processor = AtomicBatchProcessor(batch_size=BATCH_SIZE, grid_cols=GRID_COLS)
    total_grids = sum([int(np.ceil(len(v)/BATCH_SIZE)) for v in question_batches.values()])
    grids_completed = 0
    _update_status(status_box, start_t, total_chunks * 1.5, total_chunks * 3, f"{t('status_phase_3', 'Phase 3')} (Workers: {workers})...")
    
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = []
        for q_id, items in question_batches.items():
            if not items: continue 
            atomic_batches = processor.create_batches(items)
            for ab in atomic_batches:
                valid_indices = [c['index'] for c in ab['manifest']['cells'] if not c['is_empty']]
                
                grid_pil = Image.fromarray(cv2.cvtColor(ab['image'], cv2.COLOR_BGR2RGB))
                f = ex.submit(
                    GradingService.grade_collage_submission, 
                    grid_pil, q_id, rubric_text, user, mode, 
                    subject, temp, "gemini-2.5-pro", 
                    allowed_labels=q_labels,
                    valid_indices=valid_indices,
                    language=current_lang
                )
                futures.append((f, q_id, ab['manifest']))
        
        for f, q_id, manifest in futures:
            try:
                res_data = f.result()
                ai_results = res_data.get("results", [])
                cost = res_data.get("cost_usd", 0)
                valid_cnt = sum(1 for c in manifest['cells'] if not c['is_empty'])
                unit_cost = cost / max(1, valid_cnt)
                max_val = _find_max_score_in_rubric_json(rubric_json, q_id)

                for i, cell in enumerate(manifest['cells']):
                    if cell['is_empty']: continue
                    sid = cell['sid']
                    score = 0.0; reasoning = ""; breakdown = []
                    
                    if i < len(ai_results):
                        item_result = ai_results[i]
                        try: score = float(item_result.get("score", 0))
                        except: pass
                        reasoning = item_result.get("reasoning", "")
                        breakdown = item_result.get("breakdown", [])
                    
                    q_data = {"id": q_id, "score": score, "reasoning": reasoning, "breakdown": breakdown}
                    if max_val is not None:
                        q_data["max_score"] = max_val
                        if score > max_val:
                            q_data["original_ai_score"] = score
                            q_data["score"] = max_val
                            score = max_val
                            q_data["reasoning"] += f" [System Correction: Capped at {max_val}]"

                    if sid in final_grades:
                        final_grades[sid]["cost_usd"] += unit_cost
                        final_grades[sid]["cost_breakdown"]["pro_grading"] += unit_cost
                        final_grades[sid]["questions"].append(q_data)
                        final_grades[sid]["total_score"] += score
                
                grids_completed += 1
                current_prog = (total_chunks * 1.5) + (grids_completed / max(1, total_grids) * (total_chunks * 1.5))
                _update_status(status_box, start_t, current_prog, total_chunks * 3, f"Grading {q_id} (Grid {grids_completed}/{total_grids})")
            except Exception as e: print(f"Atomic Batch Error: {e}")

    results_list = list(final_grades.values())
    if results_list:
        save_batch_results(user.id, bid, results_list)
        ss["grading_results"] = results_list
        ss["current_step"] = 3
        st.rerun()
    else: st.error(t("err_grading_failed"))

def render_step_3_report(user):
    ss = st.session_state
    res = ss.get("grading_results", [])
    bid = ss.get("current_batch_id", "UNK")
    rubric_json = ss.get("rubric_json", {})
    if not res: st.warning(t("no_results_yet")); return

    df, cost = merge_and_calculate_data(res)
    if "Final Score" not in df.columns: df["Final Score"] = 0.0
    q_stats_df = analyze_questions_performance(res, rubric_json)
    
    st.success(f"✅ {t('batch_complete')}")
    st.dataframe(df)

    st.subheader(f"📊 {t('statistics_overview')}")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"##### 📈 {t('chart_score_dist', 'Score Dist')}")
        try:
            fig = generate_score_distribution_chart(df)
            if fig:
                st.pyplot(fig)
                plt.close(fig)
        except: pass
    with c2:
        st.markdown(f"##### 📉 {t('chart_question_analysis', 'Analysis')}")
        try:
            fig = generate_question_analysis_chart(q_stats_df)
            if fig: 
                st.pyplot(fig)
                plt.close(fig)
        except: pass

    st.markdown("---")
    total_flash = sum([r.get("cost_breakdown", {}).get("flash_ocr", 0) for r in res])
    total_pro = sum([r.get("cost_breakdown", {}).get("pro_grading", 0) for r in res])
    total_sum = total_flash + total_pro
    st.markdown(f"#### 💰 {t('hdr_cost_analysis', 'Cost')}")
    c1_c, c2_c, c3_c = st.columns(3)
    c1_c.metric("⚡ Flash (OCR)", f"${total_flash:.4f}")
    c2_c.metric("🧠 Pro (Grading)", f"${total_pro:.4f}")
    c3_c.metric("💵 Total", f"${total_sum:.4f}")
    
    m1, m2, m3, m4 = st.columns(4)
    scores = df["Final Score"]
    pass_len = len(scores[scores >= 60])
    m1.metric(t("average_score"), f"{scores.mean():.1f}")
    m2.metric(t("median_score"), f"{scores.median():.1f}")
    m3.metric(t("pass_count"), f"{pass_len}")
    m4.metric(t("pass_rate"), f"{(pass_len/len(scores)*100 if len(scores) else 0):.1f}%")

    if st.button(f"✨ {t('gen_class_analysis_btn')}", type="primary"):
        with st.spinner(t("analyzing")):
            ss["class_analysis"] = generate_class_analysis(
                res, ss.get("rubric_content", ""), user.google_api_key, 
                report_mode=ss.get("report_mode", "simple"), language=ss.get("language", "繁體中文")
            )
            st.rerun()
            
    pdf_bytes = None
    if "class_analysis" in ss:
        st.markdown(ss["class_analysis"])
        pdf_cache_key = f"pdf_cache_{bid}"
        if pdf_cache_key not in ss:
            with st.spinner(t("msg_generating_pdf", "Generating PDF...")):
                try: 
                    ss[pdf_cache_key] = PdfReportWorker.generate_professional_pdf(bid, df, ss["class_analysis"], user=user, q_stats_df=q_stats_df)
                except Exception as e: st.error(f"PDF Error: {e}")
        pdf_bytes = ss.get(pdf_cache_key)
        if pdf_bytes: st.download_button(t("btn_download_pdf", "Download PDF"), pdf_bytes, f"{bid}.pdf", "application/pdf")

    zip_buf = create_advanced_zip_report(bid, df, ss.get("class_analysis", ""), q_stats_df=q_stats_df, pdf_bytes=pdf_bytes)
    st.download_button(t("btn_download_zip", "Download ZIP"), zip_buf, f"{bid}.zip", "application/zip", type="primary")
    
    if st.button(f"🔄 {t('btn_new_session', 'New Session')}"):
        for k in ["grading_results", "exam_chunks", "class_analysis", "layout_map", "rubric_editor_lock_final", "rubric_json"]: ss.pop(k, None)
        pdf_cache_key = f"pdf_cache_{bid}"
        if pdf_cache_key in ss: del ss[pdf_cache_key]
        ss["current_step"] = 1; st.rerun()

# ui/dashboard_view.py

def render_dashboard(user):
    # 1. API Key 檢查 (保留原本的 BYOK 邏輯)
    user_api_key = getattr(user, 'google_api_key', None) 
    if not user_api_key or not str(user_api_key).strip():
        st.error("BYOK_REQUIRED: Missing API Key. Please configure your Gemini API Key in Settings.")
        st.info(f"💡 {t('msg_no_api_key', 'No API Key')}")
        st.warning(f"⚠️ {t('msg_system_locked', 'Locked')}")
        st.stop()
 
    st.title(t("app_title"))
    
    # 2. 側邊欄配額顯示 (核心修改處)
    with st.sidebar:
        st.markdown("---")
        st.subheader(f"📊 {t('usage_header')}")
        
        # [A] 取得本週已用量
        current_p = get_user_weekly_page_count(user.id)
        
        # [B] 讀取方案設定 (從 services/plans.py)
        # 這裡會自動讀取個人版的 300 頁，或是機構版的 5000 頁
        plan_conf = get_plan_config(user.plan)
        default_limit = plan_conf.get("grading_pages", 0)
        
        # [C] 機構版客製化邏輯 (Business Override)
        # 只有機構版才允許讀取 custom_page_limit，個人版強制使用 default_limit (300)
        limit_p = default_limit
        if user.plan == "business":
            custom = int(getattr(user, 'custom_page_limit', 0) or 0)
            if custom > 0:
                limit_p = custom

        # [D] 顯示進度條
        # 避免分母為 0 的錯誤
        if limit_p > 0:
            p_ratio = min(current_p / limit_p, 1.0)
        else:
            p_ratio = 0.0
            
        st.write(f"📝 {t('lbl_quota')}: {current_p} / {limit_p}")
        st.progress(p_ratio)
        
        if current_p >= limit_p:
            st.error(t("quota_exceeded_msg"))
            
        st.markdown("---")

    # 3. 步驟路由 (保留您原本的邏輯)
    if "current_step" not in st.session_state: 
        st.session_state["current_step"] = 1
        
    step = st.session_state["current_step"]
    render_step_indicator(step) # 請確保您檔案內有此函式
    
    # 呼叫您原檔內的步驟函式 (不做任何更動)
    if step == 1: 
        render_step_1_rubric(user)
    elif step == 2: 
        render_step_2_grading(user)
    elif step == 3: 
        render_step_3_report(user)