# main.py
# -*- coding: utf-8 -*-
# Description: Streamlit Entry Shell (The Shell)
# 這個檔案必須保持 .py 純文字格式，不能編譯。

import streamlit as st

# [關鍵] 這裡 import app，Python 會自動載入編譯後的 app.so / app.pyd
import app 

if __name__ == "__main__":
    # 呼叫 app 模組內的入口函數
    app.main_app()
