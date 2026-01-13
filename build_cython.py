# build_cython.py
# -*- coding: utf-8 -*-
# Windows Safe Version: No Emojis to prevent UnicodeEncodeError

import os
import shutil
import glob
from setuptools import setup
from Cython.Build import cythonize
from setuptools.extension import Extension

# 1. 設定要編譯的目錄
TARGET_DIRS = ["services", "utils", "database", "ui"]

# 2. 設定「絕對不能」編譯的檔案
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
        for root, _, files in os.walk(dir_name):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    if file == "__init__.py": continue
                        
                    module_name = full_path.replace(os.sep, ".").replace(".py", "")
                    
                    # [SAFE] Removed Emoji
                    print(f"[+] Adding to compilation: {module_name}")
                    extensions.append(Extension(module_name, [full_path]))
    return extensions

# 3. 執行編譯
# [SAFE] Removed Emoji
print(">>> Starting Cython compilation...")
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
# [SAFE] Removed Emoji
print("\n... Cleaning up source files...")

for dir_name in TARGET_DIRS:
    for root, _, files in os.walk(dir_name):
        for file in files:
            full_path = os.path.join(root, file)
            
            # A. 處理 .py 檔
            if file.endswith(".py") and file != "__init__.py":
                base_name = file.replace(".py", "")
                pyd_found = False
                for f in os.listdir(root):
                    if f.startswith(base_name) and f.endswith(".pyd"):
                        pyd_found = True
                        clean_pyd = f"{base_name}.pyd"
                        old_pyd_path = os.path.join(root, f)
                        new_pyd_path = os.path.join(root, clean_pyd)
                        
                        if old_pyd_path != new_pyd_path:
                            if os.path.exists(new_pyd_path): os.remove(new_pyd_path)
                            os.rename(old_pyd_path, new_pyd_path)
                        break
                
                if pyd_found:
                    os.remove(full_path) 
                    # [SAFE] Removed Emoji
                    print(f"[SECURE] Encrypted & Deleted: {full_path}")
                else:
                    # [SAFE] Removed Emoji
                    print(f"[WARN] Compilation failed for {full_path}, keeping source.")

            # B. 刪除 .c 檔
            if file.endswith(".c"):
                os.remove(full_path)

if os.path.exists("build"):
    shutil.rmtree("build")

# [SAFE] Removed Emoji
print("\n[DONE] Full compilation complete. Your algorithms are safe.")
