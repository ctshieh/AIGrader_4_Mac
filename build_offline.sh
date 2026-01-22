#!/bin/bash
# build_offline.sh - v2026.01.22
set -e

PROJECT_DIR=$(pwd)
# ⚠️ 關鍵修正：將二進位檔放入一個 Spec 會抓取的目錄 (例如 services/bin)
DIST_BIN="$PROJECT_DIR/services/bin" 

echo "🚀 [Step 1] 初始化封裝環境..."
rm -rf build dist "$DIST_BIN"
mkdir -p "$DIST_BIN/libs"

# 1. 處理 Poppler (配合 Spec 收集 services 目錄)
echo "📦 [Step 2] 提取 Poppler 依賴到 services/bin..."
BREW_PREFIX="/opt/homebrew"
cp "$BREW_PREFIX/bin/pdftoppm" "$DIST_BIN/"
cp "$BREW_PREFIX/bin/pdfinfo" "$DIST_BIN/"

# 使用 dylibbundler 修復路徑
dylibbundler -x "$DIST_BIN/pdftoppm" -b -d "$DIST_BIN/libs" -p @executable_path/../Resources/services/bin/libs/ -of > /dev/null

# 2. 執行 Cython 編譯
echo "⚙️ [Step 3] 執行 Cython 編譯..."
python3 build_cython.py

# 3. 原始碼物理隔離 (瘦身關鍵)
echo "🔐 [Step 4] 移除原始碼以保護智財並縮減體積..."
TARGET_DIRS="services database utils ui"
for dir in $TARGET_DIRS; do
    if [ -d "$dir" ]; then
        # 刪除 .py 僅保留編譯後的 .so
        find "$dir" -name "*.py" ! -name "__init__.py" -delete
        find "$dir" -name "*.c" -delete
    fi
done

# 4. 執行 PyInstaller 封裝
echo "🛠 [Step 5] 執行 PyInstaller (使用 AIGrader.spec)..."
pyinstaller --noconfirm --clean AIGrader.spec

# 5. macOS 簽名
echo "✍️ [Step 6] 執行 Ad-hoc 簽名..."
APP_PATH="dist/AI Grader Pro.app"
xattr -cr "$APP_PATH"
codesign --force --deep --sign - "$APP_PATH"

echo "✅ 封裝完成！"
