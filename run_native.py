# run_native.py
# -*- coding: utf-8 -*-
import sys
import os
import socket
import threading
import time
import webview
import traceback
import signal
import requests # 用於偵測服務狀態
from streamlit.web import cli as stcli

# ==============================================================================
# 1. 環境變數設定
# ==============================================================================
os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
os.environ["STREAMLIT_SERVER_ADDRESS"] = "127.0.0.1"

def get_free_port():
    """ 獲取閒置 Port """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def wait_for_server(url, timeout=10):
    """
    🚀 極速啟動偵測：主動檢查 Streamlit 是否已就緒
    不再傻傻等待固定秒數，只要伺服器一回應，視窗馬上開。
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # 嘗試連線，只要有回應 (即使是 404) 都代表 Server 活著
            requests.head(url, timeout=0.5)
            return True
        except requests.exceptions.ConnectionError:
            time.sleep(0.1) # 每 0.1 秒檢查一次
            continue
    return False

def run_streamlit_thread(port, script_path):
    sys.argv = [
        "streamlit",
        "run",
        script_path,
        f"--server.port={port}",
        "--server.headless=true",
        "--server.address=127.0.0.1",
        "--global.developmentMode=false",
    ]

    # 屏蔽信號 (防止與 Webview 衝突)
    original_signal = signal.signal
    def dummy_signal(signum, handler): pass 
    signal.signal = dummy_signal

    try:
        stcli.main()
    except SystemExit:
        pass 
    except Exception as e:
        log_path = os.path.join(os.path.expanduser("~"), "Desktop", "streamlit_crash.log")
        with open(log_path, "w") as f:
            f.write(traceback.format_exc())
    finally:
        signal.signal = original_signal

def start_app():
    # 1. 路徑校準
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    main_script = os.path.join(base_dir, "app.py")
    
    if not os.path.exists(main_script):
        webview.create_window("Fatal Error", html=f"<h1>Error</h1><p>Missing: {main_script}</p>")
        webview.start()
        return

    port = get_free_port()
    target_url = f"http://127.0.0.1:{port}"

    # --- 2. 啟動 Streamlit (背景) ---
    t = threading.Thread(target=run_streamlit_thread, args=(port, main_script))
    t.daemon = True 
    t.start()

    # --- 3. 🚀 智慧等待 (取代 time.sleep) ---
    # 偵測到 Port 通了才開視窗
    if wait_for_server(target_url):
        # 額外給 0.5 秒讓頁面渲染完成，避免看到全白瞬間
        time.sleep(0.5) 
        
        window = webview.create_window(
            "AI Grader Pro", 
            target_url,
            width=1280, height=800,
            confirm_close=True,
            text_select=True
        )
        webview.start()
    else:
        webview.create_window("Error", html="<h1>Timeout</h1><p>Server failed to start.</p>")
        webview.start()

if __name__ == "__main__":
    start_app()
