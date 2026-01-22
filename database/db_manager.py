# database/db_manager.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.23-Full-Core-Fix
# Description: 
# 1. [Full Restoration] 保留所有原始 Imports, Models (User, Exam, GradedExam, Payment...), Helper Functions.
# 2. [Fix] 實作 check_user_quota 邏輯，並支援 current_plan 參數。
# 3. [Fix] 確保 get_user_weekly_exam_gen_count 被正確呼叫。

import ast
import os
import json
import uuid
import datetime
import datetime as dt
import logging
import shutil
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz 
from dataclasses import dataclass
from typing import Any, Dict, Optional, Iterator, List, Tuple
import bcrypt
import pandas as pd

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, desc, func, text, Date, cast, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
import config 

# [NEW] 引入方案設定 (用於 Quota Check)
try:
    from services.plans import get_plan_config
except ImportError:
    def get_plan_config(p, f=None): return {"exam_gen_quota": 100}

try:
    from utils.paths import get_writable_path
except ImportError:
    def get_writable_path(x): return x

logger = logging.getLogger(__name__)

# ... (Breakdown helper functions preserved) ...
def _as_float(x):
    try:
        if x is None: return None
        return float(x)
    except Exception: return None

def _infer_score(d: dict):
    for k in ("score", "earned_points", "points_earned", "awarded", "sub_score", "total"):
        if k in d:
            v = _as_float(d.get(k))
            if v is not None: return v
    return None

def _infer_max_points(d: dict):
    for k in ("points", "max_points", "total_points"):
        if k in d:
            v = _as_float(d.get(k))
            if v is not None: return v
    return None

def _ensure_breakdown_node(d: dict):
    if not isinstance(d, dict): return
    has_breakdown_key = "breakdown" in d
    bd = d.get("breakdown", None)
    looks_gradable = has_breakdown_key or any(k in d for k in ("score", "earned_points", "points", "max_points"))
    if not looks_gradable: return
    if isinstance(bd, list) and len(bd) > 0: return

    score = _infer_score(d)
    maxp = _infer_max_points(d)

    d["breakdown"] = [{
        "rule": "__AUTO__",
        "max_points": maxp if maxp is not None else 0.0,
        "score": score if score is not None else _as_float(d.get("score")) or 0.0,
        "missing_work": True,
        "evidence_type": "none",
        "evidence": "",
        "comment": "⚠️ 系統未取得逐步明細（存檔時自動補上 placeholder）。"
    }]

def ensure_breakdown_present(ai_output_json):
    if isinstance(ai_output_json, list):
        for x in ai_output_json: ensure_breakdown_present(x)
        return
    if not isinstance(ai_output_json, dict): return

    qs = ai_output_json.get("questions")
    if isinstance(qs, list):
        for q in qs: ensure_breakdown_present(q)

    subs = ai_output_json.get("sub_questions")
    if isinstance(subs, list):
        for sq in subs: ensure_breakdown_present(sq)

    rs = ai_output_json.get("results")
    if isinstance(rs, list):
        for r in rs: ensure_breakdown_present(r)

    _ensure_breakdown_node(ai_output_json)

# ==============================================================================
#  1. SQLAlchemy Setup
# ==============================================================================
DB_FILE = get_writable_path("math_grader.db")
DATABASE_URL = f"sqlite:///{DB_FILE}"

engine = create_engine(
    DATABASE_URL, 
    pool_size=20, 
    max_overflow=30, 
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"check_same_thread": False} 
)

SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()

# ==============================================================================
#  2. Data Models (ALL PRESERVED)
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
    plan: str = "free"
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

@dataclass
class BatchRecord:
    batch_id: str
    user_id: str
    created_at: datetime.datetime
    student_count: int
    total_cost: float
    results: List[Dict]

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
    plan = Column(String, default='free')
    timezone = Column(String, default='Asia/Taipei')
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    ai_memory_rules = Column(JSON)
    custom_page_limit = Column(Integer, default=0)
    custom_exam_limit = Column(Integer, default=0)
    branding_logo_path = Column(Text)
    custom_advertising_url = Column(String)
    current_period_end = Column(DateTime)
    # [新增此行]
    last_active_at = Column(DateTime, nullable=True)

