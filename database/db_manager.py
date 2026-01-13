# database/db_manager.py
# -*- coding: utf-8 -*-
# Module-Version: 19.3.0 (Mac Native + High Performance SQLite)

import os
import json
import logging
import shutil
import uuid
import datetime
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import bcrypt
import pandas as pd
import pytz

# [CRITICAL] 引入路徑管理模組 (Mac 必備)
from utils.paths import get_writable_path

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, desc, func, text, Date, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
import config
from services.plans import get_plan_config

logger = logging.getLogger(__name__)

# --- JSON Helper for Breakdown ---
def _as_float(x):
    try: return float(x) if x is not None else None
    except: return None

def _infer_score(d: dict):
    for k in ("score", "earned_points", "points_earned", "total"):
        if k in d: return _as_float(d.get(k))
    return None

def _infer_max_points(d: dict):
    for k in ("points", "max_points", "total_points"):
        if k in d: return _as_float(d.get(k))
    return None

def _ensure_breakdown_node(d: dict):
    if not isinstance(d, dict): return
    if "breakdown" in d and isinstance(d["breakdown"], list) and len(d["breakdown"]) > 0: return
    
    looks_gradable = any(k in d for k in ("score", "points", "max_points"))
    if not looks_gradable: return

    score = _infer_score(d)
    maxp = _infer_max_points(d)
    
    d["breakdown"] = [{
        "rule": "__AUTO__",
        "max_points": maxp if maxp is not None else 0.0,
        "score": score if score is not None else 0.0,
        "missing_work": True,
        "evidence": "",
        "comment": "系統自動補全 (Auto-filled)"
    }]

def ensure_breakdown_present(ai_output_json):
    if isinstance(ai_output_json, list):
        for x in ai_output_json: ensure_breakdown_present(x)
        return
    if not isinstance(ai_output_json, dict): return
    
    for k in ["questions", "sub_questions", "results"]:
        if k in ai_output_json and isinstance(ai_output_json[k], list):
            for item in ai_output_json[k]: ensure_breakdown_present(item)
    _ensure_breakdown_node(ai_output_json)

