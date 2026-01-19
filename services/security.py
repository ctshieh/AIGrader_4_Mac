# services/security.py
# -*- coding: utf-8 -*-
# Module-Version: 19.7.0 (Strict Node-Locked Verification)

import os
import json
import hashlib
import platform
import subprocess
from datetime import datetime

# [CRITICAL] 商業機密 Salt (必須與 Keygen 一致)
RAW_SALT = "MathAIGrader_Enterprise_2026_CTSHIEH!730208"
SECRET_SALT = RAW_SALT.strip()

def get_machine_id():
    """
    取得 Mac 本機唯一硬體 UUID (統一轉小寫)
    """
    try:
        # 使用 ioreg 指令抓取最底層的 IOPlatformUUID
        cmd = "ioreg -d2 -c IOPlatformExpertDevice | awk -F\\\" '/IOPlatformUUID/{print $(NF-1)}'"
        output = subprocess.check_output(cmd, shell=True).decode().strip().lower()
        if output:
            return output
    except Exception:
        pass
    
    # Fallback: 使用 system_profiler
    try:
        cmd = "system_profiler SPHardwareDataType | grep 'Hardware UUID' | awk '{print $3}'"
        output = subprocess.check_output(cmd, shell=True).decode().strip().lower()
        if output:
            return output
    except:
        pass

    return "unknown-mac-uuid"

def get_fingerprint_for_ui():
    return get_machine_id()

def load_branding_title(base_dir=None):
    """讀取 branding.conf 中的標題"""
    if base_dir is None: base_dir = os.getcwd()
    
    # 優先找 App Support (Mac Native)
    try:
        from utils.paths import get_writable_path
        conf_path = get_writable_path("branding.conf")
    except ImportError:
        conf_path = os.path.join(base_dir, "branding.conf")
    
    if os.path.exists(conf_path):
        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                return json.load(f).get("title", "").strip()
        except: pass
    return None

def verify_license_tier(license_path):
    """
    嚴格驗證邏輯 (Strict Hash Check)
    不允許 Personal 版跨機器使用
    """
    # 1. 預設值
    default_title = "Math AI Grader Pro"
    current_mid = get_machine_id()
    
    # 嘗試讀取 branding.conf 的標題 (如果有的話)
    # 注意：Personal 版通常沒有 conf，所以會用 default_title
    base_dir = os.path.dirname(license_path)
    current_title = load_branding_title(base_dir) or default_title
    
    if not os.path.exists(license_path):
        return False, "License file missing", None, current_title

    # 2. 讀取 Key 檔案內容
    try:
        with open(license_path, "r") as f:
            stored_hash = f.read().strip().upper()
    except Exception:
        return False, "License file corrupt", None, current_title

    # 3. 暴力比對 (因為 Hash 不可逆，我們試算兩種可能的情況)
    # 我們假設 Keygen 產生時用了正確的 Title 和 UUID
    
    # --- 情況 A: 驗證 Personal 版 ---
    # 公式: SHA512( mid | personal | title | salt )
    raw_personal = f"{current_mid}|personal|{current_title}|{SECRET_SALT}"
    hash_personal = hashlib.sha512(raw_personal.encode('utf-8')).hexdigest().upper()
    
    if hash_personal == stored_hash:
        return True, "Valid", "personal", current_title

    # --- 情況 B: 驗證 Business 版 ---
    # 公式: SHA512( mid | business | title | salt )
    raw_business = f"{current_mid}|business|{current_title}|{SECRET_SALT}"
    hash_business = hashlib.sha512(raw_business.encode('utf-8')).hexdigest().upper()
    
    if hash_business == stored_hash:
        return True, "Valid", "business", current_title

    # --- 驗證失敗 ---
    # 通常是因為 UUID 不對 (換了電腦)，或是 Title 不對
    return False, f"License Invalid (Hardware Mismatch). Machine ID: {current_mid}", None, current_title
