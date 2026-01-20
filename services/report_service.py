# services/report_service.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.20-Chart-Stats-Enhanced
# Description: 
# 1. [Feature] Score Distribution Chart now displays stats (Count, Avg, Median, Pass Rate).
# 2. [Feature] Full support for Individual Student Reports (Markdown).
# 3. [Safety] Matplotlib aggressive warning suppression.

import matplotlib
# [CRITICAL] 強制設定 Matplotlib 後端為非互動模式 (Agg)
matplotlib.use('Agg') 

import pandas as pd
import io
import zipfile
import logging
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import os
import warnings
import re

logger = logging.getLogger(__name__)

# ==============================================================================
#  [CRITICAL FIX] 暴力靜音區
# ==============================================================================
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
warnings.filterwarnings("ignore", module="streamlit.elements.pyplot")

# ==============================================================================
#  1. Data Processing
# ==============================================================================

def merge_and_calculate_data(grading_results):
    data = []
    total_cost = 0
    for r in grading_results:
        bd = r.get("cost_breakdown", {})
        raw_score = r.get("total_score")
        if raw_score is None: raw_score = r.get("Final Score")
        if raw_score is None: raw_score = r.get("Total Score")
        if raw_score is None: raw_score = 0

        row = {
            "Student ID": r.get("Student ID", ""),
            "Name": r.get("Name", ""),
            "Seat Number": r.get("Seat Number", ""),
            "Final Score": raw_score,
            "General Comment": r.get("general_comment", ""),
            "Cost (Flash)": bd.get("flash_ocr", 0),
            "Cost (Pro)": bd.get("pro_grading", 0),
            "Total Cost": r.get("cost_usd", 0)
        }
        for q in r.get("questions", []):
            qid = q.get("id", "Q?")
            row[f"{qid} Score"] = q.get("score", 0)
            row[f"{qid} Comment"] = q.get("reasoning", "")
        data.append(row)
        total_cost += r.get("cost_usd", 0)
    
    df = pd.DataFrame(data)
    if "Final Score" in df.columns:
        df["Final Score"] = pd.to_numeric(df["Final Score"], errors='coerce').fillna(0)
    score_cols = [c for c in df.columns if c.endswith(" Score")]
    for col in score_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    if "Student ID" in df.columns:
        df = df.sort_values("Student ID")
    return df, total_cost

# ==============================================================================
#  2. Analysis Logic
# ==============================================================================

def analyze_questions_performance(grading_results, rubric_json):
    if not grading_results: return pd.DataFrame()
    stats = {}
    if rubric_json and "questions" in rubric_json:
        for q in rubric_json["questions"]:
            max_pt = float(q.get("total_points", q.get("points", 10)))
            stats[q["id"]] = {"scores": [], "max": max_pt}
            if "sub_questions" in q:
                for sq in q["sub_questions"]:
                    sub_max = float(sq.get("points", 5))
                    stats[sq["id"]] = {"scores": [], "max": sub_max}

    for res in grading_results:
        for q in res.get("questions", []):
            qid = q.get("id")
            try:
                score = float(q.get("score", 0))
                if qid not in stats: stats[qid] = {"scores": [], "max": 0} 
                stats[qid]["scores"].append(score)
            except: pass

    rows = []
    for qid, data in stats.items():
        scores = data["scores"]
        if not scores: continue
        avg = sum(scores) / len(scores)
        max_possible = data["max"]
        if max_possible == 0 and scores: max_possible = max(scores)
        rows.append({"Question": str(qid), "Avg Score": round(avg, 2), "Max Possible": max_possible})
    
    return pd.DataFrame(rows).sort_values("Question")

# ==============================================================================
#  3. Chart Generation
# ==============================================================================

