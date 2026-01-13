# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# This software is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.

# utils/helpers.py
# -*- coding: utf-8 -*-
# Module-Version: 1.0.0 (Robust PDF Splitting)

import io
import base64
import streamlit as st
from pypdf import PdfReader, PdfWriter

def display_pdf(file_input, width=None, height=800):
    """
    在 Streamlit 中顯示 PDF 預覽
    """
    # 處理 BytesIO 或 bytes
    if hasattr(file_input, "getvalue"):
        data = file_input.getvalue()
    else:
        data = file_input

    base64_pdf = base64.b64encode(data).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="{height}" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def split_pdf_by_pages(uploaded_file, pages_per_chunk: int):
    """
    將 PDF 切割為多個小檔案 (每個 chunk 代表一個學生)
    """
    try:
        # [CRITICAL FIX] 確保指標回到檔案開頭，防止讀取到空內容
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
            
        reader = PdfReader(uploaded_file)
        total_pages = len(reader.pages)
        chunks = []
        
        # 如果 PDF 總頁數小於設定的頁數，就當作一份
        if total_pages <= pages_per_chunk:
            # 重新讀取原始檔作為單一 chunk
            if hasattr(uploaded_file, "seek"): uploaded_file.seek(0)
            if hasattr(uploaded_file, "getvalue"): return [uploaded_file.getvalue()]
            return [uploaded_file.read()]

        # 開始切割
        for i in range(0, total_pages, pages_per_chunk):
            writer = PdfWriter()
            end_page = min(i + pages_per_chunk, total_pages)
            
            for page_num in range(i, end_page):
                writer.add_page(reader.pages[page_num])
            
            output_stream = io.BytesIO()
            writer.write(output_stream)
            output_stream.seek(0) # 寫入後重置指標
            chunks.append(output_stream.getvalue())
            
        return chunks

    except Exception as e:
        st.error(f"PDF Split Error: {e}")
        return []

def pdf_to_images(pdf_bytes):
    """
    將 PDF (bytes) 轉換為 PIL Image 列表 (用於 Vision Service)
    """
    try:
        from pdf2image import convert_from_bytes
        return convert_from_bytes(pdf_bytes)
    except Exception as e:
        # Fallback if pdf2image/poppler is not installed
        st.error(f"PDF to Image Error (Check poppler): {e}")
        return []
