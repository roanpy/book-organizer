#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
转移日志迁移脚本 - 将 Markdown 格式的转移记录导入数据库

用法: python scripts/migrate_transfer_logs.py <path_to_md_file>

此脚本解析 Markdown 文件中的图书转移日志，并将其导入到 SQLite 数据库。
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlite3 import Connection


# ============================================================================
# 配置常量
# ============================================================================

APP_DIR = Path.home() / ".book_organizer"
CONFIG_FILE = APP_DIR / "book_organizer_config.json"
DEFAULT_DB_NAME = "book_data.db"


# ============================================================================
# 数据类型定义
# ============================================================================


@dataclass
class TransferRecord:
    """转移记录数据类"""

    title: str = ""
    original_filename: str = ""
    new_filename: str = ""
    destination_category: str = ""
    author: str = ""
    publisher: str = ""
    tags: str = ""
    summary: str = ""
    transferred_at: str = ""


@dataclass
class MigrationResult:
    """迁移结果统计"""

    total_parsed: int = 0
    imported: int = 0
    skipped: int = 0
    errors: int = 0


# ============================================================================
# 配置读取
# ============================================================================


def get_db_path() -> Path:
    """
    从配置文件或默认位置获取数据库路径

    Returns:
        数据库文件 Path 对象
    """
    db_dir = APP_DIR

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                config = json.load(f)
                if data_dir := config.get("data_dir"):
                    db_dir = Path(data_dir)
                    print(f"从配置读取 data_dir: {db_dir}")
        except (json.JSONDecodeError, OSError) as e:
            print(f"读取配置出错: {e}")

    return db_dir / DEFAULT_DB_NAME


# ============================================================================
# Markdown 解析
# ============================================================================

# 预编译正则表达式
HEADER_PATTERN = re.compile(r"^## \d+\.\s*(.+)")
FIELD_PATTERN = re.compile(r"\*\*(.+?)\*\*:\s*`?([^`]+)`?")


def parse_field(line: str, field_name: str) -> str | None:
    """
    解析 Markdown 字段值

    Args:
        line: 待解析的行
        field_name: 字段名称前缀

    Returns:
        解析出的值，如果无法解析则返回 None
    """
    if not line.strip().startswith(f"**{field_name}**"):
        return None

    match = FIELD_PATTERN.search(line.strip())
    return match.group(2).strip() if match else None


def parse_markdown_file(file_path: Path) -> list[TransferRecord]:
    """
    解析 Markdown 文件中的转移记录

    Args:
        file_path: Markdown 文件路径

    Returns:
        TransferRecord 列表
    """
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    records: list[TransferRecord] = []
    current_record: TransferRecord | None = None
    capturing_summary = False
    summary_lines: list[str] = []

    for line in lines:
        line_stripped = line.strip()

        # 检测新记录开始: "## 1. Title"
        header_match = HEADER_PATTERN.match(line)
        if header_match:
            # 保存上一个记录
            if current_record:
                if summary_lines:
                    current_record.summary = "\n".join(summary_lines).strip()
                records.append(current_record)

            # 开始新记录
            current_record = TransferRecord(title=header_match.group(1).strip())
            summary_lines = []
            capturing_summary = False
            continue

        if not current_record:
            continue

        # 解析各字段
        if value := parse_field(line_stripped, "转移时间"):
            current_record.transferred_at = value
        elif value := parse_field(line_stripped, "原文件名"):
            current_record.original_filename = value
        elif value := parse_field(line_stripped, "新文件名"):
            current_record.new_filename = value
        elif value := parse_field(line_stripped, "转移到目录"):
            current_record.destination_category = value
        elif value := parse_field(line_stripped, "作者"):
            current_record.author = value
        elif value := parse_field(line_stripped, "出版社"):
            current_record.publisher = value
        elif value := parse_field(line_stripped, "标签"):
            current_record.tags = value
        elif "### 图书简介" in line_stripped:
            capturing_summary = True
        elif line_stripped.startswith("### "):
            capturing_summary = False
        elif capturing_summary:
            summary_lines.append(line)

    # 添加最后一个记录
    if current_record:
        if summary_lines:
            current_record.summary = "\n".join(summary_lines).strip()
        records.append(current_record)

    return records