def _configure_global_font():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_font_path = os.path.join(base_dir, "fonts", "NotoSansTC-VariableFont_wght.ttf")
    if os.path.exists(local_font_path):
        try:
            prop = fm.FontProperties(fname=local_font_path)
            plt.rcParams['font.family'] = prop.get_name()
            fm.fontManager.addfont(local_font_path)
            plt.rcParams['axes.unicode_minus'] = False
            return prop
        except Exception as e: logger.warning(f"Font Load Error: {e}")

    system_fonts = fm.findSystemFonts(fontpaths=None, fontext='ttf')
    keywords = ['Noto Sans TC', 'Hei', 'Ming', 'Kai', 'CJK', 'PingFang']
    target_names = ['Noto Sans TC', 'Microsoft JhengHei', 'SimHei', 'Heiti TC']
    
    for f in fm.fontManager.ttflist:
        if any(target in f.name for target in target_names):
            plt.rcParams['font.family'] = f.name
            plt.rcParams['axes.unicode_minus'] = False
            return fm.FontProperties(family=f.name)

    best_font_path = None
    for font_path in system_fonts:
        if any(k in os.path.basename(font_path) for k in keywords):
            best_font_path = font_path; break
            
    if best_font_path:
        prop = fm.FontProperties(fname=best_font_path)
        plt.rcParams['font.family'] = prop.get_name()
        plt.rcParams['axes.unicode_minus'] = False
        fm.fontManager.addfont(best_font_path)
        return prop
    return None

def generate_score_distribution_chart(df):
    """ 生成成績分佈直方圖 (包含詳細統計數據) """
    if df.empty or "Final Score" not in df.columns: return None
    
    try:
        # 清除之前的圖表
        plt.close('all') 
        prop = _configure_global_font()
        
        fig = plt.figure(figsize=(10, 6))
        
        scores = df["Final Score"]
        
        # [NEW] 計算統計數據
        total_n = len(scores)
        avg_val = scores.mean() if total_n > 0 else 0
        med_val = scores.median() if total_n > 0 else 0
        pass_n = len(scores[scores >= 60])
        pass_rate = (pass_n / total_n * 100) if total_n > 0 else 0.0

        # 繪製直方圖
        bins = list(range(0, 101, 10)); bins[-1] = 101
        labels = ["0-9", "10-19", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80-89", "90-100"]
        score_cats = pd.cut(scores, bins=bins, labels=labels, right=False, include_lowest=True)
        counts = score_cats.value_counts().sort_index()
        
        x = counts.index.astype(str)
        y = counts.values
        
        bars = plt.bar(x, y, color='#4B7BEC', edgecolor='white', alpha=0.9, width=0.6)
        
        # 設定標題與軸標籤
        title_font = prop if prop else None
        plt.title('成績分佈統計 (Score Distribution)', fontproperties=title_font, fontsize=14)
        plt.xlabel('分數區間 (Score Range)', fontproperties=title_font)
        plt.ylabel('人數 (Number of Students)', fontproperties=title_font)
        
        # [NEW] 在圖表右上角加入統計資訊框
        stats_text = (
            f"總人數 (Total): {total_n}\n"
            f"平均分 (Avg): {avg_val:.1f}\n"
            f"中位數 (Median): {med_val:.1f}\n"
            f"及格數 (Pass): {pass_n}\n"
            f"及格率 (Rate): {pass_rate:.1f}%"
        )
        
        plt.text(
            0.95, 0.95, stats_text,
            transform=plt.gca().transAxes,
            fontsize=11,
            verticalalignment='top',
            horizontalalignment='right',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='#cccccc', alpha=0.9),
            fontproperties=prop
        )
            
        plt.grid(axis='y', alpha=0.3)
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.1, str(int(height)), ha='center', va='bottom')
        return fig
    except Exception as e:
        logger.error(f"Chart Error: {e}")
        return None

def generate_question_analysis_chart(q_stats_df):
    if q_stats_df.empty: return None
    try:
        plt.close('all'); prop = _configure_global_font()
        fig, ax = plt.subplots(figsize=(10, 6))
        labels = q_stats_df["Question"].tolist()
        x_pos = np.arange(len(labels))
        max_scores = q_stats_df["Max Possible"].tolist()
        
        ax.bar(x_pos, max_scores, color='#E0E0E0', label='Max Possible', width=0.6)
        bars = ax.bar(x_pos, q_stats_df["Avg Score"].tolist(), color='#4B7BEC', label='Avg Score', width=0.6)
        
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels, fontproperties=prop)
        ax.set_ylabel('Score', fontproperties=prop)
        ax.legend(prop=prop)
        ax.set_title('各題平均得分 vs 配分', fontproperties=prop, fontsize=14)
        for i, bar in enumerate(bars):
            height = bar.get_height(); max_val = max_scores[i]
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1, f"{height:.1f}/{int(max_val)}", ha='center', va='bottom', fontsize=9)
        return fig
    except Exception as e: logger.error(f"Q-Chart Error: {e}"); return None

