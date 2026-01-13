# build_cython.py
# -*- coding: utf-8 -*-
# 用途：遞迴掃描專案，將所有核心代碼編譯成 .pyd (C擴充模組)
# 保護等級：最高 (Binary)

import os
import shutil
import glob
from setuptools import setup
from Cython.Build import cythonize
from setuptools.extension import Extension

# 1. 設定要編譯的目錄
# 這些資料夾內的所有 .py 都會被編譯並刪除原始碼
TARGET_DIRS = ["services", "utils", "database", "ui"]

# 2. 設定「絕對不能」編譯的檔案 (入口點)
EXCLUDE_FILES = [
    "app.py",
    "run.py",
    "build_cython.py",
    "keygen.py",
    "setup.py"
]

def get_extensions():
    extensions = []
    for dir_name in TARGET_DIRS:
        # 遞迴搜尋所有 .py 檔案
        for root, _, files in os.walk(dir_name):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    
                    # 略過 __init__.py (保留它通常比較安全，且它通常沒邏輯)
                    if file == "__init__.py":
                        continue
                        
                    # 轉換路徑為模組名稱 (例如 services/security.py -> services.security)
                    module_name = full_path.replace(os.sep, ".").replace(".py", "")
                    
                    print(f"➕ Adding to compilation: {module_name}")
                    extensions.append(Extension(module_name, [full_path]))
    return extensions

# 3. 執行編譯
print("🚀 Starting Cython compilation...")
setup(
    name="MathGraderPro_Full_Protect",
    ext_modules=cythonize(
        get_extensions(),
        compiler_directives={'language_level': "3", 'always_allow_keywords': True},
        annotate=False
    ),
    script_args=["build_ext", "--inplace"]
)

# 4. 清理與銷毀原始碼
print("\n🧹 Cleaning up source files...")

for dir_name in TARGET_DIRS:
    for root, _, files in os.walk(dir_name):
        for file in files:
            full_path = os.path.join(root, file)
            
            # A. 處理 .py 檔
            if file.endswith(".py") and file != "__init__.py":
                # 檢查是否已生成對應的 .pyd
                base_name = file.replace(".py", "")
                pyd_found = False
                for f in os.listdir(root):
                    # Windows 編譯出來的檔名通常是 module.cp311-win_amd64.pyd
                    if f.startswith(base_name) and f.endswith(".pyd"):
                        pyd_found = True
                        # 改名為標準名稱 (例如 services.cp311... -> services.pyd)
                        clean_pyd = f"{base_name}.pyd"
                        old_pyd_path = os.path.join(root, f)
                        new_pyd_path = os.path.join(root, clean_pyd)
                        
                        if old_pyd_path != new_pyd_path:
                            if os.path.exists(new_pyd_path): os.remove(new_pyd_path)
                            os.rename(old_pyd_path, new_pyd_path)
                        break
                
                if pyd_found:
                    os.remove(full_path) # ❌ 刪除原始 .py
                    print(f"🔒 Encrypted & Deleted: {full_path}")
                else:
                    print(f"⚠️ Warning: Compilation failed for {full_path}, keeping source.")

            # B. 刪除編譯過程產生的 .c 檔
            if file.endswith(".c"):
                os.remove(full_path)

# 刪除 build 暫存資料夾
if os.path.exists("build"):
    shutil.rmtree("build")

print("\n✅ Full compilation complete. Your algorithms are safe.")
