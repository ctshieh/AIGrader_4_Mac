# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# This software is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.

# ui/history_view.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.21-History-Timezone-Fix
# Description: 
# 1. [Fix] Timezone: Added UTC-to-Local conversion for history records (Fixes -8h issue).
# 2. [Maintain] Retains all previous math rendering and chart fixes.

from __future__ import annotations
import streamlit as st
import pandas as pd
import json
import os
import re
import math
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import datetime # [NEW] 引入時間處理
import pytz     # [NEW] 引入時區處理

# 匯入 Config
import config

# 匯入 DB 模組
try:
    from database.db_manager import (
        get_user_history_batches, 
        get_batch_details, 
        delete_user_batch,
        update_student_score
    )
except ImportError:
    st.error("❌ 嚴重錯誤：找不到 database.db_manager 模組。")
    st.stop()

from utils.localization import t

# --- 設定：匯率處理 ---
try:
    current_exchange_rate = float(getattr(config, 'EXCHANGE_RATE_TWD', 32.5))
except:
    current_exchange_rate = 32.5

# ==============================================================================
# [Timezone Tool] 時區轉換小工具 (這是修復時間顯示的核心)
# ==============================================================================
def format_utc_to_local(dt_input, user, fmt="%Y-%m-%d %H:%M"):
    """
    [Timezone Fix] 將 DB 內的 UTC 時間轉換為 User 的當地時間
    解決歷史紀錄顯示慢 8 小時的問題。
    """
    if dt_input is None: return "-"
    
    try:
        # 0. 處理 Pandas Timestamp
        if isinstance(dt_input, pd.Timestamp):
            dt_input = dt_input.to_pydatetime()

        # 1. 字串轉 Datetime (防呆)
        if isinstance(dt_input, str):
            try: dt_input = datetime.datetime.fromisoformat(str(dt_input))
            except: return str(dt_input)
        
        # 2. 確保有時區 (DB 拿出來的通常是 naive datetime，視為 UTC)
        if dt_input.tzinfo is None:
            dt_input = dt_input.replace(tzinfo=datetime.timezone.utc)
            
        # 3. 取得 User 時區 (預設 Asia/Taipei)
        tz_str = getattr(user, 'timezone', 'Asia/Taipei')
        if not tz_str: tz_str = 'Asia/Taipei'
        
        try: user_tz = pytz.timezone(tz_str)
        except: user_tz = pytz.timezone('Asia/Taipei')
            
        # 4. 轉換並格式化
        return dt_input.astimezone(user_tz).strftime(fmt)
    except Exception as e:
        return str(dt_input)

# ==============================================================================
# [Font Fix] 字型處理
# ==============================================================================
def resolve_matplotlib_glyphs():
    """確保圖表能正確顯示中文標點與字元。"""
    target_fonts = ['cwTeX Q Hei', 'Noto Sans CJK TC', 'PingFang TC Regular', 'Microsoft JhengHei', 'PingFang HK']
    sys_fonts = [f.name for f in fm.fontManager.ttflist]
    for font in target_fonts:
        if font in sys_fonts:
            plt.rcParams['font.sans-serif'] = [font]
            plt.rcParams['axes.unicode_minus'] = False
            return font
    return None

resolve_matplotlib_glyphs()

# --- 輔助函式 ---
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', str(s))]

def format_score_num(val):
    try:
        f_val = float(val)
        if f_val.is_integer(): return str(int(f_val))
        return f"{f_val:.1f}"
    except: return str(val)

def _smart_get_score(row, ai_data=None):
    possible_keys = ["total_score", "Total Score", "final_score", "Final Score", "Score", "score"]
    for k in possible_keys:
        try:
            val = float(row.get(k, 0))
            if val > 0: return val
        except: continue
    if ai_data and isinstance(ai_data, dict):
        for k in possible_keys:
            try:
                val = float(ai_data.get(k, 0))
                if val > 0: return val
            except: continue
    return 0.0

# ==============================================================================
# [Math Fix] LaTeX 標準化工具
# ==============================================================================
_INLINE_MATH_RE = re.compile(r"\\\(\s*(.*?)\s*\\\)", flags=re.DOTALL)
_BLOCK_MATH_RE = re.compile(r"\\\[\s*(.*?)\s*\\\]", flags=re.DOTALL)

