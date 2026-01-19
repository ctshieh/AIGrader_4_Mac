# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# This software is proprietary and confidential.

# utils/helpers.py
# -*- coding: utf-8 -*-

import io
import os
import sys
import base64
import streamlit as st
from pypdf import PdfReader, PdfWriter

def get_resource_path(relative_path):
    """
    取得資源的絕對路徑，相容 PyInstaller 打包環境 (_MEIPASS) 與開發環境。
    """
    if hasattr(sys, '_MEIPASS'):
        # 打包後，檔案會被解壓到臨時目錄
        return os.path.join(sys._MEIPASS, relative_path)
    # 開發環境下指向專案根目錄
    return os.path.join(os.path.abspath("."), relative_path)

def display_pdf(file_input, width=None, height=800):
    """
    在 Streamlit 中顯示 PDF 預覽
    """
    if hasattr(file_input, "getvalue"):
        data = file_input.getvalue()
    else:
        data = file_input

    base64_pdf = base64.b64encode(data).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="{height}" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def split_pdf_by_pages(uploaded_file, pages_per_chunk: int):
    """
    將 PDF 切割為多個小檔案
    """
    try:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
            
        reader = PdfReader(uploaded_file)
        total_pages = len(reader.pages)
        chunks = []
        
        if total_pages <= pages_per_chunk:
            if hasattr(uploaded_file, "seek"): uploaded_file.seek(0)
            if hasattr(uploaded_file, "getvalue"): return [uploaded_file.getvalue()]
            return [uploaded_file.read()]

        for i in range(0, total_pages, pages_per_chunk):
            writer = PdfWriter()
            end_page = min(i + pages_per_chunk, total_pages)
            
            for page_num in range(i, end_page):
                writer.add_page(reader.pages[page_num])
            
            output_stream = io.BytesIO()
            writer.write(output_stream)
            output_stream.seek(0)
            chunks.append(output_stream.getvalue())
            
        return chunks
    except Exception as e:
        st.error(f"PDF Split Error: {e}")
        return []

def pdf_to_images(pdf_bytes):
    """
    將 PDF (bytes) 轉換為 PIL Image 列表。
    對應 GitHub Action 打包路徑：poppler_bin
    """
    try:
        from pdf2image import convert_from_bytes
        
        # 核心修正：動態取得 poppler 路徑
        # 在 build_mac.yml 中我們設定 --add-data "dist_bin:poppler_bin"
        poppler_path = get_resource_path("poppler_bin")
        
        # 檢查路徑是否存在 (開發環境與打包環境切換邏輯)
        if not os.path.exists(poppler_path):
            # 如果 poppler_bin 不存在，嘗試尋找本機的 bin_mac (開發時用)
            dev_poppler = os.path.join(os.path.abspath("."), "bin_mac")
            poppler_path = dev_poppler if os.path.exists(dev_poppler) else None

        return convert_from_bytes(
            pdf_bytes,
            poppler_path=poppler_path
        )
    except Exception as e:
        st.error(f"PDF to Image Error (Check poppler path): {e}")
        return []
