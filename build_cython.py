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
                    # 轉換為模組路徑 (如 services.auth_service)
                    module_name = full_path.replace(os.sep, ".").replace(".py", "")
                    extensions.append(Extension(module_name, [full_path]))
    return extensions

print(f">>> Starting Cython compilation for Python {sys.version.split()[0]}...")

# 2. 執行編譯
setup(
    ext_modules=cythonize(
        get_extensions(),
        compiler_directives={'language_level': "3", 'always_allow_keywords': True},
        annotate=False
    ),
    script_args=["build_ext", "--inplace"]
)

# 3. 清理與重命名 (處理 cpython-313-darwin.so 命名問題)
print("\n>>> Cleaning up and protecting source code...")
for dir_name in TARGET_DIRS:
    for root, _, files in os.walk(dir_name):
        for file in files:
            # 尋找編譯出的檔案 (包含 Python 3.13 的後綴)
            if file.endswith(EXT_SUFFIX) and ("cpython-313" in file or "cp313" in file):
                # 取得原始檔名 (例如 auth_service.cpython-313-darwin.so -> auth_service)
                base_name = file.split('.')[0]
                new_name = base_name + EXT_SUFFIX
                old_path = os.path.join(root, file)
                new_path = os.path.join(root, new_name)

                # 重新命名為簡潔檔名，方便程式調用
                if os.path.exists(new_path): os.remove(new_path)
                os.rename(old_path, new_path)
                
                # 銷毀對應的原始 .py 檔
                py_source = os.path.join(root, base_name + ".py")
                if os.path.exists(py_source):
                    os.remove(py_source)
                    print(f"[SECURE] Compiled & Deleted: {py_source}")

# 刪除編譯過程中產生的中間檔
if os.path.exists("build"): shutil.rmtree("build")
for root, _, files in os.walk("."):
    for f in files:
        if f.endswith(".c"): os.remove(os.path.join(root, f))

print("\n[DONE] Python 3.13 Compilation Complete.")
