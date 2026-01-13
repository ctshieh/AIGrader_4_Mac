# services/security.py
import hashlib
import os
import platform
import subprocess
import json

RAW_SALT = "MathAIGrader_Enterprise_2026_CTSHIEH!730208"
SECRET_SALT = RAW_SALT.strip()

def _get_windows_uuid():
    try:
        cmd = 'wmic csproduct get uuid'
        return subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip().lower()
    except: return "unknown-win-uuid"

def get_machine_id():
    system = platform.system()
    if system == "Windows": return _get_windows_uuid()
    # 保留 Linux 邏輯以備不時之需
    if os.path.exists("/etc/machine-id"):
        with open("/etc/machine-id") as f: return f.read().strip().lower()
    return "generic-id"

def get_fingerprint_for_ui():
    return get_machine_id()

def load_branding_title(base_dir=None):
    if base_dir is None: base_dir = os.getcwd()
    conf_path = os.path.join(base_dir, "branding.conf")
    if os.path.exists(conf_path):
        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                return json.load(f).get("title", "").strip()
        except: pass
    return None

def verify_license_tier(license_path):
    """回傳: (is_valid, message, plan, title)"""
    default_title = "Math Grader Pro"
    
    # 讀取 Title
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
    
    # 嘗試驗證 Personal 和 Business
    for plan in ["personal", "business"]:
        # 驗證邏輯：MachineID + Plan + Title + Salt
        raw = f"{mid}|{plan}|{current_title}|{SECRET_SALT}"
        calc_key = hashlib.sha512(raw.encode('utf-8')).hexdigest().upper()
        
        if calc_key == stored_key:
            return True, "Valid", plan, current_title
            
    return False, "Invalid License or Branding Mismatch", None, default_title
