# app.py
# -*- coding: utf-8 -*-
# Module-Version: 18.0.1 (Windows Commercial: Strict Tiering & Branding)

import streamlit as st
import sys
import html
import logging
import os
import shutil
from dotenv import load_dotenv

# ==============================================================================
# 0. 環境與路徑適配 (Windows EXE / Linux Docker 通用)
# ==============================================================================
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8"),
    ],
)

# ==============================================================================
# 1. 預載白牌化設定 (Pre-load Branding)
# ==============================================================================
LICENSE_PATH = os.path.join(BASE_DIR, "license.key")
LOGO_PATH = os.path.join(BASE_DIR, "assets", "branding_logo.png")

app_title = "Math AI Grader Pro"
page_icon = "📝"

# 嘗試讀取機構標題
try:
    from services.security import load_branding_title
    loaded_title = load_branding_title(BASE_DIR) # 傳入 BASE_DIR 確保路徑正確
    if loaded_title:
        app_title = loaded_title
except ImportError:
    pass
except Exception:
    pass

# 如果有 Logo，用 Logo 當作 Icon
if os.path.exists(LOGO_PATH):
    page_icon = LOGO_PATH

st.set_page_config(
    page_title=app_title,
    page_icon=page_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

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

    if not os.path.exists(LICENSE_PATH):
        render_gatekeeper_ui("License Key Not Found", None)
        st.stop()

    try:
        # 驗證並取得方案與標題
        is_valid, message, plan, title = verify_license_tier(LICENSE_PATH)
    except Exception as e:
        is_valid = False
        message = f"Validation Error: {str(e)}"
        plan = None

    if not is_valid:
        render_gatekeeper_ui(message, None)
        st.stop()
    
    # 寫入 Session，這是全域權限判斷的關鍵
    st.session_state["SYSTEM_PLAN"] = plan if plan else "personal"
    st.session_state["APP_TITLE"] = title

def render_gatekeeper_ui(error_msg, mid):
    st.markdown("""<style>.license-card { background-color: #f8f9fa; padding: 20px; border-radius: 10px; text-align: center; margin-top: 50px; }</style>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=200)
        else:
            st.title(app_title)

        st.error(f"⛔ **Access Denied**")
        st.warning(f"Reason: {error_msg}")
        
        try:
            from services.security import get_fingerprint_for_ui
            mid = get_fingerprint_for_ui()
        except: mid = "Unknown"

        st.info("Machine ID:")
        st.code(f"{mid}", language="text")
        if st.button("🔄 Reload"): st.rerun()

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
    if not cm: return None
    try: return cm.get(name)
    except: return None

def _cookie_set(name, value):
    cm = _get_cookie_mgr()
    if not cm: return
    try: cm.set(name, value)
    except: pass

def _cookie_delete(name):
    cm = _get_cookie_mgr()
    if not cm: return
    try: cm.delete(name)
    except: pass

# Footer Renderer
def render_sidebar_footer():
    donation_url = "https://www.math.tku.edu.tw/"
    btn_text = "Support Mathematics"
    popover_html = "您的支持是我們持續開發的動力"
    try:
        donation_url = get_sys_conf("donation_url") or donation_url
        btn_text = get_sys_conf("support_btn_text") or btn_text
        popover_html = get_sys_conf("support_html") or popover_html
    except: pass
    
    safe_btn = html.escape(str(btn_text))
    safe_pop = html.escape(str(popover_html))
    
    st.sidebar.markdown(f"""
    <style>
    section[data-testid="stSidebar"] > div:first-child {{ padding-bottom: 110px !important; }}
    .sidebar-footer {{ position: sticky; bottom: 0; width: 100%; padding: 0.75rem; z-index: 999; background: white; text-align: center; border-top: 1px solid #eee; }}
    .btn-support {{ display: block; width: 100%; padding: 8px; background: #f0f2f6; color: #31333F; text-decoration: none; border-radius: 8px; text-align: center; font-weight: 600; }}
    .btn-support:hover {{ background: #e0e2e6; color: #31333F; }}
    </style>
    <div class="sidebar-footer">
        <div title="{safe_pop}"><a href="{donation_url}" target="_blank" class="btn-support">❤️ {safe_btn}</a></div>
    </div>
    """, unsafe_allow_html=True)

def main_app():
    _get_cookie_mgr()
    if "is_authenticated" not in st.session_state:
        st.session_state.update({"is_authenticated": False, "language": "繁體中文", "theme": "專業商務 (Pro Blue)"})
    apply_theme(st.session_state["theme"])

    # Auto Login
    if not st.session_state["is_authenticated"]:
        token = st.session_state.get("session_token") or _cookie_get("session_token")
        if token:
            user = validate_session(token)
            if user:
                st.session_state.update({"is_authenticated": True, "user": user})
                _cookie_set("session_token", token)
            else:
                _cookie_delete("session_token")

    # Login View
    if not st.session_state["is_authenticated"]:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=150)
        render_login()
        return

    user = st.session_state["user"]
    if "app_mode" not in st.session_state:
        render_portal(user)
        return

    app_mode = st.session_state.app_mode

    with st.sidebar:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, use_container_width=True)
            st.write(f"Hi, **{user.real_name}**")
        else:
            st.title(f"Hi, {user.real_name}")

        st.caption(f"{st.session_state.get('APP_TITLE', 'Math Grader')}")
        
        # Language
        lang_opts = {"繁體中文": "🇹🇼", "English": "🇺🇸"}
        curr = st.session_state.get("language", "繁體中文")
        new_l = st.selectbox("Language", list(lang_opts.keys()), index=list(lang_opts.keys()).index(curr))
        if new_l != curr:
            st.session_state["language"] = new_l
            st.rerun()

        st.markdown("---")
        mode_label = t("mode_creator") if app_mode == "creator" else t("mode_grader")
        st.info(f"Mode: {mode_label}")
        if st.button("🏠 " + t("switch_mode"), use_container_width=True):
            del st.session_state.app_mode
            st.rerun()
        st.markdown("---")

        # Menu Generation
        menu = []
        if app_mode == "creator":
            st.caption(t("menu_header_creator"))
            menu = [("menu_exam_gen", "Exam Gen"), ("menu_solution", "Solution Edit"), ("menu_my_exams", "My Exams")]
        else:
            st.caption(t("menu_header_grader"))
            menu = [("menu_grading", "Grading"), ("menu_history", "History")]
        
        menu.append(("menu_settings", "Settings"))

        # [CRITICAL] 嚴格限制 Admin 選單：只有 Business Plan + Admin User 才能看
        current_plan = st.session_state.get("SYSTEM_PLAN", "personal")
        is_user_admin = getattr(user, "is_admin", False)
        
        if is_user_admin and current_plan == "business":
            menu.append(("menu_admin", "Admin"))

        opts = [m[0] for m in menu]
        default_ix = 0
        if "page" in st.session_state:
            key = next((k for k,v in menu if v == st.session_state.page), None)
            if key in opts: default_ix = opts.index(key)

        sel = st.radio("Nav", opts, index=default_ix, format_func=lambda x: t(x), label_visibility="collapsed")
        page = next(m[1] for m in menu if m[0] == sel)
        st.session_state.page = page

        st.markdown("---")
        if st.button(t("logout"), use_container_width=True):
            try: logout_user(st.session_state.get("session_token"))
            except: pass
            _cookie_delete("session_token")
            st.session_state.clear()
            st.rerun()
        render_sidebar_footer()

    # Routing
    if page == "Exam Gen": render_exam_generator(user)
    elif page == "Solution Edit": render_solution_editor()
    elif page == "My Exams": render_my_exams_view(user)
    elif page == "Grading": render_dashboard(user)
    elif page == "History": render_history(user)
    elif page == "Settings": render_settings(user)
    elif page == "Admin":
        if is_user_admin and current_plan == "business": render_admin(user)
        else: st.error("⛔ Access Denied")

if __name__ == "__main__":
    main_app()