class SessionModel(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ExamModel(Base):
    __tablename__ = "exams"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    subject = Column(String)
    content_json = Column(JSON, nullable=False)
    is_published = Column(Boolean, default=False)
    # [NEW] 歸檔欄位
    academic_year = Column(String) # e.g. "113"
    semester = Column(String)      # e.g. "上學期"
    exam_type = Column(String)     # e.g. "期中考"
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

class PaymentRecordModel(Base):
    __tablename__ = 'payment_records'
    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    plan_type = Column(String, nullable=False)
    amount = Column(Float, default=0.0)
    remitter = Column(String, nullable=False)
    last_5 = Column(String, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

# ==============================================================================
#  3. Core Functions
# ==============================================================================
####
def init_db():
    """
    初始化資料庫並自動執行欄位遷移 (Migration)
    """
    # 1. 建立所有基本的資料表
    Base.metadata.create_all(bind=engine)
    
    # 2. 執行欄位檢查與補齊 (防禦性編程)
    with engine.connect() as conn:
        commands = [
            # --- [已有] 歷史遷移指令 ---
            "ALTER TABLE users ADD COLUMN custom_page_limit INTEGER DEFAULT 0;",
            "ALTER TABLE users ADD COLUMN custom_exam_limit INTEGER DEFAULT 0;",
            "ALTER TABLE users ADD COLUMN branding_logo_path TEXT;",
            "ALTER TABLE users ADD COLUMN custom_advertising_url TEXT;",
            "ALTER TABLE users ADD COLUMN current_period_end TIMESTAMP;",
            "ALTER TABLE usage_logs ADD COLUMN pages INTEGER DEFAULT 0;",
            "ALTER TABLE exam_drafts ADD COLUMN content TEXT;",
            "ALTER TABLE exam_drafts ADD COLUMN exam_id TEXT;",
            "ALTER TABLE exam_drafts ADD COLUMN status TEXT DEFAULT 'draft';",
            "ALTER TABLE exam_drafts ADD COLUMN academic_year TEXT;",
            "ALTER TABLE exam_drafts ADD COLUMN department TEXT;",
            "ALTER TABLE exam_drafts ADD COLUMN grade_level TEXT;",
            "ALTER TABLE exam_drafts ADD COLUMN final_pdf_path TEXT;",
            "ALTER TABLE exams ADD COLUMN academic_year TEXT;",
            "ALTER TABLE exams ADD COLUMN semester TEXT;",
            "ALTER TABLE exams ADD COLUMN exam_type TEXT;",
            
            # --- [NEW] 封堵時間漏洞所需的欄位 ---
            "ALTER TABLE users ADD COLUMN last_active_at DATETIME;"
        ]
        
        for cmd in commands:
            try:
                # 使用 text() 包裝字串，確保相容性
                conn.execute(text(cmd))
                conn.commit()
            except Exception:
                # 若欄位已存在，SQLite 會拋出錯誤，這裡直接跳過 (Pass)
                pass

    # 3. 管理員帳號初始化 (Admin User Init)
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "admin123")
    
    with SessionLocal() as session:
        exists = session.query(UserModel).filter_by(username=admin_user).first()
        if not exists:
            # 確保 hash_password 函式已定義
            ph = hash_password(admin_pass)
            new_admin = UserModel(
                username=admin_user,
                email=f"{admin_user}@admin.local",
                real_name="System Admin",
                password_hash=ph,
                is_approved=True,
                is_admin=True,
                plan='pro'
            )
            session.add(new_admin)
            try:
                session.commit()
            except Exception as e:
                session.rollback()
                print(f"Admin creation failed: {e}")

####


def init_db1():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        # [MIGRATION] Auto-add new archiving columns
        commands = [
            "ALTER TABLE users ADD COLUMN custom_page_limit INTEGER DEFAULT 0;",
            "ALTER TABLE users ADD COLUMN custom_exam_limit INTEGER DEFAULT 0;",
            "ALTER TABLE users ADD COLUMN branding_logo_path TEXT;",
            "ALTER TABLE users ADD COLUMN custom_advertising_url TEXT;",
            "ALTER TABLE users ADD COLUMN current_period_end TIMESTAMP;",
            "ALTER TABLE usage_logs ADD COLUMN pages INTEGER DEFAULT 0;",
            "ALTER TABLE exam_drafts ADD COLUMN content TEXT;", 
            "ALTER TABLE exam_drafts ADD COLUMN exam_id TEXT;",
            "ALTER TABLE exam_drafts ADD COLUMN status TEXT DEFAULT 'draft';",
            "ALTER TABLE exam_drafts ADD COLUMN academic_year TEXT;",
            "ALTER TABLE exam_drafts ADD COLUMN department TEXT;",
            "ALTER TABLE exam_drafts ADD COLUMN grade_level TEXT;",
            "ALTER TABLE exam_drafts ADD COLUMN final_pdf_path TEXT;",
            # [NEW] Archiving columns
            "ALTER TABLE exams ADD COLUMN academic_year TEXT;",
            "ALTER TABLE exams ADD COLUMN semester TEXT;",
            "ALTER TABLE exams ADD COLUMN exam_type TEXT;"
        ]
        for cmd in commands:
            try:
                conn.execute(text(cmd))
                conn.commit()
            except Exception: pass

    # Admin User Init
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "admin123")
    with SessionLocal() as session:
        exists = session.query(UserModel).filter_by(username=admin_user).first()
        if not exists:
            ph = hash_password(admin_pass)
            new_admin = UserModel(
                username=admin_user, email=f"{admin_user}@admin.local", 
                real_name="System Admin", password_hash=ph, 
                is_approved=True, is_admin=True, plan='pro'
            )
            session.add(new_admin)
            try: session.commit()
            except: session.rollback()

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

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def get_user_by_username(username: str) -> Optional[User]:
    with SessionLocal() as session:
        u = session.query(UserModel).filter_by(username=username).first()
        return get_user_from_orm(u)

def get_user_by_email(email: str) -> Optional[User]:
    with SessionLocal() as session:
        u = session.query(UserModel).filter_by(email=email).first()
        return get_user_from_orm(u)

def get_user_by_id(uid: int) -> Optional[User]:
    with SessionLocal() as session:
        u = session.get(UserModel, uid)
        return get_user_from_orm(u)

def login_user(username, password) -> Optional[User]:
    with SessionLocal() as session:
        u = session.query(UserModel).filter_by(username=username).first()
        if u and bcrypt.checkpw(password.encode('utf-8'), u.password_hash.encode('utf-8')):
            return get_user_from_orm(u)
    return None

