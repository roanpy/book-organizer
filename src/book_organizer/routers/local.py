# -*- coding: utf-8 -*-
"""Local/offline features router - ISBN lookup, categorize, duplicates, identify, suggest."""

import os
from typing import Any, Dict

from fastapi import APIRouter

from book_organizer.config import load_config
from book_organizer.database import get_db
from book_organizer.file_ops import resolve_file_path
from book_organizer.isbn_lookup import (
    auto_lookup_isbn,
    lookup_isbn_google,
    lookup_isbn_openlibrary,
)
from book_organizer.local_utils import (
    CATEGORY_RULES,
    auto_categorize,
    find_similar_titles,
    get_available_target_directories,
    local_identify_metadata,
    local_suggest_directories,
)

from .models import (
    ISBNLookupRequest,
    LocalCategorizeRequest,
    LocalDuplicateRequest,
    LocalIdentifyRequest,
    LocalSuggestDirsRequest,
)

router = APIRouter(tags=["local"])


@router.post("/api/local/isbn-lookup")
def isbn_lookup(request: ISBNLookupRequest) -> Dict[str, Any]:
    try:
        isbn = request.isbn
        result = None
        if request.file_path:
            config = load_config()
            resolved_path = resolve_file_path(request.file_path, config)
            if resolved_path and os.path.exists(resolved_path):
                result = auto_lookup_isbn(resolved_path, prefer_api=request.api)
        if not result and isbn:
            if request.api == "google":
                result = lookup_isbn_google(isbn)
            else:
                result = lookup_isbn_openlibrary(isbn)
        if result:
            return {
                "success": True,
                "isbn": result.get("isbn", isbn),
                "metadata": result,
            }
        else:
            return {"success": False, "isbn": isbn, "message": "未找到相关图书信息"}
    except Exception as e:
        print(f"Server ISBN lookup error: {e}")
        return {"success": False, "message": str(e)}


@router.post("/api/local/categorize")
def local_categorize(request: LocalCategorizeRequest) -> Dict[str, Any]:
    try:
        category = auto_categorize(request.title, request.tags)
        return {
            "success": True,
            "category": category,
            "available_categories": list(CATEGORY_RULES.keys()),
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/local/find-duplicates")
def find_local_duplicates(request: LocalDuplicateRequest) -> Dict[str, Any]:
    try:
        db = get_db()
        all_books = db.get_all_books()
        book_list = [
            {"title": b.get("filename", ""), "path": b.get("path", "")}
            for b in all_books
            if b.get("filename")
        ]
        similar = find_similar_titles(request.title, book_list, request.threshold)
        return {
            "success": True,
            "query": request.title,
            "duplicates": similar[:10],
            "total_found": len(similar),
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/local/identify-metadata")
def local_identify_metadata_endpoint(request: LocalIdentifyRequest) -> Dict[str, Any]:
    try:
        config = load_config()
        requested_path = request.file_path or request.filename
        if not requested_path:
            return {"success": False, "message": "文件路径为空"}

        resolved_path = resolve_file_path(requested_path, config)
        if not resolved_path or not os.path.exists(resolved_path):
            return {"success": False, "message": "文件不存在"}
        result = local_identify_metadata(resolved_path)
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/local/suggest-directories")
def local_suggest_directories_endpoint(
    request: LocalSuggestDirsRequest,
) -> Dict[str, Any]:
    try:
        config = load_config()
        target_dir = config.get("target_dir")
        if not target_dir:
            return {"success": False, "message": "目标目录未配置"}

        available_dirs = get_available_target_directories(target_dir)
        suggestions = local_suggest_directories(
            request.title, request.author, available_dirs
        )
        return {"success": True, "suggestions": suggestions}
    except Exception as e:
        return {"success": False, "message": str(e)}
