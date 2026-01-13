# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# This software is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.

# database/models.py
# -*- coding: utf-8 -*-
from typing import Optional
from datetime import datetime

class User:
    """使用者資料模型 (Data Object)"""
    def __init__(self, id: int, username: str, email: str, real_name: str, password_hash: str, is_approved: bool, is_admin: bool, school: str, department: str, google_api_key: Optional[str], openai_api_key: Optional[str], model_name: str, plan: str, timezone: str, created_at: datetime, last_login: Optional[datetime] = None):
        self.id = id
        self.username = username
        self.email = email
        self.real_name = real_name
        self.password_hash = password_hash
        self.is_approved = is_approved
        self.is_admin = is_admin
        self.school = school
        self.department = department
        # --- API Keys ---
        self.google_api_key = google_api_key  # Gemini Key
        self.openai_api_key = openai_api_key  # OpenAI Key
        # --- 設定 ---
        self.model_name = model_name
        self.plan = plan
        self.timezone = timezone
        self.created_at = created_at
        self.last_login = last_login

    @property
    def google_key(self):
        """兼容舊名或提供統一存取點"""
        return self.google_api_key
        
    @property
    def openai_key(self):
        """兼容舊名或提供統一存取點"""
        return self.openai_api_key

    def __repr__(self):
        return f"<User id={self.id}, username='{self.username}', name='{self.real_name}'>"
