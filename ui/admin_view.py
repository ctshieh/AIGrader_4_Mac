# ui/admin_view.py
# -*- coding: utf-8 -*-
# Module-Version: v2026.01.13-Admin-Business-Only

import streamlit as st
import pandas as pd
from database.db_manager import get_all_users, update_user, get_all_usage_stats, User
from utils.localization import t

def render_admin(user: User):
    """
    機構版管理員後台 (Business Admin View)
    專門用於管理內部員工與查看機構用量。
    """
    st.title(f"🛡️ {t('admin_title')}")
    
    if not user or not user.is_admin:
        st.error(t("warn_admin_only"))
        return

    # Tabs: 統計 | 用戶管理
    tab1, tab2 = st.tabs([f"📊 {t('admin_tab_stats')}", f"👥 {t('admin_tab_users')}"])

    # --- Tab 1: 機構用量統計 ---
    with tab1:
        st.subheader(f"💰 {t('admin_stats_usage_title')}")
        try:
            usage_df = get_all_usage_stats()
            if not usage_df.empty:
                # 簡單的統計指標
                total_jobs = usage_df['job_count'].sum()
                st.metric("Total Jobs Processed", total_jobs)
                st.dataframe(usage_df, width='stretch')
            else:
                st.info(t("admin_stats_no_data"))
        except Exception as e:
            st.error(f"Error loading stats: {e}")

    # --- Tab 2: 內部員工管理 ---
    with tab2:
        st.subheader(f"👥 {t('admin_user_mgmt_title')}")
        st.caption("您可在此核准內部員工帳號，並分配閱卷額度。")
        
        users = get_all_users()
        if not users:
            st.warning(t("admin_no_data"))
            return

        # 顯示用戶列表
        df = pd.DataFrame(users)
        valid_cols = [c for c in ["id", "username", "real_name", "email", "plan", "custom_page_limit", "is_approved"] if c in df.columns]
        st.dataframe(df[valid_cols], width='stretch', hide_index=True)

        st.markdown("---")
        st.markdown(f"### ✏️ {t('admin_user_edit_status')}")
        
        user_opts = {u['id']: f"{u['username']} ({u['real_name']})" for u in users}
        selected_uid = st.selectbox(t("admin_user_select_label"), options=list(user_opts.keys()), format_func=lambda x: user_opts[x])
        
        if selected_uid:
            target = next((u for u in users if u['id'] == selected_uid), None)
            if target:
                with st.form(key=f"edit_u_{selected_uid}"):
                    c1, c2 = st.columns(2)
                    
                    # 核准開關
                    new_appr = c1.checkbox(t("admin_user_approved"), value=bool(target.get('is_approved')))
                    
                    # 方案選擇 (限制在 Personal / Business)
                    plan_list = ["personal", "business"]
                    curr_plan = target.get('plan', 'personal')
                    if curr_plan not in plan_list: plan_list.append(curr_plan)
                    
                    new_plan = c2.selectbox(t("admin_user_plan_label"), plan_list, index=plan_list.index(curr_plan))
                    
                    st.markdown("#### 配額分配 (Quota Allocation)")
                    st.caption("設定每週可閱卷的頁數上限 (僅對 Business 方案生效)")
                    
                    c_page_limit = st.number_input("Custom Page Limit (Weekly)", value=int(target.get('custom_page_limit') or 0))
                    
                    # 只有切換成 Business 才能開 Admin 權限 (給副主任之類的)
                    new_adm = False
                    if new_plan == "business":
                        st.divider()
                        new_adm = st.checkbox("授予管理員權限 (Is Admin?)", value=bool(target.get('is_admin')), help="勾選後，該用戶也能進入此後台。")

                    if st.form_submit_button(t("admin_user_update_btn"), type="primary"):
                        success = update_user(
                            selected_uid, 
                            is_approved=new_appr,
                            plan=new_plan,
                            is_admin=new_adm,
                            custom_page_limit=c_page_limit
                        )
                        if success:
                            st.success(t("admin_user_update_success").format(username=target['username']))
                            st.rerun()
