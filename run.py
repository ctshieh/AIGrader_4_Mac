# run.py
import streamlit.web.cli as stcli
import os, sys

def resolve_path(path):
    # PyInstaller 解壓縮後的暫存路徑
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, path)
    return os.path.join(os.getcwd(), path)

if __name__ == "__main__":
    # 設定環境變數，讓 config.py 能找到正確的路徑
    # 注意：編譯後的 exe 會在暫存目錄運行，所以要鎖定路徑
    os.environ["DATA_DIR"] = os.path.join(os.getcwd(), "data")
    os.environ["LICENSE_PATH"] = os.path.join(os.getcwd(), "license.key")
    
    # 指向您的主程式 app.py
    # 這裡假設打包時 app.py 會放在同一層
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("app.py"),
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())
