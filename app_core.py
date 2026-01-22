# app_core.py
# -*- coding: utf-8 -*-
# 🚀 雙效優化版：
# 1. 啟動加速 (Lazy Import)
# 2. 視覺優化 (紅色按鈕 -> 活力天空藍)

import streamlit as st
import sys
import os
import time
import shutil
import platform
import subprocess
from dotenv import load_dotenv

# ==============================================================================
# 1. 輕量級全域變數
# ==============================================================================
from utils.paths import get_resource_path, get_writable_path

LICENSE_PATH = get_writable_path("license.key")
LOGO_PATH = get_writable_path("logo.png")

# ==============================================================================
# 2. 輔助函式
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
    return None

def render_license_setup(message=""):
    from services.security import get_fingerprint_for_ui
    from utils.localization import t

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
        from services.security import verify_license_tier
        is_valid, message, plan, title = verify_license_tier(LICENSE_PATH)
        if not is_valid: return False, message
        st.session_state["SYSTEM_PLAN"] = plan
        st.session_state["APP_TITLE"] = title
        if "license_data" not in st.session_state: st.session_state["license_data"] = {"features": []}
        return True, "OK"
    except Exception as e: return False, str(e)

# ==============================================================================
# 3. 主邏輯入口 (CSS 注入點)
# ==============================================================================
def run_app_logic():
    st.set_page_config(
        page_title="AI Grader for STEM", 
        page_icon="📝", 
        layout="wide", 
        initial_sidebar_state="expanded" 
    )

    # 🎨【視覺優化】注入 CSS 修改按鈕顏色
    st.markdown("""
        <style>
        /* 1. 側邊欄樣式 */
        [data-testid="stSidebar"] { color: #333333 !important; background-color: #FAFAFA; }
        
        /* 2. 🔵 將所有 Primary 按鈕 (原本紅色) 改為 活力天空藍 (#007AFF) */
        div.stButton > button[kind="primary"] {
            background-color: #007AFF !important;
            border-color: #007AFF !important;
            color: white !important;
            font-weight: bold !important;
            transition: all 0.2s ease-in-out;
        }
        /* 滑鼠懸停時的效果 (稍微變深) */
        div.stButton > button[kind="primary"]:hover {
            background-color: #0056b3 !important;
            border-color: #0056b3 !important;
            box-shadow: 0 4px 8px rgba(0,122,255,0.3);
        }
        /* 點擊時的效果 */
        div.stButton > button[kind="primary"]:active {
            background-color: #004494 !important;
            border-color: #004494 !important;
        }

        /* 3. 其他樣式 */
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

    # 4. 🚀【惰性載入】這裡才 Import 重型庫 (加速啟動)
    from database.db_manager import init_db
    from services.auth_service import logout_user
    from services.plans import get_plan_config
    from utils.localization import t, LANGUAGE_OPTIONS, set_language
    
    from ui.login_view import render_login
    from ui.portal_view import render_portal
    from ui.dashboard_view import render_dashboard
    from ui.exam_gen_view import render_exam_generator
    from ui.history_view import render_history
    from ui.settings_view import render_settings
    from ui.admin_view import render_admin
    from ui.my_exams_view import render_my_exams_view
    from ui.question_bank_view import render_question_bank

    load_dotenv()
    init_db()

    is_valid, msg = check_license_gatekeeper()
    if not is_valid: 
        render_license_setup(msg)
        st.stop() 

    if "is_authenticated" not in st.session_state:
        st.session_state.update({"is_authenticated": False, "lang": "zh_tw"})
    
    if not st.session_state["is_authenticated"]:
        render_login()
        return

    user = st.session_state["user"]
    user.plan = st.session_state.get("SYSTEM_PLAN", "free")

    if "app_mode" not in st.session_state:
        render_portal(user)
        return

    app_mode = st.session_state.app_mode

    with st.sidebar:
        st.subheader(f"Hi, {user.real_name or user.username}")
        
        # 使用 LANGUAGE_OPTIONS 生成選單
        lang_display_names = list(LANGUAGE_OPTIONS.values())
        curr_lang_name = st.session_state.get("language", lang_display_names[0])
        
        # 容錯：如果當前語言不在列表中，預設回第一個
        if curr_lang_name not in lang_display_names:
            curr_lang_name = lang_display_names[0]
            
        sel_lang = st.selectbox("Lang", lang_display_names, index=lang_display_names.index(curr_lang_name), key="lang_sel", label_visibility="collapsed")
        
        reverse_map = {v: k for k, v in LANGUAGE_OPTIONS.items()}
        target_code = reverse_map.get(sel_lang)
        if target_code and target_code != st.session_state.get("lang"):
            set_language(target_code); st.rerun()

        mode_icon = "📝" if app_mode == "creator" else "📈"
        mode_text = t("mode_creator") if app_mode == "creator" else t("mode_grader")
        st.markdown(f'<div class="mode-box">{mode_icon} Mode: {mode_text}</div>', unsafe_allow_html=True)
        
        # 這裡的 type="primary" 現在會變成藍色
        if st.button(f"🏠 {t('switch_mode')}", use_container_width=True, type="primary"):
            del st.session_state.app_mode
            if "page_selection_clean" in st.session_state: del st.session_state.page_selection_clean
            st.rerun()

        st.markdown("---")
        
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
        if st.button(t("logout"), use_container_width=True, type="secondary"):
            logout_user(st.session_state.get("session_token"))
            st.session_state.update({"is_authenticated": False, "user": None, "session_token": None})
            st.rerun()

        st.markdown(f"""
            <div class="support-btn">
                <div style="font-size: 14px; color: #0066cc; font-weight: bold;">AI Grader for STEM</div>
                <div style="font-size: 10px; color: #718096; margin-top: 2px;">Powered by @2026 Nexora Systems</div>
            </div>
        """, unsafe_allow_html=True)

    selected_item[2](user)
