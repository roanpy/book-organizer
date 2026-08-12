# -*- coding: utf-8 -*-
"""
目录提取模块 - 从 EPUB/PDF 提取图书目录
"""

import logging
import os
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)
TOC_STORAGE_NAVIGATION_FIELDS = {"href", "anchor", "target_index"}
TOC_INTERNAL_FILE_TITLE_RE = re.compile(
    r"^(?:part\d+|.+_split_\d+)\.x?html?$",
    re.IGNORECASE,
)


def _safe_text(value: Any) -> str:
    """Return text that can always be UTF-8 encoded for JSON responses/SQLite."""
    if value is None:
        return ""
    text = str(value)
    return text.encode("utf-8", "replace").decode("utf-8").replace("\ufffd", "")


def _clean_title(title: str) -> str:
    """清理目录标题，去掉页码点线和多余空白。"""
    if not title:
        return ""
    title = _safe_text(title)
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"[\s.·•…_-]{2,}\s*(?:\d+|[ivxlcdm]+)\s*$", "", title, flags=re.I)
    return title.strip(" \t\r\n.-·•…")


def _is_internal_file_title(title: str) -> bool:
    """Return True when a TOC title is just an EPUB internal file name."""
    normalized = _clean_title(title)
    if not normalized:
        return False
    if not any(ch.isalnum() or "\u4e00" <= ch <= "\u9fff" for ch in normalized):
        return True
    if "/" in normalized or "\\" in normalized:
        return False
    return bool(TOC_INTERNAL_FILE_TITLE_RE.match(normalized))


