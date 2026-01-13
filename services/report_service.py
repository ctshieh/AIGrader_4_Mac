# services/report_service.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.13-Path-Fix
# Description: 
# 1. [Fix] Font Path: Uses dynamic path relative to project root to find fonts.
# 2. [Safety] Matplotlib Agg backend forced.

# [CRITICAL] 強制設定 Matplotlib 後端為非互動模式 (Agg)
import matplotlib
matplotlib.use('Agg') 

import pandas as pd
import io
import zipfile
import logging
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import os

logger = logging.getLogger(__name__)

# ==============================================================================
#  1. Data Processing
# ==============================================================================

def merge_and_calculate_data(grading_results):
    """
    將 Grading Results 轉換為 Pandas DataFrame，並統一欄位名稱。
    修正：移除重複的 'Total Score'，統一使用 'Final Score'。
    """
    data = []
    total_cost = 0
    
    for r in grading_results:
        bd = r.get("cost_breakdown", {})
        
        # 嘗試取得分數，優先順序：total_score (API) > Final Score (History) > Total Score
        raw_score = r.get("total_score")
        if raw_score is None:
            raw_score = r.get("Final Score")
        if raw_score is None:
            raw_score = r.get("Total Score")
        if raw_score is None:
            raw_score = 0

        # 建構單一學生的資料列 (Dict)
        row = {
            "Student ID": r.get("Student ID", ""),
            "Name": r.get("Name", ""),
            "Seat Number": r.get("Seat Number", ""),
            "Final Score": raw_score,  # <--- 統一使用 Final Score
            # 移除 "Total Score" 以避免 Excel 出現重複欄位
            "General Comment": r.get("general_comment", ""),
            "Cost (Flash)": bd.get("flash_ocr", 0),
            "Cost (Pro)": bd.get("pro_grading", 0),
            "Total Cost": r.get("cost_usd", 0)
        }
        
        # 動態加入各題得分
        for q in r.get("questions", []):
            qid = q.get("id", "Q?")
            row[f"{qid} Score"] = q.get("score", 0)
            row[f"{qid} Comment"] = q.get("reasoning", "")
            
        data.append(row)
        total_cost += r.get("cost_usd", 0)
    
    df = pd.DataFrame(data)
    
    # 強制轉換分數為數值格式 (避免 Excel 排序錯誤)
    if "Final Score" in df.columns:
        df["Final Score"] = pd.to_numeric(df["Final Score"], errors='coerce').fillna(0)
        
    score_cols = [c for c in df.columns if c.endswith(" Score")]
    for col in score_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 依照學號排序
    if "Student ID" in df.columns:
        df = df.sort_values("Student ID")
        
    return df, total_cost

# ==============================================================================
#  2. Analysis Logic
# ==============================================================================

def analyze_questions_performance(grading_results, rubric_json):
    if not grading_results:
        return pd.DataFrame()

    stats = {}
    # 從 Rubric 初始化題目與滿分
    if rubric_json and "questions" in rubric_json:
        for q in rubric_json["questions"]:
            max_pt = float(q.get("total_points", q.get("points", 10)))
            stats[q["id"]] = {"scores": [], "max": max_pt}
            if "sub_questions" in q:
                for sq in q["sub_questions"]:
                    sub_max = float(sq.get("points", 5))
                    stats[sq["id"]] = {"scores": [], "max": sub_max}

    # 填入學生成績
    for res in grading_results:
        for q in res.get("questions", []):
            qid = q.get("id")
            try:
                score = float(q.get("score", 0))
                if qid not in stats:
                    stats[qid] = {"scores": [], "max": 0} 
                stats[qid]["scores"].append(score)
            except: pass

    # 計算統計數據
    rows = []
    for qid, data in stats.items():
        scores = data["scores"]
        if not scores: continue
        
        avg = sum(scores) / len(scores)
        max_possible = data["max"]
        # 防呆：如果 Rubric 沒抓到滿分，就用該題出現過的最高分當作滿分
        if max_possible == 0 and scores:
            max_possible = max(scores)

        rows.append({
            "Question": str(qid), 
            "Avg Score": round(avg, 2),
            "Max Possible": max_possible
        })
    
    res_df = pd.DataFrame(rows).sort_values("Question")
    return res_df

# ==============================================================================
#  3. Chart Generation
# ==============================================================================

def _get_font_prop():
    """ 
    [Fix] 動態尋找系統中的中文字型，避免亂碼。
    優先使用專案目錄下的 fonts 資料夾。
    """
    # 取得當前檔案 (report_service.py) 的父目錄 (services) 的父目錄 (Project Root)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    possible_fonts = [
        os.path.join(base_dir, "fonts", "cwTeXQHei-Bold.ttf"), # 優先：專案內字型
        "fonts/cwTeXQHei-Bold.ttf", 
        "/app/fonts/cwTeXQHei-Bold.ttf", 
        "/usr/share/fonts/truetype/custom/cwTeXQHei-Bold.ttf",
        "C:/Windows/Fonts/msjh.ttc",
        "/System/Library/Fonts/PingFang.ttc"
    ]
    
    font_path = None
    for p in possible_fonts:
        if os.path.exists(p): 
            font_path = p
            break
            
    if font_path:
        return fm.FontProperties(fname=font_path)
    return None

