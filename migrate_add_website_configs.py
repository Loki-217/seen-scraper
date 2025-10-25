#!/usr/bin/env python3
"""
数据库迁移：添加 website_configs 表

用于缓存智能识别的网站配置
"""
import sqlite3
import sys
import os


def migrate():
    """执行迁移"""
    db_path = "seen.db"

    if not os.path.exists(db_path):
        print(f"✓ 数据库文件 {db_path} 不存在")
        print("提示: 首次启动应用时会自动创建数据库和所有表")
        return True

    print(f"连接到数据库: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 检查表是否已存在
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='website_configs'
        """)

        if cursor.fetchone():
            print("✓ 表 website_configs 已存在，无需迁移")
            return True

        print("创建表 website_configs...")

        cursor.execute("""
            CREATE TABLE website_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- 网站标识
                domain VARCHAR(200) NOT NULL,
                url_pattern VARCHAR(500),
                site_name VARCHAR(100),

                -- 识别结果
                site_type VARCHAR(50),
                load_type VARCHAR(50) NOT NULL,

                -- 配置（JSON 格式）
                config_json TEXT NOT NULL,

                -- AI 分析
                ai_reasoning TEXT,
                confidence REAL,
                source VARCHAR(20),

                -- 统计信息
                success_count INTEGER DEFAULT 0 NOT NULL,
                fail_count INTEGER DEFAULT 0 NOT NULL,
                last_used_at DATETIME,

                -- 时间戳
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX idx_domain ON website_configs(domain)
        """)

        cursor.execute("""
            CREATE INDEX idx_url_pattern ON website_configs(url_pattern)
        """)

        conn.commit()
        print("✓ 迁移成功！website_configs 表已创建")
        return True

    except Exception as e:
        print(f"✗ 迁移失败: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("数据库迁移：添加智能网站识别缓存表")
    print("=" * 60)
    print()

    success = migrate()

    print()
    print("=" * 60)
    if success:
        print("✓ 迁移完成")
        print()
        print("说明：")
        print("- website_configs 表用于缓存智能识别的网站配置")
        print("- 下次访问相同网站时会直接使用缓存，无需重新分析")
        print("- 可以大大提高响应速度并节省 AI API 调用成本")
    else:
        print("✗ 迁移失败")
        print()
        print("请检查错误信息并重试")

    print("=" * 60)

    sys.exit(0 if success else 1)