def _dedupe_toc(items: List[Dict]) -> List[Dict]:
    """按 level/title/page/href 去重，保留原顺序。"""
    seen = set()
    result = []
    for item in items:
        title = _clean_title(item.get("title", ""))
        if not title:
            continue
        normalized = dict(item)
        normalized["title"] = title
        for field in ("href", "page"):
            if isinstance(normalized.get(field), str):
                normalized[field] = _safe_text(normalized[field])
        key = (
            normalized.get("level", 1),
            title,
            normalized.get("page"),
            normalized.get("href"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def sanitize_toc_result(toc_data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize TOC payload text so API responses and DB writes cannot fail."""
    sanitized = dict(toc_data or {})
    sanitized["toc"] = _dedupe_toc(sanitized.get("toc", []) or [])
    if "toc_text" in sanitized:
        sanitized["toc_text"] = _safe_text(sanitized.get("toc_text", ""))
    if "error" in sanitized:
        sanitized["error"] = _safe_text(sanitized.get("error", ""))
    return sanitized


def strip_toc_storage_noise(toc_data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a DB-cache-safe TOC payload without EPUB-internal navigation paths.

    EPUB hrefs such as ``text/part0001.html#...`` are useful for the live preview
    manifest, but they are noisy in the persistent TOC cache and unsafe to reuse
    across machines or external databases. Keep display fields only.
    """
    sanitized = sanitize_toc_result(toc_data)
    cleaned_items: List[Dict[str, Any]] = []
    for item in sanitized.get("toc", []) or []:
        if not isinstance(item, dict):
            continue
        cleaned = {
            key: value
            for key, value in item.items()
            if key not in TOC_STORAGE_NAVIGATION_FIELDS
        }
        if _is_internal_file_title(cleaned.get("title", "")):
            continue
        cleaned_items.append(cleaned)
    sanitized["toc"] = _dedupe_toc(cleaned_items)
    if sanitized.get("toc_text"):
        sanitized["entry_count"] = len(
            [line for line in sanitized["toc_text"].splitlines() if line.strip()]
        )
    else:
        sanitized["entry_count"] = len(sanitized["toc"])
    return sanitized


def extract_pdf_toc(file_path: str) -> List[Dict]:
    """
    从 PDF 提取书签目录

    Args:
        file_path: PDF 文件路径

    Returns:
        目录列表，格式: [{"level": 1, "title": "第一章", "page": 10}, ...]
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        toc = doc.get_toc()  # 返回 [[level, title, page], ...]
        doc.close()

        result = []
        for item in toc:
            if len(item) >= 3:
                result.append(
                    {
                        "level": item[0],
                        "title": item[1].strip() if item[1] else "",
                        "page": item[2],
                    }
                )

        return _dedupe_toc(result)
    except ImportError:
        logger.error("PyMuPDF (fitz) not installed")
        return []
    except Exception as e:
        logger.error("Failed to extract PDF TOC (%s)", type(e).__name__)
        return []


def _guess_pdf_toc_from_text(file_path: str, max_pages: int = 20) -> List[Dict]:
    """从 PDF 前若干页的目录页文本中提取目录。

    许多 PDF 没有书签目录，但前几页包含可见的"目录/Contents"页面。
    这里作为书签失败后的保守兜底，只提取明显带章节标记或页码点线的行。
    """
    try:
        import fitz

        doc = fitz.open(file_path)
        pages_to_scan = min(max_pages, len(doc))
        items = []
        seen_titles = set()
        found_toc_page = False

        page_number_pattern = re.compile(
            r"^(?P<title>.+?)(?:\s*[.·•…_-]{2,}\s*|\s{2,})(?P<page>\d{1,5}|[ivxlcdm]{1,8})$",
            re.I,
        )
        heading_pattern = re.compile(
            r"^(?P<title>(第[一二三四五六七八九十百千万零〇两\d]+[章节篇部卷].{0,80}|"
            r"(?:\d+[\.\、]){1,4}\s*.{1,100}|"
            r"(?:chapter|part|section)\s+\d+.{0,80}|"
            r"(?:序言|前言|引言|导论|结语|后记|附录|参考文献|索引).{0,80}))"
            r"(?:\s+(?P<page>\d{1,5}|[ivxlcdm]{1,8}))?$",
            re.I,
        )

        for page_index in range(pages_to_scan):
            text = doc[page_index].get_text("text") or ""
            lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
            lines = [line for line in lines if line]
            if not lines:
                continue

            page_has_toc_marker = any(
                _clean_title(line) in {"目录", "目 录"}
                or "table of contents" in _clean_title(line).lower()
                or _clean_title(line).lower() == "contents"
                for line in lines[:12]
            )
            if page_has_toc_marker:
                found_toc_page = True

            page_matches = []
            for line in lines:
                if len(line) > 160:
                    continue

                match = page_number_pattern.match(line) or heading_pattern.match(line)
                if not match:
                    continue

                title = _clean_title(match.group("title"))
                if not title or title in {"目录", "目 录", "contents"}:
                    continue

                page_value = match.groupdict().get("page")
                level = 1
                numeric_prefix = re.match(r"^(\d+(?:\.\d+)*)", title)
                if numeric_prefix:
                    level = min(numeric_prefix.group(1).count(".") + 1, 4)

                key = title.lower()
                if key in seen_titles:
                    continue
                seen_titles.add(key)

                item = {"level": level, "title": title}
                if page_value and page_value.isdigit():
                    item["page"] = int(page_value)
                elif page_value:
                    item["page"] = page_value
                page_matches.append(item)

            if page_matches and (found_toc_page or len(page_matches) >= 3):
                items.extend(page_matches)

            if found_toc_page and items and page_index > 0:
                # 目录页通常集中在开头，下一页无匹配后即可停止，避免误扫正文。
                next_page_text = doc[page_index].get_text("text") or ""
                if len(items) >= 3 and not next_page_text.strip():
                    break

        doc.close()
        return _dedupe_toc(items)
    except ImportError:
        logger.error("PyMuPDF (fitz) not installed")
        return []
    except Exception as e:
        logger.error("Failed to infer PDF TOC from text (%s)", type(e).__name__)
        return []


def extract_epub_toc(file_path: str, max_chapters: int = 30) -> List[Dict]:
    """
    从 EPUB 提取 NCX/NAV 目录

    Args:
        file_path: EPUB 文件路径

    Returns:
        目录列表，格式: [{"level": 1, "title": "第一章", "href": "ch1.xhtml"}, ...]
    """
    try:
        import ebooklib
        from bs4 import BeautifulSoup
        from ebooklib import epub

        book = epub.read_epub(file_path)

        result = []

        def parse_toc_item(item, level=1):
            """递归解析目录项"""
            if isinstance(item, tuple):
                # 嵌套目录: (Section, [children])
                section = item[0]
                children = item[1] if len(item) > 1 else []

                if hasattr(section, "title") and section.title:
                    result.append(
                        {
                            "level": level,
                            "title": section.title.strip(),
                            "href": getattr(section, "href", ""),
                        }
                    )

                for child in children:
                    parse_toc_item(child, level + 1)
            elif hasattr(item, "title"):
                # 单个目录项
                result.append(
                    {
                        "level": level,
                        "title": item.title.strip() if item.title else "",
                        "href": getattr(item, "href", ""),
                    }
                )

        toc = book.toc
        for item in toc:
            parse_toc_item(item)

        result = _dedupe_toc(result)
        if result:
            return result

        # 兜底 1：解析 EPUB3 NAV 文档中的 <nav epub:type="toc">。
        nav_result = []

        def parse_ol(ol, level=1):
            for li in ol.find_all("li", recursive=False):
                label = li.find(["a", "span"], recursive=False)
                title = label.get_text(" ", strip=True) if label else ""
                if title:
                    item = {"level": level, "title": title}
                    if label and label.name == "a":
                        item["href"] = label.get("href", "")
                    nav_result.append(item)
                child_ol = li.find("ol", recursive=False)
                if child_ol:
                    parse_ol(child_ol, level + 1)

        for item in book.get_items():
            if item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            soup = BeautifulSoup(item.get_content(), "html.parser")
            navs = soup.find_all("nav")
            for nav in navs:
                nav_type = " ".join(
                    [
                        nav.get("epub:type", ""),
                        nav.get("type", ""),
                        nav.get("role", ""),
                        nav.get("id", ""),
                        " ".join(nav.get("class", [])),
                    ]
                ).lower()
                if "toc" not in nav_type and "contents" not in nav_type:
                    continue
                ol = nav.find("ol")
                if ol:
                    parse_ol(ol)
            if nav_result:
                return _dedupe_toc(nav_result)

        # 兜底 2：部分 EPUB 没有 nav/toc，只能用章节标题生成可用目录。
        heading_result = []
        scanned = 0
        for item in book.get_items():
            if item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            if scanned >= max_chapters:
                break
            scanned += 1
            soup = BeautifulSoup(item.get_content(), "html.parser")
            for heading in soup.find_all(["h1", "h2", "h3"]):
                title = heading.get_text(" ", strip=True)
                if not title:
                    continue
                level = int(heading.name[1])
                heading_result.append(
                    {
                        "level": level,
                        "title": title,
                        "href": item.get_name(),
                    }
                )

        return _dedupe_toc(heading_result)
    except ImportError:
        logger.error("ebooklib or beautifulsoup4 not installed")
        return []
    except Exception as e:
        logger.error("Failed to extract EPUB TOC (%s)", type(e).__name__)
        return []


def extract_toc(
    file_path: str, use_ai: bool = False, max_pages: int = 20
) -> Dict[str, Any]:
    """
    统一目录提取接口

    Args:
        file_path: 文件路径
        use_ai: 是否使用 AI 辅助（暂未实现）

    Returns:
        {
            "success": bool,
            "method": "builtin" | "ai" | "none",
            "toc": [...],
            "file_type": "pdf" | "epub" | "unknown",
            "entry_count": int
        }
    """
    if not os.path.exists(file_path):
        return {
            "success": False,
            "method": "none",
            "toc": [],
            "file_type": "unknown",
            "entry_count": 0,
            "error": "文件不存在",
        }

    ext = os.path.splitext(file_path)[1].lower()

    toc = []
    file_type = "unknown"
    method = "none"

    if ext == ".pdf":
        file_type = "pdf"
        toc = extract_pdf_toc(file_path)
        if toc:
            method = "builtin"
        else:
            toc = _guess_pdf_toc_from_text(file_path, max_pages=max_pages)
            if toc:
                method = "content_scan"
    elif ext == ".epub":
        file_type = "epub"
        toc = extract_epub_toc(file_path, max_chapters=max_pages)
        if toc:
            method = "builtin"
    else:
        return {
            "success": False,
            "method": "none",
            "toc": [],
            "file_type": file_type,
            "entry_count": 0,
            "error": f"不支持的文件格式: {ext}",
        }

    # TODO: 如果无内置目录且 use_ai=True，使用 AI 识别

    return sanitize_toc_result(
        {
            "success": len(toc) > 0,
            "method": method,
            "toc": toc,
            "file_type": file_type,
            "entry_count": len(toc),
        }
    )


def format_toc_text(toc: List[Dict], indent_str: str = "  ") -> str:
    """
    将目录格式化为文本（用于显示）

    Args:
        toc: 目录列表
        indent_str: 缩进字符串

    Returns:
        格式化的目录文本
    """
    lines = []
    for item in toc:
        level = item.get("level", 1)
        title = _safe_text(item.get("title", ""))
        indent = indent_str * (level - 1)

        if "page" in item:
            lines.append(f"{indent}{title} (p.{_safe_text(item['page'])})")
        else:
            lines.append(f"{indent}{title}")

    return "\n".join(lines)


def extract_content_pages(file_path: str, num_pages: int = 10) -> str:
    """
    提取图书前若干页的文本内容（用于 AI 识别目录）

    Args:
        file_path: 文件路径
        num_pages: 要提取的页数/章节数

    Returns:
        提取的文本内容
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _extract_pdf_pages(file_path, num_pages)
    elif ext == ".epub":
        return _extract_epub_chapters(file_path, num_pages)
    else:
        return ""


def _extract_pdf_pages(file_path: str, num_pages: int) -> str:
    """从 PDF 提取前若干页文本"""
    try:
        import fitz

        doc = fitz.open(file_path)
        pages_to_extract = min(num_pages, len(doc))

        content = []
        for i in range(pages_to_extract):
            page = doc[i]
            text = page.get_text()
            if text.strip():
                content.append(f"--- 第 {i + 1} 页 ---\n{text}")

        doc.close()
        return "\n\n".join(content)
    except Exception as e:
        logger.error("Failed to extract PDF pages (%s)", type(e).__name__)
        return ""


def _extract_epub_chapters(file_path: str, num_chapters: int) -> str:
    """从 EPUB 提取前若干章节文本"""
    try:
        from bs4 import BeautifulSoup
        from ebooklib import epub

        book = epub.read_epub(file_path)

        content = []
        count = 0

        for item in book.get_items():
            if item.get_type() == 9:  # ITEM_DOCUMENT
                if count >= num_chapters:
                    break

                soup = BeautifulSoup(item.get_content(), "html.parser")
                text = soup.get_text(separator="\n", strip=True)

                if text and len(text) > 50:  # 跳过太短的内容
                    content.append(
                        f"--- 章节 {count + 1} ---\n{text[:3000]}"
                    )  # 限制每章字数
                    count += 1

        return "\n\n".join(content)
    except Exception as e:
        logger.error("Failed to extract EPUB chapters (%s)", type(e).__name__)
        return ""


def ai_organize_toc(raw_toc: List[Dict], prompt_template: str, ai_func) -> str:
    """
    使用 AI 整理已有目录

    Args:
        raw_toc: 原始目录列表
        prompt_template: 提示词模板（包含 {toc_content} 占位符）
        ai_func: AI 调用函数

    Returns:
        AI 整理后的目录文本
    """
    # 将目录转换为文本
    toc_text = format_toc_text(raw_toc)

    if not toc_text.strip():
        return ""

    # 替换占位符
    prompt = prompt_template.replace("{toc_content}", toc_text)

    try:
        result = ai_func(prompt)
        return result if result else ""
    except Exception as e:
        logger.error("AI organize TOC failed (%s)", type(e).__name__)
        return ""


def ai_extract_toc_from_content(content: str, prompt_template: str, ai_func) -> str:
    """
    使用 AI 从内容中提取目录

    Args:
        content: 图书内容文本
        prompt_template: 提示词模板（包含 {content} 占位符）
        ai_func: AI 调用函数

    Returns:
        AI 识别的目录文本
    """
    if not content.strip():
        return ""

    # 替换占位符
    prompt = prompt_template.replace("{content}", content)

    try:
        result = ai_func(prompt)
        return result if result else ""
    except Exception as e:
        logger.error("AI extract TOC from content failed (%s)", type(e).__name__)
        return ""