# ==============================================================================
#  4. Report Generation (In-Zip Charts)
# ==============================================================================

def _generate_single_student_report(res):
    """[NEW] 生成單一學生的 Markdown 報告"""
    sid = res.get("Student ID", "Unknown")
    name = res.get("Name", "Unknown")
    score = res.get("total_score", 0)
    
    lines = [
        f"# 📝 閱卷報告 (Grading Report)",
        f"",
        f"- **學號 (Student ID)**: {sid}",
        f"- **姓名 (Name)**: {name}",
        f"- **總分 (Total Score)**: {score}",
        f"---",
        f"## 📋 詳細評分 (Detailed Breakdown)",
    ]
    
    for q in res.get("questions", []):
        qid = q.get("id", "?")
        q_score = q.get("score", 0)
        q_max = q.get("max_score", "")
        max_str = f" / {q_max}" if q_max else ""
        
        lines.append(f"### 🔹 題號 (Question): {qid}")
        lines.append(f"- **得分**: {q_score}{max_str}")
        lines.append(f"- **評語**: {q.get('reasoning', '')}")
        
        if "breakdown" in q and isinstance(q["breakdown"], list):
            lines.append(f"> **細項 (Breakdown):**")
            for bd in q["breakdown"]:
                rule = bd.get("rule", "") or bd.get("criterion", "")
                pts = bd.get("score", bd.get("points", 0))
                comment = bd.get("comment", "")
                
                line_str = f"> * [{pts} pts] {rule}"
                if comment: line_str += f" -> {comment}"
                lines.append(line_str)
        
        lines.append("") # Empty line
        
    return "\n".join(lines)

def create_advanced_zip_report(batch_id, df, analysis_md, q_stats_df=None, report_mode="simple", pdf_bytes=None, grading_results=None):
    zip_buffer = io.BytesIO()
    img_dist_buf = None
    img_q_buf = None
    
    fig_dist = generate_score_distribution_chart(df)
    if fig_dist:
        try:
            img_dist_buf = io.BytesIO(); fig_dist.savefig(img_dist_buf, format='png', dpi=100)
            img_dist_buf.seek(0); plt.close(fig_dist)
        except: pass

    if q_stats_df is not None and not q_stats_df.empty:
        fig_q = generate_question_analysis_chart(q_stats_df)
        if fig_q:
            try:
                img_q_buf = io.BytesIO(); fig_q.savefig(img_q_buf, format='png', dpi=100)
                img_q_buf.seek(0); plt.close(fig_q)
            except: pass

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        with io.BytesIO() as excel_buf:
            with pd.ExcelWriter(excel_buf, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Grades', index=False)
                worksheet = writer.sheets['Grades']
                for i, col in enumerate(df.columns):
                    col_len = len(str(col)); max_len = 10
                    try:
                        sample_len = df[col].astype(str).str.len().max()
                        if not pd.isna(sample_len): max_len = max(col_len, min(sample_len, 50))
                    except: pass
                    worksheet.set_column(i, i, max_len + 2)
            excel_buf.seek(0)
            zf.writestr(f"Report_{batch_id}.xlsx", excel_buf.getvalue())
            
        if analysis_md: zf.writestr(f"Class_Analysis_{batch_id}.md", analysis_md)
        if pdf_bytes: zf.writestr(f"Class_Analysis_{batch_id}.pdf", pdf_bytes)
        if img_dist_buf: zf.writestr("Score_Distribution.png", img_dist_buf.getvalue())
        if img_q_buf: zf.writestr("Question_Analysis.png", img_q_buf.getvalue())

        # [NEW] Generate Individual Student Reports if Full Mode
        if report_mode == "full" and grading_results:
            for res in grading_results:
                sid = str(res.get("Student ID", "Unknown")).strip()
                # Sanitize filename
                safe_sid = "".join([c for c in sid if c.isalnum() or c in ('-','_')])
                if not safe_sid: safe_sid = "student"
                
                md_content = _generate_single_student_report(res)
                zf.writestr(f"Student_Reports/{safe_sid}.md", md_content)

    zip_buffer.seek(0)
    return zip_buffer
