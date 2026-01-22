# app.py
# -*- coding: utf-8 -*-
# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# Unified Entry Point (Shell) with Debug Mode

import streamlit as st
import sys
import os
import types
import traceback # 用於顯示詳細錯誤

# ==============================================================================
# 1. 環境路徑修復 (Critical for macOS App)
# ==============================================================================
def setup_environment():
    # 取得 App 根目錄 (相容開發環境與 PyInstaller _MEIPASS)
    bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    
    # 強制加入搜尋路徑，確保能找到 .so 檔與資源
    paths_to_add = [
        bundle_dir,
        os.path.join(bundle_dir, "ui"),
        os.path.join(bundle_dir, "utils"),
        os.path.join(bundle_dir, "services"),
        os.path.join(bundle_dir, "database"),
        os.path.join(bundle_dir, "Contents", "Frameworks") # Mac Frameworks
    ]
    
    for p in paths_to_add:
        if os.path.exists(p) and p not in sys.path:
            sys.path.insert(0, p)

    # 修復 Package Namespace (避免 database/utils 等模組在封裝後報錯)
    for pkg in ['database', 'utils', 'services', 'ui']:
        pkg_path = os.path.join(bundle_dir, pkg)
        if os.path.exists(pkg_path) and pkg not in sys.modules:
            mod = types.ModuleType(pkg)
            mod.__path__ = [pkg_path]
            sys.modules[pkg] = mod

# 執行環境設定
setup_environment()

# ==============================================================================
# 2. 啟動編譯核心
# ==============================================================================
def main():
    try:
        # 嘗試匯入編譯過的核心模組 (.so)
        # 在開發環境如果是 .py 也一樣能運作
        import app_core
        
        # 執行核心邏輯
        app_core.run_app_logic()
        
    except ImportError as e:
        st.error(f"❌ Critical Startup Error: Core module missing.")
        st.markdown(f"**Reason:** `{e}`")
        st.info("Check if 'app_core.so' exists in the app bundle.")
        st.stop()

    except Exception as e:
        # 【Debug 模式】顯示完整錯誤訊息
        st.error("❌ An unexpected error occurred.")
        
        st.subheader("🕵️ Debug Traceback (請截圖此處):")
        # 顯示漂亮的錯誤堆疊
        st.exception(e)
        
        st.subheader("📝 Raw Error Log:")
        # 顯示原始文字 Log
        st.code(traceback.format_exc(), language="python")

if __name__ == "__main__":
    main()