def register_user(username, password, email, school, dept, real_name, google_key):
    with SessionLocal() as session:
        if session.query(UserModel).filter_by(username=username).first():
            return False, "Username exists"
        ph = hash_password(password)
        u = UserModel(username=username, password_hash=ph, email=email, school=school, department=dept, real_name=real_name, google_key=google_key)
        session.add(u)
        session.commit()
        return True, "Success"

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

def approve_user(user_id: int, plan: str='free') -> bool:
    return update_user(user_id, is_approved=True, plan=plan)

def set_user_admin_status(user_id: int, is_admin: bool) -> bool:
    return update_user(user_id, is_admin=is_admin)

def update_user_last_login(user_id: int) -> bool:
    with SessionLocal() as session:
        u = session.get(UserModel, user_id)
        if u: u.last_login = datetime.datetime.utcnow(); session.commit(); return True
        return False

def get_all_users() -> List[Dict]:
    with SessionLocal() as session:
        users = session.query(UserModel).order_by(UserModel.id).all()
        return [{c.name: getattr(u, c.name) for c in u.__table__.columns if c.name != 'password_hash'} for u in users]

def get_pending_users() -> List[Dict]:
    with SessionLocal() as session:
        users = session.query(UserModel).filter_by(is_approved=False).all()
        return [{c.name: getattr(u, c.name) for c in u.__table__.columns if c.name != 'password_hash'} for u in users]

def delete_user(user_id: int) -> bool:
    try:
        with SessionLocal() as session:
            session.query(SessionModel).filter_by(user_id=user_id).delete()
            res = session.query(UserModel).filter_by(id=user_id).delete()
            session.commit()
            return res > 0
    except Exception as e:
        logger.error(f"Delete user failed: {e}")
        return False

def reset_password_by_admin(user_id: int, new_password_plain: str) -> bool:
    try:
        new_hash = hash_password(new_password_plain)
        return update_user(user_id, password_hash=new_hash)
    except Exception as e:
        logger.error(f"Reset password failed: {e}")
        return False

# --- Session APIs ---
def create_session(user_id: int, token: str) -> None:
    with SessionLocal() as session:
        session.add(SessionModel(user_id=user_id, token=token)); session.commit()

def get_user_id_by_session(token: str) -> Optional[int]:
    with SessionLocal() as session:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        s = session.query(SessionModel).filter(SessionModel.token == token, SessionModel.created_at > cutoff).first()
        return s.user_id if s else None

def delete_session(token: str) -> None:
    with SessionLocal() as session:
        session.query(SessionModel).filter_by(token=token).delete(); session.commit()

# ==============================================================================
#  4. Exam Logic (Updated for Archiving)
# ==============================================================================

# [FIX] Added archiving params
def create_exam(user_id: int, title: str, subject: str, content: dict, is_published: bool=False,
               academic_year: str=None, semester: str=None, exam_type: str=None) -> int:
    with SessionLocal() as session:
        new_e = ExamModel(
            user_id=user_id, title=title, subject=subject, content_json=content, 
            is_published=is_published,
            academic_year=academic_year, semester=semester, exam_type=exam_type
        )
        session.add(new_e); session.commit(); return new_e.id

# [FIX] Added archiving params
def update_exam(exam_id: int, user_id: int, title: str, subject: str, content: dict, is_published: bool,
               academic_year: str=None, semester: str=None, exam_type: str=None) -> bool:
    with SessionLocal() as session:
        e = session.query(ExamModel).filter_by(id=exam_id, user_id=user_id).first()
        if not e: return False
        e.title = title
        e.subject = subject
        e.content_json = content
        e.is_published = is_published
        if academic_year: e.academic_year = academic_year
        if semester: e.semester = semester
        if exam_type: e.exam_type = exam_type
        session.commit(); return True

def get_exam_by_id(exam_id: int) -> Optional[Dict]:
    with SessionLocal() as session:
        e = session.get(ExamModel, exam_id)
        if not e: return None
        return {
            "id": e.id, "title": e.title, "subject": e.subject, "content_json": e.content_json, 
            "is_published": e.is_published, "updated_at": e.updated_at,
            "academic_year": e.academic_year, "semester": e.semester, "exam_type": e.exam_type
        }

def get_user_exams(user_id: int) -> List[Dict]:
    with SessionLocal() as session:
        exams = session.query(ExamModel).filter_by(user_id=user_id).order_by(desc(ExamModel.updated_at)).all()
        return [{
            "id": e.id, "title": e.title, "subject": e.subject, "updated_at": e.updated_at, "is_published": e.is_published, "content_json": e.content_json,
            "academic_year": e.academic_year, "semester": e.semester, "exam_type": e.exam_type
        } for e in exams]

def get_user_exam_list_for_ui(user_id: int) -> List[Dict]:
    with SessionLocal() as session:
        exams = session.query(ExamModel).filter_by(user_id=user_id).order_by(desc(ExamModel.updated_at)).all()
        return [{"id": e.id, "name": e.title, "type": "exam" if e.is_published else "draft", "updated_at": e.updated_at.strftime("%Y-%m-%d %H:%M")} for e in exams]

def load_exam_content_by_id(exam_id: int, user_id: int) -> Optional[Dict]:
    with SessionLocal() as session:
        e = session.query(ExamModel).filter_by(id=exam_id, user_id=user_id).first()
        return e.content_json if e else None

def delete_exam(exam_id: int, user_id: int) -> bool:
    with SessionLocal() as session:
        res = session.query(ExamModel).filter_by(id=exam_id, user_id=user_id).delete(); session.commit(); return res > 0

