# -*- coding: utf-8 -*-
"""Library browsing/listing router - books, covers, categories, ratings, details."""

import asyncio
import datetime
import json
import os
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Response

from book_organizer import (
    extract_metadata,
    find_similar_files,
    get_book_files,
    get_book_status,
)
from book_organizer.config import load_config
from book_organizer.database import get_db, get_toc_db
from book_organizer.file_ops import (
    get_cover_image,
    get_target_categories,
    parse_filename_to_dict,
    resolve_file_path,
)
from book_organizer.library_path_repair import (
    path_is_inside,
    portable_library_path_for_target,
)
from book_organizer.metadata_sync import ensure_extracted_toc_in_db
from book_organizer.summary_utils import (
    choose_enhanced_summary,
    extract_embedded_enhanced_summary,
    sync_embedded_summary_to_db,
)

from . import internal_error, log_internal_error
from .models import (
    BrowseRequest,
    FindSimilarRequest,
    UpdateRatingRequest,
)

router = APIRouter(tags=["library"])


def format_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


@router.get("/api/books")
def get_books() -> Dict[str, List[Dict[str, Any]]]:
    config = load_config()
    source_dir = config.get("source_dir")
    if not source_dir or not os.path.exists(source_dir):
        return {"books": []}

    books = []
    try:
        all_files = get_book_files(source_dir)

        for file_path in all_files:
            rel_path = os.path.relpath(file_path, source_dir)
            status = get_book_status(rel_path)

            try:
                stat = os.stat(file_path)
                size_str = format_size(stat.st_size)
                mtime_str = datetime.datetime.fromtimestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d %H:%M"
                )
            except Exception:
                size_str = "Unknown"
                mtime_str = "Unknown"

            books.append(
                {
                    "name": rel_path,
                    "status": status,
                    "size": size_str,
                    "mtime": mtime_str,
                }
            )
    except Exception as e:
        log_internal_error("scan source books", e)
        return {"books": []}

    return {"books": books}


@router.post("/api/browse")
def browse_directory(request: BrowseRequest) -> Dict[str, Any]:
    start_path = request.path if request.path else os.path.expanduser("~")

    if not os.path.exists(start_path):
        start_path = os.path.expanduser("~")

    try:
        items = []
        if start_path != "/":
            items.append(
                {"name": "..", "path": os.path.dirname(start_path), "is_dir": True}
            )

        with os.scandir(start_path) as it:
            for entry in it:
                if entry.is_dir() and not entry.name.startswith("."):
                    items.append(
                        {"name": entry.name, "path": entry.path, "is_dir": True}
                    )

        items.sort(key=lambda x: x["name"])
        return {"current_path": start_path, "items": items}
    except Exception as e:
        raise internal_error("browse directory", e, "目录读取失败")


@router.put("/api/library/book/rating")
def update_rating(request: UpdateRatingRequest):
    try:
        db = get_db()
        success = db.update_book_rating(
            request.filename, request.rating, request.file_path
        )
        if not success:
            return {"success": False, "message": "Rating update failed"}
        return {"success": True, "rating": request.rating}
    except Exception as e:
        raise internal_error("update rating", e, "评分保存失败")


@router.get("/api/library")
def get_library():
    config = load_config()
    target_dir = config.get("target_dir")

    if not target_dir or not os.path.exists(target_dir):
        return {"books": [], "stats": {"total": 0, "enhanced": 0}}

    raw_files = get_book_files(target_dir)
    db = get_db()
    all_summaries = db.get_all_summaries()
    summaries_by_path = {}
    summaries_by_filename = {}

    for s in all_summaries:
        fn = s.get("filename") or os.path.basename(s["file_path"])
        summaries_by_filename.setdefault(fn, []).append(s)
        stored_path = s.get("file_path") or ""
        if stored_path:
            summaries_by_path[stored_path] = s

    toc_db = get_toc_db()
    toc_records = toc_db.get_all_records()
    toc_by_path = {
        item.get("file_path"): item for item in toc_records if item.get("file_path")
    }
    toc_by_filename = {}
    for item in toc_records:
        toc_by_filename.setdefault(item.get("filename"), []).append(item)

    books = []
    enhanced_count = 0

    for f in raw_files:
        if not os.path.exists(f):
            continue

        rel_path = os.path.relpath(f, target_dir)
        category = os.path.dirname(rel_path)
        filename = os.path.basename(f)

        stored_path = portable_library_path_for_target(f, target_dir)
        summary_record = summaries_by_path.get(stored_path)
        if not summary_record and len(summaries_by_filename.get(filename, [])) == 1:
            summary_record = summaries_by_filename[filename][0]
        has_enhanced = summary_record is not None
        has_toc = (
            stored_path in toc_by_path or len(toc_by_filename.get(filename, [])) == 1
        )

        if has_enhanced:
            enhanced_count += 1

        try:
            file_size = os.path.getsize(f)
        except (OSError, FileNotFoundError):
            file_size = 0

        book_data = {
            "name": filename,
            "path": rel_path,
            "category": category if category != "." else "Uncategorized",
            "full_path": f,
            "has_enhanced_summary": has_enhanced,
            "rating": summary_record.get("rating") if summary_record else None,
            "has_toc": has_toc,
            "size": file_size,
        }

        if has_enhanced:
            metadata = summary_record.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}
            book_data["title"] = metadata.get("title")
            book_data["author"] = metadata.get("author")
            book_data["publisher"] = metadata.get("publisher")
            book_data["tags"] = metadata.get("tags")

        books.append(book_data)

    return {
        "books": books,
        "stats": {
            "total": len(books),
            "enhanced": enhanced_count,
            "not_enhanced": len(books) - enhanced_count,
        },
    }


