# -*- coding: utf-8 -*-
"""
Response parsing and normalization utilities.

Contains:
- Author name normalization
- Filename normalization
- JSON extraction from AI responses
- Field cleaning/validation logic
"""

import json
import re
from typing import Any, Dict


def _normalize_author(author: str) -> str:
    """Normalize author name format.

    Rules:
    - Unify middle dots to Chinese dot '·'
    - Remove Chinese nationality markers (unnecessary for Chinese authors)
    - Unify bracket styles
    - Normalize multi-author separator '&'

    Args:
        author: Raw author name string

    Returns:
        Normalized author name
    """
    auth = author.replace("•", "·").replace("●", "·").replace("・", "·")
    auth = re.sub(r"[\(（\[]中国[\)）\]]", "", auth).strip()
    auth = re.sub(r"[\(（\[]中[\)）\]]", "", auth).strip()
    auth = auth.replace("【", "[").replace("】", "]")
    auth = auth.replace("(", "（").replace(")", "）")
    auth = re.sub(r"\](?!\s)", "] ", auth)
    auth = re.sub(r"\s*&\s*", " & ", auth)
    return auth


def _normalize_filename(filename: str) -> str:
    """Normalize filename format.

    Rules:
    - Unify middle dots to Chinese dot '·'
    - Remove Chinese nationality markers
    - Unify bracket styles

    Args:
        filename: Raw filename string

    Returns:
        Normalized filename
    """
    fn = filename.replace("•", "·").replace("●", "·").replace("・", "·")
    fn = re.sub(r"[\(（\[]中国[\)）\]]", "", fn).strip()
    fn = re.sub(r"[\(（\[]中[\)）\]]", "", fn).strip()
    fn = fn.replace("【", "[").replace("】", "]")
    return fn


def clean_json_response(response_text: str) -> str:
    """Remove markdown code fences from AI response text.

    Strips leading ```json and trailing ``` markers.

    Args:
        response_text: Raw AI response text

    Returns:
        Cleaned text suitable for JSON parsing
    """
    cleaned = response_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def parse_json_response(response_text: str) -> Any:
    """Parse JSON from AI response, stripping code fences.

    Args:
        response_text: Raw AI response text

    Returns:
        Parsed JSON object

    Raises:
        json.JSONDecodeError: If the cleaned text is not valid JSON
    """
    cleaned = clean_json_response(response_text)
    return json.loads(cleaned, strict=False)


def normalize_metadata_fields(result: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize author and filename fields in a metadata result dict.

    Applies _normalize_author to result["metadata"]["author"] and
    _normalize_filename to result["metadata"]["new_filename"].

    Args:
        result: Result dict that may contain a "metadata" key

    Returns:
        The same dict with normalized fields (modified in place)
    """
    if "metadata" in result:
        if "author" in result["metadata"] and result["metadata"]["author"]:
            result["metadata"]["author"] = _normalize_author(result["metadata"]["author"])
        if "new_filename" in result["metadata"] and result["metadata"]["new_filename"]:
            result["metadata"]["new_filename"] = _normalize_filename(
                result["metadata"]["new_filename"]
            )
    return result


def normalize_identify_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize author and filename fields in identify_book_metadata result.

    Applies _normalize_author to result["author"] and _normalize_filename
    to result["new_filename"] (top-level keys, not nested in "metadata").

    Args:
        result: Result dict from identify_book_metadata

    Returns:
        The same dict with normalized fields (modified in place)
    """
    if "author" in result and result["author"]:
        result["author"] = _normalize_author(result["author"])
    if "new_filename" in result and result["new_filename"]:
        result["new_filename"] = _normalize_filename(result["new_filename"])
    return result
