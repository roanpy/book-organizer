# -*- coding: utf-8 -*-
"""Preview/rendering router - EPUB, PDF, TXT/MD preview endpoints."""

import html
import os
import re
import urllib.parse
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

from book_organizer.file_ops import resolve_file_path
from book_organizer.pdf_converter import CONVERTIBLE_FORMATS

from . import internal_error

router = APIRouter(tags=["preview"])

PREVIEW_FORMATS = {
    ".pdf": "pdf",
    ".epub": "epub",
    ".txt": "txt",
    ".md": "markdown",
    ".markdown": "markdown",
}
EPUB_PREVIEW_MAX_TOC_ENTRIES = 120
TEXT_PREVIEW_EXTENSIONS = {".txt", ".md", ".markdown"}
TEXT_PREVIEW_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "latin-1")


def _load_config() -> Dict[str, Any]:
    """Load config through the legacy library router when available.

    Preview endpoints used to live in library.py, and a few tests/tools patch
    book_organizer.routers.library.load_config directly. This keeps that
    dependency seam stable after splitting the router.
    """
    try:
        from book_organizer.routers import library as library_router

        return library_router.load_config()
    except Exception:
        from book_organizer.config import load_config

        return load_config()


def _configured_preview_roots(config: Dict[str, Any]) -> List[str]:
    roots = []
    for key in ("source_dir", "target_dir"):
        value = config.get(key)
        if value:
            roots.append(value)
    roots.extend(config.get("library_directories") or [])
    pdf_export_dir = config.get("beta_features", {}).get("pdf_export_dir")
    if pdf_export_dir:
        roots.append(pdf_export_dir)
    return [
        os.path.realpath(os.path.abspath(os.path.expanduser(root)))
        for root in roots
        if root and os.path.exists(os.path.expanduser(root))
    ]


