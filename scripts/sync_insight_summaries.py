#!/usr/bin/env python3
# ruff: noqa: E402
"""Promote newer enhanced summaries from enhanced_insights into enhanced_summaries.

This migration only updates the local SQLite database. It does not modify EPUB,
PDF, or any other book file.
"""

from __future__ import annotations

import argparse
import json
import os
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
from book_organizer.file_ops import parse_filename_to_dict
from book_organizer.metadata_sync import iter_configured_book_files
from book_organizer.summary_utils import (
    enhanced_summary_detail_score,
    is_structured_enhanced_summary,
    normalize_enhanced_summary,
)


def backup_database(db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    backup = db_path.with_name(
        f"{db_path.stem}.before_insight_summary_sync.{time.strftime('%Y%m%d-%H%M%S')}{db_path.suffix}"
    )
    shutil.copy2(db_path, backup)
    return backup


def load_legacy_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT rowid AS legacy_rowid, file_path, filename, title, author, category, summary_json
        FROM enhanced_summaries
        """
    ).fetchall()


def matching_legacy_rows(insight_path: str, insight_filename: str, legacy_rows: list[sqlite3.Row]):
    basename = os.path.basename(insight_path or insight_filename or "")
    for row in legacy_rows:
        row_path = row["file_path"] or ""
        row_filename = row["filename"] or ""
        if row_path == insight_path or row_filename == insight_filename:
            yield row
            continue
        if basename and basename in {os.path.basename(row_path), os.path.basename(row_filename)}:
            yield row


def normalize_lookup(value: str | None) -> str:
    return "".join(str(value or "").lower().split())


def title_author_key(title: str | None, author: str | None) -> tuple[str, str]:
    return normalize_lookup(title), normalize_lookup(author)


def build_current_file_index() -> tuple[
    dict[str, list[Path]],
    dict[str, list[Path]],
    dict[tuple[str, str], list[Path]],
    dict[str, list[Path]],
]:
    by_basename: dict[str, list[Path]] = {}
    by_books_tail: dict[str, list[Path]] = {}
    by_title_author: dict[tuple[str, str], list[Path]] = {}
    by_title: dict[str, list[Path]] = {}
    for path in iter_configured_book_files(extensions={".epub", ".pdf"}):
        by_basename.setdefault(path.name, []).append(path)
        parts = path.parts
        if "Books" in parts:
            tail = "/".join(parts[parts.index("Books") + 1 :])
            by_books_tail.setdefault(tail, []).append(path)
        parsed = parse_filename_to_dict(path.name)
        title = parsed.get("title", "")
        author = parsed.get("author", "")
        if title:
            by_title.setdefault(normalize_lookup(title), []).append(path)
            if author:
                by_title_author.setdefault(title_author_key(title, author), []).append(path)
    return by_basename, by_books_tail, by_title_author, by_title


def books_tail(path: str) -> str:
    marker = "/Books/"
    if marker not in path:
        return ""
    return path.split(marker, 1)[1]


def resolve_current_path(
    insight_path: str,
    insight_filename: str,
    insight_title: str,
    insight_author: str,
    by_basename: dict[str, list[Path]],
    by_books_tail: dict[str, list[Path]],
    by_title_author: dict[tuple[str, str], list[Path]],
    by_title: dict[str, list[Path]],
) -> Path | None:
    if insight_path and Path(insight_path).exists():
        return Path(insight_path)

    tail = books_tail(insight_path or "")
    if tail:
        hits = by_books_tail.get(tail, [])
        if len(hits) == 1:
            return hits[0]

    basename = os.path.basename(insight_path or insight_filename or "")
    hits = by_basename.get(basename, [])
    if len(hits) == 1:
        return hits[0]

    parsed = parse_filename_to_dict(basename)
    title = insight_title or parsed.get("title", "")
    author = insight_author or parsed.get("author", "")
    if title and author:
        hits = by_title_author.get(title_author_key(title, author), [])
        if len(hits) == 1:
            return hits[0]
    if title:
        hits = by_title.get(normalize_lookup(title), [])
        if len(hits) == 1:
            return hits[0]
    return None


def upsert_legacy_summary(
    conn: sqlite3.Connection,
    file_path: str,
    filename: str,
    title: str,
    author: str,
    summary: str,
    category: str = "Library",
) -> None:
    payload = {
        "metadata": {
            "title": title or "",
            "author": author or "",
        },
        "summary": summary,
        "category": category,
    }
    summary_json = json.dumps(payload, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO enhanced_summaries
            (file_path, filename, title, author, category, summary_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(file_path) DO UPDATE SET
            filename=excluded.filename,
            title=excluded.title,
            author=excluded.author,
            category=excluded.category,
            summary_json=excluded.summary_json,
            updated_at=CURRENT_TIMESTAMP
        """,
        (file_path, filename, title or "", author or "", category, summary_json),
    )


