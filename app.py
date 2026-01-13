# app.py
# -*- coding: utf-8 -*-
# Module-Version: 19.3.0 (macOS Commercial Native: No Simplifications)
# Description: 整合 Mac 原生路徑、完整 Cookie 管理、多主題引擎、首次啟動精靈、機構分級權限。

import streamlit as st
import sys
import html
import logging
import os
import shutil
from dotenv import load_dotenv

# ==============================================================================
# 1. 核心模組載入 (含防禦性檢查)
# ==============================================================================
try:
    # Mac 專用路徑管理
    from utils.paths import get_resource_path, get_writable_path
    # 多國語言架構
    from utils.localization import t, set_language, LANGUAGE_OPTIONS
    # 安全與授權
    from services.security import verify_license_tier, get_fingerprint_for_ui, load_branding_title
    # 資料庫與設定
    from database.db_manager import init_db, get_sys_conf
    # 身份驗證
    from services.auth_service import validate_session, logout_user
    
    # UI 視圖模組
    from ui.login_view import render_login
    from ui.portal_view import render_portal
    from ui.dashboard_view import render_dashboard
    from ui.exam_gen_view import render_exam_generator
    from ui.solution_editor_view import render_solution_editor
    from ui.my_exams_view import render_my_exams_view
    from ui.history_view import render_history
    from ui.settings_view import render_settings
    from ui.admin_view import render_admin
    
    # Mac 風格引擎
    from utils.styles import apply_mac_style, render_mac_sidebar_footer

except ImportError as e:
    # 這是為了防止打包後缺少模組導致直接閃退 (Crash)，在畫面上顯示錯誤
    st.error(f"❌ Critical Startup Error: Missing Module. {e}")
    st.stop()

# ==============================================================================
# 2. 環境與路徑初始化 (Path Initialization)
# ==============================================================================
# 設定 Log 到可寫入的使用者目錄 (避免 Mac 權限錯誤)
LOG_FILE = get_writable_path(os.path.join("logs", "app.log"))
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)

# 定義關鍵檔案路徑
# 1. License & Config: 存在使用者可寫入區 (~/Library/Application Support/...)
LICENSE_PATH = get_writable_path("license.key")
CONF_PATH = get_writable_path("branding.conf")

# 2. Assets: 優先讀取使用者上傳的 (Writable)，沒有則讀取 App 內建的 (Resource)
USER_ASSETS_DIR = get_writable_path("assets")
if not os.path.exists(USER_ASSETS_DIR): 
    os.makedirs(USER_ASSETS_DIR, exist_ok=True)

# Logo 優先權邏輯：自訂 > 預設 > 無
CUSTOM_LOGO_PATH = os.path.join(USER_ASSETS_DIR, "branding_logo.png")
DEFAULT_LOGO_PATH = get_resource_path(os.path.join("assets", "branding_logo.png"))

if os.path.exists(CUSTOM_LOGO_PATH):
    LOGO_PATH = CUSTOM_LOGO_PATH
elif os.path.exists(DEFAULT_LOGO_PATH):
    LOGO_PATH = DEFAULT_LOGO_PATH
else:
    LOGO_PATH = None

# 預設標題 (稍後會嘗試從 branding.conf 覆蓋)
app_title = "Math AI Grader Pro"
page_icon = LOGO_PATH if LOGO_PATH else "📝"

# 嘗試讀取 Branding Title (支援機構改名)
try:
    # 傳入可寫入區的目錄，因為 branding.conf 在那裡
    base_dir = os.path.dirname(LICENSE_PATH)
    loaded_title = load_branding_title(base_dir)
    if loaded_title:
        app_title = loaded_title
except Exception:
    pass

