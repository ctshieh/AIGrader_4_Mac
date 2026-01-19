# services/grading_service.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.16-Anti-Hallucination-Fixed
# Description: Logic execution layer. Enforces strict transcription for SymPy checks.

import json
import re
import io
import logging
from typing import List, Optional, Any, Dict

from services.prompt_service import PromptService 

# Optional verification engines
try:
    import sympy as sp
    from sympy.parsing.sympy_parser import (
        parse_expr,
        standard_transformations,
        implicit_multiplication_application,
        convert_xor
    )
except ImportError:
    sp = None

from google import genai
from google.genai import types
from PIL import Image

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)

PRICING_RATES = {
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
}

###
# services/grading_service.py

# [CRITICAL UPDATE] 加強版防禦指令：對抗 AI 的知識偏見
SYMPY_TRANSCRIPTION_RULES = """
# [CRITICAL] ANTI-BIAS & TRANSCRIPTION PROTOCOL:
1. TRUST YOUR EYES, NOT THE TEXTBOOK: 
   - Students often modify the question or make weird errors (e.g., changing "1" to "x").
   - If the Rubric expects "1/(1+x^2)" but the image shows "x/(1+x^2)", you MUST extract "x/(1+x^2)".
   - DO NOT "Auto-Correct" the student's writing to match the standard math problem.
   
2. LITERAL TRANSCRIPTION (SYMPY):
   - In "sympy_expr", output EXACTLY what is written.
   - Example: If student writes "sin(x) = 5", output "sin(x) = 5" (even if impossible). Do not output "No Solution".

3. DETECT DEVIATION:
   - If the student's setup deviates from the Rubric (e.g., extra 'x', wrong coefficient), calculate the score based on THAT error.
   - DEVIATION = 0 POINTS for the "Setup" criteria. Do not give partial credit for a "Correct solution to the wrong problem" unless specified.
4. LATEX FORMATTING (CRITICAL):
   - You MUST double-escape backslashes for JSON.
   - CORRECT: "\\\\frac{a}{b}" (becomes \frac{a}{b})
   - WRONG: "\\frac{a}{b}" (becomes Form Feed character + rac, BROKEN)
   - WRONG: "frac{a}{b}" (Text, BROKEN)   
"""
###

# [CRITICAL] 定義「SymPy 逐字聽寫」規則，防止 AI 自動更正學生的錯誤

class GradingService:
    # -------------------------------------------------------------------------
    # ID / Cost / Sanitization Helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def _normalize_id(raw_id: str) -> str:
        s = str(raw_id).strip().upper()
        s = s.replace("(", "-").replace(")", "").replace("[", "").replace("]", "")
        s = s.replace("Q", "").replace("_", "-")
        match = re.match(r"^(\d+)([A-Z])$", s)
        if match:
            return f"{match.group(1)}-{ord(match.group(2)) - ord('A') + 1}"
        return re.sub(r"[_\.\s]+", "-", s).strip("-")

    @staticmethod
    def _calculate_cost(model_id: str, usage_metadata) -> float:
        if not usage_metadata: return 0.0
        rate = PRICING_RATES.get("gemini-2.5-pro", PRICING_RATES["gemini-2.5-pro"])
        for k, v in PRICING_RATES.items():
            if k in model_id: rate = v; break
        in_t = getattr(usage_metadata, "prompt_token_count", 0) or 0
        out_t = getattr(usage_metadata, "candidates_token_count", 0) or 0
        return (in_t / 1e6) * rate["input"] + (out_t / 1e6) * rate["output"]

    @staticmethod
    def _sanitize_text(s: str) -> str:
        if not isinstance(s, str): return s
        return s.replace(chr(12), r"\\f").replace("\t", r"\\t").replace("\x00", "")
##### Repair latex format ####
    @staticmethod
    def _repair_broken_latex(text: str) -> str:
        """
        [AUTO-REPAIR] 修復 AI 因為轉義失敗而產生的 broken latex。
        例如：'frac{a}{b}' -> '\\frac{a}{b}'
        """
        if not text or not isinstance(text, str): return text
        
        # 1. 修復常見的運算子 (若前面沒有反斜線，就補上)
        # 針對 frac, int, sqrt, sum, lim, sin, cos, tan, ln, log, times
        # 使用 Negative Lookbehind (?<!\\) 確保前面沒有斜線
        
        patterns = [
            (r'(?<!\\)\bfrac\b', r'\\frac'),
            (r'(?<!\\)\bint\b', r'\\int'),
            (r'(?<!\\)\bsqrt\b', r'\\sqrt'),
            (r'(?<!\\)\bsum\b', r'\\sum'),
            (r'(?<!\\)\blim\b', r'\\lim'),
            (r'(?<!\\)\btimes\b', r'\\times'),
            (r'(?<!\\)\binfty\b', r'\\infty'),
            (r'(?<!\\)\bapprox\b', r'\\approx'),
            (r'(?<!\\)\bcdot\b', r'\\cdot'),
            # 三角函數與對數
            (r'(?<!\\)\b(sin|cos|tan|cot|sec|csc|ln|log)\b', r'\\\1')
        ]
        
        fixed = text
        for pat, repl in patterns:
            fixed = re.sub(pat, repl, fixed)
            
        # 2. 確保數學式被 $ 包裹 (簡單啟發式：如果有 \frac 但沒有 $，嘗試補救)
        # 這一步比較危險，先只針對明顯的修復 backslashes
        
        return fixed

