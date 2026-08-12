#!/usr/bin/env python3
# ruff: noqa: E402
"""Remove EPUB/PDF-internal navigation fields from cached TOC records.

This script only updates the BookOrganizer SQLite cache. It does not modify any
book file.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from book_organizer.database import get_db
from book_organizer.toc_extractor import (
    TOC_STORAGE_NAVIGATION_FIELDS,
    _is_internal_file_title,
    strip_toc_storage_noise,
)


def backup_database(db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    backup = db_path.with_name(
        f"{db_path.stem}.before_toc_cache_clean.{time.strftime('%Y%m%d-%H%M%S')}{db_path.suffix}"
    )
    shutil.copy2(db_path, backup)
    return backup


def _extract_toc_payload(raw_json: str):
    data = json.loads(raw_json)
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {"toc": data}
    if isinstance(data, str):
        return {"toc": [], "toc_text": data}
    return {"toc": []}


def _count_navigation_noise(payload: dict) -> int:
    count = 0
    for item in payload.get("toc", []) or []:
        if isinstance(item, dict):
            count += sum(1 for key in TOC_STORAGE_NAVIGATION_FIELDS if key in item)
    return count


def _count_internal_file_titles(payload: dict) -> int:
    count = 0
    for item in payload.get("toc", []) or []:
        if isinstance(item, dict) and _is_internal_file_title(item.get("title", "")):
            count += 1
    return count


def clean_toc_cache(dry_run: bool = False) -> dict:
    db_path = Path(get_db().db_path)
    backup = None if dry_run else backup_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT id, filename, file_path, toc_json, extraction_method FROM book_tocs"
    ).fetchall()
    changed: list[dict] = []
    parse_errors: list[dict] = []
    removed_fields = 0
    removed_file_titles = 0

    for row in rows:
        try:
            payload = _extract_toc_payload(row["toc_json"] or "[]")
        except Exception as exc:
            if len(parse_errors) < 50:
                parse_errors.append({"filename": row["filename"], "error": str(exc)})
            continue

        noise_count = _count_navigation_noise(payload)
        file_title_count = _count_internal_file_titles(payload)
        if noise_count <= 0 and file_title_count <= 0:
            continue

        cleaned = strip_toc_storage_noise(payload)
        cleaned_json = json.dumps(cleaned.get("toc", []), ensure_ascii=False)
        if cleaned.get("toc_text"):
            cleaned_json = json.dumps(
                {
                    "toc": cleaned.get("toc", []),
                    "toc_text": cleaned.get("toc_text", ""),
                    "ai_processed": cleaned.get("ai_processed", False),
                    "modes_used": cleaned.get("modes_used", []),
                },
                ensure_ascii=False,
            )

        changed.append(
            {
                "id": row["id"],
                "filename": row["filename"],
                "file_path": row["file_path"],
                "removed_fields": noise_count,
                "removed_file_titles": file_title_count,
                "old_len": len(row["toc_json"] or ""),
                "new_len": len(cleaned_json),
            }
        )
        removed_fields += noise_count
        removed_file_titles += file_title_count
        if not dry_run:
            conn.execute(
                """
                UPDATE book_tocs
                SET toc_json = ?, entry_count = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (cleaned_json, cleaned.get("entry_count", 0), row["id"]),
            )

    if not dry_run:
        conn.commit()
    conn.close()
    return {
        "db_path": str(db_path),
        "backup": str(backup) if backup else "",
        "checked": len(rows),
        "updated": len(changed),
        "removed_fields": removed_fields,
        "removed_file_titles": removed_file_titles,
        "parse_errors": parse_errors,
        "changes": changed,
    }


def write_report(result: dict, report_path: Path, dry_run: bool = False) -> None:
    lines = [
        "# BookOrganizer TOC 缓存路径噪声清理记录",
        "",
        f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 数据库: `{result['db_path']}`",
        f"- 模式: {'dry-run' if dry_run else '已写入'}",
        f"- 备份: `{result.get('backup') or 'dry-run 未生成'}`",
        f"- 检查 TOC 记录: {result['checked']}",
        f"- 清理 TOC 记录: {result['updated']}",
        f"- 移除内部导航字段: {result['removed_fields']}",
        f"- 移除文件名式目录标题: {result['removed_file_titles']}",
        "",
        "## 说明",
        "",
        "- 仅清理应用数据库缓存中的 `href` / `anchor` / `target_index`。",
        "- 不修改 EPUB/PDF 原文件。",
        "- 预览仍会实时读取 EPUB manifest，用于目录跳转。",
        "",
        "## 清理样例",
        "",
    ]
    if result["changes"]:
        for idx, change in enumerate(result["changes"][:200], 1):
            target = change["file_path"] or change["filename"]
            lines.append(
                f"{idx}. `{target}`: 移除 {change['removed_fields']} 个字段，"
                f"移除 {change['removed_file_titles']} 个文件名式标题，"
                f"{change['old_len']} -> {change['new_len']} 字符"
            )
        if len(result["changes"]) > 200:
            lines.append(f"- 其余 {len(result['changes']) - 200} 条略。")
    else:
        lines.append("- 本次没有发现需要清理的 TOC 路径噪声。")

    if result["parse_errors"]:
        lines.extend(["", "## 解析失败样例", ""])
        for item in result["parse_errors"]:
            lines.append(f"- `{item['filename']}`: {item['error']}")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    default_report = (
        Path.home()
        / "Desktop"
        / f"BookOrganizer_TOC缓存路径噪声清理记录_{time.strftime('%Y%m%d')}.md"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report only")
    parser.add_argument(
        "--report",
        default=str(default_report),
        help="markdown report path",
    )
    args = parser.parse_args()

    result = clean_toc_cache(dry_run=args.dry_run)
    write_report(result, Path(args.report), dry_run=args.dry_run)
    print(f"DB_BACKUP={result.get('backup')}")
    print(f"TOC_CHECKED={result['checked']}")
    print(f"TOC_UPDATED={result['updated']}")
    print(f"REMOVED_FIELDS={result['removed_fields']}")
    print(f"REMOVED_FILE_TITLE_ITEMS={result['removed_file_titles']}")
    print(f"PARSE_ERRORS={len(result['parse_errors'])}")
    print(f"REPORT={args.report}")
    return 0 if not result["parse_errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
