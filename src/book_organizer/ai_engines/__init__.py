# -*- coding: utf-8 -*-
"""
AI engines subpackage - Handles AI model calls and book analysis.

This subpackage replaces the former monolithic ai_engines.py module.
All public functions are re-exported here so that existing imports like:
    from book_organizer.ai_engines import get_ai_analysis
    from book_organizer.ai_engines import get_batch_enhance_analysis
continue to work exactly as before.

Sub-modules:
- prompt_builder: Prompt construction functions
- dispatcher: Unified AI call dispatcher and engine routing
- response_parser: Response parsing and normalization
- offline_fallback: Offline fallback and metadata merging
- analysis: Business entry points (the main public API)
"""

from .analysis import (
    extract_core_content,
    get_ai_analysis,
    get_batch_enhance_analysis,
    get_batch_organize_analysis,
    get_enhanced_mode_analysis,
    get_unified_analysis,
    identify_book_metadata,
    optimize_additional_rules_with_ai,
)
from .prompt_builder import get_common_prompt

__all__ = [
    # Business entry points
    "get_ai_analysis",
    "get_unified_analysis",
    "identify_book_metadata",
    "optimize_additional_rules_with_ai",
    "get_enhanced_mode_analysis",
    "get_batch_enhance_analysis",
    "get_batch_organize_analysis",
    # Content extraction
    "extract_core_content",
    # Prompt building
    "get_common_prompt",
]
