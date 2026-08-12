# -*- coding: utf-8 -*-
"""File operations router - move, rename, delete, skip, metadata write."""

import os
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from book_organizer import (
    save_history_item,
    truncate_filename_smart,
    write_epub_metadata,
    write_pdf_metadata,
)
from book_organizer.config import load_config
from book_organizer.database import get_db, get_toc_db
from book_organizer.file_ops import resolve_file_path
from book_organizer.library_path_repair import path_is_in_book_roots, path_is_inside
from book_organizer.toc_extractor import extract_toc

from .models import (
    MoveRequest,
    RenameAndMoveRequest,
    RenameOnlyRequest,
    SkipRequest,
    WriteMetadataRequest,
)

router = APIRouter(tags=["book-ops"])


def _require_managed_file(file_path: str | None, config: dict) -> str:
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    if not path_is_in_book_roots(file_path, config):
        raise HTTPException(status_code=403, detail="文件不在已配置的图书目录内")
    return file_path


@router.post("/api/move")
def move_book(request: MoveRequest) -> Dict[str, Any]:
    import shutil

    config = load_config()
    target_dir = config.get("target_dir")
    if not target_dir:
        raise HTTPException(status_code=400, detail="Target directory not configured")

    source_path = resolve_file_path(request.filename, config)
    source_path = _require_managed_file(source_path, config)

    dest_path = os.path.join(
        target_dir, request.destination, os.path.basename(request.filename)
    )
    if not path_is_inside(dest_path, target_dir):
        raise HTTPException(status_code=400, detail="Invalid destination")
    if os.path.exists(dest_path) and os.path.realpath(source_path) != os.path.realpath(
        dest_path
    ):
        raise HTTPException(status_code=409, detail="目标位置已存在同名文件")
    dest_dir_path = os.path.dirname(dest_path)
    os.makedirs(dest_dir_path, exist_ok=True)

    try:
        shutil.move(source_path, dest_path)
        save_history_item(
            request.filename, "processed", {"destination": request.destination}
        )
        return {"success": True, "message": f"Moved to {request.destination}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/rename_and_move")
