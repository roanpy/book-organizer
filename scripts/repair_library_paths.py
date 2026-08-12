#!/usr/bin/env python3
# ruff: noqa: E402
"""Repair stale BookOrganizer database paths against the configured library.

The script only changes BookOrganizer's SQLite database. It never moves,
renames, or deletes book files.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from book_organizer.config import load_config
from book_organizer.database import get_db
from book_organizer.file_ops import get_configured_book_extensions
from book_organizer.library_path_repair import portable_library_path


@dataclass(frozen=True)
class Record:
    table: str
    row_id: int
    filename: str
    file_path: str


@dataclass(frozen=True)
class RepairPlan:
    target_dir: Path
    scanned_files: int
    by_status: dict[str, Counter]
    path_updates: list[tuple[Record, str]]
    missing_records: list[Record]
    outside_records: list[Record]
    ambiguous_records: list[Record]


def backup_database(db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    backup = db_path.with_name(
        f"{db_path.stem}.before_path_repair.{time.strftime('%Y%m%d-%H%M%S')}{db_path.suffix}"
    )
    shutil.copy2(db_path, backup)
    return backup


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
    except OSError:
        return False


def resolve_record_path(record: Record, target_dir: Path) -> Path | None:
    if record.file_path:
        raw = Path(record.file_path).expanduser()
        return raw if raw.is_absolute() else target_dir / raw
    if record.filename:
        return target_dir / record.filename
    return None


def scan_library(target_dir: Path) -> dict[str, list[str]]:
    files_by_name: dict[str, list[str]] = defaultdict(list)
    if not target_dir.exists():
        return files_by_name
    allowed_extensions = set(get_configured_book_extensions())
    for path in target_dir.rglob("*"):
        if (
            path.is_file()
            and not path.name.startswith(".")
            and path.suffix.lower() in allowed_extensions
        ):
            files_by_name[path.name].append(str(path.resolve()))
    return files_by_name


def load_records(conn: sqlite3.Connection) -> Iterable[Record]:
    for table in ("books", "enhanced_summaries", "book_tocs"):
        rows = conn.execute(f"SELECT id, filename, file_path FROM {table}").fetchall()
        for row in rows:
            yield Record(
                table=table,
                row_id=int(row["id"]),
                filename=row["filename"] or "",
                file_path=row["file_path"] or "",
            )


def build_plan(conn: sqlite3.Connection, target_dir: Path) -> RepairPlan:
    files_by_name = scan_library(target_dir)
    path_updates: list[tuple[Record, str]] = []
    missing_records: list[Record] = []
    outside_records: list[Record] = []
    ambiguous_records: list[Record] = []
    by_status: dict[str, Counter] = defaultdict(Counter)

    for record in load_records(conn):
        candidate = resolve_record_path(record, target_dir)
        if candidate and candidate.exists():
            status = (
                "exists_in_target"
                if is_relative_to(candidate, target_dir)
                else "exists_outside_target"
            )
            by_status[record.table][status] += 1
            if status == "exists_outside_target":
                outside_records.append(record)
            continue

        matches = files_by_name.get(record.filename, [])
        if len(matches) == 1:
            by_status[record.table]["relocatable"] += 1
            path_updates.append((record, portable_library_path(matches[0])))
        elif len(matches) > 1:
            by_status[record.table]["ambiguous"] += 1
            ambiguous_records.append(record)
        else:
            by_status[record.table]["missing_no_match"] += 1
            missing_records.append(record)

    return RepairPlan(
        target_dir=target_dir,
        scanned_files=sum(len(paths) for paths in files_by_name.values()),
        by_status=dict(by_status),
        path_updates=path_updates,
        missing_records=missing_records,
        outside_records=outside_records,
        ambiguous_records=ambiguous_records,
    )


def apply_plan(
    conn: sqlite3.Connection,
    plan: RepairPlan,
    *,
    delete_missing: bool,
) -> dict[str, int]:
    stats = Counter()

    for record, new_path in plan.path_updates:
        conn.execute(
            f"UPDATE {record.table} SET file_path = ? WHERE id = ?",
            (new_path, record.row_id),
        )
        stats[f"{record.table}_paths_updated"] += 1

    if delete_missing:
        missing_by_table: dict[str, list[int]] = defaultdict(list)
        for record in plan.missing_records:
            missing_by_table[record.table].append(record.row_id)

        book_ids = missing_by_table.get("books", [])
        for book_id in book_ids:
            cursor = conn.execute("DELETE FROM chapters WHERE book_id = ?", (book_id,))
            stats["chapters_deleted"] += cursor.rowcount
            cursor = conn.execute(
                "DELETE FROM enhanced_insights WHERE book_id = ?", (book_id,)
            )
            stats["enhanced_insights_deleted"] += cursor.rowcount
            cursor = conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
            stats["books_deleted"] += cursor.rowcount

        for table in ("enhanced_summaries", "book_tocs"):
            for row_id in missing_by_table.get(table, []):
                cursor = conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
                stats[f"{table}_deleted"] += cursor.rowcount

        cursor = conn.execute(
            "DELETE FROM chapters WHERE book_id NOT IN (SELECT id FROM books)"
        )
        stats["orphan_chapters_deleted"] += cursor.rowcount
        cursor = conn.execute(
            "DELETE FROM enhanced_insights WHERE book_id NOT IN (SELECT id FROM books)"
        )
        stats["orphan_enhanced_insights_deleted"] += cursor.rowcount

    conn.commit()
    return dict(stats)


def write_report(
    plan: RepairPlan,
    report_path: Path,
    *,
    dry_run: bool,
    delete_missing: bool,
    backup: Path | None,
    apply_stats: dict[str, int] | None = None,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# BookOrganizer 旧路径与未匹配记录维护报告",
        "",
        f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 模式: {'dry-run' if dry_run else '已写入'}",
        f"- 当前 Books 目录: `{plan.target_dir}`",
        f"- 扫描到图书文件: {plan.scanned_files}",
        f"- 备份: `{backup or 'dry-run 未生成'}`",
        f"- 删除确认缺失记录: {'是' if delete_missing else '否'}",
        "",
        "## 分类统计",
        "",
    ]

    for table in ("books", "enhanced_summaries", "book_tocs"):
        counter = plan.by_status.get(table, Counter())
        total = sum(counter.values())
        lines.append(f"### {table} ({total})")
        for key in (
            "exists_in_target",
            "relocatable",
            "missing_no_match",
            "exists_outside_target",
            "ambiguous",
        ):
            lines.append(f"- {key}: {counter.get(key, 0)}")
        lines.append("")

    if apply_stats:
        lines.extend(["## 写入结果", ""])
        for key in sorted(apply_stats):
            lines.append(f"- {key}: {apply_stats[key]}")
        lines.append("")

    lines.extend(["## 路径修复样例", ""])
    for record, new_path in plan.path_updates[:80]:
        lines.append(
            f"- `{record.table}` #{record.row_id}: `{record.file_path}` -> `{new_path}`"
        )
    if len(plan.path_updates) > 80:
        lines.append(f"- 其余 {len(plan.path_updates) - 80} 条略。")

    lines.extend(["", "## 删除候选样例", ""])
    for record in plan.missing_records[:80]:
        lines.append(
            f"- `{record.table}` #{record.row_id}: `{record.filename}` | `{record.file_path}`"
        )
    if len(plan.missing_records) > 80:
        lines.append(f"- 其余 {len(plan.missing_records) - 80} 条略。")

    if plan.ambiguous_records:
        lines.extend(["", "## 未自动处理的重名记录", ""])
        for record in plan.ambiguous_records[:80]:
            lines.append(
                f"- `{record.table}` #{record.row_id}: `{record.filename}` | `{record.file_path}`"
            )

    if plan.outside_records:
        lines.extend(["", "## 当前仍在 Books 外的记录", ""])
        for record in plan.outside_records[:80]:
            lines.append(
                f"- `{record.table}` #{record.row_id}: `{record.filename}` | `{record.file_path}`"
            )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def default_report_path() -> Path:
    return (
        Path.home()
        / ".book_organizer"
        / "maintenance"
        / f"path_repair_{time.strftime('%Y%m%d-%H%M%S')}.md"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write path repairs")
    parser.add_argument(
        "--delete-missing",
        action="store_true",
        help="also delete DB rows whose files are not found in the current library",
    )
    parser.add_argument("--report", default=str(default_report_path()))
    args = parser.parse_args()

    config = load_config()
    target_dir = Path(config.get("target_dir") or "").expanduser().resolve()
    if not target_dir.exists():
        print(f"TARGET_NOT_FOUND={target_dir}")
        return 2

    db_path = Path(get_db().db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    plan = build_plan(conn, target_dir)
    backup = backup_database(db_path) if args.apply else None
    apply_stats = None
    if args.apply:
        apply_stats = apply_plan(conn, plan, delete_missing=args.delete_missing)
    conn.close()

    report_path = Path(args.report)
    write_report(
        plan,
        report_path,
        dry_run=not args.apply,
        delete_missing=args.delete_missing,
        backup=backup,
        apply_stats=apply_stats,
    )

    print(f"DB={db_path}")
    print(f"TARGET_DIR={target_dir}")
    print(f"SCANNED_FILES={plan.scanned_files}")
    for table in ("books", "enhanced_summaries", "book_tocs"):
        counter = plan.by_status.get(table, Counter())
        print(
            f"{table.upper()}="
            f"exists:{counter.get('exists_in_target', 0)},"
            f"relocatable:{counter.get('relocatable', 0)},"
            f"missing:{counter.get('missing_no_match', 0)},"
            f"outside:{counter.get('exists_outside_target', 0)},"
            f"ambiguous:{counter.get('ambiguous', 0)}"
        )
    if apply_stats:
        for key in sorted(apply_stats):
            print(f"{key.upper()}={apply_stats[key]}")
    print(f"BACKUP={backup or ''}")
    print(f"REPORT={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