def save_exam_draft_or_publish(user_id: int, title: str, subject: str, data: dict, is_published: bool, exam_id: Optional[int] = None,
                              academic_year: str=None, semester: str=None, exam_type: str=None) -> int:
    if exam_id:
        if update_exam(exam_id, user_id, title, subject, data, is_published, academic_year, semester, exam_type): return exam_id
    return create_exam(user_id, title, subject, data, is_published, academic_year, semester, exam_type)

def save_exam_draft(user_id: int, exam_data, exam_id, status="draft", meta=None):
    session = SessionLocal()
    try:
        draft = session.query(ExamDraft).filter_by(exam_id=exam_id).first()
        header = exam_data.get("header", {})
        title_val = header.get("title", "Untitled")
        subject_val = header.get("subject", "General")
        
        if not draft:
            draft = ExamDraft(user_id=user_id, exam_id=exam_id, title=title_val, subject=subject_val, status=status)
            session.add(draft)
        else:
            draft.title = title_val
            draft.subject = subject_val
            draft.status = status
            draft.updated_at = datetime.datetime.utcnow()
        
        draft.content = json.dumps(exam_data, ensure_ascii=False)
        if meta:
            draft.academic_year = meta.get("year")
            draft.department = meta.get("dept")
            draft.grade_level = meta.get("grade")
            
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Save Draft Error: {e}")
        return False
    finally:
        session.close()

def _ensure_dict(data):
    if data is None: return {}
    if isinstance(data, dict): return data
    try: return json.loads(data)
    except:
        try: return ast.literal_eval(data)
        except: return {}

# [FIX] Integrated View Data
def get_user_exams_unified(user_id: int) -> List[Dict]:
    session = SessionLocal()
    results = []
    
    try:
        legacy = session.query(ExamModel).filter_by(user_id=user_id).order_by(desc(ExamModel.updated_at)).all()
        for l in legacy:
            content = _ensure_dict(l.content_json)
            results.append({
                "id": f"LEGACY_{l.id}",
                "title": l.title,
                "subject": l.subject,
                "updated_at": l.updated_at,
                "content": content,
                "academic_year": l.academic_year,
                "semester": l.semester,
                "exam_type": l.exam_type,
                "source": "legacy"
            })
        
        drafts = session.query(ExamDraft).filter_by(user_id=user_id).order_by(desc(ExamDraft.updated_at)).all()
        for d in drafts:
            results.append({
                "id": d.exam_id,
                "title": d.title,
                "subject": d.subject,
                "updated_at": d.updated_at,
                "content": _ensure_dict(d.content),
                "academic_year": d.academic_year,
                "semester": "-", 
                "exam_type": "-",
                "source": "new"
            })
    finally:
        session.close()
    
    results.sort(key=lambda x: x['updated_at'], reverse=True)
    return results

# --- Question & Sets ---
def save_question(**kwargs) -> int:
    with SessionLocal() as session:
        q = QuestionModel(
            content=kwargs.get('content'), score=kwargs.get('score', 0), question_no=kwargs.get('q_no', ''),
            solution=kwargs.get('solution', ''), sub_questions=kwargs.get('sub_questions'), user_id=kwargs.get('user_id'),
            is_public=kwargs.get('is_public', True), meta=kwargs.get('meta'), tags=kwargs.get('tags')
        )
        session.add(q); session.commit(); return q.id

def update_question(q_id: int, content: str, score: int = 0, meta=None, sub_questions=None, **kwargs) -> bool:
    with SessionLocal() as session:
        q = session.get(QuestionModel, q_id)
        if not q: return False
        q.content = content
        q.score = score
        if meta is not None: q.meta = meta
        if sub_questions is not None: q.sub_questions = sub_questions
        if 'solution' in kwargs: q.solution = kwargs['solution']
        if 'is_public' in kwargs: q.is_public = kwargs['is_public']
        if 'tags' in kwargs: q.tags = kwargs['tags']
        session.commit()
        return True

def delete_question(q_id: int) -> bool:
    with SessionLocal() as session:
        q = session.get(QuestionModel, q_id)
        if not q: return False
        session.delete(q)
        session.commit()
        return True

def update_question_solution(q_id: int, new_solution: str) -> bool:
    with SessionLocal() as session:
        q = session.get(QuestionModel, q_id)
        if q: q.solution = new_solution; session.commit(); return True
        return False

def get_all_questions() -> List[Dict]:
    with SessionLocal() as session:
        qs = session.query(QuestionModel).order_by(desc(QuestionModel.id)).all()
        return [{c.name: getattr(q, c.name) for c in q.__table__.columns} for q in qs]

def create_question_set(owner_id: int, title: str, description: str, question_ids: List[int]) -> int:
    with SessionLocal() as session:
        new_set = QuestionSetModel(owner_id=owner_id, title=title, description=description)
        session.add(new_set); session.flush()
        for idx, qid in enumerate(question_ids):
            item = QuestionSetItemModel(set_id=new_set.id, question_id=qid, item_order=idx)
            session.add(item)
        session.commit(); return new_set.id

def get_user_question_sets(user_id: int) -> List[Dict]:
    with SessionLocal() as session:
        res = session.query(QuestionSetModel).filter_by(owner_id=user_id).order_by(desc(QuestionSetModel.created_at)).all()
        return [{"id": r.id, "title": r.title, "description": r.description, "created_at": r.created_at, "is_public": r.is_public} for r in res]