# 設定頁面 (必須是第一條 Streamlit 指令)
st.set_page_config(
    page_title=app_title,
    page_icon=page_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# [UI Magic] 強制注入 Mac 風格 CSS (讀取 Session 中的主題)
current_theme = st.session_state.get("theme", "專業商務 (Pro Blue)")
apply_mac_style(current_theme)

# ==============================================================================
# 3. 授權驗證與首次啟動精靈 (License Gatekeeper & Wizard)
# ==============================================================================
def check_license_gatekeeper():
    """
    檢查授權檔。
    如果不存在 -> 顯示「首次啟動精靈」(Setup Wizard)。
    如果存在 -> 驗證有效性與方案 (Personal/Business)。
    """
    if not os.path.exists(LICENSE_PATH):
        # --- Mac Style Setup Wizard ---
        st.markdown("""<div style='text-align:center; padding:40px;'>""", unsafe_allow_html=True)
        
        if LOGO_PATH: 
            st.image(LOGO_PATH, width=120)
        
        st.title("Welcome to Math AI Grader")
        st.info("Setup Required: Please upload your license key to activate.")
        
        # 使用 Form 避免重複刷新
        with st.form("setup_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("##### 1. License Key (Required)")
                up_key = st.file_uploader("Upload `license.key`", type=["key"])
            with col_b:
                st.markdown("##### 2. Config (Optional)")
                up_conf = st.file_uploader("Upload `branding.conf`", type=["conf", "json"])
            
            submitted = st.form_submit_button("🚀 Activate System", type="primary", use_container_width=True)
            
            if submitted:
                if up_key:
                    # 寫入檔案到隱藏的系統路徑
                    try:
                        with open(LICENSE_PATH, "wb") as f:
                            f.write(up_key.getbuffer())
                        
                        if up_conf:
                            with open(CONF_PATH, "wb") as f:
                                f.write(up_conf.getbuffer())
                                
                        st.toast("✅ Activation Successful! Restarting...", icon="🎉")
                        # 標記 Session 並重啟
                        st.session_state["init_done"] = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"File Write Error: {e}")
                else:
                    st.error("⚠️ License key is required.")
        
        # 顯示 Machine ID 方便客戶複製
        try: 
            mid = get_fingerprint_for_ui()
        except: 
            mid = "Unknown"
            
        with st.expander("Show Machine ID (For Registration)"):
            st.code(mid)
            st.caption("Please send this ID to your administrator.")
            
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop() # 停止執行後續代碼

    # --- License Verification ---
    try:
        is_valid, message, plan, title = verify_license_tier(LICENSE_PATH)
    except Exception as e:
        is_valid, message, plan, title = False, str(e), None, None

    if not is_valid:
        st.error(f"⛔ License Invalid: {message}")
        st.warning("Please contact support or upload a valid license.")
        
        # 提供重置按鈕，防止因為壞掉的 Key 導致程式永遠打不開
        if st.button("🗑️ Reset License (Delete & Retry)"):
            try: 
                if os.path.exists(LICENSE_PATH): os.remove(LICENSE_PATH)
                if os.path.exists(CONF_PATH): os.remove(CONF_PATH)
            except: pass
            st.rerun()
        st.stop()
    
    # 驗證通過，將關鍵資訊存入 Session
    st.session_state["SYSTEM_PLAN"] = plan
    st.session_state["APP_TITLE"] = title

# 執行攔截
check_license_gatekeeper()

# ==============================================================================
# 4. 主應用程式邏輯 (Main App Logic)
# ==============================================================================
load_dotenv()
init_db() # 初始化 DB (路徑由 db_manager 透過 utils.paths 處理)

# --- Cookie Manager (Full Robust Version) ---
# 這裡不簡化，保留完整的錯誤處理，確保 Cookie 讀寫穩定
_COOKIE_AVAILABLE = False
_cookie_mgr = None

try:
    import extra_streamlit_components as stx  
    _COOKIE_AVAILABLE = True
except ImportError:
    pass

def _get_cookie_mgr():
    global _cookie_mgr
    if not _COOKIE_AVAILABLE: 
        return None
    if _cookie_mgr is None:
        try: 
            _cookie_mgr = stx.CookieManager(key="cookie_manager")
        except Exception: 
            _cookie_mgr = None
    return _cookie_mgr

def _cookie_ops(op, name, value=None):
    """Cookie 操作封裝：get, set, delete"""
    cm = _get_cookie_mgr()
    if not cm: return None
    try:
        if op == "get": 
            return cm.get(name)
        elif op == "set": 
            cm.set(name, value)
        elif op == "delete": 
            cm.delete(name)
    except Exception: 
        pass

def main_app():
    # 1. 初始化 Cookie Manager
    _get_cookie_mgr()
    
    # 2. 初始化 Session State 變數
    if "is_authenticated" not in st.session_state:
        st.session_state.update({
            "is_authenticated": False, 
            "lang": "zh_tw",
            "theme": "專業商務 (Pro Blue)"
        })
    
    # 3. 自動登入檢查 (Auto Login via Cookie)
    if not st.session_state["is_authenticated"]:
        token = st.session_state.get("session_token")
        
        # 如果 Session 沒 Token，試著從 Cookie 拿
        if not token:
            token = _cookie_ops("get", "session_token")
            
        if token:
            user = validate_session(token)
            if user:
                st.session_state.update({"is_authenticated": True, "user": user})
                # Refresh Cookie (延長效期)
                _cookie_ops("set", "session_token", token)
                # 確保 Token 也在 Session 中
                st.session_state["session_token"] = token
            else:
                # Token 無效 (過期或被登出)，清理殘留
                _cookie_ops("delete", "session_token")
                st.session_state.pop("session_token", None)

    # 4. 登入畫面 (Login View)
    if not st.session_state["is_authenticated"]:
        if LOGO_PATH: 
            st.image(LOGO_PATH, width=150)
        render_login()
        return

    # 5. 登入後邏輯
    user = st.session_state["user"]
    
    # Portal 模式 (選擇身分/入口)
    if "app_mode" not in st.session_state:
        render_portal(user)
        return

    app_mode = st.session_state.app_mode

    # ==========================================================================
    # 5.1 側邊欄與導航 (Sidebar & Navigation)
    # ==========================================================================
    with st.sidebar:
        # A. Logo & User Info
        if LOGO_PATH:
            st.image(LOGO_PATH, use_container_width=True)
            st.markdown(f"**Hi, {user.real_name}**")
        else:
            st.title(f"Hi, {user.real_name}")

        # 顯示機構標題 (從 License/Config 讀取)
        st.caption(f"{st.session_state.get('APP_TITLE', 'Math Grader')}")
        
        st.markdown("---")

        # B. Language Selector (使用 LANGUAGE_OPTIONS)
        lang_keys = list(LANGUAGE_OPTIONS.keys())
        curr_lang = st.session_state.get("lang", "zh_tw")
        
        # 安全取得 index
        try: ix = lang_keys.index(curr_lang)
        except: ix = 0
        
        new_lang = st.selectbox(
            "Language", 
            options=lang_keys, 
            format_func=lambda x: LANGUAGE_OPTIONS[x], 
            index=ix,
            key="sidebar_lang_select"
        )
        if new_lang != curr_lang:
            st.session_state["lang"] = new_lang
            set_language(new_lang) # 同步更新 localization 模組狀態
            st.rerun()

        # C. Theme Selector (多主題切換)
        theme_opts = ["專業商務 (Pro Blue)", "暗夜極簡 (Dark Elegant)", "溫暖紙張 (Warm Paper)"]
        curr_theme = st.session_state.get("theme", "專業商務 (Pro Blue)")
        
        theme_display = {
            "專業商務 (Pro Blue)": "🔵 Pro Blue (Light)",
            "暗夜極簡 (Dark Elegant)": "🌑 Dark Elegant",
            "溫暖紙張 (Warm Paper)": "📜 Warm Paper"
        }
        
        new_theme = st.selectbox(
            "Interface Theme", 
            theme_opts, 
            index=theme_opts.index(curr_theme) if curr_theme in theme_opts else 0,
            format_func=lambda x: theme_display.get(x, x),
            key="sidebar_theme_select"
        )
        
        if new_theme != curr_theme:
            st.session_state["theme"] = new_theme
            st.rerun()

        st.markdown("---")
        
        # D. Mode Switch (模式切換)
        mode_label = t("mode_creator") if app_mode == "creator" else t("mode_grader")
        st.info(f"Mode: {mode_label}")
        if st.button(t("switch_mode"), use_container_width=True):
            del st.session_state.app_mode
            st.rerun()
            
        st.markdown("---")

        # E. Dynamic Menu Generation (動態選單)
        menu = []
        if app_mode == "creator":
            st.caption(t("menu_header_creator"))
            menu = [
                ("menu_exam_gen", "Exam Gen"), 
                ("menu_solution", "Solution Edit"), 
                ("menu_my_exams", "My Exams")
            ]
        else:
            st.caption(t("menu_header_grader"))
            menu = [
                ("menu_grading", "Grading"), 
                ("menu_history", "History")
            ]
        
        # 共用功能
        menu.append(("menu_settings", "Settings"))

        # [Strict Admin Logic] 嚴格限制：僅 Business Plan + Admin User 可見
        current_plan = st.session_state.get("SYSTEM_PLAN", "personal")
        is_user_admin = getattr(user, "is_admin", False)
        
        if is_user_admin and current_plan == "business":
            menu.append(("menu_admin", "Admin"))

        # 渲染選單
        opts = [m[0] for m in menu]
        default_ix = 0
        if "page" in st.session_state:
            # 嘗試保持當前頁面
            key = next((k for k,v in menu if v == st.session_state.page), None)
            if key in opts: default_ix = opts.index(key)

        sel = st.radio(
            "Navigation", 
            opts, 
            index=default_ix, 
            format_func=lambda x: t(x), 
            label_visibility="collapsed"
        )
        
        # 更新 Session State
        page = next(m[1] for m in menu if m[0] == sel)
        st.session_state.page = page

        st.markdown("---")
        
        # F. Logout
        if st.button(t("logout"), use_container_width=True):
            try: 
                logout_user(st.session_state.get("session_token"))
            except: pass
            
            _cookie_ops("delete", "session_token")
            st.session_state.clear()
            st.rerun()
            
        # G. Mac Style Sticky Footer
        donation_url = get_sys_conf("donation_url") or "https://www.math.tku.edu.tw/"
        btn_text = get_sys_conf("support_btn_text") or "Support Mathematics"
        popover_html = get_sys_conf("support_html") or "Thanks for your support!"
        render_mac_sidebar_footer(donation_url, btn_text, popover_html)

    # ==========================================================================
    # 5.2 頁面路由與權限檢查 (Routing & Access Control)
    # ==========================================================================
    if page == "Exam Gen": 
        render_exam_generator(user)
    elif page == "Solution Edit": 
        render_solution_editor()
    elif page == "My Exams": 
        render_my_exams_view(user)
    elif page == "Grading": 
        render_dashboard(user)
    elif page == "History": 
        render_history(user)
    elif page == "Settings": 
        render_settings(user)
    elif page == "Admin":
        # 路由層級的雙重防護 (Double Check)
        if is_user_admin and current_plan == "business": 
            render_admin(user)
        else: 
            st.error("⛔ Access Denied: Business Plan Required.")

# Entry Point
if __name__ == "__main__":
    main_app()
