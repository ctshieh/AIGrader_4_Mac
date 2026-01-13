# services/pdf_service.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.13-PyMuPDF-Windows-Ready
# Description: 
# 1. [Critical] Replaced pdf2image with PyMuPDF (fitz) to fix Windows EXE "Poppler not found" error.
# 2. [Feature] Added split_pdf logic for large exams.

import base64
import os
import logging
import numpy as np
import fitz  # PyMuPDF
from typing import Optional, List

logger = logging.getLogger(__name__)

class PDFService:
    """
    提供 PDF 檔案處理、轉圖、顯示邏輯的靜態服務類別。
    使用 PyMuPDF (fitz) 以確保 Windows/Linux 跨平台相容性。
    """

    @staticmethod
    def save_uploaded_file(uploaded_file, save_dir: str = "uploaded_files") -> Optional[str]:
        """儲存上傳的檔案"""
        if uploaded_file is None: return None
        try:
            os.makedirs(save_dir, exist_ok=True)
            file_path = os.path.join(save_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            return file_path
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            return None

    @staticmethod
    def get_pdf_display_html(file_path: str, width: str = "100%", height: int = 800) -> Optional[str]:
        """生成 PDF 預覽 HTML (Base64 Embedding)"""
        if not file_path or not os.path.exists(file_path):
            return PDFService._render_error(f"檔案不存在: {file_path}")
        try:
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            return f"""
                <iframe src="data:application/pdf;base64,{b64}" 
                    width="{width}" height="{height}px" type="application/pdf"
                    style="border: 1px solid #ccc; border-radius: 4px;">
                </iframe>
            """
        except Exception as e:
            return PDFService._render_error(str(e))

    # ==========================================================================
    # 🔥 核心功能：PDF 轉圖片 (PyMuPDF / fitz)
    # ==========================================================================
    @staticmethod
    def convert_to_cv2_images(pdf_path: str, zoom: float = 2.0) -> List[np.ndarray]:
        """
        將 PDF 的每一頁轉換為 OpenCV 格式的圖片 (numpy array)。
        Args:
            pdf_path: PDF 檔案路徑
            zoom: 縮放倍率 (2.0 約等於 144 DPI，適合 AI 辨識)
        """
        images = []
        try:
            doc = fitz.open(pdf_path)
            mat = fitz.Matrix(zoom, zoom)
            
            for page in doc:
                pix = page.get_pixmap(matrix=mat)
                
                # 將 PyMuPDF 的 pixmap 轉換為 numpy array (RGB)
                img_data = np.frombuffer(pix.samples, dtype=np.uint8)
                img_array = img_data.reshape(pix.h, pix.w, pix.n)
                
                # 轉為 OpenCV 需要的 BGR 格式
                if pix.n >= 3:
                    img_bgr = img_array[..., ::-1].copy() if pix.n == 3 else img_array[..., 2::-1].copy()
                    images.append(img_bgr)
                else:
                    images.append(img_array) # 灰階
                    
            doc.close()
            return images
            
        except Exception as e:
            logger.error(f"PDF 轉圖片失敗: {e}")
            return []

    # ==========================================================================
    # 🔥 核心功能：PDF 分割 (用於考卷切割)
    # ==========================================================================
    @staticmethod
    def split_pdf(pdf_path: str, output_dir: str, pages_per_chunk: int = 1) -> List[str]:
        """將 PDF 分割成多個小檔案"""
        generated_files = []
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            os.makedirs(output_dir, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]

            for i in range(0, total_pages, pages_per_chunk):
                new_doc = fitz.open()
                end_page = min(i + pages_per_chunk, total_pages)
                new_doc.insert_pdf(doc, from_page=i, to_page=end_page - 1)
                
                chunk_filename = f"{base_name}_part_{i//pages_per_chunk + 1:03d}.pdf"
                save_path = os.path.join(output_dir, chunk_filename)
                new_doc.save(save_path)
                new_doc.close()
                generated_files.append(save_path)
                
            doc.close()
            return generated_files
            
        except Exception as e:
            logger.error(f"PDF 分割失敗: {e}")
            return []

    @staticmethod
    def _render_error(message: str) -> str:
        return f'<div style="color:red; padding:10px;">⚠️ PDF Error: {message}</div>'

# Alias for backward compatibility
save_uploaded_file = PDFService.save_uploaded_file
get_pdf_display_html = PDFService.get_pdf_display_html
convert_to_cv2_images = PDFService.convert_to_cv2_images
split_pdf = PDFService.split_pdf