def get_question_set_items(set_id: int) -> List[int]:
    with SessionLocal() as session:
        res = session.query(QuestionSetItemModel).filter_by(set_id=set_id).order_by(QuestionSetItemModel.item_order).all()
        return [r.question_id for r in res]

def delete_question_set(set_id: int) -> bool:
    with SessionLocal() as session:
        session.query(QuestionSetItemModel).filter_by(set_id=set_id).delete()
        res = session.query(QuestionSetModel).filter_by(id=set_id).delete(); session.commit(); return res > 0

# ==============================================================================
#  5. Grading & Stats
# ==============================================================================

def save_batch_results(user_id: int, batch_id: str, results: List[Dict]) -> bool:
    if not results: return False
    session = SessionLocal()
    try:
        total_cost = 0.0
        total_pages = 0
        session.query(GradedExamModel).filter_by(batch_id=batch_id).delete()
        for r in results:
            cost = float(r.get('cost_usd', 0.0))
            pages = int(r.get('page_count', 1)) 
            total_cost += cost
            total_pages += pages
            ensure_breakdown_present(r)
            exam = GradedExamModel(
                user_id=user_id, batch_id=batch_id, student_id=r.get('Student ID', ''),
                student_name=r.get('Name', ''), file_path=r.get('file_path', ''),
                score=r.get('total_score', 0), comment=r.get('general_comment', ''),
                ai_output_json=r
            )
            session.add(exam)
        
        existing_log = session.query(UsageLogModel).filter_by(batch_id=batch_id).first()
        if existing_log:
            existing_log.cost_usd = total_cost
            existing_log.pages = total_pages
            existing_log.created_at = datetime.datetime.utcnow()
        else:
            log = UsageLogModel(
                user_id=user_id, model_name="gemini-mixed-batch", cost_usd=total_cost, 
                task_type="batch_grading", batch_id=batch_id, pages=total_pages
            )
            session.add(log)
        session.commit()
        return True
    except Exception as e:
        session.rollback(); logger.error(f"Batch Save Error: {e}"); return False
    finally: session.close()

def delete_user_batch(batch_id: str, user_id: int) -> bool:
    with SessionLocal() as session:
        session.query(GradedExamModel).filter_by(batch_id=batch_id, user_id=user_id).delete()
        try:
            session.commit()
            if hasattr(config, 'SPLITS_DIR'):
                batch_dir = os.path.join(config.SPLITS_DIR, batch_id)
                if os.path.exists(batch_dir): shutil.rmtree(batch_dir)
            return True
        except: session.rollback(); return False

# ==============================================================================
# [NEW] 內部邏輯：計算用戶所在時區的「本週一 00:00」並轉為 UTC
# ==============================================================================
def _get_user_week_start_utc(session, user_id: int) -> datetime.datetime:
    """
    (Internal Helper) 
    取得該用戶時區的「本週一 00:00:00」，並轉換為 UTC 時間供 DB 查詢。
    """
    try:
        # 1. 查詢用戶設定的時區 (預設 Asia/Taipei)
        user = session.get(UserModel, user_id)
        tz_str = user.timezone if (user and user.timezone) else "Asia/Taipei"
        user_tz = pytz.timezone(tz_str)

        # 2. 取得當前 UTC 時間 (Aware)
        now_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

        # 3. 轉為用戶當地時間
        now_user = now_utc.astimezone(user_tz)

        # 4. 回推到當地時間的「本週一 00:00:00」
        # weekday(): 0=週一, 6=週日
        days_diff = now_user.weekday()
        start_of_week_user = now_user - datetime.timedelta(days=days_diff)
        start_of_week_user = start_of_week_user.replace(hour=0, minute=0, second=0, microsecond=0)

        # 5. 將該時間點轉回 UTC
        start_of_week_utc = start_of_week_user.astimezone(pytz.utc)

        # 6. 轉為 Naive datetime (移除時區標籤，因為 SQLite/SQLAlchemy 存的是 Naive UTC)
        return start_of_week_utc.replace(tzinfo=None)

    except Exception as e:
        logger.error(f"Timezone calc error for user {user_id}: {e}")
        # Fallback: 如果出錯，回退到 UTC 的週一 00:00
        now = datetime.datetime.utcnow()
        start = now - datetime.timedelta(days=now.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)

# ==============================================================================
# [UPDATE] 保持函式名稱不變，但邏輯改為「週一重置」
# ==============================================================================

def get_user_weekly_page_count(user_id: int) -> int:
    with SessionLocal() as session:
        try:
            # 呼叫內部邏輯取得正確的 cutoff 時間
            cutoff = _get_user_week_start_utc(session, user_id)
            
            sql = text("SELECT SUM(pages) FROM usage_logs WHERE user_id = :uid AND created_at >= :start")
            result = session.execute(sql, {"uid": user_id, "start": cutoff}).scalar()
            return int(result) if result else 0
        except Exception as e:
            logger.error(f"Get page count error: {e}")
            return 0

def get_user_weekly_exam_gen_count(user_id: int) -> int:
    with SessionLocal() as session:
        try:
            # 呼叫內部邏輯取得正確的 cutoff 時間
            cutoff = _get_user_week_start_utc(session, user_id)
            
            sql = text("SELECT COUNT(*) FROM exams WHERE user_id = :uid AND created_at >= :start")
            result = session.execute(sql, {"uid": user_id, "start": cutoff}).scalar()
            return int(result) if result else 0
        except Exception as e:
            logger.error(f"Get exam count error: {e}")
            return 0
            
