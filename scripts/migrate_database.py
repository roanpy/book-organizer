#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本 - 将旧的分离数据库合并为统一数据库

用法: python scripts/migrate_database.py [数据目录路径]

如果不指定路径，将使用配置文件中的 data_dir 或默认路径
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlite3 import Connection, Cursor


def get_data_dir(db_dir: str | None = None) -> Path:
    """
    获取数据目录路径

    Args:
        db_dir: 用户指定的数据目录，如果为 None 则从配置读取

    Returns:
        数据目录的 Path 对象
    """
    if db_dir:
        return Path(db_dir)

    # 尝试从配置读取
    config_path = Path.home() / ".book_organizer" / "book_organizer_config.json"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
            if data_dir := config.get("data_dir"):
                return Path(data_dir)

    return Path.home() / ".book_organizer"


def create_summaries_table(cursor: Cursor) -> None:
    """创建增强简介表"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enhanced_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            title TEXT,
            author TEXT,
            category TEXT,
            summary_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def create_tocs_table(cursor: Cursor) -> None:
    """创建目录表"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS book_tocs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            file_path TEXT,
            toc_json TEXT NOT NULL,
            extraction_method TEXT,
            entry_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def migrate_summaries(conn: Connection, old_db_path: Path) -> int:
    """
    迁移增强简介数据

    Args:
        conn: 新数据库连接
        old_db_path: 旧数据库路径

    Returns:
        迁移的记录数
    """
    cursor = conn.cursor()
    create_summaries_table(cursor)

    # 使用参数化查询附加数据库
    cursor.execute("ATTACH DATABASE ? AS old_db", (str(old_db_path),))

    cursor.execute("""
        INSERT OR REPLACE INTO enhanced_summaries
        (file_path, filename, title, author, category, summary_json, created_at, updated_at)
        SELECT file_path, filename, title, author, category, summary_json, created_at, updated_at
        FROM old_db.enhanced_summaries
    """)

    cursor.execute("SELECT COUNT(*) FROM enhanced_summaries")
    count: int = cursor.fetchone()[0]

    cursor.execute("DETACH DATABASE old_db")
    conn.commit()

    return count


def migrate_tocs(conn: Connection, old_db_path: Path) -> int:
    """
    迁移目录数据

    Args:
        conn: 新数据库连接
        old_db_path: 旧数据库路径

    Returns:
        迁移的记录数
    """
    cursor = conn.cursor()
    create_tocs_table(cursor)

    # 使用参数化查询附加数据库
    cursor.execute("ATTACH DATABASE ? AS old_db", (str(old_db_path),))

    cursor.execute("""
        INSERT OR REPLACE INTO book_tocs
        (filename, file_path, toc_json, extraction_method, entry_count, created_at, updated_at)
        SELECT filename, file_path, toc_json, extraction_method, entry_count, created_at, updated_at
        FROM old_db.book_tocs
    """)

    cursor.execute("SELECT COUNT(*) FROM book_tocs")
    count: int = cursor.fetchone()[0]

    cursor.execute("DETACH DATABASE old_db")
    conn.commit()

    return count


def backup_old_database(old_path: Path) -> Path:
    """
    备份旧数据库

    Args:
        old_path: 旧数据库路径

    Returns:
        备份文件路径
    """
    backup_path = old_path.with_suffix(".db.backup")
    shutil.move(old_path, backup_path)
    return backup_path


def migrate_databases(db_dir: str | None = None) -> bool:
    """
    执行数据库迁移

    Args:
        db_dir: 数据目录路径，如果为 None 则自动检测

    Returns:
        迁移是否成功
    """
    data_path = get_data_dir(db_dir)
    print(f"数据目录: {data_path}")

    old_summaries_path = data_path / "enhanced_summaries.db"
    old_tocs_path = data_path / "book_tocs.db"
    new_db_path = data_path / "book_data.db"

    # 检查旧数据库是否存在
    has_old_summaries = old_summaries_path.exists()
    has_old_tocs = old_tocs_path.exists()

    if not has_old_summaries and not has_old_tocs:
        print("没有找到旧的数据库文件，无需迁移")
        return True

    print("\n发现旧数据库文件:")
    if has_old_summaries:
        print("  - enhanced_summaries.db")
    if has_old_tocs:
        print("  - book_tocs.db")

    try:
        with sqlite3.connect(new_db_path) as conn:
            # 迁移增强简介
            if has_old_summaries:
                print("\n正在迁移 enhanced_summaries.db...")
                count = migrate_summaries(conn, old_summaries_path)
                print(f"  已迁移 {count} 条增强简介记录")

                backup = backup_old_database(old_summaries_path)
                print(f"  旧数据库已备份到: {backup}")

            # 迁移目录数据
            if has_old_tocs:
                print("\n正在迁移 book_tocs.db...")
                count = migrate_tocs(conn, old_tocs_path)
                print(f"  已迁移 {count} 条目录记录")

                backup = backup_old_database(old_tocs_path)
                print(f"  旧数据库已备份到: {backup}")

        print(f"\n✅ 迁移完成！新数据库: {new_db_path}")
        print("\n旧数据库已备份为 .backup 文件，确认无误后可手动删除")
        return True

    except sqlite3.OperationalError as e:
        if "locked" in str(e):
            print("\n❌ 错误: 数据库被锁定")
            print("请先关闭 Book Organizer 应用，然后重试")
        else:
            print(f"\n❌ 数据库错误: {e}")
        return False

    except OSError as e:
        print(f"\n❌ 文件操作错误: {e}")
        return False


if __name__ == "__main__":
    user_db_dir = sys.argv[1] if len(sys.argv) > 1 else None
    success = migrate_databases(user_db_dir)
    sys.exit(0 if success else 1)
