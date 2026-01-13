# services/ai_service.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.01-AI-Math-Enhanced
# Description: 
# 1. [Prompt Fix] Enforces strict LaTeX ($...$) formatting in generated JSON Rubrics.
# 2. [Prompt Fix] Enhanced Mathematics Guidelines for granular partial credit and ECF.
import sympy
import os
import json
import logging
import time
import re
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

def _get_valid_api_key(user_key: str) -> str:
    if user_key and user_key.strip(): return user_key
    raise ValueError("BYOK_REQUIRED: Missing API Key. Please configure your Gemini API Key in Settings.")

def _clean_json_response(text: str) -> str:
    if not text: return "{}"
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match: return match.group(1)
    return text

def _validate_and_fix_math(rubric_json: dict) -> dict:
    try:
        calculated_exam_total = 0
        questions = rubric_json.get("questions", [])
        for q in questions:
            sub_qs = q.get("sub_questions", [])
            q_points = float(q.get("points", 0))
            if sub_qs:
                sub_total = sum(float(sq.get("points", 0)) for sq in sub_qs)
                if sub_total > 0:
                    q["points"] = sub_total
                    calculated_exam_total += sub_total
                else:
                    calculated_exam_total += q_points
            else:
                calculated_exam_total += q_points
        if calculated_exam_total > 0: rubric_json["total_points"] = calculated_exam_total
        return rubric_json
    except Exception as e:
        logger.error(f"Math Fix Error: {e}")
        return rubric_json


# ----------------------------------------------------------------------
# SymPy-check metadata helpers (lightweight, backward-compatible)
# ----------------------------------------------------------------------
_ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200D\uFEFF]")

def _nfkc_clean(s: str) -> str:
    """Basic cleanup for rubric text: remove zero-width chars, collapse whitespace."""
    if not isinstance(s, str):
        return s
    s = _ZERO_WIDTH_RE.sub("", s)
    s = s.replace("\u2061", "")  # FUNCTION APPLICATION
    s = s.replace("\u2062", "")  # INVISIBLE TIMES
    s = re.sub(r"\s+", " ", s).strip()
    return s

_DERIV_EXPECTED = {
    "csc(x)": "-csc(x)*cot(x)",
    "sec(x)": "sec(x)*tan(x)",
    "cot(x)": "-csc(x)**2",
    "tan(x)": "sec(x)**2",
    "sin(x)": "cos(x)",
    "cos(x)": "-sin(x)",
    "log(x)": "1/x",
    "ln(x)": "1/x",
    "exp(x)": "exp(x)",
}

def _infer_sympy_checks(rubric_json: dict, subject: str = "Mathematics") -> dict:
    """
    Add optional `check` metadata for common strict-computation steps.
    This is a best-effort fallback if the model does not output checks.
    """
    try:
        if subject not in ("Mathematics", "Linear Algebra", "Statistics"):
            return rubric_json

        for q in rubric_json.get("questions", []):
            for sq in q.get("sub_questions", []) or []:
                for i, item in enumerate(sq.get("rubric", []) or []):
                    # Clean text fields
                    if "criterion" in item:
                        item["criterion"] = _nfkc_clean(item["criterion"])
                    if "title" in item and isinstance(item["title"], str):
                        item["title"] = _nfkc_clean(item["title"])

                    # If check already present, keep it
                    if isinstance(item.get("check"), dict):
                        continue

                    crit = str(item.get("criterion", "")).lower()

                    # Heuristic: L'Hôpital derivative checks
                    if ("羅必達" in item.get("criterion", "")) or ("l'hôpital" in crit) or ("lhopital" in crit):
                        # Common trig/log derivatives used in these problems
                        for expr, expected in _DERIV_EXPECTED.items():
                            # detect function appearance
                            key = expr.replace("(x)", "")
                            if key in crit or key in item.get("criterion", ""):
                                item["check"] = {
                                    "engine": "sympy",
                                    "type": "derivative",
                                    "var": "x",
                                    "expr": expr if expr != "ln(x)" else "log(x)",
                                    "expected": expected,
                                    "policy": {"all_or_nothing": True, "partial_credit_max": 1},
                                }
                                break

                    # Heuristic: explicit derivative mention without L'Hôpital
                    if item.get("check") is None and ("微分" in item.get("criterion", "")):
                        for expr, expected in _DERIV_EXPECTED.items():
                            key = expr.replace("(x)", "")
                            if key in crit or key in item.get("criterion", ""):
                                item["check"] = {
                                    "engine": "sympy",
                                    "type": "derivative",
                                    "var": "x",
                                    "expr": expr if expr != "ln(x)" else "log(x)",
                                    "expected": expected,
                                    "policy": {"all_or_nothing": True, "partial_credit_max": 1},
                                }
                                break

        return rubric_json
    except Exception as e:
        logger.error(f"Infer SymPy checks error: {e}")
        return rubric_json