def normalize_math_delimiters(text):
    if not text: return ""
    text = str(text)
    def _blk(m): return f"$$\n{m.group(1).strip()}\n$$"
    def _inl(m): return f"${m.group(1).strip()}$"
    text = _BLOCK_MATH_RE.sub(_blk, text)
    text = _INLINE_MATH_RE.sub(_inl, text)
    text = text.replace(r"\_", "_") 
    return text

def _render_safe_markdown(text):
    return normalize_math_delimiters(text)

# ==============================================================================
# [Rubric 工具] 深度解析與 HTML 支援
# ==============================================================================
def _safe_json_load(data):
    if isinstance(data, dict): return data
    if isinstance(data, str) and data.strip():
        try: return json.loads(data)
        except: return {}
    return {}

def _normalize_id(qid):
    s = str(qid).lower()
    return re.sub(r'[^a-z0-9]', '', s)

def _convert_rubric_to_markdown(rubric_data):
    rubric = _safe_json_load(rubric_data)
    if not rubric: return None
    md = []
    title = rubric.get("exam_title", "Grading Rubric")
    total_pts = rubric.get("total_points", "")
    header_str = f" ({total_pts} pts)" if total_pts else ""
    md.append(f"### 📑 {title}{header_str}")
    md.append("---")
    
    questions = rubric.get("questions", [])
    if not questions: return None

    for q in questions:
        q_id = q.get("id", "?")
        score = format_score_num(q.get("points", q.get("score", 0)))
        desc = _render_safe_markdown(q.get("description", q.get("criteria", "")))
        md.append(f"#### 🔹 **Q{q_id}** <span style='color:gray; font-size:0.9em;'>({score} {t('lbl_score_unit')})</span>")
        if desc: md.append(f"> {desc}")
        
        if "sub_questions" in q:
            md.append("")
            for sub in q["sub_questions"]:
                s_id = sub.get("id", "?")
                s_score = format_score_num(sub.get("points", sub.get("score", 0)))
                s_desc = _render_safe_markdown(sub.get("description", sub.get("criteria", "")))
                md.append(f"**({s_id})** `[{s_score} pts]` : {s_desc}")
                
                detailed_criteria = sub.get("rubric", [])
                if isinstance(detailed_criteria, list) and detailed_criteria:
                    for item in detailed_criteria:
                        c_pts = format_score_num(item.get("points", 0))
                        c_text = _render_safe_markdown(item.get("criterion", item.get("description", "")))
                        c_obs = _render_safe_markdown(item.get("observation", ""))
                        obs_str = f"  \n    *<span style='color:#666; font-size:0.85em;'>ℹ️ {c_obs}</span>*" if c_obs else ""
                        md.append(f"  - 🔸 <span style='color:#E67E22; font-weight:bold;'>{c_pts} pts</span>: {c_text}{obs_str}")
                md.append("")
        md.append("---")
    return "\n".join(md)

def _find_question_criteria(rubric_data, q_id):
    rubric = _safe_json_load(rubric_data)
    questions = rubric.get("questions", [])
    target_norm = _normalize_id(q_id)
    no_criteria_msg = t('msg_no_criteria') 
    
    for q in questions:
        q_norm = _normalize_id(q.get("id", ""))
        if q_norm == target_norm: 
            raw = q.get("description", q.get("criteria", no_criteria_msg))
            return _render_safe_markdown(raw)
        
        if "sub_questions" in q:
            for sub in q["sub_questions"]:
                sub_norm = _normalize_id(sub.get("id", ""))
                if sub_norm == target_norm: 
                    details = sub.get("rubric", [])
                    if isinstance(details, list) and details:
                        return "\n".join([f"• [{i.get('points',0)}p] {_render_safe_markdown(i.get('criterion',''))}" for i in details])
                    raw = sub.get("description", sub.get("criteria", no_criteria_msg))
                    return _render_safe_markdown(raw)
                if (q_norm + sub_norm) == target_norm:
                     details = sub.get("rubric", [])
                     if isinstance(details, list) and details:
                        return "\n".join([f"• [{i.get('points',0)}p] {_render_safe_markdown(i.get('criterion',''))}" for i in details])
                     raw = sub.get("description", sub.get("criteria", no_criteria_msg))
                     return _render_safe_markdown(raw)
    return no_criteria_msg

