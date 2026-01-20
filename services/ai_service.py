# services/ai_service.py
# -*- coding: utf-8 -*-
import logging
import json
import re
from google import genai
from google.genai import types
from services.rubric_service import RubricService # [CRITICAL] 必須引用

logger = logging.getLogger(__name__)


######
def generate_rubric(pdf_path: str, model_name: str, api_key: str, subject: str, language: str, granularity: str = "標準") -> dict:
    """
    [FIXED] 
    1. 支援 granularity 參數，避免 dashboard_view 報錯。
    2. 呼叫 RubricService，確保「定積分」與「Description」規則生效。
    3. 自動封裝 JSON 格式。
    """
    try:
        # 1. 驗證 API Key
        if not api_key: raise ValueError("Missing API Key")
        client = genai.Client(api_key=api_key)
        
        # 2. [關鍵] 從 RubricService 取得最新的 Prompt (包含積分規則)
        system_instr = RubricService.get_rubric_generation_prompt(
            subject_key=subject, 
            granularity=granularity, 
            language=language
        )
        
        # 3. 讀取檔案
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # 4. 發送請求
        # [提示] 我們在 user prompt 裡再次強調 JSON 格式，雙重保險
        user_prompt = "Generate the grading rubric JSON. Ensure 'description' fields are filled and LaTeX math is correct."
        
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                user_prompt
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_instr,
                response_mime_type="application/json"
            )
        )

        # 5. 解析回傳資料 (雙重解析機制)
        final_data = None
        if response.parsed:
            final_data = response.parsed
        else:
            # 手動清洗 Markdown
            raw_text = response.text
            cleaned_text = re.sub(r"```json\s*", "", raw_text, flags=re.IGNORECASE)
            cleaned_text = re.sub(r"```\s*$", "", cleaned_text, flags=re.IGNORECASE).strip()
            try:
                final_data = json.loads(cleaned_text)
            except:
                pass

        # 6. 結構封裝 (防止前端因為 List 報錯)
        if isinstance(final_data, list):
            final_data = {"questions": final_data}
            
        return final_data

    except Exception as e:
        logger.error(f"Rubric Gen Error: {e}")
        return None


######


# [FIX] 這裡加上 granularity 的預設值，防止舊代碼呼叫時報錯
def generate_rubric1(pdf_path, model_name, api_key, subject, language, granularity="標準"):
    """
    產生評分標準 JSON。
    """
    try:
        client = genai.Client(api_key=api_key)
        
        # 1. 呼叫 RubricService (確保 logic 變數正確)
        system_instr = RubricService.get_rubric_generation_prompt(
            subject_key=subject, 
            granularity=granularity, 
            language=language
        )
        
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        print(f"🚀 [AI Service] Generating Rubric for {subject}...")

        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                "Please design the grading rubric JSON based on the exam."
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_instr,
                response_mime_type="application/json"
            )
        )

        # 2. 雙重解析機制 (SDK -> Manual)
        final_data = None
        if response.parsed:
            final_data = response.parsed
        else:
            # 手動清洗 Markdown
            raw_text = response.text
            # [FIX] 使用 raw string 避免 SyntaxWarning
            cleaned_text = re.sub(r"```json\s*", "", raw_text, flags=re.IGNORECASE)
            cleaned_text = re.sub(r"```\s*$", "", cleaned_text, flags=re.IGNORECASE)
            cleaned_text = cleaned_text.strip()
            try:
                final_data = json.loads(cleaned_text)
            except json.JSONDecodeError:
                print(f"❌ JSON Decode Error. Raw: {cleaned_text[:100]}")
                return None

        # 3. [CRITICAL] 結構封裝：確保回傳的是 Dict 且包含 "questions"
        # 這是為了解決 dashboard_view.py 報錯的問題
        if isinstance(final_data, list):
            print("🔧 Detected List format. Wrapping in {'questions': ...}")
            final_data = {"questions": final_data}
        
        return final_data

    except Exception as e:
        logger.error(f"Rubric Gen Error: {str(e)}")
        return None

#####
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

######

# --- Main Function ---

def generate_rubric(pdf_path, model_name, api_key, subject, language, granularity="標準"):
    """
    產生評分標準 JSON。
    [RESTORED] 整合 RubricService 的 Prompt 與舊版的後處理邏輯。
    """
    try:
        client = genai.Client(api_key=api_key)
        
        # 1. 取得完整 Prompt (包含舊版詳細 Schema)
        system_instr = RubricService.get_rubric_generation_prompt(
            subject_key=subject, 
            granularity=granularity, 
            language=language
        )
        
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # 2. 發送請求
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                "Please generate the rubric following the JSON schema strictly."
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_instr,
                response_mime_type="application/json"
            )
        )

        # 3. [CRITICAL] 執行完整的後處理流程 (Restore Pipeline)
        clean_text = _clean_json_response(response.text)
        
        try:
            rubric_json = json.loads(clean_text)
            
            # (A) 修正分數加總
            rubric_json = _validate_and_fix_math(rubric_json)
            
            # (B) 推斷 SymPy 檢查 (如果 AI 漏掉)
            rubric_json = _infer_sympy_checks(rubric_json, subject=subject)
            
            # (C) 確保回傳格式正確 (Dict wrapper)
            if isinstance(rubric_json, list):
                rubric_json = {"questions": rubric_json}
                
            return rubric_json # 直接回傳 Dict，讓 UI 轉 JSON string
            
        except json.JSONDecodeError as je:
            logger.error(f"JSON Parse Error. Raw: {clean_text[:100]}...")
            return None

    except Exception as e:
        logger.error(f"Rubric Gen Error: {str(e)}")
        return None



#####

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