def generate_rubric(pdf_path: str, model_name: str, api_key: str, subject: str = "Mathematics", language: str = "Traditional Chinese") -> str:
    """
    產生評分標準 - 包含完整的 STEM 分段給分邏輯、數學等價性與 1-1 子題格式
    [Updated] Enhanced Math guidelines for granular scoring.
    """
    try:
        real_key = _get_valid_api_key(api_key)
        client = genai.Client(api_key=real_key)
        
        with open(pdf_path, "rb") as f:
             file_ref = client.files.upload(
                 file=f, 
                 config={'display_name': 'Rubric_Source', 'mime_type': 'application/pdf'}
             )
        time.sleep(2) 

        # ======================================================================
        # Domain-Based Strict Guidelines (領域規則) - [ENHANCED]
        # ======================================================================
        SUBJECT_GUIDELINES = {
            "Mathematics": """
            **STRICT MATHEMATICS / LINEAR ALGEBRA / STATISTICS RUBRIC GUIDELINES (University-level, STRICT):**

            1) **Adaptive Granularity (DO NOT be overly coarse or overly verbose)**:
               - Choose the number of rubric steps PER sub-question using BOTH point-value and complexity:
                 * ≤ 5 points: 2–3 steps
                 * 6–10 points: 3–5 steps
                 * 11–15 points: 5–7 steps
                 * 16–20 points: 6–8 steps
                 * > 20 points: 8–12 steps
               - Complexity adjustment:
                 * Single-line computation (e.g., det of 2x2, mean of small dataset): use the LOWER bound.
                 * One major transformation (e.g., one L'Hôpital / one RREF / one t-test): use the MIDDLE range.
                 * Multi-stage reasoning (multiple transformations or multi-part derivations): use the UPPER bound.

            2) **Strict Computation Policy (University grading)**:
               - For any step that involves calculation/derivation/simplification/substitution:
                 * If the key computation is WRONG, award **0** for that step.
                 * At most **1 point** may be awarded as "method recognition" ONLY when the method/setup is clearly correct.
               - A correct final answer with no supporting work gets **0** unless the problem explicitly states "answer-only allowed".

            3) **ECF (Error Carried Forward) DEFAULT = OFF**:
               - Only allow ECF when explicitly written in the criterion: "允許錯誤帶入(ECF)".
               - Even when ECF is allowed, NEVER award points for incorrect computations; ECF applies only to later logical steps using the student's previous result.

            4) **Criterion must be CHECKABLE (MANDATORY)**:
               - Each rubric item MUST be short and written in {language}.
               - Each rubric item MUST follow this template (single paragraph, no line breaks):
                 "（動作/要求）。需出現：<可檢核要素列表>。"
                 Optionally add: "若<常見錯誤>→此步0分。" or "允許錯誤帶入(ECF)。"
               - Avoid fancy Unicode math glyphs; keep plain text + LaTeX ($...$) only.

            5) **Statistics-specific notes**:
               - If an answer is numerical, specify acceptable rounding (e.g., to 3 decimals) and tolerance (e.g., ±0.001) in the criterion when appropriate.
               - Require both computation AND correct conclusion (reject / fail to reject H0) when applicable.

            6) **Linear Algebra-specific notes**:
               - Prefer checkable intermediate results (e.g., RREF, pivot columns, det, eigenpairs).

            7) **SymPy / SciPy Check Metadata (HIGHLY RECOMMENDED, and MANDATORY when applicable)**:
               - For each rubric item that involves a verifiable computation, include a `check` object.
               - `check.engine` should be one of: "sympy" (algebra/calculus/linear algebra) or "scipy" (statistics).
               - Keep expressions SymPy-friendly: use `log(x)` for ln, `exp(x)` for $e^x$, `sin(x)`, `csc(x)`, `cot(x)`.
               - Example (derivative step): check={engine:"sympy", type:"derivative", var:"x", expr:"csc(x)", expected:"-csc(x)*cot(x)"}.

               - Require explicit key objects: matrix, augmented matrix, row operations, RREF, pivot columns, solution set, eigenpairs, etc.
               - If a step claims a result (e.g., "RREF is ..."), it must be correct to receive points.
            """,
            
            "Physics": """
            **STRICT PHYSICS RUBRIC:**
            1. **FBD**: Missing Free Body Diagram (FBD) = Deduction.
            2. **Units**: Answer without SI units = 0 points for the answer portion.
            3. **Variables**: Points for starting with symbolic variables before plugging in numbers.
            """,
            
            "Chemistry": """
            **STRICT CHEMISTRY RUBRIC:**
            1. **Stoichiometry**: Unbalanced equations = 0 points.
            2. **States of Matter**: Missing (s), (l), (g), (aq) where crucial = Deduction.
            3. **Sig Figs**: Answers must respect significant figures (if applicable).
            """,
            
            "Coding": """
            **STRICT CODING RUBRIC:**
            1. **Edge Cases**: Must handle boundary inputs (null, empty list, negative numbers).
            2. **Complexity**: Inefficient algorithms ($O(n^2)$ when $O(n)$ exists) = Partial credit.
            3. **Style**: Variable naming and indentation checks.
            """,
            
            "Essay": """
            **STRICT ESSAY RUBRIC:**
            1. **Thesis**: Must have a clear thesis statement.
            2. **Evidence**: Claims must be supported by specific examples.
            3. **Structure**: Logical flow and paragraph transitions.
            """
        }

        subject_focus = SUBJECT_GUIDELINES.get(subject, SUBJECT_GUIDELINES.get("Math", SUBJECT_GUIDELINES["Mathematics"]))

        # [PROMPT UPDATE] Added Section 7 for LaTeX Formatting
        prompt = ("""
        Act as a **Distinguished University Professor in {subject}**. Create a rigorous Answer Key and Grading Rubric.

        ### OBJECTIVE
        Analyze the **ATTACHED PDF EXAM** and generate a JSON rubric.

        ### DOMAIN FOCUS & STRICT RULES
        {subject_focus}

        ### INSTRUCTIONS (STRICT STEP-BY-STEP SCORING)

        1. **SOLVE** the problems in the PDF step-by-step clearly to derive the Ground Truth. All University level derivation and computation cannot be ommitted.

        2. **BREAK DOWN** scoring into granular partial credit steps (Adaptive step count per sub-question using the Guideline's table) (Follow the Domain Guidelines above):
           - **Concept**: Understanding the underlying principle.
           - **Setup**: Equations/diagrams/formulas setup.
           - **Execution**: Mathematical manipulation/Calculus steps.
           - **Answer**: Final result.

        3. **Step-by-Step Verification (Carry Forward Error)**:
           - Explicitly mark in the `description` or `criteria` that ECF is allowed for logical steps derived from previous errors.
        
        4. **Zero Tolerance for Magic Answers**:
           - If a complex problem has a correct final answer but no supporting work, the score is 0.

        5. **SUB-QUESTIONS (CRITICAL FORMAT)**: 
           - You MUST use the format **"1-1", "1-2"** (NOT "1a", "1b").
           - Example: If Question 1 has parts (a) and (b), their IDs must be "1-1" and "1-2".

        6. **FORMAT**: Output strict JSON.

        6.1 **RUBRIC STEP IDENTIFIERS (RECOMMENDED)**:
           - For each rubric item, include `rule_id` (e.g., "1-3.S2") and a short `title`.
           - Keep backward compatibility: still include `points` and `criterion`.


        6.2 **CHECK METADATA (MANDATORY when the step is computational and checkable)**:
           - For each rubric item that can be mechanically verified, include a `check` object.
           - Use SymPy-friendly expressions (ASCII): log(x), exp(x), sin(x), cos(x), tan(x), csc(x), sec(x), cot(x).
           - Typical `check` types:
             * derivative: {{"engine":"sympy","type":"derivative","var":"x","expr":"csc(x)","expected":"-csc(x)*cot(x)","policy":{{"all_or_nothing":true,"partial_credit_max":1}}}}
             * matrix_rref: {{"engine":"sympy","type":"matrix_rref","var":"x","input":{{"A":"[[1,2],[3,4]]"}},"expected":{{"rref":"[[1,0], [0,1]]"}}}}
             * det: {{"engine":"sympy","type":"det","input":{{"A":"[[1,2],[3,4]]"}},"expected":{{"value":"-2"}}}}
             * ttest_pvalue: {{"engine":"scipy","type":"ttest_pvalue","input":{{"xbar":12.3,"s":2.1,"n":25,"mu0":12,"alternative":"two-sided"}},"expected":{{"pvalue":0.43,"tol":0.001}}}
           - If a step is purely conceptual and not mechanically checkable, you MAY omit `check`.


           - For each rubric item, include `rule_id` (e.g., "1-3.S2") and a short `title`.
           - Keep backward compatibility: still include `points` and `criterion`.

        6.3 **CALCULUS CHECK RULES (CRITICAL)**:
           - For **Intermediate Limits** (e.g., L'Hopital result, Simplification):
             The `expected` MUST be the algebraic expression, NOT the final number.
             * Example: If limit is -x -> 0.
             * Step "Simplification": expected="-x" (Check algebra).
             * Step "Final Answer": expected="0" (Check value).
             
           - For **L'Hopital's Rule**:
             The `expected` MUST be the fraction of derivatives.
             * correct: "(1/x)/(-1/x**2)" or simplified "-x".
             * INCORRECT: "1/x" (Numerator only) -> This causes grading errors.

        7. **[LATEX FORMATTING - MANDATORY]**:
           - **ALL mathematical expressions MUST be wrapped in LaTeX delimiters ($...$).**
           - **Correct**: "The integral is $\\int x^2 dx$."
           - **Incorrect**: "The integral is \int x^2 dx" or "The integral is x^2".
           - This applies to `description`, `criteria`, and any text field in the JSON.

        ### OUTPUT LANGUAGE
        **STRICTLY OUTPUT THE CONTENT IN {language}.**

        ### OUTPUT JSON SCHEMA (STRICT FOLLOW)
        {{
          "exam_title": "Exam Name",
          "total_points": 100,
          "questions": [
            {{
              "id": "1",
              "points": 15,
              "description": "Calculate the limit: $\\lim_{{x \\to 0}} \\frac{{\\sin x}}{{x}}$...",
              "sub_questions": [
                {{
                    "id": "1-1", 
                    "points": 5, 
                    "description": "Evaluate limit",
                    "rubric": [
                        {{ "rule_id":"1-1.S1","title":"方法辨識","points": 2, "criterion": "正確辨識方法。需出現：$...$。", "check": {{"engine":"sympy","type":"derivative","var":"x","expr":"log(x)","expected":"1/x","policy":{{"all_or_nothing":true,"partial_credit_max":1}}}} }},
                        {{ "points": 2, "criterion": "Derivative calculation: $\\cos x$" }},
                        {{ "points": 1, "criterion": " $1$" }}
                    ]
                }}
              ]
            }}
          ]
        }}
        """).replace("{language}", language)      
        
        target_model = model_name if "pro" in model_name else "gemini-2.5-pro"
        
        resp = client.models.generate_content(
            model=target_model, 
            contents=[types.Content(role="user", parts=[
                types.Part.from_uri(file_uri=file_ref.uri, mime_type=file_ref.mime_type),
                types.Part.from_text(text=prompt)
            ])]
        )
        
        clean_text = _clean_json_response(resp.text)
        try:
            rubric_json = json.loads(clean_text)
            rubric_json = _validate_and_fix_math(rubric_json)
            rubric_json = _infer_sympy_checks(rubric_json, subject=subject)
            return json.dumps(rubric_json, ensure_ascii=False, indent=2)
        except json.JSONDecodeError as je:
            logger.error(f"JSON Parse Error. Raw text: {resp.text[:500]}...") 
            return ""

    except Exception as e:
        logger.error(f"Rubric Gen Error: {e}")
        return "" 

