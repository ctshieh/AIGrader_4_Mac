# services/pdf_report_worker.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.13-Report-Link-Fix

import matplotlib
matplotlib.use('Agg')

import os
import subprocess
import tempfile
import logging
import re
import shutil
import matplotlib.pyplot as plt
import pandas as pd
import qrcode 

from utils.localization import t

# [Fix] 確保正確引用 report_service
from services.report_service import (
    generate_score_distribution_chart, 
    generate_question_analysis_chart
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PdfReportWorker:
    
    @staticmethod
    def _prepare_logo(target_dir, user=None):
        """準備 Logo"""
        target_path = os.path.join(target_dir, "logo.png")
        user_logo = getattr(user, 'branding_logo_path', None)
        # 使用 os.getcwd() 確保在不同執行環境下能找到預設資源
        default_logo = os.path.join(os.getcwd(), "assets", "logo.png")
        
        if user_logo and os.path.exists(user_logo):
            try: shutil.copy(user_logo, target_path); return True
            except: pass
        if os.path.exists(default_logo):
            try: shutil.copy(default_logo, target_path); return True
            except: pass
        return False

    @staticmethod
    def _prepare_qr_code(target_dir, user=None):
        """根據用戶設定的 URL 生成 QR Code"""
        url = getattr(user, 'custom_advertising_url', None)
        if not url or not str(url).strip():
            return False
            
        target_path = os.path.join(target_dir, "qr.png")
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            img.save(target_path)
            return True
        except Exception as e:
            logger.error(f"Failed to generate QR code: {e}")
            return False

    @staticmethod
    def escape_latex_text(text):
        if not text: return ""
        text = str(text)
        chars = {
            '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_', 
            '{': r'\{', '}': r'\}', '^': r'\textasciicircum{}', 
            '~': r'\textasciitilde{}', '\\': r'\textbackslash{}'
        }
        return "".join(chars.get(c, c) for c in text)

    @staticmethod
    def parse_markdown_to_latex(text):
        if not text: return ""
        text = text.replace('`', ' ')
        math_map = {}
        def replace_with_placeholder(match_text):
            placeholder = f"MATHBLOCK{len(math_map)}END" 
            math_map[placeholder] = match_text
            return placeholder

        pattern_math = re.compile(r'(?s)(\$\$|\\\[).*?(\$\$|\\\])|(\$|\\\().*?(\$|\\\))')
        text = pattern_math.sub(lambda m: replace_with_placeholder(m.group(0)), text)

        lines = text.split('\n')
        latex_lines = []
        in_list = False
        
        for line in lines:
            line = line.strip()
            if not line: continue
            if line.startswith('* ') or line.startswith('- ') or line.startswith('• '):
                if not in_list:
                    latex_lines.append(r'\begin{itemize}')
                    in_list = True
                content = line[1:].strip() if line.startswith('•') else line[2:].strip()
                latex_lines.append(rf'    \item {PdfReportWorker.escape_latex_text(content)}')
            else:
                if in_list:
                    latex_lines.append(r'\end{itemize}')
                    in_list = False
                
                if line.startswith('### '):
                    latex_lines.append(rf'\subsection*{{{PdfReportWorker.escape_latex_text(line[4:])}}}')
                elif line.startswith('## '):
                    latex_lines.append(rf'\section*{{{PdfReportWorker.escape_latex_text(line[3:])}}}')
                elif line.startswith('# '):
                    latex_lines.append(rf'\section*{{{PdfReportWorker.escape_latex_text(line[2:])}}}')
                else:
                    latex_lines.append(rf'{PdfReportWorker.escape_latex_text(line)} \par')
        
        if in_list: latex_lines.append(r'\end{itemize}')
        processed_text = '\n'.join(latex_lines)

        for placeholder, math_code in math_map.items():
            processed_text = processed_text.replace(placeholder, math_code)
        return processed_text

    @staticmethod
    def generate_professional_pdf(batch_id, df, analysis_text, user=None, q_stats_df=None):
        if not isinstance(df, pd.DataFrame): df = pd.DataFrame()
        df = df.copy()
        
        if 'total_score' not in df.columns:
            df['total_score'] = df['Final Score'] if 'Final Score' in df.columns else 0.0
        df['total_score'] = pd.to_numeric(df['total_score'], errors='coerce').fillna(0)
        
        if not isinstance(q_stats_df, pd.DataFrame): q_stats_df = pd.DataFrame()

        # [Config] 字型設定 (可根據環境變更)
        main_font = "cwTeX Q Ming Medium"

        with tempfile.TemporaryDirectory() as tmpdir:
            PdfReportWorker._prepare_logo(tmpdir, user=user)
            PdfReportWorker._prepare_qr_code(tmpdir, user=user)

            img_dist_path = os.path.join(tmpdir, "distchart.png") 
            fig_dist = generate_score_distribution_chart(df)
            if fig_dist:
                fig_dist.savefig(img_dist_path, dpi=300, bbox_inches='tight')
                plt.close(fig_dist)

            img_quest_path = os.path.join(tmpdir, "questchart.png")
            if not q_stats_df.empty:
                fig_q = generate_question_analysis_chart(q_stats_df)
                if fig_q:
                    fig_q.savefig(img_quest_path, dpi=300, bbox_inches='tight')
                    plt.close(fig_q)

            avg_score = df['total_score'].mean() if not df.empty else 0
            pass_rate = (len(df[df['total_score']>=60])/len(df)*100) if len(df)>0 else 0
            body_tex = PdfReportWorker.parse_markdown_to_latex(analysis_text)
            
            latex_code = rf"""
\documentclass[12pt, a4paper]{{article}}
\usepackage{{xeCJK, graphicx, float, geometry, titlesec, xcolor, lastpage, fancyhdr}}
\geometry{{top=2.5cm, bottom=2.5cm, left=2.5cm, right=2.5cm}}

\setCJKmainfont[AutoFakeBold=2.5]{{{main_font}}} 

\linespread{{1.2}}\selectfont 
\XeTeXlinebreaklocale "zh"
\XeTeXlinebreakskip = 0pt plus 1pt

\titleformat{{\section}}{{\large\bfseries}}{{\thesection}}{{1em}}{{}}[\titlerule]

\pagestyle{{fancy}}
\fancyhf{{}}
\rfoot{{ {PdfReportWorker.escape_latex_text(t('page_label'))} \thepage \ / \pageref{{LastPage}} }}

\begin{{document}}

% --- 封面 ---
\begin{{titlepage}}
    \centering
    \vspace*{{1cm}}
    
    \IfFileExists{{logo.png}}{{
        \includegraphics[width=0.8\textwidth, height=4cm, keepaspectratio]{{logo.png}}
    }}{{
        \vspace*{{1cm}}
        \Huge \textbf{{AI GRADING SYSTEM}}
    }}
    
    \vspace{{1.5cm}}
    {{\Huge \textbf{{{PdfReportWorker.escape_latex_text(t('ai_analysis_report'))}}} \par}}
    
    \vspace{{1.5cm}}
    {{\Large \textbf{{{PdfReportWorker.escape_latex_text(t('batch_id_label'))}}}: {PdfReportWorker.escape_latex_text(str(batch_id))} }} \\
    \vspace{{0.5cm}}
    {{\Large \textbf{{{PdfReportWorker.escape_latex_text(t('date_label'))}}}: \today }}
    
    \vfill
    
    \IfFileExists{{qr.png}}{{
        \vspace{{1cm}}
        \includegraphics[width=3.5cm]{{qr.png}} \\
        \vspace{{0.3cm}}
        {{\small \color{{gray}} Scan for more info / 瀏覽官網}}
    }}{{}}
    
    \vspace{{1cm}}
\end{{titlepage}}

% --- 第二頁 ---
\section*{{{PdfReportWorker.escape_latex_text(t('statistics_overview'))}}}
\begin{{itemize}}
    \item \textbf{{{PdfReportWorker.escape_latex_text(t('average_score'))}}}: {avg_score:.2f}
    \item \textbf{{{PdfReportWorker.escape_latex_text(t('pass_rate'))}}}: {pass_rate:.1f}\%
\end{{itemize}}

\IfFileExists{{distchart.png}}{{
    \begin{{figure}}[H] \centering \includegraphics[width=0.85\textwidth]{{distchart.png}} \caption{{Score Distribution}} \end{{figure}}
}}{{}}

\IfFileExists{{questchart.png}}{{
    \begin{{figure}}[H] \centering \includegraphics[width=0.95\textwidth]{{questchart.png}} \caption{{{PdfReportWorker.escape_latex_text(t('question_analysis'))}}} \end{{figure}}
}}{{}}

\newpage
\section*{{{PdfReportWorker.escape_latex_text(t('ai_insights_header'))}}}
{body_tex}

\end{{document}}
"""
            tex_file = os.path.join(tmpdir, "report.tex")
            with open(tex_file, "w", encoding="utf-8") as f: f.write(latex_code)
                
            subprocess.run(["xelatex", "-interaction=nonstopmode", "report.tex"], cwd=tmpdir, capture_output=True)
            subprocess.run(["xelatex", "-interaction=nonstopmode", "report.tex"], cwd=tmpdir, capture_output=True)
            
            pdf_path = os.path.join(tmpdir, "report.pdf")
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f: return f.read()
            return None
