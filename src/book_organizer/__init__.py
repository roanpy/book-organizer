# -*- coding: utf-8 -*-
"""
book_organizer 包 - AI 驱动的图书分类和整理工具

这个包提供了用于图书元数据提取、AI分析和文件管理的功能。
仅用于 Web 服务器模式。
"""

from .ai_engines import (
    extract_core_content,
    get_ai_analysis,
    get_enhanced_mode_analysis,
    get_unified_analysis,
    identify_book_metadata,
    optimize_additional_rules_with_ai,
)
from .config import (
    AI_CONFIG_FILE,
    APP_DIR,
    CONFIG_FILE,
    DEFAULT_CORE_RULES,
    HISTORY_FILE,
    get_book_status,
    get_default_ai_config,
    get_historical_transfers,
    load_ai_config,
    load_config,
    load_history,
    save_ai_config,
    save_config,
    save_history,
    save_history_item,
)
from .database import EnhancedSummariesDB, close_db, get_db
from .file_ops import (
    find_similar_files,
    get_book_files,
    get_cover_image,
    get_target_categories,
    parse_filename,
    truncate_filename_smart,
)

# 新增：ISBN/ISSN 查询
from .isbn_lookup import (
    auto_lookup_isbn,
    extract_isbn_from_metadata,
    extract_isbn_from_text,
    lookup_isbn_google,
    lookup_isbn_openlibrary,
)

# 新增：本地工具函数（无需 AI）
from .local_utils import (
    CATEGORY_RULES,
    auto_categorize,
    compare_versions,
    find_similar_titles,
    group_by_name,
    normalize_title,
    parse_book_name,
)
from .metadata import (
    extract_metadata,
    write_epub_metadata,
    write_pdf_metadata,
)
from .search import (
    search_book_online,
)
from .transfer import (
    _cleanup_suggestions,
    _find_heuristic_matches,
    rename_and_move_book,
)

__all__ = [
    # Config
    "APP_DIR",
    "CONFIG_FILE",
    "HISTORY_FILE",
    "AI_CONFIG_FILE",
    "DEFAULT_CORE_RULES",
    "load_config",
    "save_config",
    "load_ai_config",
    "save_ai_config",
    "get_default_ai_config",
    "load_history",
    "save_history",
    "save_history_item",
    "get_book_status",
    "get_historical_transfers",
    # File Operations
    "get_book_files",
    "get_target_categories",
    "get_cover_image",
    "parse_filename",
    "find_similar_files",
    "truncate_filename_smart",
    # Metadata
    "extract_metadata",
    "write_epub_metadata",
    "write_pdf_metadata",
    # Search
    "search_book_online",
    # AI
    "get_ai_analysis",
    "identify_book_metadata",
    "get_unified_analysis",
    "optimize_additional_rules_with_ai",
    "extract_core_content",
    "get_enhanced_mode_analysis",
    # Transfer
    "rename_and_move_book",
    "_find_heuristic_matches",
    "_cleanup_suggestions",
    # Database
    "EnhancedSummariesDB",
    "get_db",
    "close_db",
    # Local Utils (无需 AI)
    "compare_versions",
    "group_by_name",
    "parse_book_name",
    "normalize_title",
    "find_similar_titles",
    "auto_categorize",
    "CATEGORY_RULES",
    # ISBN Lookup
    "extract_isbn_from_text",
    "extract_isbn_from_metadata",
    "lookup_isbn_openlibrary",
    "lookup_isbn_google",
    "auto_lookup_isbn",
]

__version__ = "0.8.4"
