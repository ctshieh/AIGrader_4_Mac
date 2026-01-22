# AIGrader.spec
# -*- mode: python ; coding: utf-8 -*-
# 修正版：加入 safe_copy_metadata 防止 PackageNotFoundError
import sys
import os
import glob
from PyInstaller.utils.hooks import copy_metadata, collect_all

# ==============================================================================
# 0. 輔助函數：安全抓取 Metadata (有就抓，沒有就跳過)
# ==============================================================================
def safe_copy_metadata(package_name):
    try:
        print(f"🔍 Checking metadata for: {package_name}")
        return copy_metadata(package_name)
    except Exception as e:
        print(f"⚠️ Skipping metadata for {package_name}: Package not found (this is usually fine).")
        return []

datas = []
binaries = []
hidden_imports = []

# ==============================================================================
# 1. 核心與 GUI 組件 (強制收集)
# ==============================================================================
# Streamlit 本體
tmp_ret = collect_all('streamlit')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hidden_imports += tmp_ret[2]

# Streamlit 第三方組件 (必須 collect_all)
tmp_ret = collect_all('streamlit_option_menu')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hidden_imports += tmp_ret[2]

tmp_ret = collect_all('extra_streamlit_components')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hidden_imports += tmp_ret[2]

# ==============================================================================
# 2. AI 大腦 Metadata (使用安全模式)
# ==============================================================================
# 這裡改用 safe_copy_metadata，避免沒安裝舊版時報錯
datas += safe_copy_metadata('google-genai')        # 新版 SDK
datas += safe_copy_metadata('google-generativeai') # 舊版 SDK
datas += safe_copy_metadata('google-api-core')
datas += safe_copy_metadata('google-auth')
datas += safe_copy_metadata('openai')

# ==============================================================================
# 3. 其他必要 Metadata
# ==============================================================================
datas += safe_copy_metadata('tqdm')
datas += safe_copy_metadata('regex')
datas += safe_copy_metadata('requests')
datas += safe_copy_metadata('packaging')
datas += safe_copy_metadata('filelock')
datas += safe_copy_metadata('numpy')
datas += safe_copy_metadata('scipy')
datas += safe_copy_metadata('sqlalchemy')
datas += safe_copy_metadata('reportlab')
datas += safe_copy_metadata('plotly')

# ==============================================================================
# 4. 核心程式碼收集 (不刪檔安全模式)
# ==============================================================================
datas += [('app.py', '.')]

# 自動抓取 .so 和 .py
target_patterns = [
    'app_core*.so', 'app_core.py',
    'config*.so', 'config.py'
]

for pattern in target_patterns:
    for f in glob.glob(pattern):
        print(f"📦 Adding Core File: {f}")
        datas += [(f, '.')]

# 收集子模組資料夾
module_dirs = ['ui', 'services', 'database', 'utils']
for mod in module_dirs:
    if os.path.exists(mod):
        datas += [(mod, mod)]

if os.path.exists('utils/locales'):
    datas += [('utils/locales', 'utils/locales')]

# ==============================================================================
# 5. 隱藏導入清單
# ==============================================================================
hidden_imports += [
    # [1] AI 核心
    'google.genai', 'google.generativeai', 'google.ai', 
    'google.api_core', 'google.auth', 'openai',

    # [2] 介面與系統
    'config', 'streamlit', 'pywebview',
    'streamlit_option_menu', 'extra_streamlit_components',

    # [3] 數學與數據
    'numpy', 'pandas', 'sympy', 'scipy', 
    'scipy.special', 'scipy.integrate', 'scipy.optimize', 
    'scipy.spatial.transform._rotation_groups',

    # [4] 影像與 OCR
    'cv2', # opencv-python-headless
    'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont',
    'pytesseract', 'qrcode',

    # [5] PDF 與報表
    'pypdf', 'pdf2image', 'reportlab', 
    'reportlab.pdfgen', 'reportlab.platypus', 
    'xlsxwriter',

    # [6] 安全與基礎架構
    'sqlalchemy', 'sqlalchemy.dialects.sqlite',
    'bcrypt', 'cryptography', 'dotenv', 'pytz',

    # [7] 圖表分析
    'matplotlib', 'matplotlib.pyplot', 
    'seaborn', 
    'plotly', 'plotly.express', 'plotly.graph_objects',

    # [基礎依賴]
    'email.mime', 'email.mime.multipart', 'email.mime.text', 
    'email.mime.base', 'email.mime.image', 'email.mime.application', 
    'email.utils', 'email.header',
    'streamlit.web.cli', 'engineio.async_drivers.threading',
    'sqlite3', 'watchdog.observers', 'jinja2', 'smmap', 'requests'
]

# ==============================================================================
# 6. 排除項目
# ==============================================================================
excludes = [
    'PyQt6', 'PyQt5', 'PySide6', 'PySide2', 'tkinter', 
    'IPython', 'notebook', 'nbconvert', 
]

# ==============================================================================
# 7. 建置設定
# ==============================================================================
block_cipher = None

a = Analysis(
    ['run_native.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AI Grader Pro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True, # Debug Mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AI Grader Pro',
)

app = BUNDLE(
    coll,
    name='AI Grader Pro.app',
    icon='assets/app_logo.icns',
    bundle_identifier='com.Nexora_System.aigrader',
    info_plist={
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '20260120',
        'NSHumanReadableCopyright': 'Copyright © 2026  C.T. Shieh. All rights reserved.',
        'LSMinimumSystemVersion': '13.0.0',
        'NSHighResolutionCapable': 'True',
        'NSRequiresAquaSystemAppearance': 'False', 
    }
)
