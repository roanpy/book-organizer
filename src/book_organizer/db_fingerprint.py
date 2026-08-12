"""Database fingerprint and comparison utilities for sync-status checks."""

import hashlib
import json
import os
import sqlite3
from typing import Any, Dict
from urllib.parse import quote

DB_PRIMARY_SYNC_TABLES = (
    "books",
    "enhanced_insights",
    "enhanced_summaries",
    "transfer_logs",
)
DB_CACHE_SYNC_TABLES = ("chapters", "book_tocs")
DB_LOGICAL_TABLES = (*DB_PRIMARY_SYNC_TABLES, *DB_CACHE_SYNC_TABLES)
DB_FULL_CACHE_FINGERPRINT_MAX_BYTES = 80 * 1024 * 1024


def _valid_database(path: str) -> bool:
    return bool(path and os.path.exists(path) and os.path.getsize(path) > 1024)


def _wal_has_pending_data(db_path: str) -> bool:
    wal_path = db_path + "-wal"
    return os.path.exists(wal_path) and os.path.getsize(wal_path) > 0


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _normalize_db_value(value):
    if isinstance(value, bytes):
        return {"__blob__": value.hex()}
    return value


def _database_logical_fingerprint(
    path: str, tables=DB_PRIMARY_SYNC_TABLES
) -> Dict[str, Any]:
    """Return a content fingerprint for application data, ignoring SQLite mtime."""
    result: Dict[str, Any] = {
        "ok": False,
        "fingerprint": None,
        "tables": {},
        "error": None,
    }
    if not _valid_database(path):
        result["error"] = "missing-or-empty"
        return result

    digest = hashlib.sha256()
    # immutable=1 prevents read-only status checks from creating -shm files
    # after the DB has already been checkpointed.
    uri_flags = "mode=ro" if _wal_has_pending_data(path) else "mode=ro&immutable=1"
    uri = f"file:{quote(os.path.abspath(path))}?{uri_flags}"

    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA query_only = ON")
            for table in tables:
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                digest.update(f"table:{table}:".encode("utf-8"))
                if not exists:
                    digest.update(b"missing\n")
                    result["tables"][table] = {"exists": False, "rows": 0}
                    continue

                quoted_table = _quote_identifier(table)
                columns = [
                    row["name"]
                    for row in conn.execute(f"PRAGMA table_info({quoted_table})")
                ]
                quoted_columns = ",".join(_quote_identifier(col) for col in columns)
                order_by = (
                    _quote_identifier("id")
                    if "id" in columns
                    else ",".join(_quote_identifier(col) for col in columns)
                )
                digest.update(
                    json.dumps(columns, ensure_ascii=True, separators=(",", ":"))
                    .encode("utf-8")
                )
                digest.update(b"\n")

                row_count = 0
                cursor = conn.execute(
                    f"SELECT {quoted_columns} FROM {quoted_table} ORDER BY {order_by}"
                )
                while True:
                    rows = cursor.fetchmany(500)
                    if not rows:
                        break
                    for row in rows:
                        payload = [
                            _normalize_db_value(row[col]) for col in row.keys()
                        ]
                        digest.update(
                            json.dumps(
                                payload,
                                ensure_ascii=True,
                                separators=(",", ":"),
                                default=str,
                            ).encode("utf-8")
                        )
                        digest.update(b"\n")
                        row_count += 1

                result["tables"][table] = {"exists": True, "rows": row_count}
        finally:
            conn.close()
    except Exception as e:
        result["error"] = str(e)
        return result

    result["ok"] = True
    result["fingerprint"] = digest.hexdigest()
    return result


