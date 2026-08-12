"""Helpers for reconciling enhanced summaries across files and database."""

from __future__ import annotations

import re
from typing import Any, Dict

ENHANCED_SUMMARY_SEPARATOR = "★ 增强简介 (AI Generated) ★"
STRUCTURED_SUMMARY_MARKERS = ("图书简介", "详细要点", "具体应用")
NUMBERED_DETAIL_RE = re.compile(r"(?m)^\s*(?:\d+[.、．]|[-*•])\s*")


def normalize_enhanced_summary(summary: str | None) -> str:
    """Strip storage wrappers around an enhanced summary."""
    if not summary:
        return ""
    text = str(summary).strip()
    if ENHANCED_SUMMARY_SEPARATOR in text:
        text = text.split(ENHANCED_SUMMARY_SEPARATOR)[-1].strip()
    return text


def is_structured_enhanced_summary(summary: str | None) -> bool:
    """Return True for the current three-section enhanced summary format."""
    normalized_text = normalize_enhanced_summary(summary)
    if not normalized_text:
        return False
    normalized = normalized_text.replace("：", ":")
    marker_count = sum(marker in normalized for marker in STRUCTURED_SUMMARY_MARKERS)
    numbered_count = len(NUMBERED_DETAIL_RE.findall(normalized_text))
    return marker_count == len(STRUCTURED_SUMMARY_MARKERS) or (
        marker_count >= 2 and numbered_count >= 3
    )


def enhanced_summary_detail_score(summary: str | None) -> int:
    """Score detail richness so newer structured summaries can replace old compact ones."""
    text = normalize_enhanced_summary(summary)
    if not text:
        return 0
    marker_score = sum(20 for marker in STRUCTURED_SUMMARY_MARKERS if marker in text)
    numbered_score = min(len(NUMBERED_DETAIL_RE.findall(text)), 12) * 10
    length_score = min(len(text) // 120, 20)
    return marker_score + numbered_score + length_score


def extract_embedded_enhanced_summary(metadata: Dict[str, Any] | None) -> str:
    """Extract an enhanced summary from file metadata when it is clearly present.

    PDF writes may append the summary after a separator. EPUB writes store the
    summary directly in dc:description, so accept it only when it matches the
    current three-section format.
    """
    description = str((metadata or {}).get("description") or "").strip()
    if not description:
        return ""

    description = normalize_enhanced_summary(description)

    if is_structured_enhanced_summary(description):
        return description

    return ""


def should_sync_embedded_summary(db_summary: str | None, embedded_summary: str | None) -> bool:
    """Decide whether embedded metadata should refresh the database copy."""
    if not embedded_summary:
        return False
    if not db_summary:
        return True
    if not is_structured_enhanced_summary(embedded_summary):
        return False
    if not is_structured_enhanced_summary(db_summary):
        return True
    return enhanced_summary_detail_score(embedded_summary) > enhanced_summary_detail_score(
        db_summary
    )


def sync_embedded_summary_to_db(
    db: Any,
    file_path: str,
    metadata: Dict[str, Any],
    db_summary: str,
    embedded_summary: str,
    category: str = "Library",
) -> bool:
    """Persist a newer embedded enhanced summary to the application database."""
    if not should_sync_embedded_summary(db_summary, embedded_summary):
        return False
    summary_metadata = dict(metadata or {})
    summary_metadata.pop("description", None)
    return db.save_summary(
        file_path,
        {
            "metadata": summary_metadata,
            "summary": embedded_summary,
            "category": category,
        },
    )


def choose_enhanced_summary(
    db_summary: str | None,
    embedded_summary: str | None,
    priority: str = "database",
) -> str:
    """Choose the display summary without letting stale DB content hide new format."""
    db_summary = (db_summary or "").strip()
    embedded_summary = (embedded_summary or "").strip()

    if should_sync_embedded_summary(db_summary, embedded_summary):
        return embedded_summary

    if priority == "database":
        return db_summary or embedded_summary
    return embedded_summary or db_summary
