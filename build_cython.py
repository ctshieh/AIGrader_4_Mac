# build_cython.py
import os
import shutil
import platform
import sys
from setuptools import setup
from Cython.Build import cythonize
from setuptools.extension import Extension

# 1. 設定要編譯的目錄
TARGET_DIRS = ["services", "utils", "database", "ui"]
EXCLUDE_FILES = ["main.py","run_native.py", "run.py", "build_cython.py", "setup.py", "__init__.py"]

# 根據系統決定擴展名
IS_WINDOWS = platform.system() == "Windows"
EXT_SUFFIX = ".pyd" if IS_WINDOWS else ".so"

def get_extensions():
    extensions = []
    for dir_name in TARGET_DIRS:
        for root, _, files in os.walk(dir_name):
            for file in files:
                if file.endswith(".py") and file not in EXCLUDE_FILES:
                    full_path = os.path.join(root, file)
                    module_name = full_path.replace(os.sep, ".").replace(".py", "")
                    extensions.append(Extension(module_name, [full_path]))
    return extensions

print(f">>> Starting Cython compilation for Python {sys.version.split()[0]}...")

# 2. 執行編譯 (加入關鍵的 binding 指令)
setup(
    ext_modules=cythonize(
        get_extensions(),
        compiler_directives={
            'language_level': "3", 
            'always_allow_keywords': True,
            'binding': True  # 👈 修正：這能解決 UI 檔案編譯失敗的問題
        },
        annotate=False
    ),
    script_args=["build_ext", "--inplace"]
)

# 3. 僅進行重新命名，不再刪除原始碼
print("\n>>> Organizing compiled binary files...")
for dir_name in TARGET_DIRS:
    for root, _, files in os.walk(dir_name):
        for file in files:
            if file.endswith(EXT_SUFFIX) and ("cpython-313" in file or "cp313" in file):
                base_name = file.split('.')[0]
                new_name = base_name + EXT_SUFFIX
                old_path = os.path.join(root, file)
                new_path = os.path.join(root, new_name)

                if os.path.exists(new_path): os.remove(new_path)
                os.rename(old_path, new_path)
                
                # [MODIFIED] 已移除 os.remove(py_source) 邏輯，保留本地原始碼
                print(f"[SUCCESS] Compiled: {base_name}{EXT_SUFFIX}")

# 刪除編譯過程中產生的中間檔 (.c)
if os.path.exists("build"): shutil.rmtree("build")
for root, _, files in os.walk("."):
    for f in files:
        if f.endswith(".c"): os.remove(os.path.join(root, f))

print("\n[DONE] Full compilation complete. Your source files are safe.")