def rename_and_move(request: RenameAndMoveRequest):
    from book_organizer.transfer import rename_and_move_book

    result = rename_and_move_book(
        request.original_filename,
        request.metadata,
        request.destination,
        request.summary,
    )
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.post("/api/rename_only")
def rename_only(request: RenameOnlyRequest):
    config = load_config()
    source_dir = config.get("source_dir")
    target_dir = config.get("target_dir")
    source_path = resolve_file_path(request.original_filename, config)

    source_path = _require_managed_file(source_path, config)

    ext = os.path.splitext(request.original_filename)[1]
    new_name_stem = request.metadata.get("new_filename")

    if not new_name_stem:
        author = request.metadata.get("author", "").strip()
        title = request.metadata.get("title", "").strip()
        if author and title:
            new_name_stem = f"[{author}] {title}"
        else:
            new_name_stem = os.path.splitext(request.original_filename)[0]

    illegal_chars = ["\\", "/", "*", "?", ":", '"', "<", ">", "|"]
    for char in illegal_chars:
        new_name_stem = new_name_stem.replace(char, "")

    new_name_stem = truncate_filename_smart(new_name_stem, ext)
    new_filename = new_name_stem + ext
    source_dir_path = os.path.dirname(source_path)
    new_path = os.path.join(source_dir_path, new_filename)

    try:
        metadata_updated = False
        config = load_config()
        beta_features = config.get("beta_features", {})
        allow_write_summary_epub = beta_features.get("enable_summary_write_epub", False)
        allow_write_summary_pdf = beta_features.get("enable_summary_write_pdf", False)

        if request.summary:
            if ext.lower() == ".epub" and allow_write_summary_epub:
                request.metadata["description"] = request.summary
            elif ext.lower() == ".pdf" and allow_write_summary_pdf:
                request.metadata["description"] = request.summary

        if ext.lower() == ".epub":
            if beta_features.get("enable_metadata_write_epub", False):
                metadata_updated = write_epub_metadata(source_path, request.metadata)
        elif ext.lower() == ".pdf":
            if beta_features.get("enable_metadata_write_pdf", False):
                metadata_updated = write_pdf_metadata(source_path, request.metadata)

        if os.path.basename(source_path) == new_filename:
            db = get_db()
            existing_summary = db.get_summary(source_path)
            summary_text = (
                request.summary
                if request.summary
                else (existing_summary.get("summary", "") if existing_summary else "")
            )
            db.save_summary(
                source_path,
                {
                    "metadata": request.metadata,
                    "summary": summary_text,
                    "category": "Library",
                },
            )
            save_history_item(
                request.original_filename,
                "updated",
                {
                    "path": source_path,
                    "summary_updated": bool(request.summary),
                    "metadata_updated": metadata_updated,
                },
            )
            msg = "已保存" + (" (元数据已写入文件)" if metadata_updated else "")

            rel_path = os.path.basename(source_path)
            if source_dir and source_path.startswith(source_dir):
                rel_path = os.path.relpath(source_path, source_dir)
            elif target_dir and source_path.startswith(target_dir):
                rel_path = os.path.relpath(source_path, target_dir)
            return {"success": True, "message": msg, "new_filename": rel_path}

        temp_name = f".tmp_{uuid.uuid4().hex[:8]}{ext}"
        temp_path = os.path.join(source_dir_path, temp_name)

        try:
            os.rename(source_path, temp_path)
            if os.path.exists(new_path) and os.path.realpath(
                temp_path
            ) != os.path.realpath(new_path):
                os.rename(temp_path, source_path)
                raise HTTPException(status_code=409, detail="目标文件名已存在")
            os.rename(temp_path, new_path)
        except HTTPException:
            raise
        except Exception as e:
            if os.path.exists(temp_path) and not os.path.exists(source_path):
                try:
                    os.rename(temp_path, source_path)
                except OSError:
                    pass
            raise HTTPException(status_code=500, detail=f"重命名失败: {str(e)}")

        db = get_db()
        old_filename = os.path.basename(source_path)
        new_filename_base = os.path.basename(new_path)
        if old_filename != new_filename_base:
            db.update_filename(source_path, new_filename_base, new_path)
            try:
                toc_db = get_toc_db()
                toc_db.update_filename(source_path, new_filename_base, new_path)
            except Exception:
                pass

        existing_summary = db.get_summary(new_path)
        summary_text = (
            request.summary
            if request.summary
            else (existing_summary.get("summary", "") if existing_summary else "")
        )
        db.save_summary(
            new_path,
            {
                "metadata": request.metadata,
                "summary": summary_text,
                "category": "Library",
            },
        )

        has_toc = False
        try:
            toc_result = extract_toc(new_path)
            if toc_result.get("success") and toc_result.get("entry_count", 0) > 0:
                toc_db = get_toc_db()
                toc_db.save_toc(new_path, toc_result)
                has_toc = True
        except Exception:
            pass

        new_relative_path = os.path.basename(new_path)
        if source_dir and new_path.startswith(source_dir):
            new_relative_path = os.path.relpath(new_path, source_dir)
        elif target_dir and new_path.startswith(target_dir):
            new_relative_path = os.path.relpath(new_path, target_dir)

        message = f"已重命名为: {os.path.basename(new_path)}" + (
            "（元数据已更新）" if metadata_updated else ""
        )
        save_history_item(
            request.original_filename,
            "renamed",
            {
                "new_filename": os.path.basename(new_path),
                "path": new_path,
                "metadata_updated": metadata_updated,
            },
        )

        return {
            "success": True,
            "message": message,
            "new_filename": new_relative_path,
            "has_toc": has_toc,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重命名失败: {str(e)}")


@router.post("/api/delete")
def delete_book(request: SkipRequest) -> Dict[str, Any]:
    try:
        config = load_config()
        file_path = resolve_file_path(request.filename, config)
        file_path = _require_managed_file(file_path, config)

        os.remove(file_path)
        db = get_db()
        delete_stats = db._db.delete_book_records(request.filename, file_path)
        save_history_item(request.filename, "deleted")

        msg = "文件已删除"
        if delete_stats["summaries"] > 0 or delete_stats["tocs"] > 0:
            msg += f" (清理记录: 简介{delete_stats['summaries']}条, 目录{delete_stats['tocs']}条)"

        return {"success": True, "message": msg}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/skip")
def skip_book(request: SkipRequest) -> Dict[str, Any]:
    try:
        save_history_item(request.filename, "skipped")
        return {"success": True, "message": "Book skipped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/unskip")
def unskip_book(request: SkipRequest) -> Dict[str, Any]:
    try:
        save_history_item(request.filename, "pending")
        return {"success": True, "message": "Book unskipped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/write_epub_metadata")
def handle_write_epub_metadata(request: WriteMetadataRequest):
    config = load_config()
    file_path = resolve_file_path(request.filename, config)
    file_path = _require_managed_file(file_path, config)
    ext = os.path.splitext(request.filename)[1].lower()
    if ext != ".epub":
        raise HTTPException(status_code=400, detail="不是EPUB文件")
    try:
        success = write_epub_metadata(file_path, request.metadata)
        if success:
            return {"success": True, "message": "EPUB元数据写入成功"}
        else:
            raise HTTPException(status_code=500, detail="EPUB元数据写入失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入失败: {str(e)}")


@router.post("/api/write_pdf_metadata")
def handle_write_pdf_metadata(request: WriteMetadataRequest):
    config = load_config()
    file_path = resolve_file_path(request.filename, config)
    file_path = _require_managed_file(file_path, config)
    ext = os.path.splitext(request.filename)[1].lower()
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="不是PDF文件")
    try:
        success = write_pdf_metadata(file_path, request.metadata)
        if success:
            return {"success": True, "message": "PDF元数据写入成功"}
        else:
            raise HTTPException(status_code=500, detail="PDF元数据写入失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入失败: {str(e)}")
