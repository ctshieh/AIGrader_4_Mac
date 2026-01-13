# services/security.py
# -*- coding: utf-8 -*-
import hashlib
import os
import platform
import subprocess
import json

# 請確保這個 SALT 與 keygen.py 內的一模一樣
RAW_SALT = "MathAIGrader_Enterprise_2026_CTSHIEH!730208"
SECRET_SALT = RAW_SALT.strip()

def _get_windows_uuid():
    try:
        # Windows: 使用 wmic 抓取主機板 UUID
        cmd = 'wmic csproduct get uuid'
        return subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip().lower()
    except:
        return "unknown-win-uuid"

def _get_mac_uuid():
    try:
        # [NEW] macOS: 使用 ioreg 抓取 IOPlatformUUID
        cmd = "ioreg -d2 -c IOPlatformExpertDevice | awk -F\\\" '/IOPlatformUUID/{print $(NF-1)}'"
        output = subprocess.check_output(cmd, shell=True).decode().strip().lower()
        if output:
            return output
        return "unknown-mac-uuid"
    except:
        return "unknown-mac-uuid"

def get_machine_id():
    """
    跨平台取得機器唯一碼 (Fingerprint)
    """
    system = platform.system()
    
    if system == "Windows":
        return _get_windows_uuid()
    elif system == "Darwin": # Darwin 代表 macOS
        return _get_mac_uuid()
    elif system == "Linux":
        # Linux 通常讀取 machine-id
        if os.path.exists("/etc/machine-id"):
            with open("/etc/machine-id") as f: return f.read().strip().lower()
        if os.path.exists("/var/lib/dbus/machine-id"):
            with open("/var/lib/dbus/machine-id") as f: return f.read().strip().lower()
            
    return "generic-unknown-id"

def get_fingerprint_for_ui():
    """UI 顯示用的申請代碼"""
    return get_machine_id()

def load_branding_title(base_dir=None):
    if base_dir is None: base_dir = os.getcwd()
    conf_path = os.path.join(base_dir, "branding.conf")
    # 同時檢查 App Support 目錄 (針對 Mac)
    if not os.path.exists(conf_path):
        from utils.paths import get_writable_path
        conf_path = get_writable_path("branding.conf")

    if os.path.exists(conf_path):
        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                return json.load(f).get("title", "").strip()
        except: pass
    return None

def verify_license_tier(license_path):
    """回傳: (is_valid, message, plan, title)"""
    default_title = "Math AI Grader Pro"
    
    # 讀取 Title (優先讀取 branding.conf)
    base_dir = os.path.dirname(license_path)
    current_title = load_branding_title(base_dir) or default_title
    
    if not os.path.exists(license_path):
        return False, "License file missing", None, current_title
        
    try:
        with open(license_path, "r") as f:
            stored_key = f.read().strip().upper()
    except Exception as e:
        return False, f"Read Error: {e}", None, current_title

    mid = get_machine_id()
    
    # 驗證 Personal 與 Business
    for plan in ["personal", "business"]:
        # 雜湊邏輯：MachineID + Plan + Title + Salt
        raw = f"{mid}|{plan}|{current_title}|{SECRET_SALT}"
        calc_key = hashlib.sha512(raw.encode('utf-8')).hexdigest().upper()
        
        if calc_key == stored_key:
            return True, "Valid", plan, current_title
            
    return False, f"Invalid License (MID: {mid})", None, default_title
