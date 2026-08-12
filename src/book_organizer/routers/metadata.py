# -*- coding: utf-8 -*-
"""Metadata query router - summary, TOC, metadata lookups."""

import asyncio
import os
from typing import Any, Dict

from fastapi import APIRouter

from book_organizer import extract_metadata
from book_organizer.config import load_config
from book_organizer.database import get_db, get_toc_db
from book_organizer.file_ops import resolve_file_path
from book_organizer.summary_utils import (
    choose_enhanced_summary,
    extract_embedded_enhanced_summary,
    sync_embedded_summary_to_db,
)
from book_organizer.toc_extractor import extract_toc

router = APIRouter(tags=["metadata"])


@router.get("/api/metadata/{filename:path}")
async def get_book_metadata(filename: str) -> Dict[str, Any]:
    def do_load_metadata():
        config = load_config()
        file_path = resolve_file_path(filename, config)
        if not file_path or not os.path.exists(file_path):
            return {}

        metadata = extract_metadata(file_path)
        embedded_summary = extract_embedded_enhanced_summary(metadata)

        saved_summary_text = ""
        try:
            db = get_db()
            abs_path = os.path.abspath(file_path)
            saved_data = db.get_summary(abs_path)
            if not saved_data:
                saved_data = db.get_summary(file_path)

            data_priority = config.get("beta_features", {}).get(
                "data_priority", "database"
            )
            db_summary = saved_data.get("summary", "") if saved_data else ""
            saved_summary_text = choose_enhanced_summary(
                db_summary, embedded_summary, data_priority
            )
            if sync_embedded_summary_to_db(
                db, abs_path, metadata, db_summary, embedded_summary
            ):
                saved_data = db.get_summary(abs_path)
                db_summary = saved_data.get("summary", "") if saved_data else db_summary

            if saved_summary_text:
                metadata["db_summary"] = saved_summary_text
                metadata["db_summary_raw"] = db_summary
                metadata["embedded_summary"] = embedded_summary
                metadata["summary_source"] = (
                    "metadata" if saved_summary_text == embedded_summary else "database"
                )
        except Exception as e:
            print(f"Error loading enhanced summary: {e}")
            if embedded_summary:
                metadata["db_summary"] = embedded_summary
                metadata["embedded_summary"] = embedded_summary
                metadata["summary_source"] = "metadata"

        return metadata

    return await asyncio.to_thread(do_load_metadata)


@router.get("/api/enhanced_summary")
def get_existing_enhanced_summary(filename: str):
    try:
        config = load_config()
        file_path = resolve_file_path(filename, config)
        if not file_path:
            return {"success": False, "error": "File not found"}
        db = get_db()
        summary_data = db.get_summary(file_path) or db.get_summary(filename)
        db_summary = summary_data.get("summary", "") if summary_data else ""
        metadata = {}
        embedded_summary = ""
        try:
            if os.path.exists(file_path):
                metadata = extract_metadata(file_path) or {}
                embedded_summary = extract_embedded_enhanced_summary(metadata)
        except Exception as e:
            print(f"Error reading embedded summary: {e}")

        summary_text = choose_enhanced_summary(
            db_summary,
            embedded_summary,
            config.get("beta_features", {}).get("data_priority", "database"),
        )
        if embedded_summary and sync_embedded_summary_to_db(
                db, file_path, metadata, db_summary, embedded_summary
        ):
            summary_data = db.get_summary(file_path) or summary_data
            db_summary = summary_data.get("summary", "") if summary_data else db_summary

        if summary_text:
            return {
                "success": True,
                "summary": summary_text,
                "database_summary": db_summary,
                "embedded_summary": embedded_summary,
                "metadata": (summary_data or {}).get("metadata", {}),
                "source": "metadata" if summary_text == embedded_summary else "database",
            }
        return {"success": False, "message": "No summary found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/toc_query")
def get_existing_toc(filename: str):
    try:
        config = load_config()
        file_path = resolve_file_path(filename, config)
        if not file_path:
            return {"success": False, "error": "File not found"}

        toc_db = get_toc_db()
        toc_data = toc_db.get_toc(file_path) or toc_db.get_toc(filename)
        if toc_data and (
            toc_data.get("toc")
            or toc_data.get("toc_text")
            or toc_data.get("entry_count", 0) > 0
        ):
            return toc_data

        # 数据库没有缓存时，只读原文件内置目录并写入应用数据库缓存。
        # 这不会修改 PDF/EPUB 文件本体；只有显式写入元数据接口才会改文件。
        extracted = extract_toc(file_path)
        if extracted.get("success") and (
            extracted.get("toc")
            or extracted.get("toc_text")
            or extracted.get("entry_count", 0) > 0
        ):
            toc_db.save_toc(file_path, extracted)
            extracted["source"] = "metadata"
            return extracted

        return {"success": False, "message": "No TOC in database or metadata"}
    except Exception as e:
        return {"success": False, "error": str(e)}