def get_user_history_batches(user_id: int) -> pd.DataFrame:
    session = SessionLocal()
    try:
        rubric_col = func.max(cast(GradedExamModel.ai_output_json['rubric'], Text)).label("rubric")
        q = session.query(
            GradedExamModel.batch_id, func.min(GradedExamModel.created_at).label("created_at"),
            func.count(GradedExamModel.id).label("count"), func.avg(GradedExamModel.score).label("avg_score"),
            rubric_col
        ).filter(GradedExamModel.user_id == user_id).group_by(GradedExamModel.batch_id).order_by(desc("created_at"))
        df = pd.read_sql(q.statement, session.bind)
        if not df.empty:
            costs = session.query(UsageLogModel.batch_id, func.sum(UsageLogModel.cost_usd).label("cost")).filter(UsageLogModel.batch_id.in_(df['batch_id'].tolist())).group_by(UsageLogModel.batch_id).all()
            cost_map = {c.batch_id: float(c.cost) for c in costs}
            df['cost_usd'] = df['batch_id'].map(cost_map).fillna(0.0)
            df['status'] = 'Completed'
        return df
    except: return pd.DataFrame()
    finally: session.close()

def get_batch_details(batch_id: str) -> pd.DataFrame:
    with SessionLocal() as session:
        q = session.query(GradedExamModel).filter_by(batch_id=batch_id).order_by(GradedExamModel.id)
        return pd.read_sql(q.statement, session.bind)

def update_graded_exam_score_and_comment(record_id: int, new_score: float, new_comment_str: str, user_id: int) -> bool:
    with SessionLocal() as session:
        exam = session.query(GradedExamModel).filter_by(id=record_id, user_id=user_id).first()
        if exam: exam.score, exam.comment = new_score, new_comment_str; session.commit(); return True
        return False

def update_student_score(batch_id: str, student_id: str, ai_output_json_str: str) -> bool:
    try:
        data_dict = ai_output_json_str if isinstance(ai_output_json_str, dict) else json.loads(ai_output_json_str)
    except: return False
    
    new_total = float(data_dict.get("total_score", data_dict.get("Final Score", 0.0)))
    with SessionLocal() as session:
        try:
            exam = session.query(GradedExamModel).filter_by(batch_id=str(batch_id), student_id=str(student_id)).first()
            if exam:
                exam.ai_output_json = data_dict
                exam.score = new_total
                if "general_comment" in data_dict: exam.comment = data_dict["general_comment"]
                session.commit(); return True
            return False
        except: session.rollback(); return False

def get_all_usage_stats() -> pd.DataFrame:
    with SessionLocal() as session:
        sql = text("SELECT u.username, COUNT(l.id) as job_count, SUM(l.cost_usd) as total_cost FROM usage_logs l JOIN users u ON l.user_id = u.id GROUP BY u.username")
        return pd.read_sql(sql, session.bind)

def get_batch_billing_stats(limit: int = 100) -> pd.DataFrame:
    with SessionLocal() as session:
        sql = text("""
            SELECT u.username, u.real_name, g.batch_id, MIN(g.created_at) as start_time,
                   COUNT(*) as student_count, SUM(l.cost_usd) as total_cost
            FROM graded_exams g JOIN users u ON g.user_id = u.id LEFT JOIN usage_logs l ON g.batch_id = l.batch_id
            GROUP BY u.username, u.real_name, g.batch_id ORDER BY start_time DESC LIMIT :limit
        """)
        return pd.read_sql(sql, session.bind, params={"limit": limit})

def get_user_usage_logs(user_id: int, limit: int = 500) -> List[Dict]:
    with SessionLocal() as session:
        logs = session.query(UsageLogModel).filter_by(user_id=user_id).order_by(desc(UsageLogModel.created_at)).limit(limit).all()
        return [{"model_name": l.model_name, "input_tokens": l.input_tokens, "output_tokens": l.output_tokens, "cost_usd": l.cost_usd, "task_type": l.task_type, "batch_id": l.batch_id, "created_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S")} for l in logs]

def cleanup_old_data(days: int) -> int:
    if days <= 0: return 0
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    with SessionLocal() as session:
        targets = session.query(GradedExamModel.batch_id, GradedExamModel.user_id).filter(GradedExamModel.created_at < cutoff).distinct().all()
        count = 0
        for bid, uid in targets:
            if delete_user_batch(bid, uid): count += 1
        return count

def get_today_batch_count(user_id: int) -> int:
    with SessionLocal() as session:
        return session.query(func.count(func.distinct(UsageLogModel.batch_id))).filter(
            UsageLogModel.user_id == user_id, 
            func.date(UsageLogModel.created_at) == func.date(datetime.datetime.utcnow())
        ).scalar() or 0

def get_ai_memory_rules(user_id: int) -> List[str]:
    with SessionLocal() as session:
        u = session.get(UserModel, user_id)
        if u and u.ai_memory_rules: return u.ai_memory_rules if isinstance(u.ai_memory_rules, list) else json.loads(u.ai_memory_rules)
        return []

def update_ai_memory_rules(user_id: int, rules: List[str]) -> bool:
    with SessionLocal() as session:
        u = session.get(UserModel, user_id)
        if u: u.ai_memory_rules = rules; session.commit(); return True
        return False

def get_ai_memory_text(user_id: int) -> str:
    rules = get_ai_memory_rules(user_id)
    return "\n".join([f"- {r}" for r in rules]) if rules else ""

