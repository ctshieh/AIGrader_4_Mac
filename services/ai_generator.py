# services/ai_generator.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.26-Timeout-Unit-Fix
# Description: 
# 1. [CRITICAL FIX] 修正 Timeout 單位錯誤。Google SDK 使用毫秒 (ms)，原設定 60 被視為 0.06秒導致秒斷。
#    現改為 60000 (60秒)。
# 2. [Logic] 保持文字/PDF 通用處理邏輯。

import json
import logging
from io import BytesIO

# [DEPENDENCY CHECK]
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    import pypdf
except ImportError:
    pypdf = None

def extract_text_from_pdf(pdf_bytes):
    """
    從 PDF 二進位資料中提取文字
    """
    if not pypdf:
        return "Error: pypdf module not found. Please pip install pypdf."
    
    try:
        reader = pypdf.PdfReader(BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
        return text if text else "[PDF Content Empty or Scanned Image]"
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

def generate_questions_from_material(api_key, material_text, config):
    """
    呼叫 Gemini 2.5 API 生成題目 (含防卡死機制)
    """
    if not HAS_GENAI:
        return {
            "success": False, 
            "error": "Critical: 'google-genai' SDK not found. Please run `pip install google-genai`"
        }

    try:
        # 1. 初始化 Client (關鍵修復：Timeout 單位修正)
        # ⚠️ 注意：SDK 的 timeout 單位是「毫秒」(ms)
        # 60000 ms = 60 秒
        client = genai.Client(
            api_key=api_key, 
            http_options={'timeout': 60000} 
        )
        
        # 2. 參數配置
        q_type = config.get("q_type", "Mixed")
        count = config.get("count", 5)
        diff = config.get("difficulty", "Medium")
        focus = config.get("focus_topic", "")
        # 確保有預設語言，避免 None
        target_lang = config.get("language", "Traditional Chinese (繁體中文)")
        score = config.get("score_per_q", 10)
        
        # 3. 構建 Prompt
        prompt = f"""
        Role: You are a strict academic exam creator for STEM subjects.
        Task: Based on the provided [Source Material], create {count} questions of '{diff}' difficulty.
        
        [Source Material]:
        {material_text[:15000]} ... (Truncated if too long)
        
        [Focus Topic]:
        {focus}

        [Output Language Requirement]:
        **CRITICAL**: Regardless of the source material's language, you MUST generate the Questions, Options, and Solutions in **{target_lang}**.
        Ensure the terminology fits the local academic context of **{target_lang}**.

        [Question Type]:
        {q_type}

        [Format Requirement (Strict JSON)]:
        Return ONLY a JSON Array. No Markdown blocks.
        Format Example:
        [
            {{
                "text": "Question text here (Use LaTeX for math: $x^2$)",
                "options": ["Option A", "Option B", "Option C", "Option D"] (or null if not applicable),
                "answer": "Correct Answer",
                "solution": "Step-by-step explanation in {target_lang}...",
                "type": "{q_type}",
                "score": {score}
            }}
        ]
        """

        # 4. 設定模型
        model_id = "gemini-2.5-flash" 

        # 5. 發送請求
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,
                max_output_tokens=8192 
            )
        )

        # 6. 解析回傳資料
        raw_content = response.text
        
        # 移除可能的 Markdown 標記
        if raw_content.startswith("```json"):
            raw_content = raw_content.replace("```json", "").replace("```", "")
        
        try:
            questions = json.loads(raw_content)
        except json.JSONDecodeError:
            return {"success": False, "error": "AI 回傳了無效的 JSON 格式，請重試。"}
        
        # 容錯處理：如果模型回傳了 {"questions": [...]} 結構
        if isinstance(questions, dict):
            for key, val in questions.items():
                if isinstance(val, list):
                    questions = val
                    break
            
        if not isinstance(questions, list):
            if isinstance(questions, dict) and "text" in questions:
                questions = [questions]
            else:
                return {"success": False, "error": "AI response format error (List expected)"}

        return {
            "success": True,
            "data": questions
        }

    except Exception as e:
        err_msg = str(e)
        # 捕捉 Timeout 錯誤並提供友善提示
        if "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
            return {
                "success": False,
                "error": "⏳ AI 回應逾時 (Timeout)。這通常是網路連線不穩或 Google API 暫時壅塞，請稍後再試。"
            }
            
        if "404" in err_msg or "Not Found" in err_msg:
            return {
                "success": False,
                "error": f"Model '{model_id}' not found. Please check API availability."
            }
            
        return {
            "success": False, 
            "error": f"AI Error: {err_msg}"
        }
