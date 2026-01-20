# Copyright (c) 2026 [謝忠村/Chung Tsun Shieh]. All Rights Reserved.
# app.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.20-K16-Multilang-Final

import streamlit as st
import sys
import os
import time
import shutil
import platform
import subprocess
from dotenv import load_dotenv

# ==============================================================================
# 1. 系統初始化
# ==============================================================================
st.set_page_config(
    page_title="AI Grader for STEM", 
    page_icon="📝", 
    layout="wide", 
    initial_sidebar_state="expanded" 
)

# ==============================================================================
# 2. CSS 樣式 (完整保留原始視覺規範)
# ==============================================================================
st.markdown("""
    <style>
    [data-testid="stSidebar"] { color: #333333 !important; background-color: #FAFAFA; }
    [data-testid="stSidebar"] p { font-size: 15px !important; color: #333333 !important; }
    [data-testid="stSidebarCollapsedControl"] {
        display: block !important; color: black !important;
        background-color: rgba(200, 200, 200, 0.4) !important; 
        border-radius: 0 8px 8px 0; z-index: 999999;
    }
    .mode-box {
        background-color: #E6F2FF; border: 1px solid #CCE5FF; color: #0056b3;
        padding: 12px; border-radius: 6px; margin-bottom: 12px;
        font-weight: bold; display: flex; align-items: center; gap: 8px;
    }
    .support-btn {
        width: 100%; background-color: white; border: 1px solid #dddddd;
        border-radius: 20px; padding: 10px 0; color: #0066cc;
        text-align: center; font-weight: bold; margin-top: 40px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); cursor: default;
    }
    .license-card {
        background-color: #ffffff; padding: 40px; border-radius: 10px;
        border: 1px solid #e0e0e0; box-shadow: 0 8px 16px rgba(0,0,0,0.1);
        text-align: center; max-width: 650px; margin: 40px auto;
    }
    .mid-box {
        background-color: #f8f9fa; padding: 15px; border: 1px dashed #6c757d;
        border-radius: 5px; font-family: monospace; font-size: 1.2em;
        color: #d63384; margin: 20px 0; word-break: break-all;
    }
    .upload-area {
        border: 1px solid #ddd; padding: 20px; border-radius: 8px;
        background-color: #fafafa; text-align: center; margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. 模組載入
# ==============================================================================
try:
    from utils.paths import get_resource_path, get_writable_path
    from utils.localization import t, LANGUAGE_OPTIONS, set_language
    from services.security import verify_license_tier, get_fingerprint_for_ui
    from database.db_manager import init_db, login_user
    from services.auth_service import validate_session, logout_user
    from services.plans import get_plan_config
    
    from ui.login_view import render_login
    from ui.portal_view import render_portal
    from ui.dashboard_view import render_dashboard
    from ui.exam_gen_view import render_exam_generator
    from ui.history_view import render_history
    from ui.settings_view import render_settings
    from ui.admin_view import render_admin
    from ui.my_exams_view import render_my_exams_view
    from ui.question_bank_view import render_question_bank
    
    from utils.styles import apply_mac_style
    import matplotlib.pyplot as plt
except ImportError as e:
    st.error(f"❌ Startup Error: {e}"); st.stop()

LICENSE_PATH = get_writable_path("license.key")
LOGO_PATH = get_writable_path("logo.png")

# ==============================================================================
# 4. OS-Level File Dialog (Native Only - 確保 pywebview 穩定)
# ==============================================================================
def get_native_file(file_extensions=None, prompt="Select File"):
    system = platform.system()
    if system == "Darwin":
        try:
            type_str = ""
            if file_extensions:
                ext_list = ', '.join([f'"{ext}"' for ext in file_extensions])
                type_str = f'of type {{{ext_list}}}'
            script = f'''
            tell application "System Events"
                activate
                set f to choose file with prompt "{prompt}" {type_str}
                return POSIX path of f
            end tell
            '''
            cmd = ['osascript', '-e', script]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                path = result.stdout.decode('utf-8').strip()
                if path: return [path] 
            return None
        except Exception as e:
            st.error(f"System Dialog Error: {e}"); return None
    else:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk(); root.withdraw(); root.wm_attributes('-topmost', 1)
            filetypes = []
            if file_extensions:
                ext_str = " ".join([f"*.{ext}" for ext in file_extensions])
                filetypes.append(("Allowed Files", ext_str))
            filetypes.append(("All Files", "*.*"))
            file_path = filedialog.askopenfilename(title=prompt, filetypes=filetypes)
            root.destroy()
            if file_path: return [file_path]
            return None
        except Exception as e:
            st.error(f"Tkinter Error: {e}"); return None

# ==============================================================================
# 5. 授權與初始化頁面 (100% 多國語系整合)
# ==============================================================================
def render_license_setup(message=""):
    st.markdown(f"""
        <div class="license-card">
            <h2>{t('hdr_license_setup', '🔐 系統授權設定')}</h2>
            <p style="color: #666;">{message if message else t('msg_license_init', '請完成授權以啟動系統。')}</p>
            <div class="mid-box">{get_fingerprint_for_ui()}</div>
            <p><small>{t('msg_copy_mid', '☝️ 請複製上方機器碼提供給客服人員。')}</small></p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown('<div class="upload-area">', unsafe_allow_html=True)
        st.subheader(f"📂 {t('lbl_license_file', '授權檔案')}")
        if st.button(t('btn_select_license', '選取 License'), key="btn_lic_native", type="primary", use_container_width=True):
            files = get_native_file(file_extensions=["key"], prompt=t('btn_select_license'))
            if files:
                shutil.copy(files[0], LICENSE_PATH)
                st.toast(f"✅ {t('msg_license_imported', 'License 已匯入！')}")
                time.sleep(1.5); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="upload-area">', unsafe_allow_html=True)
        st.subheader(f"🖼️ {t('settings_branding_title', '品牌 Logo')}")
        if st.button(t('btn_select_logo', '選取 Logo'), key="btn_logo_native", use_container_width=True):
            files = get_native_file(file_extensions=["png", "jpg"], prompt=t('btn_select_logo'))
            if files:
                shutil.copy(files[0], LOGO_PATH)
                st.toast(f"✅ {t('msg_logo_imported', 'Logo 已匯入！')}")
                time.sleep(1.5); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

def check_license_gatekeeper():
    if not os.path.exists(LICENSE_PATH): return False, "License missing."
    try:
        is_valid, message, plan, title = verify_license_tier(LICENSE_PATH)
        if not is_valid: return False, message
        st.session_state["SYSTEM_PLAN"] = plan
        st.session_state["APP_TITLE"] = title
        if "license_data" not in st.session_state: st.session_state["license_data"] = {"features": []}
        return True, "OK"
    except Exception as e: return False, str(e)

load_dotenv(); init_db()

# ==============================================================================
# 6. 主應用程式邏輯 (四國語言動態驅動)
# ==============================================================================
def main_app():
    is_valid, msg = check_license_gatekeeper()
    if not is_valid: render_license_setup(msg); st.stop()

    if "is_authenticated" not in st.session_state:
        st.session_state.update({"is_authenticated": False, "lang": "zh_tw"})
    
    if not st.session_state["is_authenticated"]:
        render_login(); return

    user = st.session_state["user"]
    user.plan = st.session_state.get("SYSTEM_PLAN", "free")

    if "app_mode" not in st.session_state:
        render_portal(user); return

    app_mode = st.session_state.app_mode

    with st.sidebar:
        st.subheader(f"Hi, {user.real_name or user.username}")
        st.caption("Language / Langue")
        
        # [修復] 動態讀取四國語系選單
        lang_display_names = list(LANGUAGE_OPTIONS.values())
        curr_lang_name = st.session_state.get("language", lang_display_names[0])
        sel_lang = st.selectbox("Lang", lang_display_names, index=lang_display_names.index(curr_lang_name), key="lang_sel", label_visibility="collapsed")
        
        # 反查並更新語系
        reverse_map = {v: k for k, v in LANGUAGE_OPTIONS.items()}
        target_code = reverse_map.get(sel_lang)
        if target_code and target_code != st.session_state.get("lang"):
            set_language(target_code); st.rerun()

        mode_icon = "📝" if app_mode == "creator" else "📈"
        mode_text = t("mode_creator") if app_mode == "creator" else t("mode_grader")
        st.markdown(f'<div class="mode-box">{mode_icon} Mode: {mode_text}</div>', unsafe_allow_html=True)
        
        if st.button(f"🏠 {t('switch_mode')}", use_container_width=True, type="primary"):
            del st.session_state.app_mode
            if "page_selection_clean" in st.session_state: del st.session_state.page_selection_clean
            st.rerun()

        st.markdown("---")
        
        # 選單結構與標籤翻譯
        if app_mode == "creator":
            menu_structure = [
                ("menu_exam_gen", t("menu_exam_gen"), render_exam_generator),
                ("menu_my_exams", t("menu_my_exams"), render_my_exams_view),
                ("menu_bank", t("menu_bank"), render_question_bank),
                ("menu_settings", t("menu_settings"), render_settings),
            ]
            plan_config = get_plan_config(user.plan, st.session_state.get("license_data", {}).get("features", []))
            if getattr(user, "is_admin", False) and plan_config.get("show_admin", False):
                menu_structure.append(("menu_admin", t("menu_admin"), render_admin))
        else:
            menu_structure = [
                ("menu_grading", t("menu_grading"), render_dashboard),
                ("menu_history", t("menu_history"), render_history),
                ("menu_settings", t("menu_settings"), render_settings),
            ]

        # 導覽路由邏輯
        raw_labels = [m[1] for m in menu_structure]
        current_selection = st.session_state.get("page_selection_clean", raw_labels[0])
        if current_selection not in raw_labels: current_selection = raw_labels[0]
            
        display_labels = [f"🔴 {lbl}" if lbl == current_selection else f"⚪ {lbl}" for lbl in raw_labels]
        label_map = {d: m for d, m in zip(display_labels, menu_structure)}
        
        sel = st.radio("Nav", display_labels, index=raw_labels.index(current_selection), label_visibility="collapsed", key="nav_radio")
        selected_item = label_map[sel]
        
        if st.session_state.get("page_selection_clean") != selected_item[1]:
            st.session_state.page_selection_clean = selected_item[1]; st.rerun()

        st.markdown("---")
        # [修復] 登出傳遞 Token 避免缺失錯誤
        if st.button(t("logout"), use_container_width=True, type="secondary"):
            logout_user(st.session_state.get("session_token"))
            st.session_state.update({"is_authenticated": False, "user": None, "session_token": None})
            st.rerun()

        # [Branding] 指定 Footer 格式
        st.markdown(f"""
            <div class="support-btn">
                <div style="font-size: 14px; color: #0066cc; font-weight: bold;">AI Grader for STEM</div>
                <div style="font-size: 10px; color: #718096; margin-top: 2px;">Powered by @2026 Nexora Systems</div>
            </div>
        """, unsafe_allow_html=True)

    selected_item[2](user)

#if __name__ == "__main__":
#    main_app()
def run():
    """ 這就是對外的啟動接口 """
    main_app()

if __name__ == "__main__":
    # 這是為了讓您在本地開發測試時仍能直接執行 python app.py
    run()
