# -*- coding: utf-8 -*-
"""
Offline fallback logic for when AI is unavailable.

Contains:
- merge_metadata(): Unified metadata merging (replaces 3 duplicated versions)
- Offline fallback handlers for each analysis function
- Local rule matching logic
"""

from typing import Any, Dict, Optional


def _get_deps():
    """Lazy import dependencies to avoid circular references."""
    from ..config import get_historical_transfers, load_config
    from ..file_ops import parse_filename_to_dict

    return {
        "load_config": load_config,
        "get_historical_transfers": get_historical_transfers,
        "parse_filename_to_dict": parse_filename_to_dict,
    }


def merge_metadata(
    user_metadata: Optional[Dict[str, Any]],
    internal_metadata: Dict[str, Any],
    file_meta: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge metadata from multiple sources with priority: user > internal > filename.

    This is the single canonical implementation replacing the three duplicated
    merge blocks that were previously inline in identify_book_metadata,
    get_batch_enhance_analysis, and get_batch_organize_analysis.

    Args:
        user_metadata: User-provided metadata (highest priority)
        internal_metadata: Metadata extracted from the file itself
        file_meta: Metadata parsed from the filename

    Returns:
        Merged metadata dict with fields: title, author, publisher, series, tags, new_filename
    """
    final_result = {}

    # Title
    if user_metadata and user_metadata.get("title"):
        final_result["title"] = user_metadata["title"]
    elif internal_metadata.get("title"):
        final_result["title"] = internal_metadata["title"]
    else:
        final_result["title"] = file_meta.get("title", "")

    # Author
    if user_metadata and user_metadata.get("author"):
        final_result["author"] = user_metadata["author"]
    elif internal_metadata.get("author"):
        final_result["author"] = internal_metadata["author"]
    else:
        final_result["author"] = file_meta.get("author", "")

    # Publisher
    if user_metadata and user_metadata.get("publisher"):
        final_result["publisher"] = user_metadata["publisher"]
    else:
        final_result["publisher"] = internal_metadata.get("publisher", "")

    # Series
    if user_metadata and user_metadata.get("series"):
        final_result["series"] = user_metadata["series"]
    else:
        final_result["series"] = internal_metadata.get("series", "")

    # Tags
    if user_metadata and user_metadata.get("tags"):
        final_result["tags"] = user_metadata["tags"]
    else:
        tags = internal_metadata.get("tags", [])
        if isinstance(tags, list):
            final_result["tags"] = ", ".join(tags)
        else:
            final_result["tags"] = str(tags) if tags else ""

    # Generate new filename suggestion (Standard logic: {title} - {author})
    t = final_result.get("title", "Unknown")
    a = final_result.get("author", "Unknown")
    final_result["new_filename"] = f"{t} - {a}"

    return final_result


def merge_metadata_no_user(
    internal_metadata: Optional[Dict[str, Any]],
    file_meta: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge metadata from internal and filename sources (no user input).

    Used by batch functions where user metadata is not available.
    Priority: internal_metadata > file_meta

    Args:
        internal_metadata: Metadata extracted from the file itself
        file_meta: Metadata parsed from the filename

    Returns:
        Merged metadata dict
    """
    final_meta = {}
    final_meta["title"] = (internal_metadata or {}).get("title") or file_meta.get(
        "title", ""
    )
    final_meta["author"] = (internal_metadata or {}).get("author") or file_meta.get(
        "author", ""
    )
    final_meta["publisher"] = (internal_metadata or {}).get("publisher") or file_meta.get(
        "publisher", ""
    )
    final_meta["series"] = (internal_metadata or {}).get("series") or file_meta.get(
        "series", ""
    )
    final_meta["tags"] = (internal_metadata or {}).get("tags") or []

    if isinstance(final_meta["tags"], list):
        final_meta["tags"] = ", ".join(final_meta["tags"])

    # Generate new filename suggestion
    t = final_meta.get("title", "Unknown")
    a = final_meta.get("author", "Unknown")
    final_meta["new_filename"] = f"{t} - {a}"

    return final_meta


def offline_identify_metadata(
    filename: str,
    user_metadata: Optional[Dict[str, Any]],
    internal_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Offline fallback for identify_book_metadata.

    Uses filename parsing and internal metadata only.

    Args:
        filename: The book filename
        user_metadata: User-provided metadata (highest priority)
        internal_metadata: Metadata extracted from the file

    Returns:
        Merged metadata dict
    """
    deps = _get_deps()
    parse_filename_to_dict = deps["parse_filename_to_dict"]

    file_meta = parse_filename_to_dict(filename)
    return merge_metadata(user_metadata, internal_metadata, file_meta)


def offline_identify_with_warning(
    filename: str,
    user_metadata: Optional[Dict[str, Any]],
    internal_metadata: Dict[str, Any],
    error: Exception,
) -> Dict[str, Any]:
    """Offline fallback for identify_book_metadata when AI fails.

    Same as offline_identify_metadata but adds a warning field.

    Args:
        filename: The book filename
        user_metadata: User-provided metadata
        internal_metadata: Metadata extracted from the file
        error: The exception that caused the fallback

    Returns:
        Merged metadata dict with warning field
    """
    result = offline_identify_metadata(filename, user_metadata, internal_metadata)
    result["warning"] = f"AI 识别失败 ({error})，已自动使用本地数据"
    return result


def offline_batch_enhance(
    filename: str,
    internal_metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Offline fallback for get_batch_enhance_analysis.

    Args:
        filename: The book filename
        internal_metadata: Metadata extracted from the file

    Returns:
        Dict with metadata and empty summary
    """
    deps = _get_deps()
    parse_filename_to_dict = deps["parse_filename_to_dict"]

    file_meta = parse_filename_to_dict(filename)
    final_meta = merge_metadata_no_user(internal_metadata, file_meta)

    return {
        "metadata": final_meta,
        "summary": "",  # Offline batch enhance does not generate summary to avoid overwriting
        "warning": "离线模式：仅更新元数据，跳过 AI 简介生成",
    }


def offline_batch_enhance_fallback(
    filename: str,
    internal_metadata: Optional[Dict[str, Any]],
    error: Exception,
) -> Dict[str, Any]:
    """Offline fallback for get_batch_enhance_analysis when AI fails.

    Args:
        filename: The book filename
        internal_metadata: Metadata extracted from the file
        error: The exception that caused the fallback

    Returns:
        Dict with metadata, empty summary, and warning
    """
    deps = _get_deps()
    parse_filename_to_dict = deps["parse_filename_to_dict"]

    file_meta = parse_filename_to_dict(filename)
    final_meta = merge_metadata_no_user(internal_metadata, file_meta)

    return {
        "metadata": final_meta,
        "summary": "",
        "warning": f"AI 分析失败 ({error})，已自动使用本地数据",
    }


def offline_batch_organize(
    filename: str,
    config: Dict[str, Any],
    internal_metadata: Optional[Dict[str, Any]],
    enable_enhanced_summary: bool = True,
) -> Dict[str, Any]:
    """Offline fallback for get_batch_organize_analysis.

    Uses local rules for categorization and directory suggestions.

    Args:
        filename: The book filename
        config: Application config dict
        internal_metadata: Metadata extracted from the file
        enable_enhanced_summary: Whether enhanced summary was requested

    Returns:
        Dict with metadata, suggestions, category, and empty summary
    """
    from ..local_utils import (
        auto_categorize,
        get_available_target_directories,
        local_suggest_directories,
    )

    deps = _get_deps()
    parse_filename_to_dict = deps["parse_filename_to_dict"]
    get_historical_transfers = deps["get_historical_transfers"]

    file_meta = parse_filename_to_dict(filename)
    final_meta = merge_metadata_no_user(internal_metadata, file_meta)

    # Local Categorization
    tags_list = final_meta["tags"] if isinstance(final_meta["tags"], list) else []
    category = auto_categorize(final_meta["title"], tags_list)

    # Local Directory Suggestions
    target_dir = config.get("target_dir", "")
    available_dirs = (
        get_available_target_directories(target_dir) if target_dir else []
    )
    history = get_historical_transfers(30)
    suggestions = local_suggest_directories(
        final_meta["title"], final_meta["author"], available_dirs, history
    )

    result = {
        "metadata": final_meta,
        "suggestions": suggestions,
        "category": category or "",
        "summary": "",
        "warning": "离线模式：使用本地规则分类，跳过 AI 简介生成",
    }

    if enable_enhanced_summary:
        result["enhancedSummary"] = ""

    return result


def offline_batch_organize_fallback(
    filename: str,
    config: Dict[str, Any],
    internal_metadata: Optional[Dict[str, Any]],
    enable_enhanced_summary: bool = True,
    error: Exception = None,
) -> Dict[str, Any]:
    """Offline fallback for get_batch_organize_analysis when AI fails.

    Args:
        filename: The book filename
        config: Application config dict
        internal_metadata: Metadata extracted from the file
        enable_enhanced_summary: Whether enhanced summary was requested
        error: The exception that caused the fallback

    Returns:
        Dict with metadata, suggestions, category, empty summary, and warning
    """
    from ..local_utils import (
        auto_categorize,
        get_available_target_directories,
        local_suggest_directories,
    )

    deps = _get_deps()
    parse_filename_to_dict = deps["parse_filename_to_dict"]
    get_historical_transfers = deps["get_historical_transfers"]

    file_meta = parse_filename_to_dict(filename)
    final_meta = merge_metadata_no_user(internal_metadata, file_meta)

    tags_list = final_meta["tags"] if isinstance(final_meta["tags"], list) else []
    category = auto_categorize(final_meta["title"], tags_list)

    target_dir = config.get("target_dir", "")
    available_dirs = (
        get_available_target_directories(target_dir) if target_dir else []
    )
    history = get_historical_transfers(30)
    suggestions = local_suggest_directories(
        final_meta["title"], final_meta["author"], available_dirs, history
    )

    warning_msg = (
        f"AI 分析失败 ({error})，已自动使用本地数据"
        if error
        else "离线模式：使用本地规则分类，跳过 AI 简介生成"
    )

    result = {
        "metadata": final_meta,
        "suggestions": suggestions,
        "category": category or "",
        "summary": "",
        "warning": warning_msg,
    }

    if enable_enhanced_summary:
        result["enhancedSummary"] = ""

    return result