def log_usage(user_id: int, model_name: str, p_tok: int, c_tok: int, cost: float, u_type: str, batch_id: str) -> None:
    with SessionLocal() as session:
        log = UsageLogModel(user_id=user_id, model_name=model_name, input_tokens=p_tok, output_tokens=c_tok, cost_usd=cost, task_type=u_type, batch_id=batch_id)
        session.add(log); session.commit()

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

def get_all_batches(user_id: str) -> List[BatchRecord]:
    with SessionLocal() as session:
        sql = text("""
            SELECT batch_id, user_id, MIN(created_at) as created_at, 
                   (SELECT COUNT(*) FROM graded_exams WHERE batch_id = g.batch_id) as student_count, 
                   (SELECT SUM(cost_usd) FROM usage_logs WHERE batch_id = g.batch_id) as total_cost 
            FROM graded_exams g WHERE user_id = :u GROUP BY batch_id, user_id ORDER BY created_at DESC
        """)
        rows = session.execute(sql, {"u": user_id}).mappings().all()
        return [BatchRecord(batch_id=r['batch_id'], user_id=str(r['user_id']), created_at=r['created_at'], student_count=r['student_count'], total_cost=float(r['total_cost'] or 0), results=[]) for r in rows]

def get_batch_results(batch_id: str) -> List[Dict]:
    with SessionLocal() as session:
        rows = session.execute(text("SELECT ai_output_json FROM graded_exams WHERE batch_id = :b"), {"b": batch_id}).scalars().all()
        return [r if isinstance(r, dict) else json.loads(r) for r in rows if r]

# --- Payment & OTP ---
def create_payment_record(user_id: int, plan_type: str, amount: float, remitter: str, last_5: str) -> bool:
    try:
        with SessionLocal() as session:
            new_record = PaymentRecordModel(
                id=str(uuid.uuid4()), user_id=user_id, plan_type=plan_type, amount=amount,
                remitter=remitter, last_5=last_5, status="pending", created_at=datetime.datetime.utcnow()
            )
            session.add(new_record); session.commit(); return True
    except Exception as e: logger.error(f"Payment Error: {e}"); return False

def get_pending_payments() -> List[Dict]:
    try:
        with SessionLocal() as session:
            results = session.query(PaymentRecordModel, UserModel).join(UserModel, PaymentRecordModel.user_id == UserModel.id).filter(PaymentRecordModel.status == "pending").order_by(desc(PaymentRecordModel.created_at)).all()
            return [{"id": pay.id, "user_id": pay.user_id, "username": usr.username, "real_name": usr.real_name, "plan_type": pay.plan_type, "amount": pay.amount, "remitter": pay.remitter, "last_5": pay.last_5, "created_at": pay.created_at} for pay, usr in results]
    except: return []

def approve_payment_record(payment_id: str, user_id: int, plan_type: str) -> bool:
    try:
        with SessionLocal() as session:
            pay_record = session.query(PaymentRecordModel).filter_by(id=payment_id).first()
            if not pay_record: return False
            pay_record.status = "approved"; pay_record.processed_at = datetime.datetime.utcnow()
            user = session.query(UserModel).filter_by(id=user_id).first()
            if user:
                user.plan = plan_type
                user.current_period_end = datetime.datetime.utcnow() + datetime.timedelta(days=30)
            session.commit(); return True
    except: return False

def reject_payment_record(payment_id: str) -> bool:
    try:
        with SessionLocal() as session:
            pay_record = session.query(PaymentRecordModel).filter_by(id=payment_id).first()
            if not pay_record: return False
            pay_record.status = "rejected"; pay_record.processed_at = datetime.datetime.utcnow()
            session.commit(); return True
    except: return False

def create_password_reset_otp(username_or_email: str) -> Tuple[bool, str]:
    with SessionLocal() as session:
        user = session.query(UserModel).filter((UserModel.username == username_or_email) | (UserModel.email == username_or_email)).first()
        if not user or not user.email: return False, "User not found."
        otp = "".join([str(random.randint(0, 9)) for _ in range(6)])
        expire_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
        new_reset = PasswordResetModel(user_id=user.id, otp_code=otp, expires_at=expire_time)
        session.add(new_reset); session.commit()
        return True, f"{otp}|{user.email}"

def verify_otp_and_reset_password(username: str, otp: str, new_password: str) -> Tuple[bool, str]:
    with SessionLocal() as session:
        user = session.query(UserModel).filter_by(username=username).first()
        if not user: return False, "User error."
        record = session.query(PasswordResetModel).filter(
            PasswordResetModel.user_id == user.id, PasswordResetModel.otp_code == otp,
            PasswordResetModel.is_used == False, PasswordResetModel.expires_at > datetime.datetime.utcnow()
        ).first()
        if not record: return False, "Invalid OTP."
        user.password_hash = hash_password(new_password)
        record.is_used = True; session.commit()
        return True, "Success."

# [FIX] Quota Check Implementation
def get_verified_now():
    """
    [NEW] 取得經驗證的時間：優先使用網路時間，失敗則回退至系統時間
    """
    try:
        # 使用 worldtimeapi，設定超時 1.5 秒以免影響使用者體驗
        resp = requests.get("http://worldtimeapi.org/api/timezone/Etc/UTC", timeout=1.5)
        if resp.status_code == 200:
            data = resp.json()
            return datetime.datetime.fromisoformat(data['datetime'].replace('Z', '+00:00')).replace(tzinfo=None)
    except:
        pass
    # 沒網路時回退到系統時間 (配合下方的資料庫鎖定機制仍具防禦力)
    return datetime.datetime.utcnow()