def generate_score_distribution_chart(df):
    """ 生成成績分佈直方圖 """
    if df.empty or "Final Score" not in df.columns:
        return None
    
    try:
        scores = df["Final Score"]
        
        bins = list(range(0, 101, 10)); bins[-1] = 101
        labels = ["0-9", "10-19", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80-89", "90-100"]
        
        score_cats = pd.cut(scores, bins=bins, labels=labels, right=False, include_lowest=True)
        counts = score_cats.value_counts().sort_index()
        
        fig = plt.figure(figsize=(10, 6))
        prop = _get_font_prop()
        
        x = counts.index.astype(str)
        y = counts.values
        
        bars = plt.bar(x, y, color='#4B7BEC', edgecolor='white', alpha=0.9, width=0.6)
        
        if prop:
            plt.title('成績分佈統計 (Score Distribution)', fontproperties=prop, fontsize=14)
            plt.xlabel('分數區間 (Score Range)', fontproperties=prop)
            plt.ylabel('人數 (Number of Students)', fontproperties=prop)
        else:
            plt.title('Score Distribution')
            plt.xlabel('Score Range')
            plt.ylabel('Count')
            
        plt.grid(axis='y', alpha=0.3)
        
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.1, 
                         str(int(height)), ha='center', va='bottom')

        return fig
    except Exception as e:
        logger.error(f"Chart Error: {e}")
        return None

def generate_question_analysis_chart(q_stats_df):
    """ 生成各題平均得分 vs 滿分圖 """
    if q_stats_df.empty: 
        return None
    
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        prop = _get_font_prop()
        
        labels = q_stats_df["Question"].tolist()
        avg_scores = q_stats_df["Avg Score"].tolist()
        max_scores = q_stats_df["Max Possible"].tolist()
        
        x_pos = np.arange(len(labels))
        
        # 繪製雙層 Bar: 灰色底是滿分，藍色是平均得分
        ax.bar(x_pos, max_scores, color='#E0E0E0', label='Max Possible', width=0.6)
        bars = ax.bar(x_pos, avg_scores, color='#4B7BEC', label='Avg Score', width=0.6)
        
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels)
        ax.set_ylabel('Score')
        
        if prop:
            ax.legend(prop=prop)
            ax.set_title('各題平均得分 vs 配分', fontproperties=prop, fontsize=14)
        else:
            ax.legend()
            ax.set_title('Average Score vs Allocation')
            
        for i, bar in enumerate(bars):
            height = bar.get_height()
            max_val = max_scores[i]
            # 格式化顯示：平均 / 滿分
            text_label = f"{height:.1f}/{int(max_val)}"
            ax.text(bar.get_x() + bar.get_width()/2., height + (max_val * 0.02),
                     text_label, ha='center', va='bottom', fontsize=9, fontweight='bold', color='#333333')
        
        return fig
    except Exception as e:
        logger.error(f"Q-Chart Error: {e}")
        return None

# ==============================================================================
#  4. Report Generation (In-Zip Charts)
# ==============================================================================

def create_advanced_zip_report(batch_id, df, analysis_md, q_stats_df=None, report_mode="simple", pdf_bytes=None):
    """
    建立包含 Excel, Markdown, PDF, 圖表的 ZIP 檔案
    """
    zip_buffer = io.BytesIO()
    
    img_dist_buf = None
    img_q_buf = None
    
    # 1. 生成圖表並轉為 Byte Stream
    fig_dist = generate_score_distribution_chart(df)
    if fig_dist:
        try:
            img_dist_buf = io.BytesIO()
            fig_dist.savefig(img_dist_buf, format='png', dpi=100)
            img_dist_buf.seek(0)
            plt.close(fig_dist)
        except: pass

    if q_stats_df is not None and not q_stats_df.empty:
        fig_q = generate_question_analysis_chart(q_stats_df)
        if fig_q:
            try:
                img_q_buf = io.BytesIO()
                fig_q.savefig(img_q_buf, format='png', dpi=100)
                img_q_buf.seek(0)
                plt.close(fig_q)
            except: pass

    # 2. 寫入 ZIP
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Excel Report
        with io.BytesIO() as excel_buf:
            with pd.ExcelWriter(excel_buf, engine='xlsxwriter') as writer:
                # 這裡寫入的 df 已經由 merge_and_calculate_data 清理過，只含 Final Score
                df.to_excel(writer, sheet_name='Grades', index=False)
                
                # 自動調整欄寬
                worksheet = writer.sheets['Grades']
                for i, col in enumerate(df.columns):
                    # 簡單估算寬度
                    col_len = len(str(col))
                    max_len = 10
                    try:
                        # 取前10筆資料估算長度，避免遍歷太久
                        sample_len = df[col].astype(str).str.len().max()
                        if not pd.isna(sample_len):
                            max_len = max(col_len, min(sample_len, 50))
                    except: pass
                    worksheet.set_column(i, i, max_len + 2)
            
            excel_buf.seek(0)
            zf.writestr(f"Report_{batch_id}.xlsx", excel_buf.getvalue())
            
        # Markdown Analysis
        if analysis_md:
            zf.writestr(f"Class_Analysis_{batch_id}.md", analysis_md)
            
        # PDF Report
        if pdf_bytes:
            zf.writestr(f"Class_Analysis_{batch_id}.pdf", pdf_bytes)
            
        # PNG Charts
        if img_dist_buf:
            zf.writestr("Score_Distribution.png", img_dist_buf.getvalue())
            
        if img_q_buf:
            zf.writestr("Question_Analysis.png", img_q_buf.getvalue())

    zip_buffer.seek(0)
    return zip_buffer
