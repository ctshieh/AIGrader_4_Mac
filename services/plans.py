# services/plans.py
# -*- coding: utf-8 -*-
# [Security Critical] 授權規則定義檔 (Compiled into EXE)

PLAN_LIMITS = {
    # ---------------------------------------------------------
    # 1. 個人版 (Personal) - 賣給個別老師
    # 特性：單機單人，"設定"頁面即後台
    # ---------------------------------------------------------
    "personal": {
        "name": "個人版 (Personal)",
        "grading_pages": 300,           # [修正] 提升至 300 頁/週
        "exam_gen": 30,                 # 每週出卷 30 份
        "max_workers": 4,               # 運算速度 (普通)
        "allow_register": False,        # 禁止註冊
        "show_admin": False,            # 不顯示 Admin
        "branding": False,              # 不可換 Logo
        "has_subscription": False       # 無訂閱功能
    },

    # ---------------------------------------------------------
    # 2. 機構版 (Business) - 賣給補習班/學校
    # 特性：買斷授權，可管理內部員工
    # ---------------------------------------------------------
    "business": {
        "name": "機構版 (Business)",
        "grading_pages": 5000,          # 每週 5000 頁 (多人共用)
        "exam_gen": 1000,               # 每週 1000 份
        "max_workers": 8,               # 運算速度 (快)
        "allow_register": True,         # 允許內部員工註冊
        "show_admin": True,             # 顯示 Admin 後台
        "branding": True,               # 允許換 Logo
        "has_subscription": False       # 無訂閱功能 (防止競業)
    }
}

def get_plan_config(plan_name: str):
    """取得方案設定，若找不到則預設為 personal"""
    return PLAN_LIMITS.get(plan_name, PLAN_LIMITS["personal"])