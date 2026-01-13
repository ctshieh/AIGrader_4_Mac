# app.py
# -*- coding: utf-8 -*-
# Module-Version: 17.1.0 (Windows Native + Tiered Licensing)

import streamlit as st
import sys
import html
import logging
import os
from dotenv import load_dotenv

# --- 初始化設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_DIR, "logs"))
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8"),
    ],
)

st.set_page_config(page_title="Math AI Grader Pro", layout="wide")

# ==============================================================================
# 🔒 授權驗證攔截區
# ==============================================================================
def check_license_gatekeeper():
    try:
        from services.security import verify_license_tier, get_fingerprint_for_ui
    except ImportError as e:
        st.error("❌ Critical System Error: Security module missing.")
        st.code(str(e))
        st.stop()
        return

    LICENSE_PATH = os.getenv("LICENSE_PATH", os.path.join(BASE_DIR, "license.key"))

    def show_registration_screen(error_msg=""):
        st.markdown("""
            <style>
            .license-card { background-color: #f8f9fa; border: 1px solid #ddd; padding: 20px; border-radius: 10px; text-align: center; margin-top: 50px; }
            </style>
            """, unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.error(f"⛔ {error_msg}")
            try: fingerprint = get_fingerprint_for_ui()
            except: fingerprint = "UNKNOWN"
            st.info("👋 歡迎使用 Math AI Grader Pro！\n\n您的系統尚未啟用。請複製下方的【申請代碼】，並寄回給客服人員。")
            st.text_input("您的申請代碼", value=fingerprint)
            st.caption(f"請將 license.key 放入：{LICENSE_PATH}")
            if st.button("🔄 重新檢查"): st.rerun()
        st.stop()

    if not os.path.exists(LICENSE_PATH):
         show_registration_screen("未偵測到授權檔 (License Key Not Found)")

    try:
        is_valid, message, authorized_plan = verify_license_tier(LICENSE_PATH)
    except Exception as e:
        is_valid = False
        message = str(e)
        authorized_plan = None

    if not is_valid:
        show_registration_screen(f"授權驗證失敗: {message}")
    else:
        st.session_state["SYSTEM_PLAN"] = authorized_plan

check_license_gatekeeper()

# ==============================================================================
# ✅ 應用程式邏輯
# ==============================================================================
load_dotenv()

try:
    from ui.admin_view import render_admin
    from database.db_manager import init_db, get_sys_conf
    from services.auth_service import validate_session, logout_user
    from ui.login_view import render_login
    from ui.portal_view import render_portal
    from ui.dashboard_view import render_dashboard
    from ui.exam_gen_view import render_exam_generator
    from ui.solution_editor_view import render_solution_editor
    from ui.my_exams_view import render_my_exams_view
    from ui.history_view import render_history
    from ui.settings_view import render_settings
    from utils.styles import apply_theme
    from utils.localization import t

    init_db()
except ImportError as e:
    st.error(f"Startup Error: {e}")
    sys.exit()

# Cookie Support
_COOKIE_AVAILABLE = False
_cookie_mgr = None
try:
    import extra_streamlit_components as stx  
    _COOKIE_AVAILABLE = True
except: pass

def _get_cookie_mgr():
    global _cookie_mgr
    if not _COOKIE_AVAILABLE: return None
    if _cookie_mgr is None:
        try: _cookie_mgr = stx.CookieManager(key="cookie_manager")
        except: _cookie_mgr = None
    return _cookie_mgr

def _cookie_get(name):
    cm = _get_cookie_mgr()
    if cm: 
        try: return cm.get(name)
        except: return None
    return None

def _cookie_set(name, value):
    cm = _get_cookie_mgr()
    if cm:
        try: cm.set(name, value)
        except: pass

def _cookie_delete(name):
    cm = _get_cookie_mgr()
    if cm:
        try: cm.delete(name)
        except: pass

def render_sidebar_footer():
    donation_url = "https://www.math.tku.edu.tw/"
    btn_text = "Support Mathematics"
    popover_html = "您的支持是我們持續開發的動力"
    try:
        donation_url = get_sys_conf("donation_url") or donation_url
        btn_text = get_sys_conf("support_btn_text") or btn_text
        popover_html = get_sys_conf("support_html") or popover_html
    except: pass
    
    st.sidebar.markdown(f"""
    <style>section[data-testid="stSidebar"] > div:first-child {{ padding-bottom: 100px !important; }}</style>
    <div style="position:fixed; bottom:0; width:100%; padding:10px; text-align:center; background:white;">
        <a href="{donation_url}" target="_blank" style="text-decoration:none; color:#4c7dff; font-weight:bold;">
           {html.escape(btn_text)}
        </a>
    </div>
    """, unsafe_allow_html=True)

def main_app():
    _get_cookie_mgr()
    if "is_authenticated" not in st.session_state:
        st.session_state.update({"is_authenticated": False, "language": "繁體中文", "theme": "專業商務 (Pro Blue)"})
    apply_theme(st.session_state["theme"])

    if not st.session_state["is_authenticated"]:
        token = st.session_state.get("session_token") or _cookie_get("session_token")
        if token:
            user = validate_session(token)
            if user:
                st.session_state.update({"is_authenticated": True, "user": user})
                _cookie_set("session_token", token)
            else:
                _cookie_delete("session_token")

    if not st.session_state["is_authenticated"]:
        render_login()
        return

    user = st.session_state["user"]
    if "app_mode" not in st.session_state:
        render_portal(user)
        return

    app_mode = st.session_state.app_mode
    with st.sidebar:
        plan = st.session_state.get("SYSTEM_PLAN", "unknown")
        if plan == "enterprise": st.success("🏢 Enterprise License")
        elif plan == "pro": st.info("🚀 Pro License")
        else: st.caption(f"👤 {plan.title()} License")
        
        st.title(f"Hi, {user.real_name}")
        
        # Language
        lang_opts = {"繁體中文": "🇹🇼", "English": "🇺🇸", "日本語": "🇯🇵", "Français": "🇫🇷"}
        curr = st.session_state.get("language", "繁體中文")
        new_l = st.selectbox("Language", list(lang_opts.keys()), index=list(lang_opts.keys()).index(curr))
        if new_l != curr:
            st.session_state["language"] = new_l
            st.rerun()
            
        st.markdown("---")
        if st.button("🏠 " + t("switch_mode"), use_container_width=True):
            del st.session_state.app_mode
            st.rerun()
        st.markdown("---")
        
        menu = []
        if app_mode == "creator":
            menu = [("menu_exam_gen", "Exam Gen"), ("menu_solution", "Solution Edit"), ("menu_my_exams", "My Exams")]
        else:
            menu = [("menu_grading", "Grading"), ("menu_history", "History")]
        menu.append(("menu_settings", "Settings"))
        if getattr(user, "is_admin", False):
            menu.append(("menu_admin", "Admin"))
            
        opts = [m[0] for m in menu]
        sel = st.radio("Nav", opts, format_func=lambda x: t(x), label_visibility="collapsed")
        page = next(m[1] for m in menu if m[0] == sel)
        
        st.markdown("---")
        if st.button(t("logout"), use_container_width=True):
            _cookie_delete("session_token")
            st.session_state.clear()
            st.rerun()
        render_sidebar_footer()

    if page == "Exam Gen": render_exam_generator(user)
    elif page == "Solution Edit": render_solution_editor()
    elif page == "My Exams": render_my_exams_view(user)
    elif page == "Grading": render_dashboard(user)
    elif page == "History": render_history(user)
    elif page == "Settings": render_settings(user)
    elif page == "Admin": render_admin(user)

if __name__ == "__main__":
    main_app()
