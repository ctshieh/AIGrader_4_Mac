# fix_db.py
# 用於修復資料庫缺少的欄位
import sqlite3
import os

DB_FILE = "math_grader.db"

def fix_database():
    if not os.path.exists(DB_FILE):
        print(f"❌ 找不到資料庫檔案: {DB_FILE}")
        return

    print(f"🔧 正在修復資料庫: {DB_FILE} ...")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 需要補上的新欄位
    new_columns = [
        ("academic_year", "TEXT"),
        ("semester", "TEXT"),
        ("exam_type", "TEXT")
    ]
    
    success_count = 0
    
    for col_name, col_type in new_columns:
        try:
            print(f"   -> 嘗試新增欄位 '{col_name}'...", end=" ")
            cursor.execute(f"ALTER TABLE exams ADD COLUMN {col_name} {col_type}")
            print("✅ 成功")
            success_count += 1
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠️ 已存在 (跳過)")
            else:
                print(f"❌ 失敗: {e}")
                
    conn.commit()
    conn.close()
    
    print("-" * 30)
    print(f"🎉 修復完成！新增了 {success_count} 個欄位。")
    print("現在您可以重新啟動 Streamlit 了。")

if __name__ == "__main__":
    fix_database()