def _get_max_score_from_rubric(rubric_data, q_id):
    rubric = _safe_json_load(rubric_data)
    questions = rubric.get("questions", [])
    target_norm = _normalize_id(q_id)
    for q in questions:
        q_norm = _normalize_id(q.get("id", ""))
        if q_norm == target_norm: return float(q.get("points", q.get("score", 0)))
        if "sub_questions" in q:
            for sub in q["sub_questions"]:
                sub_norm = _normalize_id(sub.get("id", ""))
                def get_val(item): return float(item.get("points", item.get("score", 0)))
                if sub_norm == target_norm: return get_val(sub)
                if (q_norm + sub_norm) == target_norm: return get_val(sub)
    return None

# ==============================================================================
# [Token 儀表板]
# ==============================================================================
def _render_usage_dashboard(raw_df):
    stats = {} 
    total_cost_usd = 0.0
    total_flash_cost = 0.0
    total_pro_cost = 0.0
    has_breakdown_data = False
    
    for _, row in raw_df.iterrows():
        ai_data = {}
        try:
            raw_json = row.get("ai_output_json")
            if raw_json: ai_data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
        except: continue
            
        model_name = ai_data.get("model", ai_data.get("model_name", "Unknown"))
        usage = ai_data.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)))
        output_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)))
        if input_tokens == 0 and output_tokens == 0 and "total_tokens" in usage:
             input_tokens = int(usage.get("total_tokens", 0))

        row_cost = 0.0
        if row.get("cost") is not None and pd.notna(row.get("cost")): row_cost = float(row.get("cost", 0.0))
        if row_cost == 0.0: row_cost = float(ai_data.get("cost_usd", 0.0))
        if row_cost == 0.0: row_cost = float(ai_data.get("Total Cost", 0.0))

        breakdown = ai_data.get("cost_breakdown", {})
        if breakdown:
            has_breakdown_data = True
            total_flash_cost += float(breakdown.get("flash_ocr", 0.0))
            total_pro_cost += float(breakdown.get("pro_grading", 0.0))

        if model_name not in stats: stats[model_name] = {'input': 0, 'output': 0, 'count': 0, 'cost': 0.0}
        stats[model_name]['input'] += input_tokens
        stats[model_name]['output'] += output_tokens
        stats[model_name]['count'] += 1
        stats[model_name]['cost'] += row_cost
        total_cost_usd += row_cost

    if not stats: return

    st.markdown(f"#### 💰 {t('header_cost_analysis')}")
    cols = st.columns(4)
    total_twd = total_cost_usd * current_exchange_rate
    total_tokens = sum(s['input'] + s['output'] for s in stats.values())
    
    cols[0].metric(f"{t('lbl_total_cost')} (USD)", f"${total_cost_usd:.4f}")
    cols[1].metric(f"{t('lbl_est_twd')} (TWD)", f"NT$ {total_twd:.1f}")
    cols[2].metric(t('lbl_total_tokens'), f"{total_tokens:,}")
    cols[3].metric(t('lbl_sheet_count'), f"{len(raw_df)}")

    if has_breakdown_data:
        c1, c2, c3 = st.columns(3)
        c1.metric("⚡ Flash (OCR)", f"${total_flash_cost:.4f}")
        c2.metric("🧠 Pro (Grading)", f"${total_pro_cost:.4f}")
        c3.caption(f"Breakdown: {total_cost_usd > 0 and (total_flash_cost+total_pro_cost)/total_cost_usd*100:.0f}%")

    table_data = []
    for model, data in stats.items():
        t_tokens = data['input'] + data['output']
        table_data.append({
            t('lbl_model'): model, t('lbl_count'): data['count'],
            "Input": f"{data['input']:,}", "Output": f"{data['output']:,}", "Total": f"{t_tokens:,}",
            "USD": f"${data['cost']:.5f}", "TWD": f"NT$ {data['cost'] * current_exchange_rate:.1f}"
        })
    st.dataframe(pd.DataFrame(table_data),  width='stretch', hide_index=True)
    st.divider()

