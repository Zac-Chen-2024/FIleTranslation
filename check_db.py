import sqlite3
import os

db_path = 'NewServer/translation_platform.db'

if os.path.exists(db_path):
    print(f"数据库文件存在: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"数据库中的表: {tables}")
        
        # 如果有users表，检查用户
        if ('users',) in tables:
            cursor.execute("SELECT email, name FROM users")
            users = cursor.fetchall()
            print(f"用户列表: {users}")
        else:
            print("没有找到users表")
        
        conn.close()
        print("数据库检查完成")
    except Exception as e:
        print(f"数据库检查出错: {e}")
else:
    print(f"数据库文件不存在: {db_path}")
