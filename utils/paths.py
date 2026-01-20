# utils/paths.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.23-Cross-Platform
# Description: 全平台路徑管理 (Mac/Win/Linux)，解決打包後的寫入權限問題。

import sys
import os
import platform

# 定義 App 名稱 (用於建立專屬資料夾)
APP_NAME = "MathGraderPro"

def get_base_path():
    """
    [內部使用] 取得程式執行的基礎路徑
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包後
        return sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
    else:
        # 開發模式：專案根目錄 (假設 utils 在根目錄下一層)
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_resource_path(relative_path):
    """
    [唯讀區] 取得 App 內建靜態資源 (如預設 Logo, 字型)
    """
    base_path = get_base_path()
    return os.path.join(base_path, relative_path)

def get_writable_path(filename):
    """
    [寫入區] 取得使用者資料儲存路徑 (License, DB, Logs)
    會自動根據 OS 選擇正確的 AppData/Library 目錄，並確保資料夾存在。
    """
    system = platform.system()
    is_frozen = getattr(sys, 'frozen', False)
    
    user_data_dir = ""

    if is_frozen:
        # --- 打包環境 (Production) ---
        if system == "Darwin":
            # macOS: ~/Library/Application Support/MathGraderPro
            user_data_dir = os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
            
        elif system == "Windows":
            # Windows: C:\Users\<User>\AppData\Roaming\MathGraderPro
            # 使用環境變數 APPDATA 確保路徑正確
            app_data = os.getenv('APPDATA')
            if app_data:
                user_data_dir = os.path.join(app_data, APP_NAME)
            else:
                # Fallback: 如果抓不到 APPDATA，存在 User Home
                user_data_dir = os.path.expanduser(f"~/.{APP_NAME}")
                
        else:
            # Linux/Unix: ~/.local/share/MathGraderPro (XDG Standard)
            user_data_dir = os.path.expanduser(f"~/.local/share/{APP_NAME}")
            
    else:
        # --- 開發環境 (Development) ---
        # 直接存放在專案根目錄，方便開發時查看 DB 和 Log
        user_data_dir = get_base_path()

    # 確保資料夾存在 (如果是第一次執行)
    if not os.path.exists(user_data_dir):
        try:
            os.makedirs(user_data_dir, exist_ok=True)
        except Exception as e:
            print(f"Error creating directory {user_data_dir}: {e}")
            # 極端情況 fallback 到暫存區
            return filename

    return os.path.join(user_data_dir, filename)
