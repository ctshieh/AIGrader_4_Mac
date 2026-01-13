# ui/settings_view.py
# -*- coding: utf-8 -*-
# Module-Version: 18.0.3 (DRY Architecture: Uses shared LANGUAGE_OPTIONS)

import streamlit as st
import os
# [優化] 直接從 localization 引入語言選項，不再重複定義
from utils.localization import t, set_language, LANGUAGE_OPTIONS
from database.db_manager import update_user, User

def render_settings(user: User):
    """
    渲染設定頁面
    1. 一般設定 (語言) - 所有人可見
    2. 機構品牌設定 (Logo/URL/Running Head) - 僅 Business 用戶可見
    3. 系統維護 (清除暫存) - 所有人可見
    """
    
    st.title(f"⚙️ {t('menu_settings')}")

    # =========================================================
    # 1. 一般設定 (General Settings)
    # =========================================================
    with st.expander(f"🌐 {t('settings_general')}", expanded=True):
        
        # 取得當前語言代碼 (預設 zh_tw)
        current_lang_code = st.session_state.get('lang', 'zh_tw')
        
        # 防呆：確保 current_lang_code 在選項內，否則預設第一個
        # (因為 LANGUAGE_OPTIONS 是來自 localization.py 的 Single Source of Truth)
        lang_keys = list(LANGUAGE_OPTIONS.keys())
        try:
            current_index = lang_keys.index(current_lang_code)
        except ValueError:
            current_index = 0

        # 語言選擇選單
        sel_lang_code = st.selectbox(
            t('lbl_language'), 
            options=lang_keys, 
            format_func=lambda x: LANGUAGE_OPTIONS[x], # 直接從共用字典取值顯示
            index=current_index
        )
        
        # 如果語言改變，寫入 Session 並重新執行
        if sel_lang_code != current_lang_code:
            set_language(sel_lang_code)
            st.rerun()

    # =========================================================
    # 2. 機構專屬設定 (Branding) - 僅 Business Plan 可見
    # =========================================================
    # 嚴格檢查 Session 中的授權方案 (由 app.py 的 Gatekeeper 寫入)
    current_plan = st.session_state.get("SYSTEM_PLAN", "personal")
    
    if current_plan == "business":
        with st.expander(f"🏢 {t('settings_branding_title')} (Business Only)", expanded=False):
            st.info(t('settings_branding_hint'))
            
            c1, c2 = st.columns([1, 1])
            
            # --- Column 1: Logo 上傳 ---
            with c1:
                st.subheader("Logo Image")
                
                # 確保 assets 資料夾存在 (Windows 相容路徑)
                base_dir = os.getcwd()
                assets_dir = os.path.join(base_dir, "assets")
                if not os.path.exists(assets_dir):
                    os.makedirs(assets_dir)
                
                # 定義全域 Logo 路徑 (覆蓋既有檔案)
                global_logo_path = os.path.join(assets_dir, "branding_logo.png")

                # 顯示目前的 Logo
                if os.path.exists(global_logo_path):
                    st.image(global_logo_path, caption=t('current_logo', default="Current Logo"), width=150)
                
                # 檔案上傳器
                uploaded_logo = st.file_uploader(t('lbl_upload_logo'), type=['png', 'jpg', 'jpeg'])
                
                if uploaded_logo:
                    # 1. 寫入實體檔案 (供 Login/Sidebar 讀取)
                    with open(global_logo_path, "wb") as f:
                        f.write(uploaded_logo.getbuffer())
                    
                    # 2. 更新資料庫路徑 (供 PDF 生成服務讀取)
                    update_user(user.id, branding_logo_path=global_logo_path)
                    
                    st.success(t('msg_save_success'))
                    st.rerun()

            # --- Column 2: 文字設定 (URL & Running Head) ---
            with c2:
                st.subheader("Marketing & Header")
                
                # 讀取現有值
                curr_url = getattr(user, 'custom_advertising_url', "") or ""
                curr_header = getattr(user, 'custom_header_text', "") or ""
                
                # 輸入框
                new_url = st.text_input(t('lbl_marketing_url'), value=curr_url, placeholder="https://...")
                new_header = st.text_input(t('lbl_running_head'), value=curr_header, placeholder="e.g. 2026 Spring Exam")

                # 儲存按鈕
                if st.button(t('btn_save_branding')):
                    if update_user(user.id, custom_advertising_url=new_url, custom_header_text=new_header):
                        st.success(t('msg_save_success'))
                        st.rerun()
    
    # =========================================================
    # 3. 資料維護 (Maintenance) - 所有人可見
    # =========================================================
    with st.expander(f"🧹 {t('settings_maintenance')}", expanded=False):
        st.warning(t('warn_maintenance'))
        
        c_m1, c_m2 = st.columns(2)
        
        # 按鈕 1: 清除上傳暫存
        if c_m1.button(t('btn_clear_uploads')):
            folder = os.path.join(os.getcwd(), "uploaded_files")
            if os.path.exists(folder):
                try:
                    count = 0
                    for filename in os.listdir(folder):
                        file_path = os.path.join(folder, filename)
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                            count += 1
                    st.toast(f"✅ Cleared {count} files from uploads.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.toast("✅ Upload folder is empty.")
        
        # 按鈕 2: 清除輸出暫存 (Output)
        if c_m2.button(t('btn_clear_outputs')):
             # 假設輸出在 output 資料夾
            folder = os.path.join(os.getcwd(), "output")
            if os.path.exists(folder):
                try:
                    count = 0
                    for filename in os.listdir(folder):
                        file_path = os.path.join(folder, filename)
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                            count += 1
                    st.toast(f"✅ Cleared {count} files from output.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                 st.toast("✅ Output folder is empty.")

    # 頁尾資訊
    st.markdown("---")
    plan_display = user.plan.upper() if user.plan else "UNKNOWN"
    st.caption(f"User ID: {user.id} | Plan: {plan_display} | System: Release V1.0")
