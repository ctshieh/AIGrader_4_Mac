# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# This software is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.

"""
Module: PDF Service
Version: 9.1.0
Description: 負責處理 PDF 檔案的儲存、讀取、Base64 編碼以及生成 Streamlit 顯示用的 HTML iframe。
"""

import base64
import os
import logging
import shutil
from typing import Optional
from pathlib import Path

# 設定模組層級的 Logger
logger = logging.getLogger(__name__)

class PDFService:
    """
    提供 PDF 檔案處理與顯示邏輯的靜態服務類別。
    """

    @staticmethod
    def save_uploaded_file(uploaded_file, save_dir: str = "uploaded_files") -> Optional[str]:
        """
        將 Streamlit 上傳的檔案物件儲存到指定目錄。

        Args:
            uploaded_file: Streamlit 的 UploadedFile 物件。
            save_dir (str): 儲存的目標資料夾路徑。

        Returns:
            Optional[str]: 成功儲存後的檔案絕對路徑，失敗回傳 None。
        """
        if uploaded_file is None:
            return None

        try:
            # 確保目錄存在
            os.makedirs(save_dir, exist_ok=True)
            
            # 組合完整路徑
            file_path = os.path.join(save_dir, uploaded_file.name)
            
            # 寫入檔案
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            logger.info(f"File saved successfully at: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to save file {uploaded_file.name}: {e}")
            return None

    @staticmethod
    def get_pdf_display_html(file_path: str, width: str = "100%", height: int = 800) -> Optional[str]:
        """
        讀取 PDF 並轉換為嵌入式 HTML 字串 (Iframe)。

        Args:
            file_path (str): PDF 檔案的路徑。
            width (str): 顯示寬度 (預設 "100%")。
            height (int): 顯示高度 (預設 800px)。

        Returns:
            Optional[str]: 成功時回傳 HTML 字串，失敗時回傳 None 或錯誤提示 HTML。
        """
        if not file_path:
            logger.error("PDF path is empty.")
            return PDFService._render_error("檔案路徑為空")

        if not os.path.exists(file_path):
            logger.error(f"PDF file not found: {file_path}")
            return PDFService._render_error(f"找不到檔案: {os.path.basename(file_path)}")

        try:
            with open(file_path, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode('utf-8')

            # 建構 HTML
            pdf_display = f"""
                <iframe 
                    src="data:application/pdf;base64,{base64_pdf}" 
                    width="{width}" 
                    height="{height}px" 
                    type="application/pdf"
                    style="border: 1px solid #ccc; border-radius: 4px;">
                </iframe>
            """
            return pdf_display

        except Exception as e:
            logger.error(f"Error reading PDF file {file_path}: {str(e)}")
            return PDFService._render_error(f"讀取 PDF 失敗: {str(e)}")

    @staticmethod
    def _render_error(message: str) -> str:
        """
        內部私有方法：統一錯誤訊息的 HTML 樣式。
        """
        return f"""
        <div style="
            padding: 1rem;
            background-color: #ffebee;
            color: #c62828;
            border: 1px solid #ef9a9a;
            border-radius: 4px;
            font-family: monospace;
            margin-top: 10px;">
            ⚠️ <strong>PDF Error:</strong> {message}
        </div>
        """

# --- 為了相容舊程式碼的 Alias ---
# 這樣做可以讓 `from services.pdf_service import save_uploaded_file` 正常運作
save_uploaded_file = PDFService.save_uploaded_file
get_pdf_display_html = PDFService.get_pdf_display_html
