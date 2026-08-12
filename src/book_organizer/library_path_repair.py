# -*- coding: utf-8 -*-
"""Portable library path repair utilities.

These helpers repair stale absolute paths after moving the library to another
machine or a differently named sync mount. They only update database paths and
never move, rename, or delete book files.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .config import load_config
from .database import get_db
from .file_ops import get_configured_book_extensions

logger = logging.getLogger(__name__)

PATH_TABLES = ("books", "enhanced_summaries", "book_tocs")
_auto_repair_started = False
_auto_repair_lock = threading.Lock()


def path_is_inside(path: str | os.PathLike[str], root: str | os.PathLike[str]) -> bool:
    try:
        path_abs = os.path.realpath(os.path.expanduser(os.fspath(path)))
        root_abs = os.path.realpath(os.path.expanduser(os.fspath(root)))
        return os.path.commonpath([path_abs, root_abs]) == root_abs
    except (OSError, ValueError):
        return False


def path_is_in_book_roots(path: str, config: dict[str, Any]) -> bool:
    """Return whether a path belongs to a configured source or library root."""
    roots = [config.get("source_dir"), config.get("target_dir")]
    roots.extend(config.get("library_directories") or [])
    return any(root and path_is_inside(path, root) for root in roots)


def portable_library_path(file_path: str) -> str:
    """Return a sync-portable path when the file lives under target_dir.

    Files in the configured library are stored relative to target_dir. Source
    folder files and arbitrary absolute paths are left untouched.
    """
    if not file_path or not os.path.isabs(file_path):
        return file_path

    try:
        target_dir = load_config().get("target_dir") or ""
    except Exception:
        target_dir = ""

    if target_dir and path_is_inside(file_path, target_dir):
        return os.path.relpath(file_path, target_dir)
    return file_path


def portable_library_path_for_target(
    file_path: str, target_dir: str | os.PathLike[str]
) -> str:
    if file_path and os.path.isabs(file_path) and path_is_inside(file_path, target_dir):
        return os.path.relpath(file_path, target_dir)
    return file_path


def resolve_library_path(
    file_path: str, target_dir: str | os.PathLike[str]
) -> str | None:
    if not file_path:
        return None
    expanded = os.path.expanduser(file_path)
    if os.path.isabs(expanded):
        return os.path.abspath(expanded)
    return os.path.abspath(os.path.join(os.fspath(target_dir), expanded))


def scan_library_files(target_dir: str | os.PathLike[str]) -> dict[str, list[str]]:
    files_by_name: dict[str, list[str]] = defaultdict(list)
    target = Path(target_dir)
    if not target.exists():
        return files_by_name
    allowed_extensions = set(get_configured_book_extensions())

    for path in target.rglob("*"):
        if (
            path.is_file()
            and not path.name.startswith(".")
            and path.suffix.lower() in allowed_extensions
        ):
            files_by_name[path.name].append(str(path.resolve()))
    return files_by_name


def repair_stale_library_paths(
    *,
    db_path: str | os.PathLike[str] | None = None,
    target_dir: str | os.PathLike[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Repair missing DB paths when a unique same-name file exists in target_dir.

    The function intentionally does not delete rows. Missing records may simply
    be waiting for a cloud drive to finish syncing on a new machine.
    """
    if target_dir is None:
        target_dir = load_config().get("target_dir") or ""
    target_dir = os.path.abspath(os.path.expanduser(os.fspath(target_dir)))
    if not target_dir or not os.path.isdir(target_dir):
        return {"ok": False, "reason": "target_dir_missing", "target_dir": target_dir}

    if db_path is None:
        db_path = get_db().db_path
    db_path = os.path.abspath(os.path.expanduser(os.fspath(db_path)))
    if not os.path.exists(db_path):
        return {"ok": False, "reason": "db_missing", "db_path": db_path}

    files_by_name = scan_library_files(target_dir)
    stats: Counter[str] = Counter(
        scanned_files=sum(len(v) for v in files_by_name.values())
    )
    updates: list[tuple[str, int, str, str]] = []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        for table in PATH_TABLES:
            rows = conn.execute(
                f"SELECT id, filename, file_path FROM {table}"
            ).fetchall()
            for row in rows:
                stats[f"{table}_checked"] += 1
                filename = row["filename"] or os.path.basename(row["file_path"] or "")
                resolved = resolve_library_path(row["file_path"] or "", target_dir)
                if resolved and os.path.exists(resolved):
                    if path_is_inside(resolved, target_dir):
                        portable = portable_library_path_for_target(
                            resolved, target_dir
                        )
                        if portable != (row["file_path"] or ""):
                            updates.append(
                                (
                                    table,
                                    int(row["id"]),
                                    row["file_path"] or "",
                                    portable,
                                )
                            )
                    continue

                candidates = files_by_name.get(filename, [])
                if len(candidates) == 1:
                    updates.append(
                        (
                            table,
                            int(row["id"]),
                            row["file_path"] or "",
                            portable_library_path_for_target(candidates[0], target_dir),
                        )
                    )
                elif len(candidates) > 1:
                    stats[f"{table}_ambiguous"] += 1
                else:
                    stats[f"{table}_missing"] += 1

        deduped = []
        seen = set()
        for item in updates:
            key = (item[0], item[1], item[3])
            if key not in seen:
                seen.add(key)
                deduped.append(item)

        if not dry_run:
            for table, row_id, _old_path, new_path in deduped:
                conn.execute(
                    f"UPDATE {table} SET file_path = ? WHERE id = ?",
                    (new_path, row_id),
                )
                stats[f"{table}_updated"] += 1
            conn.commit()

        stats["updates"] = len(deduped)
        return {
            "ok": True,
            "db_path": db_path,
            "target_dir": target_dir,
            "dry_run": dry_run,
            "stats": dict(stats),
            "sample_updates": deduped[:20],
        }
    finally:
        conn.close()


