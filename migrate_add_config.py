#!/usr/bin/env python3
"""
数据库迁移：为 Job 表添加 config_json 字段
"""
import sqlite3
import sys
import os


def migrate():
    """执行迁移"""
    db_path = "seen.db"

    if not os.path.exists(db_path):
        print(f"错误: 数据库文件 {db_path} 不存在")
        print("提示: 请先启动应用，让它自动创建数据库")
        return False

    print(f"连接到数据库: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(jobs)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'config_json' in columns:
            print("✓ 字段 config_json 已存在，无需迁移")
            return True

        print("添加字段 config_json...")
        cursor.execute("""
            ALTER TABLE jobs
            ADD COLUMN config_json TEXT
        """)

        conn.commit()
        print("✓ 迁移成功！")
        return True

    except Exception as e:
        print(f"✗ 迁移失败: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