#######
def check_user_quota(user_id: int, current_plan: str, quota_type: str = "exam_gen") -> Tuple[bool, str]:
    """
    [ENHANCED] 強化版配額檢查：防止修改系統時間
    """
    session = SessionLocal()
    try:
        # 1. 取得經驗證的「現在時間」
        verified_now = get_verified_now()
        
        # 2. 【防作弊檢查】讀取用戶最後活動時間
        user = session.get(UserModel, user_id)
        if user and user.last_active_at:
            # 如果發現「現在時間」竟然比「最後活動時間」還要早，代表用戶調低了系統時間
            if verified_now < user.last_active_at:
                return False, "❌ 偵測到系統時間異常，請校正您的電腦時間。"

        # 更新最後活動時間（存入資料庫作為標竿）
        user.last_active_at = verified_now
        session.commit()

        # 3. 讀取方案設定
        plan_config = get_plan_config(current_plan)
        
        if quota_type == "exam_gen":
            limit = plan_config.get("exam_gen_quota", 30)
            if current_plan == 'admin' or limit > 9999:
                return True, "Unlimited"

            # 使用驗證過的時間計算週一重置點
            # 這裡呼叫您之前的 _get_user_week_start_utc，但內部改用 verified_now
            cutoff = _get_user_week_start_utc_fixed(session, user_id, verified_now)
            
            sql = text("SELECT COUNT(*) FROM exams WHERE user_id = :uid AND created_at >= :start")
            current_usage = session.execute(sql, {"uid": user_id, "start": cutoff}).scalar() or 0
            
            if current_usage >= limit:
                return False, f"❌ 已超出每週配額 ({current_usage}/{limit})"
                
        return True, "OK"
    except Exception as e:
        logger.error(f"Quota check error: {e}")
        return True, "Error bypassing" # 出錯時寬鬆處理或嚴格限制依您決定
    finally:
        session.close()
 #######
 
def _get_user_week_start_utc_fixed(session, user_id, base_now_utc):
    """
    修改原本的週一計算函式，使其接受外部傳入的 base_now_utc (驗證過的時間)
    """
    # 邏輯與之前一致，但將 datetime.datetime.utcnow() 換成 base_now_utc
    user = session.get(UserModel, user_id)
    tz_str = user.timezone if (user and user.timezone) else "Asia/Taipei"
    user_tz = pytz.timezone(tz_str)
    
    # 將驗證過的 UTC 時間轉為用戶時區
    now_user = base_now_utc.replace(tzinfo=pytz.utc).astimezone(user_tz)
    start_of_week_user = now_user - datetime.timedelta(days=now_user.weekday())
    start_of_week_user = start_of_week_user.replace(hour=0, minute=0, second=0, microsecond=0)
    
    return start_of_week_user.astimezone(pytz.utc).replace(tzinfo=None)
 
 
###Any
def check_user_quota1(user_id: int, current_plan: str, quota_type: str = "exam_gen") -> Tuple[bool, str]:
    """
    檢查用戶配額
    Args:
        user_id: 用戶 ID
        current_plan: 當前方案 (來自 app.py 的 user.plan)
        quota_type: 檢查類型 ('exam_gen' / 'grading_pages')
    """
    # 1. 讀取方案設定 (不查 DB，直接用傳入的 plan)
    # 需確保 services.plans.get_plan_config 存在
    plan_config = get_plan_config(current_plan)
    
    if quota_type == "exam_gen":
        limit = plan_config.get("exam_gen_quota", 30) # 預設給 30
        
        # Admin 或無限額度
        if current_plan == 'admin' or limit > 9999: 
            return True, "Unlimited"

        # 2. 計算已用量 (使用 get_user_weekly_exam_gen_count)
        current_usage = get_user_weekly_exam_gen_count(user_id)
        
        # 3. 比對
        if current_usage >= limit:
            return False, f"❌ 已超出每週配額 ({current_usage}/{limit})"
        
        return True, f"({current_usage}/{limit})"

    return True, "OK"

def deduct_user_quota(user_id: int, quota_type: str, amount: int = 1): 
    pass # 實際計數依賴 DB 查詢，無需手動扣除

def _ensure_dict(data):
    if data is None: return {}
    if isinstance(data, dict): return data
    try: return json.loads(data)
    except:
        try: return ast.literal_eval(data)
        except: return {}

# database/db_manager.py
# (請保留原有的 imports 和其他函數，新增以下函數)

def delete_unified_exam(unified_id: str, user_id: int) -> bool:
    """
    [NEW] 統一刪除函數：可處理 LEGACY_{id} 與 Draft UUID
    """
    session = SessionLocal()
    try:
        # 判斷是否為舊版資料 (LEGACY_ 開頭)
        if str(unified_id).startswith("LEGACY_"):
            try:
                real_id = int(unified_id.replace("LEGACY_", ""))
                # 刪除 exams 表
                res = session.query(ExamModel).filter_by(id=real_id, user_id=user_id).delete()
            except ValueError:
                return False
        else:
            # 視為新版草稿，刪除 exam_drafts 表
            res = session.query(ExamDraft).filter_by(exam_id=unified_id, user_id=user_id).delete()
            
        session.commit()
        return res > 0
    except Exception as e:
        logger.error(f"Delete Unified Error: {e}")
        session.rollback()
        return False
    finally:
        session.close()