def _render_question_chart(df_display):
    q_cols = [c for c in df_display.columns if str(c).endswith(" Score") and c not in ["Final Score", "Total Score"]]
    if not q_cols: return
    try: q_cols.sort(key=natural_sort_key)
    except: pass
    if df_display[q_cols].isnull().all().all(): return

    avg_scores = df_display[q_cols].mean()
    labels = [c.replace(" Score", "") for c in q_cols]
    values = avg_scores.values

    font_path = None
    possible_fonts = ["fonts/cwTeXHei-Bold.ttf", "/app/fonts/cwTeXHei-Bold.ttf"]
    for p in possible_fonts:
        if os.path.exists(p): font_path = p; break
    prop = fm.FontProperties(fname=font_path) if font_path else None
    
    if not prop:
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial']
        plt.rcParams['axes.unicode_minus'] = False

    fig, ax = plt.subplots(figsize=(10, 4))
    x = np.arange(len(labels))
    ax.bar(x, values, color='#4B7BEC', alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45 if len(labels) > 10 else 0)
    title = t("chart_avg_score_by_q")
    ax.set_title(title, fontproperties=prop) if prop else ax.set_title(title)

    for i, v in enumerate(values): ax.text(i, v + 0.1, f"{v:.1f}", ha='center', va='bottom', fontsize=9)
    st.pyplot(fig)
    plt.close(fig)