def promote_summaries(dry_run: bool = False) -> dict:
    db_path = Path(get_db().db_path)
    backup = None if dry_run else backup_database(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    by_basename, by_books_tail, by_title_author, by_title = build_current_file_index()
    insight_rows = conn.execute(
        """
        SELECT
            b.file_path AS book_path,
            b.filename AS filename,
            b.title AS title,
            b.author AS author,
            i.content AS content,
            i.created_at AS created_at
        FROM enhanced_insights i
        JOIN books b ON b.id = i.book_id
        WHERE i.insight_type = 'summary_v1'
          AND COALESCE(i.content, '') != ''
        ORDER BY i.created_at DESC, i.id DESC
        """
    ).fetchall()
    legacy_rows = load_legacy_rows(conn)

    seen_targets: set[int] = set()
    seen_create_paths: set[str] = set()
    changes: list[dict] = []
    skipped_missing = 0
    created_from_old_path = 0
    skipped_not_richer = 0
    skipped_unstructured = 0
    unresolved_missing: list[dict] = []

    for insight in insight_rows:
        new_summary = normalize_enhanced_summary(insight["content"])
        if not is_structured_enhanced_summary(new_summary):
            skipped_unstructured += 1
            continue

        matches = list(matching_legacy_rows(insight["book_path"], insight["filename"], legacy_rows))
        if not matches:
            current_path = resolve_current_path(
                insight["book_path"],
                insight["filename"],
                insight["title"],
                insight["author"],
                by_basename,
                by_books_tail,
                by_title_author,
                by_title,
            )
            if current_path:
                current_path_str = str(current_path)
                if current_path_str in seen_create_paths:
                    continue
                seen_create_paths.add(current_path_str)
                changes.append(
                    {
                        "rowid": 0,
                        "file_path": current_path_str,
                        "filename": current_path.name,
                        "old_len": 0,
                        "new_len": len(new_summary),
                        "created_from_old_path": insight["book_path"],
                    }
                )
                created_from_old_path += 1
                if not dry_run:
                    upsert_legacy_summary(
                        conn,
                        str(current_path),
                        current_path.name,
                        insight["title"] or "",
                        insight["author"] or "",
                        new_summary,
                    )
                continue
            skipped_missing += 1
            if len(unresolved_missing) < 50:
                unresolved_missing.append(
                    {
                        "file_path": insight["book_path"],
                        "filename": insight["filename"],
                        "new_len": len(new_summary),
                    }
                )
            continue

        for legacy in matches:
            rowid = int(legacy["legacy_rowid"])
            if rowid in seen_targets:
                continue
            try:
                payload = json.loads(legacy["summary_json"] or "{}")
            except Exception:
                payload = {}
            old_summary = normalize_enhanced_summary(payload.get("summary"))
            if old_summary == new_summary:
                seen_targets.add(rowid)
                continue
            if enhanced_summary_detail_score(new_summary) <= enhanced_summary_detail_score(old_summary):
                skipped_not_richer += 1
                continue

            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            metadata.setdefault("title", insight["title"] or legacy["title"] or "")
            metadata.setdefault("author", insight["author"] or legacy["author"] or "")
            metadata.pop("description", None)
            payload.update(
                {
                    "metadata": metadata,
                    "summary": new_summary,
                    "category": payload.get("category") or legacy["category"] or "Library",
                }
            )
            new_json = json.dumps(payload, ensure_ascii=False)
            changes.append(
                {
                    "rowid": rowid,
                    "file_path": legacy["file_path"],
                    "filename": legacy["filename"],
                    "old_len": len(old_summary),
                    "new_len": len(new_summary),
                }
            )
            seen_targets.add(rowid)
            if not dry_run:
                conn.execute(
                    """
                    UPDATE enhanced_summaries
                    SET summary_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE rowid = ?
                    """,
                    (new_json, rowid),
                )

    if not dry_run:
        conn.commit()

    conn.close()
    return {
        "db_path": str(db_path),
        "backup": str(backup) if backup else "",
        "insights_checked": len(insight_rows),
        "updated": len(changes),
        "created_from_old_path": created_from_old_path,
        "skipped_missing_legacy": skipped_missing,
        "skipped_not_richer": skipped_not_richer,
        "skipped_unstructured": skipped_unstructured,
        "unresolved_missing": unresolved_missing,
        "changes": changes,
    }


def write_report(result: dict, report_path: Path) -> None:
    lines = [
        "# BookOrganizer 增强简介新旧表同步记录",
        "",
        f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 数据库: `{result['db_path']}`",
        f"- 备份: `{result.get('backup') or 'dry-run 未生成'}`",
        f"- 检查 summary_v1: {result['insights_checked']}",
        f"- 写入 enhanced_summaries: {result['updated']}",
        f"- 其中旧机器路径映射创建: {result['created_from_old_path']}",
        f"- 跳过无旧展示记录: {result['skipped_missing_legacy']}",
        f"- 跳过非新版结构: {result['skipped_unstructured']}",
        f"- 跳过未比旧版更详细: {result['skipped_not_richer']}",
        "",
        "## 写入明细",
        "",
    ]
    if result["changes"]:
        for idx, change in enumerate(result["changes"], 1):
            target = change["file_path"] or change["filename"]
            suffix = ""
            if change.get("created_from_old_path"):
                suffix = f"；旧路径 `{change['created_from_old_path']}`"
            lines.append(f"{idx}. `{target}`: {change['old_len']} 字 -> {change['new_len']} 字{suffix}")
    else:
        lines.append("- 本次没有需要写入的增强简介。")

    if result["unresolved_missing"]:
        lines.extend(["", "## 未能映射到当前书库的旧记录", ""])
        for idx, item in enumerate(result["unresolved_missing"], 1):
            lines.append(f"{idx}. `{item['file_path'] or item['filename']}`: {item['new_len']} 字")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="only report planned changes")
    parser.add_argument(
        "--report",
        default=str(Path.home() / "Desktop" / "BookOrganizer_增强简介新旧表同步记录_20260522.md"),
        help="markdown report path",
    )
    args = parser.parse_args()

    result = promote_summaries(dry_run=args.dry_run)
    write_report(result, Path(args.report))
    print(f"DB_BACKUP={result.get('backup')}")
    print(f"INSIGHTS_CHECKED={result['insights_checked']}")
    print(f"SUMMARY_UPDATED={result['updated']}")
    print(f"CREATED_FROM_OLD_PATH={result['created_from_old_path']}")
    print(f"SKIPPED_MISSING_LEGACY={result['skipped_missing_legacy']}")
    print(f"SKIPPED_NOT_RICHER={result['skipped_not_richer']}")
    print(f"SKIPPED_UNSTRUCTURED={result['skipped_unstructured']}")
    print(f"REPORT={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