def _path_is_under_root(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _resolve_existing_book_file(requested_path: str) -> tuple[str, str, Dict[str, Any]]:
    config = _load_config()
    roots = _configured_preview_roots(config)
    requested_real_path = os.path.realpath(
        os.path.abspath(os.path.expanduser(requested_path))
    )
    if os.path.isabs(os.path.expanduser(requested_path)) and os.path.isfile(
        requested_real_path
    ):
        if not roots or not any(
            _path_is_under_root(requested_real_path, root) for root in roots
        ):
            raise HTTPException(status_code=403, detail="预览路径不在已配置的图书目录内")
        file_path = requested_real_path
    else:
        file_path = resolve_file_path(requested_path, config)
    if not file_path:
        raise HTTPException(status_code=404, detail="文件不存在")

    real_path = os.path.realpath(os.path.abspath(os.path.expanduser(file_path)))
    if not os.path.isfile(real_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    if not roots or not any(_path_is_under_root(real_path, root) for root in roots):
        raise HTTPException(status_code=403, detail="预览路径不在已配置的图书目录内")

    ext = os.path.splitext(real_path)[1].lower()

    return real_path, ext, config


def _resolve_preview_file(requested_path: str) -> tuple[str, str, Dict[str, Any]]:
    real_path, ext, config = _resolve_existing_book_file(requested_path)
    if ext not in PREVIEW_FORMATS:
        raise HTTPException(status_code=400, detail="仅支持 PDF/EPUB/TXT/MD 预览")
    return real_path, ext, config


def _find_same_name_pdf(file_path: str, config: Dict[str, Any]) -> str | None:
    source = os.path.realpath(os.path.abspath(os.path.expanduser(file_path)))
    stem = os.path.splitext(os.path.basename(source))[0]
    candidates = []

    pdf_export_dir = config.get("beta_features", {}).get("pdf_export_dir")
    if pdf_export_dir:
        candidates.append(os.path.join(os.path.expanduser(pdf_export_dir), f"{stem}.pdf"))
    candidates.append(os.path.join(os.path.dirname(source), f"{stem}.pdf"))

    roots = _configured_preview_roots(config)
    seen = set()
    for candidate in candidates:
        real_candidate = os.path.realpath(os.path.abspath(candidate))
        if real_candidate in seen:
            continue
        seen.add(real_candidate)
        if not os.path.isfile(real_candidate):
            continue
        if roots and any(_path_is_under_root(real_candidate, root) for root in roots):
            return real_candidate
    return None


def _sanitize_epub_html(content: bytes | str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, "html.parser")
    root = soup.body or soup
    for tag in root.find_all(["script", "style", "iframe", "object", "embed", "link", "meta"]):
        tag.decompose()

    allowed_tags = {
        "p",
        "br",
        "div",
        "span",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "blockquote",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "pre",
        "code",
        "hr",
    }
    for tag in list(root.find_all(True)):
        if tag.name not in allowed_tags:
            tag.unwrap()
            continue
        tag.attrs = {}

    return "".join(str(child) for child in root.contents).strip()


def _is_epub_navigation_item(item: Any) -> bool:
    item_id = (item.get_id() or "").lower()
    item_name = (item.get_name() or "").lower()
    return item_id in {"nav", "toc"} or item_name.endswith(
        ("nav.xhtml", "nav.html", "toc.xhtml", "toc.html")
    )


def _collect_epub_toc_entries(
    toc_items: Any,
    level: int = 0,
    max_entries: int = EPUB_PREVIEW_MAX_TOC_ENTRIES,
    entries: list[Dict[str, Any]] | None = None,
) -> list[Dict[str, Any]]:
    if entries is None:
        entries = []
    if not toc_items or len(entries) >= max_entries:
        return entries

    for item in toc_items:
        if len(entries) >= max_entries:
            break

        if isinstance(item, tuple) and item:
            node = item[0]
            children = item[1] if len(item) > 1 else []
            _append_epub_toc_node(node, level, entries, max_entries)
            _collect_epub_toc_entries(children, level + 1, max_entries, entries)
            continue

        if isinstance(item, list):
            _collect_epub_toc_entries(item, level, max_entries, entries)
            continue

        _append_epub_toc_node(item, level, entries, max_entries)

    return entries


def _append_epub_toc_node(
    node: Any,
    level: int,
    entries: list[Dict[str, Any]],
    max_entries: int,
) -> None:
    if len(entries) >= max_entries:
        return

    title = getattr(node, "title", None)
    if not title and isinstance(node, str):
        title = node
    title = str(title or "").strip()
    if not title:
        return

    entries.append(
        {
            "title": title,
            "href": str(getattr(node, "href", "") or ""),
            "level": max(0, min(level, 6)),
        }
    )


def _get_epub_ordered_items(book: Any) -> list[Any]:
    import ebooklib

    ordered_items = []
    seen_ids = set()
    for item_ref in book.spine or []:
        item_id = item_ref[0] if isinstance(item_ref, tuple) else item_ref
        item = book.get_item_with_id(item_id)
        if (
            item
            and item.get_type() == ebooklib.ITEM_DOCUMENT
            and item.get_id() not in seen_ids
            and not _is_epub_navigation_item(item)
        ):
            ordered_items.append(item)
            seen_ids.add(item.get_id())

    if not ordered_items:
        ordered_items = [
            item
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
            if not _is_epub_navigation_item(item)
        ]
    return ordered_items


def _get_epub_chapter_title(item: Any) -> str:
    from bs4 import BeautifulSoup

    raw_soup = BeautifulSoup(item.get_content(), "html.parser")
    heading = raw_soup.find(["h1", "h2", "h3", "title"])
    return (
        heading.get_text(" ", strip=True)
        if heading
        else getattr(item, "title", None) or item.get_name()
    )


def _assign_epub_toc_targets(
    toc_entries: list[Dict[str, Any]], chapters: list[Dict[str, Any]]
) -> list[Dict[str, Any]]:
    href_to_index: dict[str, int] = {}
    for chapter in chapters:
        href = str(chapter.get("href") or "").split("#", 1)[0]
        if href:
            href_to_index[href] = int(chapter["index"])

    for entry in toc_entries:
        href = str(entry.get("href") or "").split("#", 1)[0]
        if href in href_to_index:
            entry["target_index"] = href_to_index[href]
    return toc_entries


def _extract_epub_manifest(file_path: str) -> Dict[str, Any]:
    from ebooklib import epub

    book = epub.read_epub(file_path)
    title_meta = book.get_metadata("DC", "title")
    title = title_meta[0][0] if title_meta and title_meta[0] else os.path.basename(file_path)
    toc_entries = _collect_epub_toc_entries(book.toc)
    ordered_items = _get_epub_ordered_items(book)

    chapters = []
    for item in ordered_items:
        chapters.append(
            {
                "index": len(chapters),
                "id": item.get_id(),
                "href": item.get_name(),
                "title": _get_epub_chapter_title(item) or f"章节 {len(chapters) + 1}",
            }
        )

    toc_entries = _assign_epub_toc_targets(toc_entries, chapters)

    return {
        "success": True,
        "format": "epub",
        "filename": os.path.basename(file_path),
        "title": title,
        "chapter_count": len(chapters),
        "toc_count": len(toc_entries),
        "toc": toc_entries,
        "chapters": chapters,
    }


def _extract_epub_chapter(file_path: str, index: int) -> Dict[str, Any]:
    from ebooklib import epub

    book = epub.read_epub(file_path)
    ordered_items = _get_epub_ordered_items(book)
    if index < 0 or index >= len(ordered_items):
        raise HTTPException(status_code=404, detail="EPUB 章节不存在")

    item = ordered_items[index]
    return {
        "success": True,
        "format": "epub",
        "index": index,
        "title": _get_epub_chapter_title(item) or f"章节 {index + 1}",
        "html": _sanitize_epub_html(item.get_content()),
    }


def _extract_epub_preview(file_path: str) -> Dict[str, Any]:
    manifest = _extract_epub_manifest(file_path)
    chapters = []
    for chapter in manifest["chapters"]:
        chapters.append(_extract_epub_chapter(file_path, int(chapter["index"])))
    return {
        **manifest,
        "returned_chapters": len(chapters),
        "truncated": False,
        "chapters": chapters,
    }


def _get_pdf_page_count(file_path: str) -> int:
    import fitz

    with fitz.open(file_path) as doc:
        return doc.page_count


def _extract_pdf_toc(file_path: str) -> list[Dict[str, Any]]:
    import fitz

    entries = []
    with fitz.open(file_path) as doc:
        for level, title, page in doc.get_toc(simple=True):
            clean_title = str(title or "").strip()
            if not clean_title:
                continue
            entries.append(
                {
                    "title": clean_title,
                    "level": max(0, min(int(level) - 1, 6)),
                    "page": max(1, min(int(page or 1), doc.page_count or 1)),
                }
            )
    return entries


def _read_text_preview_file(file_path: str) -> tuple[str, str]:
    with open(file_path, "rb") as file:
        data = file.read()
    last_error: Exception | None = None
    for encoding in TEXT_PREVIEW_ENCODINGS:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    raise HTTPException(status_code=500, detail=f"文本解码失败: {last_error}")


def _extract_text_toc(text: str, markdown: bool) -> list[Dict[str, Any]]:
    entries = []
    txt_patterns = (
        re.compile(r"^\s*(第[一二三四五六七八九十百千万零〇\d]+[章节卷篇部].{0,80})\s*$"),
        re.compile(r"^\s*((?:Chapter|CHAPTER)\s+\d+.{0,80})\s*$"),
        re.compile(r"^\s*(\d{1,3}[\.、]\s*\S.{0,80})\s*$"),
    )

    for line_index, line in enumerate(text.splitlines()):
        title = ""
        level = 0
        if markdown:
            match = re.match(r"^\s*(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if match:
                level = len(match.group(1)) - 1
                title = match.group(2).strip()
        else:
            for pattern in txt_patterns:
                match = pattern.match(line)
                if match:
                    title = match.group(1).strip()
                    break

        if title:
            entries.append(
                {
                    "title": title[:120],
                    "level": max(0, min(level, 6)),
                    "anchor": f"text-line-{line_index}",
                    "line": line_index,
                }
            )
        if len(entries) >= 240:
            break
    return entries


def _render_plain_text_preview(text: str, toc: list[Dict[str, Any]]) -> str:
    anchors_by_line = {int(entry["line"]): entry["anchor"] for entry in toc}
    rendered_lines = []
    for line_index, line in enumerate(text.splitlines()):
        prefix = ""
        if line_index in anchors_by_line:
            prefix = f'<span id="{html.escape(anchors_by_line[line_index])}"></span>'
        rendered_lines.append(prefix + html.escape(line))
    rendered = "\n".join(rendered_lines)
    return f'<pre class="text-preview-pre">{rendered}</pre>'


def _render_markdown_preview(text: str, toc: list[Dict[str, Any]]) -> str:
    anchors_by_line = {int(entry["line"]): entry["anchor"] for entry in toc}
    html_parts = []
    in_code = False
    list_open = False
    quote_open = False
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            html_parts.append(f"<p>{' '.join(paragraph)}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            html_parts.append("</ul>")
            list_open = False

    def close_quote() -> None:
        nonlocal quote_open
        if quote_open:
            html_parts.append("</blockquote>")
            quote_open = False

    for line_index, raw_line in enumerate(text.splitlines()):
        anchor = anchors_by_line.get(line_index)
        anchor_html = f'<span id="{html.escape(anchor)}"></span>' if anchor else ""
        line = raw_line.rstrip()

        if line.strip().startswith("```"):
            flush_paragraph()
            close_list()
            close_quote()
            if in_code:
                html_parts.append("</code></pre>")
                in_code = False
            else:
                html_parts.append(anchor_html + '<pre class="markdown-code"><code>')
                in_code = True
            continue

        if in_code:
            html_parts.append(html.escape(raw_line))
            continue

        heading = re.match(r"^\s*(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            flush_paragraph()
            close_list()
            close_quote()
            level = len(heading.group(1))
            html_parts.append(
                f"{anchor_html}<h{level}>{html.escape(heading.group(2).strip())}</h{level}>"
            )
            continue

        list_item = re.match(r"^\s*[-*+]\s+(.+)$", line)
        if list_item:
            flush_paragraph()
            close_quote()
            if not list_open:
                html_parts.append(anchor_html + "<ul>")
                list_open = True
            html_parts.append(f"<li>{html.escape(list_item.group(1).strip())}</li>")
            continue

        quote = re.match(r"^\s*>\s?(.*)$", line)
        if quote:
            flush_paragraph()
            close_list()
            if not quote_open:
                html_parts.append(anchor_html + "<blockquote>")
                quote_open = True
            html_parts.append(f"<p>{html.escape(quote.group(1).strip())}</p>")
            continue

        if not line.strip():
            flush_paragraph()
            close_list()
            close_quote()
            continue

        close_list()
        close_quote()
        paragraph.append(anchor_html + html.escape(line.strip()))

    flush_paragraph()
    close_list()
    close_quote()
    if in_code:
        html_parts.append("</code></pre>")
    return "\n".join(html_parts)


# ── Preview endpoints ──────────────────────────────────────────────────────────


@router.get("/api/preview/info")
def get_preview_info(path: str) -> Dict[str, Any]:
    file_path, ext, _ = _resolve_preview_file(path)
    data = {
        "success": True,
        "format": PREVIEW_FORMATS[ext],
        "filename": os.path.basename(file_path),
        "size": os.path.getsize(file_path),
        "file_url": f"/api/preview/file?path={urllib.parse.quote(path)}",
    }
    if ext == ".pdf":
        try:
            data["page_count"] = _get_pdf_page_count(file_path)
        except Exception:
            data["page_count"] = None
        try:
            data["toc"] = _extract_pdf_toc(file_path)
        except Exception:
            data["toc"] = []
        data["toc_count"] = len(data["toc"])
    return data


@router.get("/api/preview/resolve")
def resolve_preview_target(path: str) -> Dict[str, Any]:
    file_path, ext, config = _resolve_existing_book_file(path)
    if ext in PREVIEW_FORMATS:
        return {
            "success": True,
            "action": "preview",
            "source": "original",
            "path": file_path,
            "preview_path": file_path,
            "format": PREVIEW_FORMATS[ext],
            "filename": os.path.basename(file_path),
        }

    same_name_pdf = _find_same_name_pdf(file_path, config)
    if same_name_pdf:
        return {
            "success": True,
            "action": "preview",
            "source": "same_name_pdf",
            "path": file_path,
            "preview_path": same_name_pdf,
            "format": "pdf",
            "filename": os.path.basename(same_name_pdf),
            "message": "已打开同名 PDF",
        }

    if ext in CONVERTIBLE_FORMATS:
        return {
            "success": True,
            "action": "convert",
            "source": "conversion_required",
            "path": file_path,
            "format": ext.lstrip("."),
            "filename": os.path.basename(file_path),
            "message": "当前格式需导出为 PDF 后预览",
        }

    return {
        "success": False,
        "action": "unsupported",
        "path": file_path,
        "format": ext.lstrip("."),
        "filename": os.path.basename(file_path),
        "message": f"暂不支持预览或导出此格式: {ext or 'unknown'}",
    }


@router.get("/api/preview/file")
def get_preview_file(path: str):
    file_path, ext, _ = _resolve_preview_file(path)
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="该接口仅用于 PDF 预览")

    filename = os.path.basename(file_path)
    quoted_filename = urllib.parse.quote(filename)
    headers = {
        "Content-Disposition": f"inline; filename*=UTF-8''{quoted_filename}",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }
    return FileResponse(file_path, media_type="application/pdf", headers=headers)


@router.get("/api/preview/pdf/page")
def get_pdf_preview_page(path: str, page: int = 1, zoom: float = 1.35):
    file_path, ext, _ = _resolve_preview_file(path)
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="该接口仅用于 PDF 页面预览")

    try:
        import fitz

        safe_zoom = max(0.5, min(2.5, zoom))
        with fitz.open(file_path) as doc:
            if doc.page_count == 0:
                raise HTTPException(status_code=400, detail="PDF 没有可预览页面")
            page_index = max(0, min(page - 1, doc.page_count - 1))
            pdf_page = doc.load_page(page_index)
            pix = pdf_page.get_pixmap(
                matrix=fitz.Matrix(safe_zoom, safe_zoom),
                alpha=False,
            )
            return Response(
                content=pix.tobytes("png"),
                media_type="image/png",
                headers={"Cache-Control": "no-store"},
            )
    except HTTPException:
        raise
    except Exception as e:
        raise internal_error("render PDF preview", e, "PDF 页面预览失败")


@router.get("/api/preview/epub")
def get_epub_preview(path: str) -> Dict[str, Any]:
    file_path, ext, _ = _resolve_preview_file(path)
    if ext != ".epub":
        raise HTTPException(status_code=400, detail="该接口仅用于 EPUB 预览")
    try:
        return _extract_epub_preview(file_path)
    except Exception as e:
        raise internal_error("load EPUB preview", e, "EPUB 预览读取失败")


@router.get("/api/preview/epub/manifest")
def get_epub_preview_manifest(path: str, response: Response) -> Dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    file_path, ext, _ = _resolve_preview_file(path)
    if ext != ".epub":
        raise HTTPException(status_code=400, detail="该接口仅用于 EPUB 预览")
    try:
        return _extract_epub_manifest(file_path)
    except Exception as e:
        raise internal_error("load EPUB manifest", e, "EPUB 目录读取失败")


@router.get("/api/preview/epub/chapter")
def get_epub_preview_chapter(path: str, index: int, response: Response) -> Dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    file_path, ext, _ = _resolve_preview_file(path)
    if ext != ".epub":
        raise HTTPException(status_code=400, detail="该接口仅用于 EPUB 预览")
    try:
        return _extract_epub_chapter(file_path, index)
    except HTTPException:
        raise
    except Exception as e:
        raise internal_error("load EPUB chapter", e, "EPUB 正文读取失败")


@router.get("/api/preview/text")
def get_text_preview(path: str, response: Response) -> Dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    file_path, ext, _ = _resolve_preview_file(path)
    if ext not in TEXT_PREVIEW_EXTENSIONS:
        raise HTTPException(status_code=400, detail="该接口仅用于 TXT/MD 预览")

    text, encoding = _read_text_preview_file(file_path)
    markdown = ext in {".md", ".markdown"}
    toc_entries = _extract_text_toc(text, markdown)
    rendered = (
        _render_markdown_preview(text, toc_entries)
        if markdown
        else _render_plain_text_preview(text, toc_entries)
    )
    return {
        "success": True,
        "format": "markdown" if markdown else "txt",
        "filename": os.path.basename(file_path),
        "encoding": encoding,
        "toc": toc_entries,
        "toc_count": len(toc_entries),
        "html": rendered,
        "char_count": len(text),
    }
