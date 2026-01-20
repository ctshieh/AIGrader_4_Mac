# config.py
# -*- coding: utf-8 -*-
# Module-Version: 19.4.0 (Mac Native: Application Support Integration)

import os
import logging
from utils.paths import get_writable_path, get_resource_path

# ==============================================================================
# 1. 路徑配置 (Mac Native Architecture)
# ==============================================================================
# [CRITICAL] Mac App 必須寫入 User Home 下的 Application Support，不能寫入 App Bundle
DATA_DIR = get_writable_path("data")

# 定義子目錄 (全部位於可寫入區)
EXAM_DIR = os.path.join(DATA_DIR, "exams")      
SPLITS_DIR = os.path.join(DATA_DIR, "splits")  
HISTORY_DIR = os.path.join(DATA_DIR, "history_data") 
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DRAFT_DIR = os.path.join(DATA_DIR, "drafts")

# 確保目錄存在
for d in [DATA_DIR, UPLOAD_DIR, DRAFT_DIR, EXAM_DIR, SPLITS_DIR, HISTORY_DIR]:
    try:
        os.makedirs(d, exist_ok=True)
    except Exception as e:
        # 這裡用 print 因為 logging 可能還沒設好
        print(f"❌ Failed to create directory {d}: {e}")

# 機構名稱
INSTITUTION_NAME = os.getenv("INSTITUTION_NAME", "AI Grader Pro (Mac)")

# ==============================================================================
# 2. 應用程式參數
# ==============================================================================
# --- AI 成本配置 ---
COSTS = {
    "pro_in": 1.25,
    "pro_out": 5.00,
    "flash_in": 0.075,
    "flash_out": 0.30,
}

EXCHANGE_RATE_TWD = 32.5

# --- 效能配置 (Mac Silicon 優化) ---
# M1/M2/M3 晶片效能強大，可以允許較高的並發
DEFAULT_MAX_WORKERS = 10          
DEFAULT_RETENTION_DAYS = 180

# 根據方案決定批改速度
PLAN_MAX_WORKERS = {
    "personal": 5, # Mac 個人版
    "free": 1,
    "pro": 5,
    "business": 8
}

# 方案預設配額
PLAN_LIMITS = {
    "free": {"grading_pages": 70, "exam_gen": 10},
    "personal": {"grading_pages": 300, "exam_gen": 30}, # Mac 單機版通常不限額
    "pro": {"grading_pages": 500, "exam_gen": 50},
    "business": {"grading_pages": 2000, "exam_gen": 9999}
}

# ==============================================================================
# 3. 系統服務
# ==============================================================================
# --- SMTP Email (保留但不一定用得到) ---
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
RESET_TOKEN_EXPIRE_MINUTES = 10
RESET_COOLDOWN_SECONDS = 60

# --- 日誌配置 (寫入 Application Support/logs) ---
# 注意：app.py 已經有設定 logging，這裡作為備用或模組級設定
LOG_DIR = get_writable_path("logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 這裡不呼叫 basicConfig 以免覆蓋 app.py 的設定
# 僅定義 Logger 名稱
logger = logging.getLogger("SystemConfig")
