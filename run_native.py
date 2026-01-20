# run_native.py
import sys
import os
import threading
import time
import signal
import socket
import webview
from streamlit.web import cli as stcli

def get_resource_path(relative_path):
    """ 取得 PyInstaller 環境下或開發環境下的絕對路徑 """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def patch_signal():
    """ 修正：讓背景線程中的 Streamlit 不再報錯 """
    if threading.current_thread() is not threading.main_thread():
        # 攔截訊號處理，避免背景線程崩潰
        signal.signal = lambda s, f: None

def is_port_open(port):
    """ 偵測 127.0.0.1 的指定端口是否已啟用 """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_streamlit_background():
    """在背景線程啟動 Streamlit Server"""
    patch_signal() 
    
    main_script_path = get_resource_path("main.py")
    
    # [關鍵修正] 確保子進程環境變數包含 main.py 所在的資料夾
    # 這能解決 Streamlit 啟動時找不到 app 模組的問題
    base_dir = os.path.dirname(main_script_path)
    os.environ["PYTHONPATH"] = base_dir + os.pathsep + os.environ.get("PYTHONPATH", "")
    
    sys.argv = [
        "streamlit", 
        "run", 
        main_script_path, 
        "--global.developmentMode=false", 
        "--server.headless=true", 
        "--server.port=8501",
        "--server.address=127.0.0.1",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false"
    ]

    try:
        stcli.main()
    except Exception as e:
        print(f"❌ Streamlit Error: {e}")

def start_app():
    # 1. 啟動背景 Server
    t = threading.Thread(target=start_streamlit_background)
    t.daemon = True 
    t.start()

    # 2. 智能偵測端口 (加速畫面開啟)
    print("⏳ Detecting Streamlit Server (127.0.0.1:8501)...")
    start_time = time.time()
    max_wait = 20  # 最多等待 20 秒
    
    while time.time() - start_time < max_wait:
        if is_port_open(8501):
            print(f"✅ Server ready in {round(time.time() - start_time, 2)}s!")
            break
        time.sleep(0.5) 

    # 3. 開啟 WebView 視窗
    webview.create_window(
        "AI Grader Pro",       
        "http://127.0.0.1:8501", 
        width=1280, 
        height=850,
        resizable=True,
        confirm_close=True,
        text_select=True
    )
    
    webview.start()
    sys.exit(0)

if __name__ == '__main__':
    start_app()