# ==============================================================================
# UI Component: 編輯面板
# ==============================================================================
@st.dialog("📝 Detail View & Edit", width="large")
def show_detail_dialog(student_entry, batch_id, rubric_data=None):
    st_name = student_entry.get(t("real_name"), "Unknown")
    st_id = student_entry.get(t("lbl_id"), "Unknown")
    
    if "editing_scores" not in st.session_state: st.session_state.editing_scores = {}

    col_pdf, col_panel = st.columns([1.6, 1], gap="medium")
    
    with col_pdf:
        st.subheader(f"📄 {st_name}")
        fpath = student_entry.get("file_path")
        if fpath and os.path.exists(fpath):
            try:
                from utils.helpers import display_pdf
                with open(fpath, "rb") as f: display_pdf(f.read(), height=800) 
            except ImportError: st.error("Missing utils.helpers.display_pdf")
            except Exception as e: st.error(f"Error reading PDF: {e}")
        else: st.warning(f"File not found: {fpath}")

    with col_panel:
        ai_data = student_entry.get("ai_data", {})
        questions = ai_data.get("questions", [])
        
        current_total = 0.0
        validation_errors = []
        global_has_changes = False
        temp_total_calc = 0.0
        
        if questions:
            for q in questions:
                qid = q.get("id", "Q")
                edit_key = f"score_{batch_id}_{st_id}_{qid}"
                if edit_key in st.session_state: temp_total_calc += float(st.session_state[edit_key])
                else: temp_total_calc += float(q.get("score", 0))
        else: temp_total_calc = float(student_entry.get("Final Score", 0))
        
        current_total = temp_total_calc
        original_final = float(student_entry.get("Final Score", 0))

        with st.container(border=True):
            c1, c2 = st.columns([1, 1])
            with c1:
                st.metric(t("lbl_total_score"), f"{format_score_num(current_total)}", delta=f"{current_total - original_final:.1f}" if current_total != original_final else None)
            with c2:
                st.caption(t("lbl_id")); st.markdown(f"**{st_id}**")
            thinking = student_entry.get("thinking_process", "")
            if thinking:
                with st.expander(f"💭 {t('lbl_ai_thinking')}", expanded=False): st.write(_render_safe_markdown(thinking))

        st.divider()
        st.markdown(f"### {t('lbl_questions_breakdown')}") 
        
        rubric_md_content = _convert_rubric_to_markdown(rubric_data)
        if rubric_md_content:
            with st.expander(f"📜 {t('btn_view_rubric')} (Full Rubric)", expanded=False): 
                st.markdown(rubric_md_content, unsafe_allow_html=True)
        else: st.caption(f"ℹ️ {t('msg_no_rubric_data')}")
        st.write("")
        
        if questions:
            questions.sort(key=lambda x: natural_sort_key(str(x.get("id", "0"))))
            for q in questions:
                qid = q.get("id", "Q")
                original_score = float(q.get("score", 0)) 
                
                max_score = None
                detected_max = q.get("max_score")
                if detected_max is not None: max_score = float(detected_max)
                if max_score is None:
                     detected_points = q.get("points")
                     if detected_points is not None: max_score = float(detected_points)
                if max_score is None and rubric_data: max_score = _get_max_score_from_rubric(rubric_data, qid)
                if max_score is None: max_score = max(original_score, 10.0)

                original_reason = q.get("manual_adjustment_reason", "")
                icon = "✅"
                if original_score == 0: icon = "❌"
                elif original_score < max_score: icon = "⚠️"
                
                label = f"{icon} **{qid}** ｜ {t('lbl_score')}: {format_score_num(original_score)} / {format_score_num(max_score)}"
                
                with st.expander(label, expanded=False):
                    col_q_info, col_q_edit = st.columns([3, 1])
                    
                    with col_q_info:
                        st.caption(f"**🤖 {t('lbl_ai_analysis')}:**")
                        
                        breakdown = q.get("breakdown", [])
                        breakdown_html = ""
                        score_parts = []
                        calc_sum = 0.0
                        
                        if breakdown and isinstance(breakdown, list) and len(breakdown) > 0:
                            st.markdown("###### 🧩 Scoring Breakdown")
                            for item in breakdown:
                                b_rule = item.get("rule", "Rule")
                                try: b_score = float(item.get("score", 0))
                                except: b_score = 0.0
                                b_comment = item.get("comment", "")
                                
                                calc_sum += b_score
                                score_parts.append(format_score_num(b_score))
                                
                                safe_comment = _render_safe_markdown(b_comment)
                                breakdown_html += f"- **{b_rule}**: <span style='color:#E67E22; font-weight:bold;'>{format_score_num(b_score)}</span> pts  \n  <span style='color:gray; font-size:0.9em; margin-left:1em;'>↳ {safe_comment}</span>\n"
                            
                            st.markdown(breakdown_html, unsafe_allow_html=True)
                            st.divider()

                        st.markdown(f"**📝 Summary:**")
                        reason_text = _render_safe_markdown(q.get("reasoning", t("msg_no_comment")))
                        st.info(reason_text)

                        if score_parts:
                            formula_str = " + ".join(score_parts)
                            is_mismatch = abs(calc_sum - original_score) > 0.1
                            
                            bg_color = "#f0f2f6"
                            text_color = "#2c3e50"
                            mismatch_html = ""
                            
                            if is_mismatch:
                                bg_color = "#fff5f5"
                                text_color = "#c0392b"
                                mismatch_html = f"<div style='color:red; font-size:0.8em; margin-top:5px;'>⚠️ <b>Mismatch Warning:</b> Breakdown sum ({format_score_num(calc_sum)}) != AI Total ({format_score_num(original_score)}). <br>System detected a calculation error in AI response.</div>"

                            html_block = f"""
                            <div style="text-align: right; background-color: {bg_color}; padding: 10px; border-radius: 8px; margin-top: 15px; border: 1px solid #e0e0e0;">
                                <div style="color: {text_color}; font-size: 0.9em;">得分結構 (Calculated):</div>
                                <div style="font-weight: bold; font-size: 1.1em; color: {text_color};">
                                    {formula_str} = {format_score_num(calc_sum)}
                                </div>
                                {mismatch_html}
                            </div>
                            """
                            st.markdown(html_block, unsafe_allow_html=True)
                            
                        elif not breakdown:
                            st.caption("(⚠️ No breakdown data available in DB. Re-grade to generate formula.)")

                        if rubric_data:
                            st.write("") 
                            criteria_text = _find_question_criteria(rubric_data, qid)
                            st.caption(f"**📏 {t('lbl_grading_criteria')}:**")
                            st.markdown(f"{criteria_text}")
                            
                    with col_q_edit:
                        score_key = f"score_{batch_id}_{st_id}_{qid}"
                        safe_max = max(float(max_score), float(original_score))
                        new_val = st.number_input(f"{t('lbl_score')}", min_value=0.0, max_value=safe_max, value=original_score, step=0.5, key=score_key)
                        
                        reason_key = f"reason_{batch_id}_{st_id}_{qid}"
                        is_modified = (new_val != original_score)
                        
                        reason_label = "📝 Reason (Req.)" if is_modified else "📝 Note"
                        user_reason = st.text_area(reason_label, value=original_reason, placeholder="Reason...", key=reason_key, height=100)

                        if is_modified:
                            global_has_changes = True
                            st.caption(f"🔄 {format_score_num(original_score)}→{format_score_num(new_val)}")
                            if not user_reason.strip():
                                st.error("⚠️ Reason Required"); validation_errors.append(qid)
                            else:
                                q['temp_score'] = new_val; q['temp_reason'] = user_reason
                        elif user_reason != original_reason:
                             global_has_changes = True; q['temp_reason'] = user_reason

            if global_has_changes:
                st.divider()
                if validation_errors:
                    st.error(f"❌ Cannot save. Missing reasons for: {', '.join(validation_errors)}")
                    st.button(f"💾 {t('btn_save_changes')}", disabled=True, key="save_disabled")
                else:
                    if st.button(f"💾 {t('btn_save_changes')}", type="primary", width='stretch'):
                        for q in questions:
                            if 'temp_score' in q: q['score'] = q.pop('temp_score')
                            if 'temp_reason' in q: q['manual_adjustment_reason'] = q.pop('temp_reason')
                            elif 'manual_adjustment_reason' not in q: q['manual_adjustment_reason'] = ""
                        if update_student_score:
                            ai_data['total_score'] = current_total
                            success = update_student_score(batch_id, st_id, json.dumps(ai_data, ensure_ascii=False))
                            if success: st.success(t("msg_save_success")); st.rerun()
                            else: st.error(t("msg_save_failed"))
                        else: st.warning("⚠️ DB Update function missing.")
        else: st.info(t("msg_no_details"))