########
   
   

    # [MODIFIED] 修改這個函數：注入修復邏輯
    @staticmethod
    def _sanitize_json(obj: Any) -> Any:
        """遞迴清理 JSON 並修復 Latex"""
        if isinstance(obj, dict):
            return {k: GradingService._sanitize_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [GradingService._sanitize_json(v) for v in obj]
        if isinstance(obj, str):
            clean = GradingService._sanitize_text(obj)
            # 關鍵修改：呼叫修復函數
            return GradingService._repair_broken_latex(clean)
        return obj

    @staticmethod
    def _safe_parse_rubric(text: str) -> Optional[dict]:
        try: return json.loads(text.strip()) if text else None
        except: return None

    # -------------------------------------------------------------------------
    # SymPy Engine
    # -------------------------------------------------------------------------
    @staticmethod
    def _clean_latex_for_sympy(expr: str) -> str:
        if not expr: return ""
        s = expr.strip()
        s = s.replace(r"\left", "").replace(r"\right", "")
        s = s.replace(r"\mathrm", "").replace(r"\text", "")
        s = s.replace("{", "(").replace("}", ")") 
        s = s.replace(r"\frac", "") 
        s = s.replace("\\", "") 
        s = s.replace("−", "-").replace("×", "*").replace("÷", "/")
        return s

    @staticmethod
    def _canonicalize_sympy_expr(expr: str) -> str:
        if not isinstance(expr, str): return expr
        s = GradingService._clean_latex_for_sympy(expr)
        s = re.sub(r"(?<!\*)\^(?!\*)", "**", s)
        return s

    @staticmethod
    def _sympy_ok(expr: str, expected: str, var: str = "x") -> bool:
        if sp is None: return True
        try:
            expr_str = GradingService._canonicalize_sympy_expr(expr)
            expected_str = GradingService._canonicalize_sympy_expr(expected)
            transformations = (standard_transformations + (implicit_multiplication_application, convert_xor))
            locals_map = {var: sp.Symbol(var), "x": sp.Symbol("x"), "e": sp.E, "pi": sp.pi}
            for f in ["sin", "cos", "tan", "csc", "sec", "cot", "log", "ln", "exp", "sqrt"]:
                locals_map[f] = getattr(sp, f, None)
                if f == "csc": locals_map["csc"] = lambda arg: 1/sp.sin(arg)
                if f == "sec": locals_map["sec"] = lambda arg: 1/sp.cos(arg)
                if f == "cot": locals_map["cot"] = lambda arg: 1/sp.tan(arg)

            A = parse_expr(expr_str, transformations=transformations, local_dict=locals_map)
            B = parse_expr(expected_str, transformations=transformations, local_dict=locals_map)
            
            # 1. 嘗試直接相減簡化
            diff = sp.simplify(A - B)
            if diff == 0: return True
            
            # 2. 嘗試數值代入 (Double Check)
            f = sp.lambdify(sp.Symbol(var), A - B, modules="math")
            for val in [0.1, 0.5, 1.0, 10.0]:
                try:
                    if abs(f(val)) > 1e-6: return False
                except: continue
            return True
        except Exception:
            return False

    @staticmethod
    def _build_rubric_step_index(rubric: dict) -> dict:
        steps_by_subq = {}; step_by_rule_id = {}
        try:
            for q in rubric.get("questions", []) or []:
                for sq in q.get("sub_questions", []) or []:
                    sid = str(sq.get("id", "")).strip()
                    steps = sq.get("rubric", []) or []
                    steps_by_subq[sid] = steps
                    for st in steps:
                        if rid := str(st.get("rule_id", "")).strip():
                            step_by_rule_id[rid] = (sid, st)
        except: pass
        return {"steps_by_subq": steps_by_subq, "step_by_rule_id": step_by_rule_id}

    @staticmethod
    def _apply_step_check(bd_item: dict, step_def: dict, mode: str) -> dict:
        if not isinstance(bd_item, dict): return bd_item
        c = (bd_item.get("comment") or "").strip()
        ev = (bd_item.get("evidence") or "").strip()
        if not c or (not c.startswith("學生寫：") and not c.startswith("未見：")):
            bd_item["comment"] = (f"學生寫：{ev}。" + c) if ev else ("未見：" + c)

        check = (step_def or {}).get("check")
        if not isinstance(check, dict): return bd_item

        if step_def.get("require_work") is True and not ev:
            bd_item["score"] = 0.0
            bd_item["missing_work"] = True
            bd_item["comment"] = "未見：此步驟需算式但空白，不給分。"
            return bd_item

        if (check.get("engine") or "").lower() == "sympy":
            expected = str(check.get("expected", "")).strip()
            student_expr = str(bd_item.get("sympy_expr", "")).strip()
            # 只有當兩者都有值時才驗算
            if expected and student_expr:
                if not GradingService._sympy_ok(student_expr, expected, str(check.get("var", "x"))):
                    bd_item["score"] = 0.0
                    bd_item["error_type"] = "Computational"
                    bd_item["comment"] += f" [系統驗算失敗: 學生寫 '{student_expr}' vs 預期 '{expected}']"
        return bd_item

    @staticmethod
    def _apply_rubric_checks(res_json: dict, rubric: dict, mode: str) -> dict:
        idx = GradingService._build_rubric_step_index(rubric)
        for q in res_json.get("questions", []) or []:
            qid = str(q.get("id", "")).strip()
            steps = idx["steps_by_subq"].get(qid, [])
            for i, bd in enumerate(q.get("breakdown", [])):
                step_def = None
                rid = bd.get("rule_id")
                if rid and rid in idx["step_by_rule_id"]: step_def = idx["step_by_rule_id"][rid][1]
                elif i < len(steps): step_def = steps[i]
                if step_def: q["breakdown"][i] = GradingService._apply_step_check(bd, step_def, mode)
            try: q["score"] = sum(float(b.get("score", 0)) for b in q["breakdown"])
            except: pass
        return res_json

    @staticmethod
    def _get_grading_instruction(subject_key: str, mode: str, language: str, ai_memory: str) -> str:
        subj_conf = PromptService.get_prompt_config(subject_key)
        role = subj_conf.get("Role", "Academic Grader")
        available_modes = subj_conf.get("Modes", {})
        mode_rules = available_modes.get(mode, available_modes.get("Strict", ""))

        return f"""
# ROLE
You are a **{role}**.

# LANGUAGE
Write ALL comments in {language}.

# MODE: {mode.upper()}
{mode_rules}

# OUTPUT FORMAT (JSON)
- You MUST provide a detailed breakdown for each step.
- Each breakdown item MUST include:
  (A) "rule": Copy the rubric text.
  (B) "score": Points awarded.
  (C) "comment": MUST start with "學生寫：" (Student wrote: ...) or "未見：" (Missing: ...).
      - **MANDATORY**: Use LaTeX ($...$) for ALL math expressions in comments.
  (D) "sympy_expr": [CRITICAL] If the step involves a math formula/calculation, extract the student's raw math expression here in Python/SymPy syntax (e.g., "x**2", "-csc(x)*cot(x)"). If text only, leave empty.
  (E) "evidence": The verbatim text/latex found in the image.

# LATEX ENFORCEMENT
- **NO PLAIN TEXT MATH**: Do not output "x^2" or "sin(x)". ALWAYS output "$x^2$" or "$\\sin(x)$".
- **JSON ESCAPING**: To output a backslash, you need FOUR backslashes in code, or TWO in string.
  - Just output `\\frac` to be safe.
"""

    @staticmethod
    def get_subject_options() -> Dict[str, str]:
        return {k: f"[{k}]" for k in PromptService._PROMPTS.keys()}

    # -------------------------------------------------------------------------
    # MAIN ENTRY POINTS
    # -------------------------------------------------------------------------
    @staticmethod
    def grade_submission(
        images: List[Image.Image], rubric_text: str, user: Any, batch_id: str,
        student_idx: int, mode: str, subject: str = "univ_math", ai_memory: str = "",
        temperature: float = 0.0, model_id: str = "gemini-2.5-pro",
        allowed_labels: Optional[List[str]] = None, language: str = "Traditional Chinese"
    ) -> dict:
        
        if not getattr(user, "google_api_key", None):
            return {"questions": [], "total_score": 0, "general_comment": "Missing API Key"}

        client = genai.Client(api_key=user.google_api_key)
        sys_instr = GradingService._get_grading_instruction(subject, mode, language, ai_memory)
        
        schema = {
            "type": "OBJECT",
            "properties": {
                "student_info": {"type": "OBJECT", "properties": {"name": {"type": "STRING"}, "id": {"type": "STRING"}}},
                "thinking_process": {"type": "STRING"},
                "questions": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "id": {"type": "STRING"},
                            "score": {"type": "NUMBER"},
                            "reasoning": {"type": "STRING"},
                            "breakdown": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "rule_id": {"type": "STRING"},
                                        "rule": {"type": "STRING"},
                                        "score": {"type": "NUMBER"},
                                        "comment": {"type": "STRING"},
                                        "evidence": {"type": "STRING"},
                                        "sympy_expr": {"type": "STRING"}
                                    },
                                    "required": ["score", "comment", "sympy_expr"]
                                }
                            }
                        },
                        "required": ["id", "score", "breakdown"]
                    }
                },
                "general_comment": {"type": "STRING"}
            },
            "required": ["student_info", "questions", "general_comment"]
        }

        # [MODIFIED] 插入 SYMPY_TRANSCRIPTION_RULES 到 prompt 中
        prompt = f"""
{sys_instr}

# TASK 1: IDENTITY EXTRACTION (Look at Page 1 Header)
- Extract **Student Name** (姓名) and **Student ID** (學號).
- If handwriting is unclear, guess. If completely missing, use "Unknown".

# TASK 2: GRADING
- Grade based on RUBRIC.
{SYMPY_TRANSCRIPTION_RULES}

# RUBRIC
{rubric_text}

Output JSON.
"""
        content = [prompt]
        for img in images:
            buf = io.BytesIO(); img.save(buf, format="PNG")
            content.append(types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png"))

        try:
            resp = client.models.generate_content(
                model=model_id,
                contents=content,
                config=types.GenerateContentConfig(
                    temperature=0.0 if mode == "Strict" else temperature,
                    response_mime_type="application/json",
                    response_schema=schema
                )
            )
            res_json = json.loads(resp.text)
            res_json = GradingService._sanitize_json(res_json)
            
            rubric_obj = GradingService._safe_parse_rubric(rubric_text)
            if rubric_obj:
                res_json = GradingService._apply_rubric_checks(res_json, rubric_obj, mode)

            res_json["cost_usd"] = GradingService._calculate_cost(model_id, resp.usage_metadata)
            res_json["total_score"] = sum(float(q.get("score", 0)) for q in res_json.get("questions", []))
            return res_json

        except Exception as e:
            logger.error(f"Grading Error: {e}")
            return {"questions": [], "total_score": 0, "general_comment": str(e)}

    @staticmethod
    def grade_collage_submission(
        image: Image.Image, question_id: str, rubric_text: str, user: Any,
        mode: str, subject: str, temperature: float, model_name: str,
        allowed_labels: Optional[List[str]] = None, valid_indices: Optional[List[int]] = None,
        language: str = "Traditional Chinese"
    ):
        if not getattr(user, "google_api_key", None): return {"results": [], "cost_usd": 0.0}
        
        sys_instr = GradingService._get_grading_instruction(subject, mode, language, "")
        whitelist_msg = f"VALID INDICES: {valid_indices}. IGNORE other cells." if valid_indices else ""
        
        # [MODIFIED] 插入 SYMPY_TRANSCRIPTION_RULES 到 prompt 中
        prompt = f"""
{sys_instr}
# TASK: GRADE GRID (Question: {question_id})
- {whitelist_msg}
{SYMPY_TRANSCRIPTION_RULES}
- Comment must start with "學生寫：".

# RUBRIC
{rubric_text}
"""
        schema = {"type": "OBJECT", "properties": {"results": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"index": {"type": "INTEGER"}, "score": {"type": "NUMBER"}, "reasoning": {"type": "STRING"}, "breakdown": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"rule": {"type": "STRING"}, "score": {"type": "NUMBER"}, "comment": {"type": "STRING"}, "sympy_expr": {"type": "STRING"}}, "required": ["score", "comment"]}}}, "required": ["index", "score"]}}}}

        try:
            client = genai.Client(api_key=user.google_api_key)
            buf = io.BytesIO(); image.save(buf, format="PNG")
            resp = client.models.generate_content(
                model=model_name,
                contents=[prompt, types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png")],
                config=types.GenerateContentConfig(temperature=temperature, response_mime_type="application/json", response_schema=schema)
            )
            res = json.loads(resp.text)
            return {"results": res.get("results", []), "cost_usd": GradingService._calculate_cost(model_name, resp.usage_metadata)}
        except Exception as e:
            return {"results": [], "cost_usd": 0.0, "error": str(e)}
