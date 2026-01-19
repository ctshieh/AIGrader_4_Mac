# services/ai_generator.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.22-Gemini-2.5-Native
# Description: 
# 適配 2026 年環境：
# 1. 使用 Google 官方新版 SDK 'google-genai'。
# 2. 模型升級為 'gemini-2.5-flash' (棄用已下架的 1.5/2.0)。
# 3. 強制 JSON Schema 輸出。

import json
import logging
from io import BytesIO

# [DEPENDENCY CHECK]
# Env Check: pip install google-genai pypdf
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
        return text if text else "[PDF 無法讀取文字，可能是掃描圖檔]"
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

def generate_questions_from_material(api_key, material_text, config):
    """
    呼叫 Gemini 2.5 API 生成題目
    """
    if not HAS_GENAI:
        return {
            "success": False, 
            "error": "Critical: 'google-genai' SDK not found. Please run `pip install google-genai`"
        }

    try:
        # 1. 初始化 Client (2026 Standard)
        client = genai.Client(api_key=api_key)
        
        # 2. 參數配置
        q_type = config.get("q_type", "混合題型")
        count = config.get("count", 5)
        diff = config.get("difficulty", "Medium")
        focus = config.get("focus_topic", "")
        score = config.get("score_per_q", 10)
        
        # 3. 構建 Prompt
        prompt = f"""
        角色：你是一位嚴謹的學科命題老師。
        任務：請根據[教材內容]，編寫 {count} 道 {diff} 程度的「{q_type}」。
        
        [教材內容]:
        {material_text[:15000]} ... (Truncated if too long)
        
        [出題重點]:
        {focus}

        [輸出格式 (Strict JSON)]:
        請直接回傳一個 JSON Array，不要包含 Markdown 標記。
        格式範例：
        [
            {{
                "text": "題目敘述 (數學公式用 LaTeX: $x^2$)",
                "options": ["A", "B", "C", "D"],
                "answer": "A",
                "solution": "解析...",
                "type": "{q_type}",
                "score": {score}
            }}
        ]
        """

        # 4. 設定模型與參數
        # [UPDATE 2026] 1.5/2.0 已過時，改用 gemini-2.5-flash
        model_id = "gemini-2.5-flash" 

        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,
                # 2026 年的模型通常支援較大的 context，可適度放寬 token 限制
                max_output_tokens=8192 
            )
        )

        # 5. 解析回傳資料
        raw_content = response.text
        
        # 雖然指定了 JSON MIME，但仍做基礎清理以防萬一
        if raw_content.startswith("```json"):
            raw_content = raw_content.replace("```json", "").replace("```", "")
        
        questions = json.loads(raw_content)
        
        # 容錯處理：如果模型回傳了 {"questions": [...]} 結構
        if isinstance(questions, dict):
            # 嘗試尋找可能是列表的 key
            for key, val in questions.items():
                if isinstance(val, list):
                    questions = val
                    break
            
        if not isinstance(questions, list):
            # 如果還是字典且找不到列表，可能是單題
            if isinstance(questions, dict) and "text" in questions:
                questions = [questions]
            else:
                return {"success": False, "error": "AI 回傳格式不符 (需為 JSON Array)"}

        return {
            "success": True,
            "data": questions
        }

    except Exception as e:
        # 錯誤捕捉：包含模型不存在的錯誤 (404 Not Found)
        err_msg = str(e)
        if "404" in err_msg or "Not Found" in err_msg:
            return {
                "success": False,
                "error": f"Model '{model_id}' not found. Please check API availability in 2026 region."
            }
        return {
            "success": False, 
            "error": f"AI Error: {err_msg}"
        }