# ==============================================================================
#  1. SQLAlchemy Setup (Mac Native Path + High Perf Settings)
# ==============================================================================
# [Mac Fix] 使用 get_writable_path 確保資料庫存放在使用者可寫入的目錄
# Mac: ~/Library/Application Support/MathGraderPro/math_grader.db
DB_PATH = get_writable_path("math_grader.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# [High Performance] 保留您指定的高並發設定
engine = create_engine(
    DATABASE_URL,
    pool_size=20, 
    max_overflow=30, 
    pool_pre_ping=True, 
    pool_recycle=3600,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()

# ==============================================================================
#  2. Data Models
# ==============================================================================

@dataclass
class User:
    id: int
    username: str
    email: str = ""
    real_name: str = ""
    password_hash: str = ""
    is_approved: bool = False
    is_admin: bool = False
    school: str = ""
    department: str = ""
    google_key: str = ""      
    openai_key: str = ""
    model_name: str = "gemini-2.5-pro"
    plan: str = "personal" # Default
    timezone: str = "Asia/Taipei"
    custom_page_limit: int = 0
    custom_exam_limit: int = 0
    branding_logo_path: str = ""
    custom_advertising_url: str = ""
    current_period_end: Optional[datetime.datetime] = None

    @property
    def google_api_key(self) -> str: return self.google_key or ""
    @property
    def openai_api_key(self) -> str: return self.openai_key or ""

class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True)
    real_name = Column(String)
    password_hash = Column(String, nullable=False)
    is_approved = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    school = Column(String)
    department = Column(String)
    google_key = Column(String)
    openai_key = Column(String)
    model_name = Column(String, default='gemini-2.5-pro')
    plan = Column(String, default='personal')
    timezone = Column(String, default='Asia/Taipei')
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    ai_memory_rules = Column(JSON)
    custom_page_limit = Column(Integer, default=0)
    custom_exam_limit = Column(Integer, default=0)
    branding_logo_path = Column(Text)
    custom_advertising_url = Column(String)
    current_period_end = Column(DateTime)

class SessionModel(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ExamModel(Base): # Legacy
    __tablename__ = "exams"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    subject = Column(String)
    content_json = Column(JSON, nullable=False)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ExamDraft(Base):
    __tablename__ = "exam_drafts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exam_id = Column(String, unique=True, index=True)
    title = Column(String, default="Untitled")
    subject = Column(String, default="General")
    content = Column(Text) 
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    status = Column(String, default="draft")
    academic_year = Column(String)
    department = Column(String)
    grade_level = Column(String)
    final_pdf_path = Column(String)

class QuestionModel(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    question_no = Column(String)
    content = Column(Text)
    score = Column(Integer, default=0)
    solution = Column(Text)
    sub_questions = Column(JSON)
    tags = Column(String)
    is_public = Column(Boolean, default=True)
    meta = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class QuestionSetModel(Base):
    __tablename__ = "question_sets"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    title = Column(String, nullable=False)
    description = Column(Text)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class QuestionSetItemModel(Base):
    __tablename__ = "question_set_items"
    id = Column(Integer, primary_key=True)
    set_id = Column(Integer, ForeignKey("question_sets.id", ondelete="CASCADE"))
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"))
    item_order = Column(Integer)

class GradedExamModel(Base):
    __tablename__ = "graded_exams"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(String, index=True, nullable=False)
    student_id = Column(String)
    student_name = Column(String)
    file_path = Column(String)
    score = Column(Float, default=0.0)
    comment = Column(JSON)
    ai_output_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class UsageLogModel(Base):
    __tablename__ = "usage_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    model_name = Column(String)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    task_type = Column(String)
    batch_id = Column(String, index=True)
    pages = Column(Integer, default=0) 
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class SystemConfigModel(Base):
    __tablename__ = "system_config"
    key = Column(String, primary_key=True)
    value = Column(Text)

class PasswordResetModel(Base):
    __tablename__ = 'password_resets'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"))
    otp_code = Column(String(6))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime)
    is_used = Column(Boolean, default=False)

# ==============================================================================
#  3. Core Functions
# ==============================================================================

def init_db():
    # [Robustness] 確保 DB 資料夾存在 (防止 Mac 上資料夾未建立導致錯誤)
    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create DB directory: {e}")

    Base.metadata.create_all(bind=engine)
    
    # Admin User Init
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "admin123")
    
    session = SessionLocal()
    try:
        exists = session.query(UserModel).filter_by(username=admin_user).first()
        if not exists:
            ph = bcrypt.hashpw(admin_pass.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            new_admin = UserModel(
                username=admin_user, email=f"{admin_user}@admin.local", 
                real_name="System Admin", password_hash=ph, 
                is_approved=True, is_admin=True, plan='business'
            )
            session.add(new_admin)
            session.commit()
    except Exception as e:
        logger.error(f"Init DB Error: {e}")
    finally:
        session.close()

def get_user_from_orm(u: UserModel) -> Optional[User]:
    if not u: return None
    return User(
        id=u.id, username=u.username, email=u.email or "", real_name=u.real_name or "",
        password_hash=u.password_hash, is_approved=u.is_approved, is_admin=u.is_admin,
        school=u.school or "", department=u.department or "", 
        google_key=u.google_key or "", openai_key=u.openai_key or "",
        model_name=u.model_name, plan=u.plan, timezone=u.timezone,
        custom_page_limit=u.custom_page_limit or 0,
        custom_exam_limit=u.custom_exam_limit or 0,
        branding_logo_path=u.branding_logo_path or "",
        custom_advertising_url=u.custom_advertising_url or "",
        current_period_end=u.current_period_end
    )

def get_user_by_username(username: str) -> Optional[User]:
    with SessionLocal() as session:
        u = session.query(UserModel).filter_by(username=username).first()
        return get_user_from_orm(u)

def get_user_by_id(uid: int) -> Optional[User]:
    with SessionLocal() as session:
        u = session.get(UserModel, uid)
        return get_user_from_orm(u)
        
def get_user_by_email(email: str) -> Optional[User]:
    with SessionLocal() as session:
        u = session.query(UserModel).filter_by(email=email).first()
        return get_user_from_orm(u)

def update_user_last_login(user_id: int) -> bool:
    with SessionLocal() as session:
        u = session.get(UserModel, user_id)
        if u: u.last_login = datetime.datetime.utcnow(); session.commit(); return True
        return False

def create_user(username, email, password_hash, real_name, school, department, google_api_key, openai_api_key, is_approved=False, is_admin=False, plan="personal"):
    session = SessionLocal()
    try:
        u = UserModel(
            username=username, email=email, password_hash=password_hash,
            real_name=real_name, school=school, department=department,
            google_key=google_api_key, openai_key=openai_api_key,
            is_approved=is_approved, is_admin=is_admin, plan=plan
        )
        session.add(u)
        session.commit()
        session.refresh(u)
        return get_user_from_orm(u)
    except Exception as e:
        session.rollback()
        logger.error(f"Create User Error: {e}")
        return None
    finally: session.close()

def update_user(user_id: int, **kwargs) -> bool:
    with SessionLocal() as session:
        u = session.get(UserModel, user_id)
        if not u: return False
        key_map = {'google_api_key': 'google_key', 'openai_api_key': 'openai_key'}
        for k, v in kwargs.items():
            attr = key_map.get(k, k)
            if hasattr(u, attr): setattr(u, attr, v)
        try: session.commit(); return True
        except: session.rollback(); return False

# --- Enforcement & Quota ---

def enforce_license_plan(user_id: int, licensed_plan: str) -> bool:
    session = SessionLocal()
    try:
        user = session.get(UserModel, user_id)
        if not user: return False

        plan_conf = get_plan_config(licensed_plan)
        user.plan = licensed_plan
        
        # 依規則強制設定權限
        if not plan_conf["show_admin"]:
            user.is_admin = False
        
        # 非 Business 版強制歸零客製額度
        if licensed_plan != "business":
            user.custom_page_limit = 0
            user.custom_exam_limit = 0
            
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"License Enforce Error: {e}")
        return False
    finally: session.close()

def get_user_weekly_page_count(user_id: int) -> int:
    with SessionLocal() as session:
        try:
            # 簡化版：計算過去 7 天的總量 (SQLite/Postgres 通用)
            cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
            sql = text("SELECT SUM(pages) FROM usage_logs WHERE user_id = :uid AND created_at >= :start")
            result = session.execute(sql, {"uid": user_id, "start": cutoff}).scalar()
            return int(result) if result else 0
        except: return 0

def get_user_weekly_exam_gen_count(user_id: int) -> int:
    with SessionLocal() as session:
        try:
            cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
            sql = text("SELECT COUNT(*) FROM exams WHERE user_id = :uid AND created_at >= :start")
            result = session.execute(sql, {"uid": user_id, "start": cutoff}).scalar()
            return int(result) if result else 0
        except: return 0

def check_user_quota(user_id: int, quota_type: str = "grading_pages") -> Tuple[bool, str]:
    session = SessionLocal()
    try:
        user = session.get(UserModel, user_id)
        if not user: return False, "User not found"

        plan_conf = get_plan_config(user.plan)
        default_limit = plan_conf.get(quota_type, 0)

        final_limit = default_limit
        if user.plan == "business":
            custom = user.custom_page_limit if quota_type == "grading_pages" else user.custom_exam_limit
            if custom and custom > 0:
                final_limit = custom
        
        used = 0
        if quota_type == "grading_pages": used = get_user_weekly_page_count(user_id)
        elif quota_type == "exam_gen": used = get_user_weekly_exam_gen_count(user_id)

        if used >= final_limit: return False, f"Quota Exceeded ({used}/{final_limit})"
        return True, "OK"
    except: return False, "Error"
    finally: session.close()

# --- Other required functions ---
def create_session(user_id: int, token: str):
    with SessionLocal() as session:
        session.add(SessionModel(user_id=user_id, token=token)); session.commit()

def get_user_id_by_session(token: str) -> Optional[int]:
    with SessionLocal() as session:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        s = session.query(SessionModel).filter(SessionModel.token == token, SessionModel.created_at > cutoff).first()
        return s.user_id if s else None

def delete_session(token: str):
    with SessionLocal() as session:
        session.query(SessionModel).filter_by(token=token).delete(); session.commit()

def cleanup_old_data(days: int) -> int:
    if days <= 0: return 0
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    with SessionLocal() as session:
        targets = session.query(GradedExamModel.batch_id, GradedExamModel.user_id).filter(GradedExamModel.created_at < cutoff).distinct().all()
        count = 0
        for bid, uid in targets:
            session.query(GradedExamModel).filter_by(batch_id=bid).delete()
            count += 1
        session.commit()
        return count

def get_sys_conf(key: str) -> Optional[str]:
    with SessionLocal() as session:
        c = session.get(SystemConfigModel, key)
        return c.value if c else None

def set_sys_conf(key: str, value: str) -> bool:
    with SessionLocal() as session:
        c = session.get(SystemConfigModel, key)
        if c: c.value = str(value)
        else: session.add(SystemConfigModel(key=key, value=str(value)))
        try: session.commit(); return True
        except: session.rollback(); return False

def get_all_users() -> List[Dict]:
    with SessionLocal() as session:
        users = session.query(UserModel).order_by(UserModel.id).all()
        return [{c.name: getattr(u, c.name) for c in u.__table__.columns if c.name != 'password_hash'} for u in users]

def get_all_usage_stats() -> pd.DataFrame:
    with SessionLocal() as session:
        sql = text("SELECT u.username, COUNT(l.id) as job_count, SUM(l.cost_usd) as total_cost FROM usage_logs l JOIN users u ON l.user_id = u.id GROUP BY u.username")
        return pd.read_sql(sql, session.bind)

def get_batch_billing_stats(limit: int = 100) -> pd.DataFrame:
    with SessionLocal() as session:
        sql = text("""
            SELECT u.username, u.real_name, g.batch_id, COUNT(*) as student_count
            FROM graded_exams g JOIN users u ON g.user_id = u.id 
            GROUP BY u.username, u.real_name, g.batch_id 
            ORDER BY g.batch_id DESC LIMIT :limit
        """)
        return pd.read_sql(sql, session.bind, params={"limit": limit})