# ==============================================================================
# Main View
# ==============================================================================
def render_history(user):
    st.title(f"📜 {t('menu_history')}")
    user_id = getattr(user, "id", user.get("id") if isinstance(user, dict) else None)
    if user_id is None: st.error("❌ 無法讀取使用者 ID。"); return
    try: batches_df = get_user_history_batches(user_id)
    except Exception as e: st.error(f"DB Error: {e}"); return
    if batches_df is None or batches_df.empty: st.info(t("no_data")); return

    for _, batch_row in batches_df.iterrows():
        batch_id = str(batch_row['batch_id'])
        
        # [Timezone Fix] 取得 UTC 時間並轉為 User 本地時間
        raw_time = batch_row.get('created_at', '')
        created_at = format_utc_to_local(raw_time, user)
        
        rubric_json = batch_row.get('rubric', None) 
        label = f"{t('batch_id_label')}: {batch_id} ({created_at})"
        
        with st.expander(label, expanded=False):
            c1, c2, _ = st.columns([1, 1, 3])
            zip_path = os.path.join(config.SPLITS_DIR, batch_id, "graded_papers.zip")
            if not os.path.exists(zip_path) and hasattr(config, 'DATA_DIR'):
                zip_path = os.path.join(config.DATA_DIR, "history_data", batch_id, "graded_papers.zip")
            with c1:
                if os.path.exists(zip_path):
                    with open(zip_path, "rb") as fp: st.download_button(f"📥 {t('download_zip_btn')}", fp, f"{batch_id}.zip", "application/zip", key=f"dl_{batch_id}")
            with c2:
                if st.button(f"🗑️ {t('delete_batch')}", key=f"del_{batch_id}"): st.session_state[f"confirm_del_{batch_id}"] = True
            if st.session_state.get(f"confirm_del_{batch_id}"):
                st.warning(t("warn_delete_batch"))
                if st.button("✅ Yes", key=f"yes_{batch_id}"):
                    delete_user_batch(batch_id, user_id); st.success("Deleted"); del st.session_state[f"confirm_del_{batch_id}"]; st.rerun()
            st.divider()

            if rubric_json:
                with st.expander(f"📖 {t('btn_view_rubric')}", expanded=False): 
                    st.markdown(_convert_rubric_to_markdown(rubric_json), unsafe_allow_html=True)
                st.divider()

            raw_df = get_batch_details(batch_id)
            if raw_df.empty: st.warning(t("no_data")); continue
            _render_usage_dashboard(raw_df)

            processed_data = []
            all_q_ids = set()
            student_map = {}
            for _, row in raw_df.iterrows():
                ai_data = {}
                try: 
                    raw_json = row.get("ai_output_json")
                    if raw_json: ai_data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
                except: pass
                db_path = row.get("file_path", "")
                real_path = db_path
                if db_path and not os.path.exists(db_path):
                    fname = os.path.basename(db_path)
                    alt_path = os.path.join(config.SPLITS_DIR, batch_id, fname)
                    if os.path.exists(alt_path): real_path = alt_path
                final_score = _smart_get_score(row, ai_data)
                s_id = row.get("student_id")
                entry = {
                    t("lbl_id"): s_id, t("real_name"): row.get("student_name"), "Final Score": final_score,
                    "Status": t("status_failed") if final_score < 60 else t("status_graded"), "file_path": real_path,
                    "thinking_process": ai_data.get("thinking_process", ""), "ai_data": ai_data
                }
                qs = ai_data.get("questions", [])
                for q in qs:
                    qid = q.get("id", "Q").strip()
                    all_q_ids.add(qid)
                    entry[f"{qid} Score"] = q.get("score", 0)
                    entry[f"{qid} Comment"] = q.get("reasoning", "")
                processed_data.append(entry); student_map[s_id] = entry

            df_display = pd.DataFrame(processed_data)
            if not df_display.empty:
                st.markdown(f"### 📊 {t('header_class_stats')}")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(t("lbl_student_count"), f"{len(df_display)}")
                m2.metric(t("lbl_avg_score"), f"{df_display['Final Score'].mean():.1f}")
                pass_rate = (len(df_display[df_display["Final Score"] >= 60]) / len(df_display)) * 100
                m3.metric(t("lbl_pass_rate"), f"{pass_rate:.0f}%")
                m4.metric(t("lbl_max_score"), f"{df_display['Final Score'].max()}")
                with st.expander(f"📈 {t('btn_view_charts')}", expanded=False): _render_question_chart(df_display)

            st.markdown("---"); st.markdown(f"### 📋 {t('header_student_list')}")
            col_search, col_sort, col_toggle = st.columns([2, 2, 1.5], gap="small")
            with col_search: search_query = st.text_input(f"🔍 {t('lbl_search')}", placeholder="ID/Name...", key=f"search_{batch_id}")
            with col_sort:
                sort_opts = [t("sort_id_asc"), t("sort_id_desc"), t("sort_score_desc"), t("sort_score_asc")]
                sort_mode = st.selectbox(f"⇅ {t('lbl_sort')}", sort_opts, key=f"sort_{batch_id}")
            with col_toggle: st.write(""); st.write(""); show_details = st.toggle(t("btn_show_subquestions"), False, key=f"toggle_{batch_id}")

            if search_query:
                mask = (df_display[t("lbl_id")].astype(str).str.contains(search_query, case=False, na=False) | df_display[t("real_name")].astype(str).str.contains(search_query, case=False, na=False))
                df_display = df_display[mask]
            if sort_mode == t("sort_id_asc"): df_display = df_display.sort_values(by=t("lbl_id"), ascending=True)
            elif sort_mode == t("sort_id_desc"): df_display = df_display.sort_values(by=t("lbl_id"), ascending=False)
            elif sort_mode == t("sort_score_desc"): df_display = df_display.sort_values(by="Final Score", ascending=False)
            elif sort_mode == t("sort_score_asc"): df_display = df_display.sort_values(by="Final Score", ascending=True)

            base_cols = [t("lbl_id"), t("real_name"), "Final Score", "Status"]
            if show_details:
                sorted_q_ids = sorted(list(all_q_ids), key=natural_sort_key)
                detail_cols = []
                for qid in sorted_q_ids: detail_cols.extend([f"{qid} Score", f"{qid} Comment"])
                cols_to_show = base_cols + detail_cols
            else: cols_to_show = base_cols
            cols_to_show = [c for c in cols_to_show if c in df_display.columns]
            
            event = st.dataframe(df_display[cols_to_show], width='stretch', column_config={"Final Score": st.column_config.ProgressColumn("Score", format="%.1f", min_value=0, max_value=100)}, hide_index=True, height=500, on_select="rerun", selection_mode="single-row", key=f"table_{batch_id}_filtered")

            if len(event.selection.rows) > 0:
                display_index = event.selection.rows[0]; row_data = df_display.iloc[display_index]
                if row_data[t("lbl_id")] in student_map: show_detail_dialog(student_map[row_data[t("lbl_id")]], batch_id, rubric_data=rubric_json)
                else: st.error("Mapping error")
