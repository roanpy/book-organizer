"""Database sync helpers for file metadata-derived content."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .config import load_config
from .database import get_db, get_toc_db
from .file_ops import get_configured_book_extensions, normalize_book_extensions
from .metadata import extract_metadata
from .summary_utils import (
    choose_enhanced_summary,
    extract_embedded_enhanced_summary,
    should_sync_embedded_summary,
)
from .toc_extractor import extract_toc

TOC_SOURCE_FORMATS = {".epub", ".pdf"}
SUMMARY_SOURCE_FORMATS = {".epub", ".pdf"}


def configured_book_roots(config: Dict[str, Any] | None = None) -> List[Path]:
    """Return existing configured book roots without duplicates."""
    config = config or load_config()
    roots: List[Path] = []
    for key in ("target_dir", "source_dir"):
        value = config.get(key)
        if value:
            roots.append(Path(os.path.expanduser(value)))
    for value in config.get("library_directories") or []:
        if value:
            roots.append(Path(os.path.expanduser(value)))

    result: List[Path] = []
    seen = set()
    for root in roots:
        try:
            resolved = root.resolve()
        except Exception:
            continue
        if not resolved.exists() or resolved in seen:
            continue
        seen.add(resolved)
        result.append(resolved)
    return result


def iter_configured_book_files(
    config: Dict[str, Any] | None = None,
    extensions: Iterable[str] | None = None,
):
    if extensions is None:
        extensions = get_configured_book_extensions(config)
    extensions = set(normalize_book_extensions(extensions))
    for root in configured_book_roots(config):
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in extensions:
                yield path


def sync_embedded_summary_to_db(
    file_path: str,
    *,
    prefer_embedded: bool = False,
    category: str = "Library",
) -> Dict[str, Any]:
    """Copy a structured embedded enhanced summary into the DB when appropriate."""
    path = os.path.abspath(os.path.expanduser(file_path))
    if Path(path).suffix.lower() not in SUMMARY_SOURCE_FORMATS:
        return {"checked": False, "updated": False, "reason": "unsupported_format"}

    metadata = extract_metadata(path) or {}
    embedded_summary = extract_embedded_enhanced_summary(metadata)
    if not embedded_summary:
        return {"checked": True, "updated": False, "reason": "no_embedded_summary"}

    db = get_db()
    db_record = db.get_summary(path)
    db_summary = db_record.get("summary", "") if db_record else ""
    should_update = (
        bool(prefer_embedded and embedded_summary != db_summary)
        or should_sync_embedded_summary(db_summary, embedded_summary)
    )
    if not should_update:
        return {
            "checked": True,
            "updated": False,
            "reason": "database_current",
            "summary": choose_enhanced_summary(db_summary, embedded_summary),
        }

    summary_metadata = dict(metadata)
    summary_metadata.pop("description", None)
    ok = db.save_summary(
        path,
        {
            "metadata": summary_metadata,
            "summary": embedded_summary,
            "category": (db_record or {}).get("category", category),
        },
    )
    return {
        "checked": True,
        "updated": bool(ok),
        "reason": "updated" if ok else "save_failed",
    }


def ensure_extracted_toc_in_db(
    file_path: str,
    *,
    overwrite: bool = False,
    max_pages: int = 20,
) -> Dict[str, Any]:
    """Extract a built-in/readable TOC into DB, without writing to the book file."""
    path = os.path.abspath(os.path.expanduser(file_path))
    if Path(path).suffix.lower() not in TOC_SOURCE_FORMATS:
        return {"checked": False, "updated": False, "reason": "unsupported_format"}

    toc_db = get_toc_db()
    existing = toc_db.get_toc(path)
    if (
        not overwrite
        and existing
        and existing.get("success")
        and existing.get("entry_count", 0) > 0
    ):
        return {
            "checked": True,
            "updated": False,
            "reason": "database_current",
            "entry_count": existing.get("entry_count", 0),
        }

    toc_result = extract_toc(path, max_pages=max_pages)
    if not toc_result.get("success") or toc_result.get("entry_count", 0) <= 0:
        return {"checked": True, "updated": False, "reason": "no_extractable_toc"}

    ok = toc_db.save_toc(path, toc_result)
    return {
        "checked": True,
        "updated": bool(ok),
        "reason": "updated" if ok else "save_failed",
        "entry_count": toc_result.get("entry_count", 0),
        "method": toc_result.get("method", "builtin"),
    }