def generate_class_analysis(grading_results, rubric_text, api_key, report_mode="simple", language="Traditional Chinese") -> str:
    """
    班級分析報告 - 強制 LaTeX 格式
    """
    try:
        real_key = _get_valid_api_key(api_key)
        client = genai.Client(api_key=real_key)
        
        data_summary = []
        for r in grading_results:
            mistakes = []
            questions = r.get("questions", [])
            if not questions and "ai_data" in r:
                questions = r["ai_data"].get("questions", [])
                
            for q in questions:
                try:
                    score = float(q.get("score", 0))
                    if q.get("reasoning") and (score == 0 or "error" in str(q.get("error_type", "")).lower()):
                        mistakes.append(f"{q.get('id')}: {q.get('reasoning')}")
                except: pass
            
            if mistakes: 
                data_summary.append({"id": r.get("Student ID"), "mistakes": mistakes})
        
        data_str = json.dumps(data_summary[:30], ensure_ascii=False) 

        # [STRICT FORMAT]
        prompt = f"""
        Act as a **Distinguished Professor**. Generate a Class Analysis Report based on the grading data.
        
        [INPUT DATA]
        1. **Rubric**: {rubric_text[:1500]}...
        2. **Student Errors**: {data_str}
        
        [OUTPUT LANGUAGE]
        **WRITE THE ENTIRE REPORT IN {language}.**
        
        [LATEX FORMATTING - STRICT]
        1. **MANDATORY**: You MUST use single `$` for inline math (e.g., $f(x)$) and double `$$` for block math.
        2. **SYNTAX**: Use standard LaTeX syntax (e.g., `\\frac`, `\\int`, `\\sum`, `_` for subscript).
        3. **NO PLAIN TEXT MATH**: Do not write "x^2", always write $x^2$.
        
        [OUTPUT FORMAT - Markdown]
        # Class Analysis Report (班級成績分析)
        ## 1. Overview (整體表現總評)
        ## 2. Common Mistakes & Misconceptions (觀念迷思與常見錯誤)
           - Use LaTeX for formulas.
        ## 3. Strengths (學生亮點)
        ## 4. Remedial Strategy (教學改進建議)
        """
        
        logger.info(f"Generating Analysis using gemini-2.5-flash")
        
        resp = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=[prompt]
        )
        
        return resp.text

    except Exception as e:
        logger.error(f"Class Analysis Gen Error: {e}")
        return f"Analysis Failed: {e}"