def inspect_library_health(
    *,
    db_path: str | os.PathLike[str] | None = None,
    target_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Return a read-only health report for the configured library and database."""
    path_report = repair_stale_library_paths(
        db_path=db_path, target_dir=target_dir, dry_run=True
    )
    if not path_report.get("ok"):
        return path_report

    db_path = path_report["db_path"]
    stats = Counter(path_report.get("stats", {}))
    conn = sqlite3.connect(db_path)
    try:
        database_health = inspect_database_connection(conn)
    finally:
        conn.close()

    issues = {
        "path_repairs": int(stats.get("updates", 0)),
        "missing_records": sum(
            int(stats.get(f"{table}_missing", 0)) for table in PATH_TABLES
        ),
        "ambiguous_records": sum(
            int(stats.get(f"{table}_ambiguous", 0)) for table in PATH_TABLES
        ),
        **database_health["issues"],
    }
    return {
        "ok": database_health["ok"],
        "status": "healthy" if database_health["ok"] and not any(issues.values()) else "attention",
        "integrity": database_health["integrity"],
        "issues": issues,
        "scanned_files": int(stats.get("scanned_files", 0)),
        "sample_path_repairs": path_report.get("sample_updates", []),
    }


def inspect_database_connection(conn: sqlite3.Connection) -> dict[str, Any]:
    """Inspect database-only invariants without scanning the filesystem."""
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    invalid_toc_json = 0
    for (toc_json,) in conn.execute("SELECT toc_json FROM book_tocs"):
        try:
            json.loads(toc_json)
        except (TypeError, json.JSONDecodeError):
            invalid_toc_json += 1
    issues = {
        "orphan_chapters": int(
            conn.execute(
                "SELECT count(*) FROM chapters WHERE book_id NOT IN (SELECT id FROM books)"
            ).fetchone()[0]
        ),
        "orphan_insights": int(
            conn.execute(
                "SELECT count(*) FROM enhanced_insights WHERE book_id NOT IN (SELECT id FROM books)"
            ).fetchone()[0]
        ),
        "invalid_toc_json": invalid_toc_json,
    }
    return {
        "ok": integrity == "ok",
        "status": "healthy" if integrity == "ok" and not any(issues.values()) else "attention",
        "integrity": integrity,
        "issues": issues,
    }


def start_auto_library_path_repair(delay_seconds: float = 4.0) -> bool:
    """Start one non-blocking path repair pass for app startup."""
    global _auto_repair_started
    with _auto_repair_lock:
        if _auto_repair_started:
            return False
        _auto_repair_started = True

    def worker() -> None:
        try:
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            result = repair_stale_library_paths(dry_run=False)
            if result.get("ok"):
                updates = result.get("stats", {}).get("updates", 0)
                if updates:
                    logger.info("[Startup] repaired stale library paths: %s", result)
                    print(f"[Startup] Repaired stale library paths: {updates}")
            else:
                logger.debug("[Startup] skipped path repair: %s", result)
        except Exception as exc:
            logger.warning("[Startup] library path repair skipped: %s", exc)
            print(f"[Startup] Library path repair skipped: {exc}")

    thread = threading.Thread(target=worker, name="library-path-repair", daemon=True)
    thread.start()
    return True