def _database_fast_fingerprint(
    path: str, tables=DB_PRIMARY_SYNC_TABLES
) -> Dict[str, Any]:
    """Return a lightweight DB signature for large sync-status checks.

    The full logical fingerprint is exact but expensive for cache-heavy tables
    such as extracted chapters. This path keeps status checks responsive by
    using SQLite aggregates over table shape, row counts, update markers, and
    payload lengths.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "fingerprint": None,
        "tables": {},
        "error": None,
        "mode": "fast",
    }
    if not _valid_database(path):
        result["error"] = "missing-or-empty"
        return result

    digest = hashlib.sha256()
    uri_flags = "mode=ro" if _wal_has_pending_data(path) else "mode=ro&immutable=1"
    uri = f"file:{quote(os.path.abspath(path))}?{uri_flags}"

    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA query_only = ON")
            for table in tables:
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                digest.update(f"table:{table}:".encode("utf-8"))
                if not exists:
                    digest.update(b"missing\n")
                    result["tables"][table] = {"exists": False, "rows": 0}
                    continue

                quoted_table = _quote_identifier(table)
                column_rows = list(conn.execute(f"PRAGMA table_info({quoted_table})"))
                columns = [row["name"] for row in column_rows]
                aggregate_exprs = ["COUNT(*) AS row_count"]
                for marker in ("id", "updated_at", "created_at", "filename"):
                    if marker in columns:
                        aggregate_exprs.append(
                            f"MAX({_quote_identifier(marker)}) AS max_{marker}"
                        )

                payload_columns = [
                    col
                    for col in columns
                    if col
                    not in {
                        "created_at",
                        "updated_at",
                    }
                ]
                for col in payload_columns:
                    quoted_col = _quote_identifier(col)
                    aggregate_exprs.append(
                        f"SUM(LENGTH(COALESCE(CAST({quoted_col} AS TEXT), ''))) "
                        f"AS len_{col}"
                    )

                row = conn.execute(
                    f"SELECT {', '.join(aggregate_exprs)} FROM {quoted_table}"
                ).fetchone()
                table_info = {
                    "exists": True,
                    "columns": columns,
                    "rows": int(row["row_count"] or 0) if row else 0,
                    "markers": {},
                    "lengths": {},
                }
                if row:
                    row_keys = row.keys()
                    for key in row_keys:
                        value = row[key]
                        if key.startswith("max_"):
                            table_info["markers"][key[4:]] = value
                        elif key.startswith("len_"):
                            table_info["lengths"][key[4:]] = int(value or 0)

                digest.update(
                    json.dumps(
                        table_info,
                        ensure_ascii=True,
                        separators=(",", ":"),
                        default=str,
                    ).encode("utf-8")
                )
                digest.update(b"\n")
                result["tables"][table] = {
                    "exists": True,
                    "rows": table_info["rows"],
                }
        finally:
            conn.close()
    except Exception as e:
        result["error"] = str(e)
        return result

    result["ok"] = True
    result["fingerprint"] = digest.hexdigest()
    return result


def _compare_database_files(local_path: str, cloud_path: str) -> Dict[str, Any]:
    local_exists = _valid_database(local_path)
    cloud_exists = _valid_database(cloud_path)
    local_size = os.path.getsize(local_path) if local_exists else 0
    cloud_size = os.path.getsize(cloud_path) if cloud_exists else 0
    local_mtime = os.path.getmtime(local_path) if local_exists else 0
    cloud_mtime = os.path.getmtime(cloud_path) if cloud_exists else 0

    comparison: Dict[str, Any] = {
        "different": False,
        "same_content": False,
        "reason": "missing",
        "size_diff": abs(local_size - cloud_size),
        "mtime_diff": abs(local_mtime - cloud_mtime),
        "local_fingerprint_ok": False,
        "cloud_fingerprint_ok": False,
        "fingerprint_mode": "none",
    }

    if not local_exists or not cloud_exists:
        return comparison

    use_fast_cache_fingerprint = (
        max(local_size, cloud_size) > DB_FULL_CACHE_FINGERPRINT_MAX_BYTES
    )
    cache_fingerprint_fn = (
        _database_fast_fingerprint
        if use_fast_cache_fingerprint
        else _database_logical_fingerprint
    )
    comparison["fingerprint_mode"] = (
        "primary-full/cache-fast" if use_fast_cache_fingerprint else "full"
    )

    local_fp = _database_logical_fingerprint(local_path, DB_PRIMARY_SYNC_TABLES)
    cloud_fp = _database_logical_fingerprint(cloud_path, DB_PRIMARY_SYNC_TABLES)
    comparison["local_fingerprint_ok"] = local_fp["ok"]
    comparison["cloud_fingerprint_ok"] = cloud_fp["ok"]
    comparison["local_tables"] = local_fp.get("tables", {})
    comparison["cloud_tables"] = cloud_fp.get("tables", {})
    comparison["cache_different"] = False

    if local_fp["ok"] and cloud_fp["ok"]:
        same_content = local_fp["fingerprint"] == cloud_fp["fingerprint"]
        cache_different = False
        if same_content:
            local_cache_fp = cache_fingerprint_fn(local_path, DB_CACHE_SYNC_TABLES)
            cloud_cache_fp = cache_fingerprint_fn(cloud_path, DB_CACHE_SYNC_TABLES)
            cache_different = (
                local_cache_fp["ok"]
                and cloud_cache_fp["ok"]
                and local_cache_fp["fingerprint"] != cloud_cache_fp["fingerprint"]
            )
        comparison["same_content"] = same_content
        comparison["cache_different"] = cache_different
        comparison["different"] = not same_content
        if same_content and cache_different:
            comparison["reason"] = "same-primary-content-cache-different"
        else:
            comparison["reason"] = (
                "same-logical-content"
                if same_content
                else "logical-content-different"
            )
        return comparison

    if comparison["size_diff"] > 100:
        comparison["different"] = True
        comparison["reason"] = "size-different"
    else:
        comparison["same_content"] = True
        comparison["reason"] = "size-same-fingerprint-unavailable"

    return comparison
