from typing import Any, Dict

from fastapi import APIRouter

from book_organizer.library_path_repair import inspect_library_health

# Sync Manager
from book_organizer.sync_manager import sync_manager

from . import internal_error
from .models import (
    DeleteFileRequest,
    ExecuteSyncRequest,
    IgnoreGroupRequest,
    UnignoreGroupRequest,
)

router = APIRouter()


@router.get("/api/db/health")
def get_database_health() -> Dict[str, Any]:
    """Run a read-only database and library path health check."""
    try:
        return inspect_library_health()
    except Exception as e:
        raise internal_error("database health check", e, "数据库检查失败")

# ==============================================================================
# 数据库同步 API
# ==============================================================================


@router.post("/api/db/sync/analyze")
def analyze_db_sync() -> Dict[str, Any]:
    """分析数据库与文件系统的同步状态"""
    try:
        return sync_manager.analyze()
    except Exception as e:
        raise internal_error("database sync analysis", e, "同步分析失败")


@router.post("/api/db/sync/execute")
def execute_db_sync(request: ExecuteSyncRequest) -> Dict[str, Any]:
    """执行数据库同步操作"""
    try:
        return sync_manager.execute(request.operations)
    except Exception as e:
        raise internal_error("database sync execution", e, "同步处理失败")


# ==============================================================================
# 查重功能 API
# ==============================================================================


@router.post("/api/db/deduplicate/analyze")
def analyze_duplicates() -> Dict[str, Any]:
    """Library Deduplication Analysis"""
    try:
        return sync_manager.analyze_duplicates()
    except Exception as e:
        raise internal_error("duplicate analysis", e, "查重分析失败")


@router.post("/api/db/deduplicate/delete")
def delete_duplicate_file(request: DeleteFileRequest) -> Dict[str, Any]:
    """Delete a specific file for deduplication"""
    try:
        return sync_manager.delete_file(request.path)
    except Exception as e:
        raise internal_error("duplicate deletion", e, "删除重复文件失败")


@router.post("/api/db/deduplicate/ignore")
def ignore_deduplicate_group(request: IgnoreGroupRequest) -> Dict[str, Any]:
    """Ignore a duplicate group"""
    try:
        return sync_manager.ignore_group(request.paths)
    except Exception as e:
        raise internal_error("ignore duplicate group", e, "忽略查重记录失败")


@router.post("/api/db/deduplicate/unignore")
def unignore_deduplicate_group(request: UnignoreGroupRequest) -> Dict[str, Any]:
    """Unignore a duplicate group"""
    try:
        return sync_manager.unignore_group(request.id)
    except Exception as e:
        raise internal_error("restore duplicate group", e, "恢复查重记录失败")
