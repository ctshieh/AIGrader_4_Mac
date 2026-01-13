# setup_ui.py
import os

# 定義需要建立的檔案及其對應的函式名稱 (與 app.py 呼叫的一致)
ui_files = {
    "login_view.py": "render_login",
    "portal_view.py": "render_portal(user)",
    "dashboard_view.py": "render_dashboard(user)",
    "exam_gen_view.py": "render_exam_generator(user)",
    "solution_editor_view.py": "render_solution_editor",
    "my_exams_view.py": "render_my_exams_view(user)",
    "history_view.py": "render_history(user)",
    "settings_view.py": "render_settings(user)",
    "admin_view.py": "render_admin(user)",
    # "subscription_view.py": "render_subscription_page(user)", # 暫時註解
}

def create_ui_structure():
    base_dir = "ui"
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        print(f"Created directory: {base_dir}")
    
    # 建立 __init__.py
    with open(os.path.join(base_dir, "__init__.py"), "w") as f:
        pass

    for filename, func_sig in ui_files.items():
        path = os.path.join(base_dir, filename)
        if not os.path.exists(path):
            func_name = func_sig.split("(")[0]
            args = func_sig.split("(")[1].replace(")", "") if "(" in func_sig else ""
            
            content = f"""import streamlit as st

def {func_name}({args}):
    st.title("🚧 {filename} Under Construction")
    st.info("此模組尚未實作，請等待後續更新。")
    st.write("Function called: `{func_name}`")
"""
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ Generated: {path}")
        else:
            print(f"⚠️ Skipped (exists): {path}")

    # 建立 services/auth_service.py (這是 app.py 的另一個依賴)
    auth_dir = "services"
    os.makedirs(auth_dir, exist_ok=True)
    auth_path = os.path.join(auth_dir, "auth_service.py")
    if not os.path.exists(auth_path):
        with open(auth_path, "w", encoding="utf-8") as f:
            f.write("""from database.db_manager import login_user, get_user_id_by_session, get_user_by_id, create_session, delete_session
import uuid

def validate_session(token):
    user_id = get_user_id_by_session(token)
    if user_id:
        return get_user_by_id(user_id)
    return None

def logout_user(token):
    delete_session(token)
""")
        print(f"✅ Generated: {auth_path}")

if __name__ == "__main__":
    create_ui_structure()