@router.get("/api/cover")
def get_cover(path: str):
    config = load_config()
    final_path = resolve_file_path(path, config)
    if not final_path:
        return Response(status_code=404)

    img_data = get_cover_image(final_path)
    if img_data:
        return Response(content=img_data, media_type="image/jpeg")
    return Response(status_code=404)


@router.get("/api/library/book_details")
def get_library_book_details(path: str, skip_file_read: bool = False):
    config = load_config()
    target_dir = config.get("target_dir")
    if not target_dir:
        raise HTTPException(status_code=400, detail="Target directory not set")

    full_path = path
    if not os.path.isabs(path):
        full_path = os.path.join(target_dir, path)

    if not path_is_inside(full_path, target_dir):
        raise HTTPException(status_code=403, detail="Path is outside the library")

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    db = get_db()
    metadata = {}
    summary_text = ""
    has_enhanced = False

    if skip_file_read:
        db_record = db.get_summary(full_path)
        if db_record and db_record.get("metadata"):
            metadata = db_record.get("metadata")
        if not metadata:
            metadata = parse_filename_to_dict(os.path.basename(full_path))
    else:
        try:
            metadata = extract_metadata(full_path) or {}
            if metadata.get("publisher") == "Pdg2Pic":
                metadata["publisher"] = ""
            if not metadata.get("title") or not metadata.get("author"):
                fname_meta = parse_filename_to_dict(os.path.basename(full_path))
                if not metadata.get("title") and fname_meta.get("title"):
                    metadata["title"] = fname_meta["title"]
                if not metadata.get("author") and fname_meta.get("author"):
                    metadata["author"] = fname_meta["author"]
        except Exception:
            metadata = {}

    priority = config.get("beta_features", {}).get("data_priority", "database")
    if priority not in {"database", "metadata"}:
        legacy_priority = config.get("display_priority", "file")
        priority = "database" if legacy_priority == "db" else "metadata"
    file_summary = ""
    db_summary = ""

    try:
        file_summary = extract_embedded_enhanced_summary(metadata)
    except Exception:
        pass

    summary_data = db.get_summary(full_path)
    if summary_data:
        db_summary = summary_data.get("summary", "")

    summary_text = choose_enhanced_summary(db_summary, file_summary, priority)
    has_enhanced = bool(summary_text)
    if file_summary and sync_embedded_summary_to_db(
        db, full_path, metadata, db_summary, file_summary
    ):
        summary_data = db.get_summary(full_path)
        db_summary = summary_data.get("summary", "") if summary_data else db_summary

    if summary_data:
        db_metadata = summary_data.get("metadata", {})
        for key, value in db_metadata.items():
            if not metadata.get(key) and value:
                metadata[key] = value

    rating = db.get_book_rating(full_path) or 0

    toc_data = []
    toc_text = ""
    try:
        toc_db = get_toc_db()
        toc_record = toc_db.get_toc(full_path)
        if (
            not toc_record
            or not toc_record.get("success")
            or toc_record.get("entry_count", 0) <= 0
        ):
            ensure_extracted_toc_in_db(full_path)
            toc_record = toc_db.get_toc(full_path)
        if toc_record:
            toc_data = toc_record.get("toc", [])
            toc_text = toc_record.get("toc_text", "")
    except Exception as e:
        print(f"Error loading TOC: {e}")

    return {
        "metadata": metadata,
        "summary": summary_text,
        "database_summary": db_summary,
        "embedded_summary": file_summary,
        "summary_source": "metadata" if summary_text == file_summary else "database",
        "has_enhanced": has_enhanced,
        "rating": rating,
        "toc": toc_data,
        "toc_text": toc_text,
    }


@router.get("/api/cover/{filename:path}")
async def get_book_cover(filename: str) -> Response:
    config = load_config()
    file_path = resolve_file_path(filename, config)
    if not file_path:
        return Response(status_code=404)

    img_data = await asyncio.to_thread(get_cover_image, file_path)
    if img_data:
        return Response(content=img_data, media_type="image/jpeg")

    return Response(status_code=404)


@router.get("/api/categories")
def list_categories() -> Dict[str, List[str]]:
    config = load_config()
    target_dir = config.get("target_dir")
    if not target_dir or not os.path.exists(target_dir):
        return {"categories": []}
    return {"categories": get_target_categories(target_dir)}


@router.post("/api/find_similar")
def find_similar(request: FindSimilarRequest):
    config = load_config()
    target_dir = config.get("target_dir")
    if not target_dir:
        return {"matches": []}
    exclude_paths = list(request.exclude_paths or [])
    if request.current_path:
        exclude_paths.append(request.current_path)
    matches = find_similar_files(target_dir, request.query, exclude_paths=exclude_paths)
    return {"matches": matches}