# ============================================================================
# 数据库操作
# ============================================================================


def ensure_table_exists(conn: Connection) -> None:
    """确保 transfer_logs 表存在"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transfer_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER,
            original_filename TEXT NOT NULL,
            new_filename TEXT NOT NULL,
            destination_category TEXT,
            title TEXT,
            author TEXT,
            publisher TEXT,
            series TEXT,
            tags TEXT,
            summary TEXT,
            transferred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE SET NULL
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_transfer_logs_time ON transfer_logs(transferred_at);"
    )
    conn.commit()


def is_duplicate(conn: Connection, record: TransferRecord) -> bool:
    """检查记录是否重复"""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM transfer_logs WHERE transferred_at = ? AND original_filename = ?",
        (record.transferred_at, record.original_filename),
    )
    return cursor.fetchone() is not None


def insert_record(conn: Connection, record: TransferRecord) -> bool:
    """
    插入单条记录

    Returns:
        是否插入成功
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO transfer_logs
        (original_filename, new_filename, destination_category, title, author, publisher, tags, summary, transferred_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.original_filename,
            record.new_filename or record.original_filename,
            record.destination_category,
            record.title or record.new_filename,
            record.author,
            record.publisher,
            record.tags,
            record.summary,
            record.transferred_at,
        ),
    )
    return True


def migrate_records(db_path: Path, records: list[TransferRecord]) -> MigrationResult:
    """
    将解析的记录迁移到数据库

    Args:
        db_path: 数据库路径
        records: 待迁移的记录列表

    Returns:
        迁移结果统计
    """
    result = MigrationResult(total_parsed=len(records))

    # 确保目录存在
    db_dir = db_path.parent
    if not db_dir.exists():
        print(f"警告: 数据库目录不存在: {db_dir}")
        response = input("是否创建? [y/N] ")
        if response.lower() == "y":
            db_dir.mkdir(parents=True, exist_ok=True)
        else:
            return result

    print(f"连接数据库: {db_path}")

    with sqlite3.connect(db_path) as conn:
        ensure_table_exists(conn)

        for record in records:
            # 基本验证
            if not record.original_filename:
                print(f"跳过不完整记录 (无文件名): {record.title}")
                result.errors += 1
                continue

            # 检查重复
            if is_duplicate(conn, record):
                result.skipped += 1
                continue

            # 插入记录
            try:
                insert_record(conn, record)
                result.imported += 1
            except sqlite3.Error as e:
                print(f"插入失败 {record.original_filename}: {e}")
                result.errors += 1

        conn.commit()

    return result


# ============================================================================
# 主程序
# ============================================================================


def main(md_path: str) -> int:
    """
    主程序入口

    Args:
        md_path: Markdown 文件路径

    Returns:
        退出码 (0=成功, 1=失败)
    """
    file_path = Path(md_path)

    if not file_path.exists():
        print(f"错误: 文件不存在: {file_path}")
        return 1

    # 解析 Markdown
    print(f"解析文件: {file_path}")
    records = parse_markdown_file(file_path)
    print(f"解析到 {len(records)} 条记录")

    if not records:
        print("没有找到有效记录")
        return 0

    # 迁移到数据库
    db_path = get_db_path()
    result = migrate_records(db_path, records)

    # 输出结果
    print("\n迁移完成:")
    print(f"  - 目标数据库: {db_path}")
    print(f"  - 解析记录数: {result.total_parsed}")
    print(f"  - 成功导入: {result.imported}")
    print(f"  - 跳过 (重复): {result.skipped}")
    print(f"  - 错误: {result.errors}")

    return 0 if result.errors == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python migrate_transfer_logs.py <path_to_md_file>")
        sys.exit(1)

    exit_code = main(sys.argv[1])
    sys.exit(exit_code)
