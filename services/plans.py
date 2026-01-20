# services/plans.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.23-Feature-Flag-Ready
# Description: 修正 get_plan_config 以支援 features 參數，解決 TypeError。

PLAN_LIMITS = {
    "free": {
        "name": "試用版 (Free)",
        "grading_pages": 10,
        "exam_gen_quota": 3,
        "ai_gen_enabled": False,
        "ai_gen_batch_limit": 0,
        "branding_enabled": False,
        "show_admin": False
    },
    "personal": {
        "name": "個人版 (Personal)",
        "grading_pages": 300,
        "exam_gen_quota": 30,
        "ai_gen_enabled": True,
        "ai_gen_batch_limit": 10,
        "branding_enabled": False,
        "show_admin": False
    },
    "business": {
        "name": "機構版 (Business)",
        "grading_pages": 5000,
        "exam_gen_quota": 1000,
        "ai_gen_enabled": True,
        "ai_gen_batch_limit": 20,
        "branding_enabled": True,
        "show_admin": True
    }
}

# [FIX] 增加 features 參數 (預設 None)
def get_plan_config(plan_name: str, features: list = None):
    """
    取得方案設定
    Args:
        plan_name: 方案名稱 (free/personal/business)
        features: License 功能列表 (用於判斷 superuser)
    """
    key = str(plan_name).lower()
    config = PLAN_LIMITS.get(key, PLAN_LIMITS["personal"]).copy()
    
    # 開發者上帝模式 (Superuser)
    if features and "superuser" in features:
        config["name"] = f"{config['name']} (Dev)"
        config["ai_gen_batch_limit"] = 100
        config["exam_gen_quota"] = 99999
        config["show_admin"] = True
        config["branding_enabled"] = True
        
    return config
