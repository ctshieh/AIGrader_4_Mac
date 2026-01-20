# services/exam_gen_service.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.23-Layout-Spacing-Fix
# Description: 
# 1. [Fix] Compact Header: 增加 subtitle 與 學生資料欄之間的間距 (0.4cm)。
# 2. [Core] 保留完整 LaTeX 生成邏輯與字型偵測。

import os
import sys 
import subprocess
import tempfile
import logging
import re
import uuid
import qrcode
import string
import shutil
import platform
from math import ceil
from utils.localization import t
from database.db_manager import get_sys_conf
from services.plans import get_plan_config

class ExamBuilder:
    def __init__(self):
        self.compiler = "xelatex"
        self.logger = logging.getLogger(__name__)

    def _get_font_config(self):
        """
        [Font Strategy]
        偵測字型路徑，支援 Windows/Mac/Linux 的 Portable 模式與安裝模式。
        """
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.getcwd()
            
        local_fonts_dir = os.path.join(application_path, "fonts")

        cwtex_targets = {
            "main": "cwTeXQMing-Medium.ttf",
            "sans": "cwTeXQHei-Bold.ttf",
            "mono": "cwTeXQYuan-Medium.ttf"
        }

        search_paths = [local_fonts_dir]

        system = platform.system()
        if system == "Darwin":
            search_paths.append(os.path.expanduser("~/Library/Fonts"))
            search_paths.append("/Library/Fonts")
        elif system == "Windows":
            search_paths.append("C:\\Windows\\Fonts")
            search_paths.append(os.path.join(os.getenv("LOCALAPPDATA", ""), "Microsoft\\Windows\\Fonts"))
        else:
            search_paths.append("/usr/share/fonts/truetype/custom")
            search_paths.append(os.path.expanduser("~/.local/share/fonts"))

        # 1. 尋找 cwTeX
        found_cwtex = {}
        for ftype, fname in cwtex_targets.items():
            for path in search_paths:
                full_path = os.path.join(path, fname)
                if os.path.exists(full_path):
                    dir_path = path.replace("\\", "/") 
                    if not dir_path.endswith("/"): dir_path += "/"
                    found_cwtex[ftype] = f"[Path={dir_path}, AutoFakeBold=3, AutoFakeSlant=.2]{{{fname}}}"
                    break
        
        if "main" in found_cwtex:
            main = found_cwtex["main"]
            sans = found_cwtex.get("sans", main)
            mono = found_cwtex.get("mono", main)
            return main, sans, mono

        # 2. 尋找 Noto (Fallback)
        noto_serif = "NotoSerifTC-VariableFont_wght.ttf"
        noto_sans = "NotoSansTC-VariableFont_wght.ttf"
        
        has_serif = os.path.exists(os.path.join(local_fonts_dir, noto_serif))
        has_sans = os.path.exists(os.path.join(local_fonts_dir, noto_sans))
        
        dir_path_safe = local_fonts_dir.replace("\\", "/")
        if not dir_path_safe.endswith("/"): dir_path_safe += "/"

        def make_cmd(fname): return f"[Path={dir_path_safe}, AutoFakeBold=3, AutoFakeSlant=.2]{{{fname}}}"

        if has_serif and has_sans:
            return make_cmd(noto_serif), make_cmd(noto_sans), make_cmd(noto_sans)
        elif has_sans:
            return make_cmd(noto_sans), make_cmd(noto_sans), make_cmd(noto_sans)

        return "{cwTeX Q Ming}", "{cwTeX Q Hei}", "{cwTeX Q Yuan}"

    def _generate_qr_file(self, content: str, save_path: str):
        try:
            qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
            qr.add_data(content); qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(save_path)
        except Exception as e: self.logger.error(f"QR Gen Failed: {e}")

    def clean_latex_content(self, text):
        if not text: return ""
        text = str(text).replace('\u00A0', ' ')
        text = re.sub(r'[\u200b-\u200f\u202a-\u202e\ufeff]', '', text)
        chars_to_escape = {'&': r'\&', '%': r'\%', '#': r'\#'}
        for char, escaped in chars_to_escape.items(): text = text.replace(char, escaped)
        return text

    def calc_total_score(self, questions) -> str:
        total = 0.0
        for q in questions or []:
            sub_qs = q.get('sub_questions', []) or []
            if sub_qs:
                for sq in sub_qs:
                    try: total += float(sq.get('score', 0) or 0)
                    except: pass
            else:
                try: total += float(q.get('score', 0) or 0)
                except: pass
        return str(int(round(total))) if abs(total - round(total)) < 1e-9 else str(total)

    def generate_tex_source(self, header_info, questions, exam_uuid="UNK", has_logo=False, has_marketing_qr=False):
        tex = []
        total_score_str = self.calc_total_score(questions)
        
        is_compact = header_info.get('is_compact', False)
        layout_mode = header_info.get('layout_mode', 'combined')

        lbl_score_unit = t('lbl_score_unit')
        lbl_subject = t('gen_subject')
        lbl_total = t('lbl_total_score')
        lbl_dept = t('gen_dept')
        lbl_note = t('gen_exam_note')
        lbl_time = t('lbl_time')
        lbl_name = t('lbl_name')
        lbl_id = t('lbl_id')
        lbl_seat = t('lbl_seat')
        lbl_grader = t('lbl_grader')
        lbl_score_box = t('lbl_score_box')

        txt_q_suffix = t('suffix_question_paper') 
        txt_a_suffix = t('suffix_answer_sheet')   
        txt_footer_q = t('footer_question_paper') 
        txt_footer_a = t('footer_answer_sheet')   

        title = self.clean_latex_content(header_info.get('title', 'Exam'))
        subject = self.clean_latex_content(header_info.get('subject', 'General'))
        subtitle = self.clean_latex_content(header_info.get('subtitle', ''))
        exam_time = self.clean_latex_content(header_info.get('exam_time', ''))

        # --- Preamble ---
        tex.append(r"% !TEX program = xelatex")
        tex.append(r"\documentclass[12pt, a4paper]{article}")
        top_margin = "1.0cm" if is_compact else "1.5cm"
        tex.append(rf"\usepackage[top={top_margin}, bottom=2.0cm, left=1.2cm, right=1.2cm, headsep=0.3cm, includehead, includefoot]{{geometry}}")
        tex.append(r"\usepackage{array, tabularx, xcolor, xeCJK}")
        
        main_font, sans_font, mono_font = self._get_font_config()
        tex.append(rf"\setCJKmainfont{main_font}")
        tex.append(rf"\setCJKsansfont{sans_font}")
        tex.append(rf"\setCJKmonofont{mono_font}")
        
        tex.append(r"\XeTeXlinebreaklocale 'zh'")
        tex.append(r"\XeTeXlinebreakskip = 0pt plus 1pt")
        tex.append(r"\linespread{1.1}\selectfont")
        tex.append(r"\usepackage{amsmath, amssymb, amsthm, mathrsfs, graphicx, tikz, pgfplots, enumitem, fancyhdr, lastpage, eso-pic, calc, multicol, tcolorbox}")
        tex.append(r"\tcbuselibrary{skins, breakable}")
        tex.append(r"\pgfplotsset{compat=1.18}")

        tex.append(r"\newif\ifanswersheet")
        tex.append(r"\answersheetfalse") 

        # [MARKERS & SYSTEM QR]
        tex.append(r"\AddToShipoutPictureFG{\begin{tikzpicture}[remember picture, overlay]")
        tex.append(r"\fill[black] ([xshift=0.5cm, yshift=-0.5cm]current page.north west) rectangle ++(0.3, -0.3);")
        tex.append(r"\fill[black] ([xshift=-0.5cm, yshift=-0.5cm]current page.north east) rectangle ++(-0.3, -0.3);")
        tex.append(r"\fill[black] ([xshift=0.5cm, yshift=0.5cm] current page.south west) rectangle ++(0.3, 0.3);")
        tex.append(r"\fill[black] ([xshift=-0.5cm, yshift=0.5cm] current page.south east) rectangle ++(-0.3, 0.3);")
        
        tex.append(r"\node[anchor=south east, inner sep=0pt] at ([xshift=-2.0cm, yshift=1.5cm]current page.south east) {")
        tex.append(r"\ifanswersheet")
        tex.append(r"\IfFileExists{qrcode_p\thepage.png}{\includegraphics[width=1.3cm]{qrcode_p\thepage.png}}{\textbf{[QR-P?]}}")
        tex.append(r"\else")
        tex.append(r"\IfFileExists{qrcode_q\thepage.png}{\includegraphics[width=1.3cm]{qrcode_q\thepage.png}}{\textbf{[QR-Q?]}}")
        tex.append(r"\fi};")
        tex.append(r"\end{tikzpicture}}")

        head_font = r"\footnotesize" if is_compact else r"\small"
        tex.append(r"\setlength{\headheight}{28pt}\pagestyle{fancy}\fancyhf{}")
        tex.append(rf"\lhead{{{head_font} {subject}}}\chead{{{head_font} {title}}}\rhead{{{head_font} \texttt{[{exam_uuid[:8]}]}}}")
        
        tex.append(rf"\cfoot{{\ifanswersheet \small {txt_footer_a} - p. \thepage \else \small {txt_footer_q} - p. \thepage \fi}}")
        tex.append(r"\renewcommand{\headrulewidth}{0.4pt}")
        
        tex.append(r"\begin{document}")

        # ======================================================================
        # HEADER RENDERERS
        # ======================================================================
        
        def render_full_header(title_suffix=""):
            header_title_tex = rf"{{\Large \textbf{{{title}}}}}"
            if title_suffix:
                header_title_tex += rf" \quad {{\large \textbf{{{title_suffix}}}}}"
            
            full_subtitle = subtitle 

            if is_compact:
                # Compact Mode
                tex.append(r"\vspace{-0.3cm}")
                tex.append(r"\noindent \begin{tabularx}{\linewidth}{@{} X r @{}}")
                tex.append(rf"{header_title_tex} & \small \textbf{{{lbl_total}：{total_score_str} {lbl_score_unit}}} \\")
                if full_subtitle: 
                    tex.append(rf"{{\small {full_subtitle}}} & \\[0.2cm]")
                else:
                    tex.append(r" & \\")
                tex.append(r"\end{tabularx}")
                
                # [FIX] 增加間距 0.4cm (Subtitle 與 學生資料框 之間)
                tex.append(r"\par\vspace{0.4cm}")
                
                # 學生資料框
                tex.append(r"\noindent \begin{tcolorbox}[colframe=black, colback=white, boxrule=0.8pt, arc=2pt, left=4pt, right=4pt, top=10pt, bottom=10pt, width=\linewidth]")
                tex.append(r"\small")
                strut = r"\rule[-0.2cm]{0pt}{0.8cm}"
                tex.append(rf"\textbf{{{lbl_dept}：}}\underline{{\hspace{{1.5cm}}{strut}}} \quad \textbf{{{lbl_name}：}}\underline{{\hspace{{1.5cm}}{strut}}} \quad")
                tex.append(rf"\textbf{{{lbl_id}：}} \underline{{\hspace{{2.5cm}}{strut}}} \quad \textbf{{{lbl_seat}：}} \underline{{\hspace{{1.0cm}}{strut}}} \quad")
                tex.append(rf"\textbf{{{lbl_score_box}：}} \underline{{\hspace{{1.0cm}}{strut}}}")
                tex.append(r"\end{tcolorbox}")
                tex.append(r"\vspace{-0.2cm}")
            else:
                # Normal Mode
                tex.append(r"\noindent \begin{minipage}[c]{0.15\textwidth}")
                if has_logo: tex.append(r"\includegraphics[width=\linewidth, height=1.2cm, keepaspectratio]{logo.png}")
                else: tex.append(r"\hfill")
                tex.append(r"\end{minipage}")
                tex.append(r"\begin{minipage}[c]{0.68\textwidth} \centering " + header_title_tex)
                if full_subtitle: tex.append(r"\\[0.1cm] {\small \textmd{" + full_subtitle + r"}}")
                tex.append(r"\end{minipage}")
                tex.append(r"\begin{minipage}[c]{0.15\textwidth} \raggedleft")
                if has_marketing_qr: tex.append(r"\includegraphics[width=1.1cm, keepaspectratio]{marketing_qr.png}")
                else: tex.append(r"\hfill")
                tex.append(r"\end{minipage} \vspace{0.1cm}") 
                tex.append(r"\noindent \begin{tcolorbox}[colframe=black, colback=white, arc=4pt, boxrule=0.8pt, left=6pt, right=6pt, top=3pt, bottom=3pt]")
                tex.append(r"\begin{minipage}{0.78\linewidth} \renewcommand{\arraystretch}{1.2} \small")
                tex.append(r"\begin{tabular}{@{}ll}")
                tex.append(rf"\textbf{{{lbl_subject}：}} {subject} & \textbf{{{lbl_total}：}} {total_score_str} {lbl_score_unit} \quad \textbf{{{lbl_time}：}} \underline{{{exam_time}}} \\")
                tex.append(rf"\textbf{{{lbl_dept}：}} \underline{{\hspace{{2.0cm}}}} & \textbf{{{lbl_name}：}} \underline{{\hspace{{2.0cm}}}} \quad \textbf{{{lbl_seat}：}} \underline{{\hspace{{1.0cm}}}} \\")
                tex.append(r"\end{tabular}")
                tex.append(rf"\vspace{{2pt}} \\ \noindent \textbf{{{lbl_id}：}} \underline{{\hspace{{5.0cm}}}}")
                tex.append(r"\end{minipage}")
                tex.append(rf"\begin{{minipage}}{{0.20\linewidth}} \centering \begin{{tabular}}{{|p{{2.0cm}}|}} \hline \centering \footnotesize \textbf{{{lbl_score_box}}} \\ \hline \vspace{{0.6cm}} \\ \hline \end{{tabular}} \end{{minipage}}")
                tex.append(r"\end{tcolorbox}")
                tex.append(r"\vspace{0.1cm}\hrule height 0.6pt \vspace{0.2cm}")

        def render_branding_header(suffix_text=""):
            tex.append(r"\noindent \begin{minipage}[c]{0.15\textwidth}")
            if has_logo: tex.append(r"\includegraphics[width=\linewidth, height=1.2cm, keepaspectratio]{logo.png}")
            else: tex.append(r"\hfill")
            tex.append(r"\end{minipage}")
            
            tex.append(r"\begin{minipage}[c]{0.68\textwidth} \centering {\Large \textbf{" + title + suffix_text + r"}}")
            if subtitle: tex.append(r"\\[0.1cm] {\small \textmd{" + subtitle + r"}}")
            tex.append(r"\end{minipage}")
            
            tex.append(r"\begin{minipage}[c]{0.15\textwidth} \raggedleft")
            if has_marketing_qr: tex.append(r"\includegraphics[width=1.1cm, keepaspectratio]{marketing_qr.png}")
            else: tex.append(r"\hfill")
            tex.append(r"\end{minipage} \vspace{0.2cm}")
            
            tex.append(r"\noindent \small")
            tex.append(rf"\textbf{{{lbl_dept}：}}\underline{{\hspace{{2.0cm}}}} \quad")
            tex.append(rf"\textbf{{{lbl_name}：}}\underline{{\hspace{{2.0cm}}}} \quad")
            tex.append(rf"\textbf{{{lbl_id}：}}\underline{{\hspace{{2.5cm}}}} \quad")
            tex.append(rf"\textbf{{{lbl_seat}：}}\underline{{\hspace{{1.5cm}}}}")
            
            tex.append(r"\vspace{0.1cm}\hrule height 0.6pt \vspace{0.3cm}")

        # ======================================================================
        # QUESTION LOOP
        # ======================================================================
        def render_questions(mode="full"): 
            tex.append(r"\begin{enumerate}[label=\textbf{\arabic*.}, leftmargin=*, itemsep=1.0em]")
            letters = string.ascii_lowercase

            for q_idx, q in enumerate(questions):
                sub_qs = q.get('sub_questions', []) or []
                score = q.get('score', 0)
                q_text = self.clean_latex_content(q.get('text') or q.get('content') or "")
                box_h = f"{q.get('height', 6)}cm"

                if mode in ["full", "text_only"]:
                    if sub_qs: tex.append(r"\item " + q_text)
                    else: tex.append(r"\item ({\small " + str(score) + lbl_score_unit + r"}) " + q_text)
                    
                    if q.get('media'):
                        media = q['media']
                        tex.append(r"\par\vspace{0.2cm}\noindent\begin{minipage}{\linewidth}")
                        if media['type'] == 'image':
                            img_path = os.path.abspath(media['content']).replace('\\', '/')
                            if os.path.exists(img_path): tex.append(r"\begin{center}\includegraphics[width=0.6\linewidth, height=6cm, keepaspectratio]{" + img_path + r"}\end{center}")
                        elif media['type'] == 'tikz':
                            tex.append(media['content'])
                        tex.append(r"\end{minipage}")
                
                if mode == "box_only":
                    tex.append(r"\item ") 

                should_render_structure = (mode in ["full", "box_only"]) or (mode == "text_only" and (sub_qs or q.get('options')))

                if should_render_structure:
                    if sub_qs:
                        layout_cols = int(q.get('layout_cols', 2))
                        width_factor = 0.99 / layout_cols
                        rows = ceil(len(sub_qs) / layout_cols)
                        tex.append(r"\par\vspace{0.2cm}\noindent")
                        for r in range(rows):
                            tex.append(r"\par\noindent")
                            for c in range(layout_cols):
                                idx = r * layout_cols + c
                                if idx < len(sub_qs):
                                    sq = sub_qs[idx]
                                    sq_text = self.clean_latex_content(sq.get('text') or "")
                                    sq_score = sq.get('score', 0)
                                    sub_letter = letters[idx] if idx < 26 else str(idx+1)
                                    tex.append(r"\begin{minipage}[t]{\dimexpr " + str(width_factor) + r"\linewidth - 6pt \relax}")
                                    label_str = f"[Q{q_idx+1}-{idx+1}]"
                                    
                                    if mode == "full":
                                        tex.append(r"\textbf{(" + sub_letter + r")} ({\small " + str(sq_score) + lbl_score_unit + r"}) " + sq_text + r"\par\vspace{2pt}")
                                        tex.append(r"\noindent\begin{tikzpicture}")
                                        tex.append(r"\draw[line width=0.8pt, color=black] (0,0) rectangle (\linewidth, -" + box_h + r");")
                                        tex.append(r"\node[anchor=north west, inner sep=3pt] at (0, 0) {\small \textbf{" + label_str + r"}};")
                                        tex.append(r"\end{tikzpicture}")
                                    elif mode == "text_only":
                                        tex.append(r"\textbf{(" + sub_letter + r")} ({\small " + str(sq_score) + lbl_score_unit + r"}) " + sq_text + r"\par")
                                    else:
                                        tex.append(r"\textbf{(" + sub_letter + r")} \par\vspace{2pt}")
                                        tex.append(r"\noindent\begin{tikzpicture}")
                                        tex.append(r"\draw[line width=0.8pt, color=black] (0,0) rectangle (\linewidth, -" + box_h + r");")
                                        tex.append(r"\node[anchor=north west, inner sep=3pt] at (0, 0) {\small \textbf{" + label_str + r"}};")
                                        tex.append(r"\end{tikzpicture}")
                                    tex.append(r"\end{minipage}\hfill")
                            tex.append(r"\vspace{0.3cm}")

                    elif not q.get('options'):
                        if mode == "full":
                            label_str = f"[Q{q_idx+1}]"
                            tex.append(r"\par\vspace{0.1cm}")
                            tex.append(r"\noindent\begin{tikzpicture}")
                            tex.append(r"\draw[line width=0.8pt, color=black] (0,0) rectangle (\linewidth, -" + box_h + r");")
                            tex.append(r"\node[anchor=north west, inner sep=3pt] at (0, 0) {\small \textbf{" + label_str + r"}};")
                            tex.append(r"\end{tikzpicture}\par\vspace{0.3cm}")
                        elif mode == "box_only":
                            label_str = f"[Q{q_idx+1}]"
                            tex.append(r"\mbox{} \par\vspace{2pt}") 
                            tex.append(r"\noindent\begin{tikzpicture}")
                            tex.append(r"\draw[line width=0.8pt, color=black] (0,0) rectangle (\linewidth, -" + box_h + r");")
                            tex.append(r"\node[anchor=north west, inner sep=3pt] at (0, 0) {\small \textbf{" + label_str + r"}};")
                            tex.append(r"\end{tikzpicture}\par\vspace{0.3cm}")
                    
                    elif q.get('options'):
                        if mode in ["full", "text_only"]:
                            opts = [self.clean_latex_content(o) for o in q['options']]
                            tex.append(r"\begin{enumerate}[label=(\Alph*), itemsep=0pt, topsep=2pt]")
                            for opt in opts: tex.append(r"\item " + opt)
                            tex.append(r"\end{enumerate}")
                            tex.append(r"\par\vspace{0.1cm}")
                        elif mode == "box_only":
                             label_str = f"[Q{q_idx+1}]"
                             tex.append(r"\par\vspace{0.1cm}\noindent\begin{tikzpicture}")
                             tex.append(r"\draw[line width=0.8pt, color=black] (0,0) rectangle (2cm, -1.5cm);")
                             tex.append(r"\node[anchor=north west, inner sep=1pt] at (0, 0) {\scriptsize \textbf{" + label_str + r"}};")
                             tex.append(r"\end{tikzpicture}")

            tex.append(r"\end{enumerate}")

        if layout_mode == "separate":
            tex.append(r"\answersheetfalse") 
            render_branding_header(suffix_text=txt_q_suffix)
            render_questions(mode="text_only")
            tex.append(r"\newpage")
            tex.append(r"\answersheettrue")
            tex.append(r"\setcounter{page}{1}") 
            render_full_header(title_suffix=txt_a_suffix)
            render_questions(mode="box_only")
        else:
            tex.append(r"\answersheettrue") 
            render_full_header()
            render_questions(mode="full")

        tex.append(r"\end{document}")
        return "\n".join(tex)

    def generate_pdf(self, header_info, questions, user=None):
        exam_id = header_info.get('exam_id') or f"EXAM_{uuid.uuid4().hex[:8].upper()}"
        header_info['exam_id'] = exam_id
        system_qr_content = f"{exam_id}" 
        
        user_plan = getattr(user, 'plan', 'personal')
        plan_conf = get_plan_config(user_plan)
        allow_branding = plan_conf.get('branding', False)

        marketing_url = None
        if allow_branding:
            user_url = getattr(user, 'custom_advertising_url', '')
            sys_adv = get_sys_conf("advertising_url")
            sys_donate = get_sys_conf("donation_url")
            marketing_url = user_url if user_url else (sys_adv or sys_donate)
        else:
            marketing_url = None

        user_logo = getattr(user, 'branding_logo_path', None)
        logo_path_to_use = None
        
        if allow_branding:
            if user_logo and os.path.exists(user_logo):
                logo_path_to_use = user_logo
        
        has_logo_flag = bool(logo_path_to_use)
        
        source = self.generate_tex_source(
            header_info, 
            questions, 
            exam_uuid=exam_id, 
            has_logo=has_logo_flag, 
            has_marketing_qr=bool(marketing_url)
        )
        
        pdf_bytes = self.compile_tex_to_pdf(
            source, 
            exam_id, 
            system_qr_content, 
            marketing_url, 
            logo_path=logo_path_to_use
        )
        
        safe_title = re.sub(r'[\\/*?:"<>|]', "", header_info.get('title', 'Exam'))
        safe_subject = re.sub(r'[\\/*?:"<>|]', "", header_info.get('subject', 'General'))
        return pdf_bytes, f"{safe_title}_{safe_subject}.pdf"

    def compile_tex_to_pdf(self, tex_source, exam_id, system_qr_content, marketing_url, logo_path=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            for i in range(1, 15): 
                self._generate_qr_file(f"{system_qr_content}-P{i}", os.path.join(temp_dir, f"qrcode_p{i}.png"))
                self._generate_qr_file(f"{system_qr_content}-Q{i}", os.path.join(temp_dir, f"qrcode_q{i}.png"))

            if marketing_url: self._generate_qr_file(marketing_url, os.path.join(temp_dir, "marketing_qr.png"))

            if logo_path and os.path.exists(logo_path):
                target_logo = os.path.join(temp_dir, "logo.png")
                shutil.copy(logo_path, target_logo)

            tex_file = os.path.join(temp_dir, "exam.tex")
            with open(tex_file, "w", encoding="utf-8") as f: f.write(tex_source)
            
            cmd = [self.compiler, "-output-directory", temp_dir, "-interaction=nonstopmode", "exam.tex"]
            try:
                subprocess.run(cmd, cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                subprocess.run(cmd, cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                pdf_path = os.path.join(temp_dir, "exam.pdf")
                if os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f: return f.read()
                return None
            except Exception as e:
                self.logger.error(f"LaTeX Compile Error: {e}")
                return None
