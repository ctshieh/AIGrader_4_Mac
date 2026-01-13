# services/security.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.13-Final-License-Lock
# Description: 
# 1. 負責讀取硬體機器碼 (Windows UUID / Linux Machine-ID)。
# 2. 驗證 License Key 是否合法，並回傳授權等級 (personal / business)。

import hashlib
import os
import platform
import subprocess
import logging

logger = logging.getLogger(__name__)

# --- 核心加密鹽 (請務必保管好，這是產生 License 的金鑰) ---
# 注意：一旦編譯成 EXE，這個字串就會被藏在二進位檔中
RAW_SALT = "MathAIGrader_Enterprise_2026_CTSHIEH!730208"
SECRET_SALT = RAW_SALT.strip()

def _get_windows_uuid():
    """透過 WMIC 取得 Windows 主機板 UUID (最穩定的硬體特徵)"""
    try:
        cmd = 'wmic csproduct get uuid'
        uuid_str = subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip()
        return uuid_str.lower()
    except Exception as e:
        logger.error(f"Failed to get Windows UUID: {e}")
        return "unknown-windows-uuid"

def get_machine_id():
    """跨平台取得機器唯一識別碼"""
    system = platform.system()
    
    if system == "Windows":
        return _get_windows_uuid()
    elif system == "Linux":
        # Docker 或 Linux 環境通常讀取此檔案
        try:
            if os.path.exists("/etc/machine-id"):
                with open("/etc/machine-id", "r") as f: 
                    return f.read().strip().lower()
            # Fallback for some Linux distros
            if os.path.exists("/var/lib/dbus/machine-id"):
                with open("/var/lib/dbus/machine-id", "r") as f:
                    return f.read().strip().lower()
        except Exception:
            pass
        return "linux-generic-id"
    else:
        # macOS 或其他
        return "non-windows-system-id"

def verify_license_tier(license_path):
    """
    驗證授權檔並回傳 (is_valid, message, plan_name)
    
    Returns:
        tuple: (True/False, "Message", "personal"|"business"|None)
    """
    if not os.path.exists(license_path):
        return False, "License file not found.", None
        
    try:
        with open(license_path, "r") as f:
            stored_key = f.read().strip().upper()
    except Exception as e:
        return False, f"Read error: {str(e)}", None

    mid = get_machine_id()
    
    # [關鍵] 支援的方案列表 (必須與 services/plans.py 對應)
    # 系統會依序嘗試驗證，看這把 Key 是屬於哪個方案
    SUPPORTED_PLANS = ["personal", "business"]
    
    for plan in SUPPORTED_PLANS:
        # 雜湊公式：SHA512( MachineID | PLAN | SALT )
        # 這確保了 Key 只能在這台機器上用，且無法被竄改方案
        raw_payload = f"{mid}|{plan}|{SECRET_SALT}"
        calculated_key = hashlib.sha512(raw_payload.encode('utf-8')).hexdigest().upper()
        
        if calculated_key == stored_key:
            return True, "License Valid", plan
            
    return False, f"Invalid License for Machine ID: {mid}", None

def get_fingerprint_for_ui():
    """給 UI 顯示用的機器碼 (讓客戶複製給您產生 Key)"""
    return get_machine_id()
