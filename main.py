# main.py
import sys
import os
import streamlit as st

# --- [核心修正] 確保能找到編譯後的 .so / .pyd 模組 ---
def add_bundler_path():
    # 1. 取得 PyInstaller 解壓路徑或當前執行路徑
    bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    
    # 2. 強制將路徑插入 sys.path 最前端
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)
    
    # 3. 處理 Mac 打包時 Frameworks 內的 _internal 資料夾
    internal_dir = os.path.join(bundle_dir, "_internal")
    if os.path.exists(internal_dir) and internal_dir not in sys.path:
        sys.path.insert(0, internal_dir)
    
    # 4. [最重要] 同步更新環境變數 PYTHONPATH
    # 這能確保 Streamlit 的內部 ScriptRunner 也能正確搜尋到 app.so
    os.environ["PYTHONPATH"] = bundle_dir + os.pathsep + os.environ.get("PYTHONPATH", "")

# 執行路徑修補
add_bundler_path()
# --------------------------------------------------

# 現在可以安全地匯入已編譯的 app 模組了
try:
    import app 
except ImportError as e:
    # 假如還是失敗，列出路徑供 debug
    print(f"❌ ModuleNotFoundError: {e}")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)

if __name__ == "__main__":
    # 呼叫您在 app.py 中定義的 run() 函數
    app.run()
