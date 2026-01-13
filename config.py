# config.py
# -*- coding: utf-8 -*-
import os
import logging

# --- 路徑配置 (Windows/Local 相容) ---
# 優先讀取環境變數，否則使用當前目錄下的 data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))

# 定義子目錄
EXAM_DIR = os.path.join(DATA_DIR, "exams")      
SPLITS_DIR = os.path.join(DATA_DIR, "splits")  
HISTORY_DIR = os.path.join(DATA_DIR, "history_data") 
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DRAFT_DIR = os.path.join(DATA_DIR, "drafts")

# 確保目錄存在
for d in [DATA_DIR, UPLOAD_DIR, DRAFT_DIR, EXAM_DIR, SPLITS_DIR, HISTORY_DIR]:
    os.makedirs(d, exist_ok=True)

# 機構名稱
INSTITUTION_NAME = os.getenv("INSTITUTION_NAME", "AI 之星高校 (Local)")

# --- AI 成本配置 ---
COSTS = {
    "pro_in": 1.25,
    "pro_out": 5.00,
    "flash_in": 0.075,
    "flash_out": 0.30,
}

EXCHANGE_RATE_TWD = 32.5

# --- 應用程式通用配置 ---
DEFAULT_MAX_WORKERS = 4          # Windows 本地建議設低一點
DEFAULT_RETENTION_DAYS = 180

# 根據方案決定批改速度
PLAN_MAX_WORKERS = {
    "free": 1,
    "pro": 4,
    "premium": 6,
    "enterprise": 8
}

# [NEW] 方案預設配額
PLAN_LIMITS = {
    "free": {"grading_pages": 70, "exam_gen": 10},
    "pro": {"grading_pages": 500, "exam_gen": 50},
    "premium": {"grading_pages": 1000, "exam_gen": 100},
    "enterprise": {"grading_pages": 2000, "exam_gen": 9999}
}

# --- SMTP Email ---
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "your_email@gmail.com")
SMTP_PASS = os.getenv("SMTP_PASS", "your_app_password")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
RESET_TOKEN_EXPIRE_MINUTES = 10
RESET_COOLDOWN_SECONDS = 60

# --- 日誌配置 ---
LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_DIR, "logs"))
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "system.log"), encoding="utf-8")
    ]
)
