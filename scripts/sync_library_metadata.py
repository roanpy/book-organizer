#!/usr/bin/env python3
# ruff: noqa: E402,I001
"""Sync extractable TOCs and embedded enhanced summaries into the local DB.

This script never writes to EPUB/PDF files. It only updates book_data.db.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from book_organizer.database import get_db, get_toc_db
from book_organizer.metadata import extract_metadata
from book_organizer.metadata_sync import (
    SUMMARY_SOURCE_FORMATS,
    TOC_SOURCE_FORMATS,
    ensure_extracted_toc_in_db,
    iter_configured_book_files,
    sync_embedded_summary_to_db,
)
from book_organizer.summary_utils import (
    extract_embedded_enhanced_summary,
    should_sync_embedded_summary,
)
from book_organizer.toc_extractor import extract_toc


def backup_database() -> Path | None:
    db = get_db()
    db_path = Path(db.db_path)
    if not db_path.exists():
        return None
    backup = db_path.with_name(
        f"{db_path.stem}.before_metadata_sync.{time.strftime('%Y%m%d-%H%M%S')}{db_path.suffix}"
    )
    shutil.copy2(db_path, backup)
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summaries", action="store_true", help="sync embedded enhanced summaries")
    parser.add_argument("--toc", action="store_true", help="sync extractable PDF/EPUB TOCs")
    parser.add_argument(
        "--prefer-embedded-summary",
        action="store_true",
        help="overwrite DB summaries when embedded structured summary differs",
    )
    parser.add_argument("--overwrite-toc", action="store_true", help="replace existing DB TOCs")
    parser.add_argument("--max-pages", type=int, default=20, help="PDF/EPUB scan depth for TOC fallback")
    parser.add_argument("--limit", type=int, default=0, help="max files to check, for dry runs")
    parser.add_argument("--dry-run", action="store_true", help="report only; do not write DB")
    args = parser.parse_args()

    sync_summaries = args.summaries or not args.toc
    sync_toc = args.toc or not args.summaries

    if args.dry_run:
        backup = None
    else:
        backup = backup_database()
    if backup:
        print(f"DB_BACKUP={backup}")

    extensions = set()
    if sync_summaries:
        extensions |= SUMMARY_SOURCE_FORMATS
    if sync_toc:
        extensions |= TOC_SOURCE_FORMATS

    checked = 0
    summary_checked = 0
    summary_updated = 0
    toc_checked = 0
    toc_updated = 0
    errors = 0
    samples: list[str] = []

    for path in iter_configured_book_files(extensions=extensions):
        checked += 1
        if args.limit and checked > args.limit:
            break

        try:
            if sync_summaries and path.suffix.lower() in SUMMARY_SOURCE_FORMATS:
                summary_checked += 1
                if args.dry_run:
                    metadata = extract_metadata(str(path)) or {}
                    embedded = extract_embedded_enhanced_summary(metadata)
                    db_record = get_db().get_summary(str(path))
                    db_summary = db_record.get("summary", "") if db_record else ""
                    result = {
                        "updated": bool(
                            embedded
                            and (
                                args.prefer_embedded_summary
                                and embedded != db_summary
                                or should_sync_embedded_summary(db_summary, embedded)
                            )
                        )
                    }
                else:
                    result = sync_embedded_summary_to_db(
                        str(path), prefer_embedded=args.prefer_embedded_summary
                    )
                if result.get("updated"):
                    summary_updated += 1
                    if len(samples) < 12:
                        samples.append(f"SUMMARY {path}")

            if sync_toc and path.suffix.lower() in TOC_SOURCE_FORMATS:
                toc_checked += 1
                if args.dry_run:
                    toc_result = extract_toc(str(path), max_pages=args.max_pages)
                    existing = get_toc_db().get_toc(str(path))
                    result = {
                        "updated": bool(
                            toc_result.get("success")
                            and toc_result.get("entry_count", 0) > 0
                            and (
                                args.overwrite_toc
                                or not existing
                                or existing.get("entry_count", 0) <= 0
                            )
                        ),
                        "entry_count": toc_result.get("entry_count", 0),
                        "method": toc_result.get("method", ""),
                    }
                else:
                    result = ensure_extracted_toc_in_db(
                        str(path), overwrite=args.overwrite_toc, max_pages=args.max_pages
                    )
                if result.get("updated"):
                    toc_updated += 1
                    if len(samples) < 12:
                        samples.append(
                            f"TOC {result.get('entry_count', 0)} {result.get('method', '')} {path}"
                        )
        except Exception as exc:
            errors += 1
            if len(samples) < 12:
                samples.append(f"ERROR {path}: {exc}")

    print(f"CHECKED={checked}")
    print(f"SUMMARY_CHECKED={summary_checked}")
    print(f"SUMMARY_UPDATED={summary_updated}")
    print(f"TOC_CHECKED={toc_checked}")
    print(f"TOC_UPDATED={toc_updated}")
    print(f"ERRORS={errors}")
    for sample in samples:
        print(f"SAMPLE={sample}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
