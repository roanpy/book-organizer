# -*- coding: utf-8 -*-
"""
ISBN/ISSN 识别与查询模块

功能：
1. 从 PDF/EPUB 元数据提取 ISBN
2. 从图书正文（前N页）正则提取 ISBN
3. 调用外部 API 获取图书元数据

支持的 API：
- Open Library (免费，无需 API Key)
- Google Books (需要 API Key)

注意：此模块不依赖 AI，可在离线环境使用（仅 API 查询需要网络）
"""

import re
from typing import Any, Dict, List, Optional

# ISBN-10 和 ISBN-13 正则模式
ISBN_PATTERNS = [
    # ISBN-13 (带分隔符)
    r"(?:ISBN(?:-13)?:?\s*)?(\d{3}[-\s]?\d[-\s]?\d{3}[-\s]?\d{5}[-\s]?\d)",
    # ISBN-10 (带分隔符)
    r"(?:ISBN(?:-10)?:?\s*)?(\d[-\s]?\d{3}[-\s]?\d{5}[-\s]?[\dXx])",
    # 纯数字 ISBN-13
    r"(?:ISBN(?:-13)?:?\s*)?(\d{13})",
    # 纯数字 ISBN-10
    r"(?:ISBN(?:-10)?:?\s*)?(\d{9}[\dXx])",
]

# ISSN 正则模式
ISSN_PATTERN = r"ISSN:?\s*(\d{4}[-\s]?\d{3}[\dXx])"


def validate_isbn_10(isbn: str) -> bool:
    """验证 ISBN-10 校验码。"""
    isbn = isbn.replace("-", "").replace(" ", "").upper()
    if len(isbn) != 10:
        return False

    total = 0
    for i, char in enumerate(isbn):
        if char == "X" and i == 9:
            total += 10
        elif char.isdigit():
            total += int(char) * (10 - i)
        else:
            return False

    return total % 11 == 0


def validate_isbn_13(isbn: str) -> bool:
    """验证 ISBN-13 校验码。"""
    isbn = isbn.replace("-", "").replace(" ", "")
    if len(isbn) != 13 or not isbn.isdigit():
        return False

    total = 0
    for i, char in enumerate(isbn):
        weight = 1 if i % 2 == 0 else 3
        total += int(char) * weight

    return total % 10 == 0


def normalize_isbn(isbn: str) -> str:
    """标准化 ISBN，移除分隔符。"""
    return isbn.replace("-", "").replace(" ", "").upper()


def extract_isbn_from_text(text: str) -> List[str]:
    """
    从文本中提取所有 ISBN。

    Args:
        text: 要搜索的文本

    Returns:
        提取到的有效 ISBN 列表（去重）
    """
    found_isbns = set()

    for pattern in ISBN_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            normalized = normalize_isbn(match)
            # 验证 ISBN
            if len(normalized) == 13 and validate_isbn_13(normalized):
                found_isbns.add(normalized)
            elif len(normalized) == 10 and validate_isbn_10(normalized):
                found_isbns.add(normalized)

    return list(found_isbns)


def extract_issn_from_text(text: str) -> List[str]:
    """
    从文本中提取所有 ISSN。

    Args:
        text: 要搜索的文本

    Returns:
        提取到的 ISSN 列表
    """
    matches = re.findall(ISSN_PATTERN, text, re.IGNORECASE)
    return [m.replace("-", "").replace(" ", "").upper() for m in matches]


def extract_isbn_from_metadata(file_path: str) -> Optional[str]:
    """
    从文件元数据中提取 ISBN。

    支持 EPUB 和 PDF 格式。

    Args:
        file_path: 文件路径

    Returns:
        找到的 ISBN，如果未找到返回 None
    """
    ext = file_path.lower().split(".")[-1]

    if ext == "epub":
        return _extract_isbn_from_epub(file_path)
    elif ext == "pdf":
        return _extract_isbn_from_pdf(file_path)

    return None


def _extract_isbn_from_epub(file_path: str) -> Optional[str]:
    """从 EPUB 元数据提取 ISBN。"""
    try:
        from ebooklib import epub

        book = epub.read_epub(file_path)

        # 检查 dc:identifier
        identifiers = book.get_metadata("DC", "identifier")
        for identifier in identifiers:
            value = str(identifier[0]) if identifier else ""
            isbns = extract_isbn_from_text(value)
            if isbns:
                return isbns[0]

        # 检查 dc:source
        sources = book.get_metadata("DC", "source")
        for source in sources:
            value = str(source[0]) if source else ""
            isbns = extract_isbn_from_text(value)
            if isbns:
                return isbns[0]

    except ImportError:
        pass
    except Exception as e:
        print(f"Warning: Failed to extract ISBN from EPUB: {e}")

    return None


def _extract_isbn_from_pdf(file_path: str) -> Optional[str]:
    """从 PDF 元数据提取 ISBN。"""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        metadata = doc.metadata

        # 检查常见元数据字段
        fields_to_check = ["subject", "keywords", "producer", "creator"]
        for field in fields_to_check:
            value = metadata.get(field, "")
            if value:
                isbns = extract_isbn_from_text(value)
                if isbns:
                    doc.close()
                    return isbns[0]

        # 扫描前几页内容
        for page_num in range(min(5, len(doc))):
            page = doc[page_num]
            text = page.get_text()
            isbns = extract_isbn_from_text(text)
            if isbns:
                doc.close()
                return isbns[0]

        doc.close()

    except ImportError:
        pass
    except Exception as e:
        print(f"Warning: Failed to extract ISBN from PDF: {e}")

    return None


def lookup_isbn_openlibrary(isbn: str) -> Optional[Dict[str, Any]]:
    """
    通过 Open Library API 查询图书信息。

    Args:
        isbn: ISBN（10 或 13 位）

    Returns:
        图书元数据字典，包含 title, author, publisher 等
    """
    try:
        import json
        import urllib.request

        normalized = normalize_isbn(isbn)
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{normalized}&format=json&jscmd=data"

        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        key = f"ISBN:{normalized}"
        if key not in data:
            return None

        book_data = data[key]

        # 提取作者
        authors = []
        for author in book_data.get("authors", []):
            authors.append(author.get("name", ""))

        # 提取出版社
        publishers = book_data.get("publishers", [])
        publisher = publishers[0].get("name", "") if publishers else ""

        return {
            "title": book_data.get("title", ""),
            "author": " & ".join(authors),
            "publisher": publisher,
            "publish_date": book_data.get("publish_date", ""),
            "number_of_pages": book_data.get("number_of_pages"),
            "isbn": normalized,
            "source": "openlibrary",
        }

    except Exception as e:
        print(f"Open Library lookup failed: {e}")
        return None


def lookup_isbn_google(
    isbn: str, api_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    通过 Google Books API 查询图书信息。

    Args:
        isbn: ISBN（10 或 13 位）
        api_key: Google Books API Key（可选，但有配额限制）

    Returns:
        图书元数据字典
    """
    try:
        import json
        import urllib.request

        normalized = normalize_isbn(isbn)
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{normalized}"
        if api_key:
            url += f"&key={api_key}"

        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        if data.get("totalItems", 0) == 0:
            return None

        volume = data["items"][0]["volumeInfo"]

        return {
            "title": volume.get("title", ""),
            "author": " & ".join(volume.get("authors", [])),
            "publisher": volume.get("publisher", ""),
            "publish_date": volume.get("publishedDate", ""),
            "description": volume.get("description", ""),
            "categories": volume.get("categories", []),
            "page_count": volume.get("pageCount"),
            "isbn": normalized,
            "source": "google_books",
        }

    except Exception as e:
        print(f"Google Books lookup failed: {e}")
        return None


def lookup_via_calibre(
    title: str, author: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    调用 Calibre 命令行工具 (fetch-ebook-metadata) 查询元数据。
    支持豆瓣、亚马逊等插件。

    Args:
        title: 书名
        author: 作者 (可选)

    Returns:
        图书元数据字典
    """
    import subprocess
    import xml.etree.ElementTree as ET

    from .pdf_converter import find_calibre_tool

    installed, calibre_path = find_calibre_tool("fetch-ebook-metadata")
    if not installed:
        return None

    try:
        # 清理标题
        clean_title = title.split("(")[0].split("[")[0].strip().replace("_", " ")

        cmd = [calibre_path, "--title", clean_title, "--timeout", "30", "--opf"]
        if author:
            # 清理作者名 (移除括号内的外文名)
            clean_author = author.split("(")[0].split("[")[0].strip()
            cmd.extend(["--author", clean_author])

        # 运行命令
        # 注意：Calibre 输出可能包含日志在 stderr，OPF 内容在 stdout
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)

        if result.returncode != 0:
            print(f"Calibre lookup failed: {result.stderr[:200]}")
            return None

        # 解析 OPF (XML)
        # stdout 包含 XML
        xml_content = result.stdout
        # 有时 stdout 会包含非 XML 的日志信息，寻找 <?xml ... >
        start_idx = xml_content.find("<?xml")
        if start_idx == -1:
            start_idx = xml_content.find("<package")

        if start_idx != -1:
            xml_content = xml_content[start_idx:]

        root = ET.fromstring(xml_content)
        ns = {
            "dc": "http://purl.org/dc/elements/1.1/",
            "opf": "http://www.idpf.org/2007/opf",
        }

        # 提取元数据
        metadata = {}

        # Title
        title_elem = root.find(".//dc:title", ns)
        if title_elem is not None:
            metadata["title"] = title_elem.text

        # Author
        author_elem = root.find(".//dc:creator", ns)
        if author_elem is not None:
            metadata["author"] = author_elem.text

        # Publisher
        pub_elem = root.find(".//dc:publisher", ns)
        if pub_elem is not None:
            metadata["publisher"] = pub_elem.text

        # Description
        desc_elem = root.find(".//dc:description", ns)
        if desc_elem is not None:
            metadata["description"] = desc_elem.text

        # Date
        date_elem = root.find(".//dc:date", ns)
        if date_elem is not None:
            metadata["publish_date"] = date_elem.text

        # ISBN
        # 标识符通常在 <dc:identifier opf:scheme="ISBN">...
        for ident in root.findall(".//dc:identifier", ns):
            scheme = ident.get(f"{{{ns['opf']}}}scheme", "").upper()
            if scheme == "ISBN":
                metadata["isbn"] = ident.text
                break

        metadata["source"] = "calibre"
        return metadata

    except Exception as e:
        print(f"Calibre lookup error: {e}")
        return None


def lookup_book_by_title(title: str) -> Optional[Dict[str, Any]]:
    """
    通过书名搜索在 Open Library 中查找图书（兜底策略）。

    Args:
        title: 书名

    Returns:
        图书元数据字典
    """
    try:
        import json
        import urllib.parse
        import urllib.request

        # 清理书名，移除可能的附加信息
        clean_title = title.split("(")[0].split("[")[0].strip()
        # 替换下划线为空格 (常见于文件名)
        clean_title = clean_title.replace("_", " ")
        encoded_title = urllib.parse.quote(clean_title)

        # 使用 Open Library Search API
        url = f"https://openlibrary.org/search.json?title={encoded_title}&limit=1"

        # 设置 User-Agent 避免请求被拒
        headers = {"User-Agent": "BookOrganizer/1.0"}
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        if data.get("numFound", 0) == 0 or not data.get("docs"):
            return None

        book = data["docs"][0]

        # 提取第一个 ISBN 作为参考
        isbn = ""
        if book.get("isbn"):
            isbn = book["isbn"][0]

        return {
            "title": book.get("title", ""),
            "author": ", ".join(book.get("author_name", [])),
            "publisher": ", ".join(book.get("publisher", []))[:100],  # 截断过长信息
            "publish_date": str(book.get("first_publish_year", "")),
            "isbn": isbn,
            "source": "openlibrary_search",
        }

    except Exception as e:
        print(f"Open Library title search failed: {e}")
        return None


def auto_lookup_isbn(
    file_path: str,
    prefer_api: str = "openlibrary",
    google_api_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    自动从文件提取 ISBN 并查询元数据。
    如果 ISBN 未找到或查询失败，尝试使用文件名进行书名搜索。

    Args:
        file_path: 图书文件路径
        prefer_api: 优先使用的 API ("openlibrary" 或 "google")
        google_api_key: Google Books API Key

    Returns:
        图书元数据字典
    """
    import os

    # 1. 尝试提取 ISBN
    isbn = extract_isbn_from_metadata(file_path)

    if isbn:
        # 2. 如果有 ISBN，查询 API
        if prefer_api == "google" and google_api_key:
            result = lookup_isbn_google(isbn, google_api_key)
            if result:
                return result

        # 默认使用 Open Library
        result = lookup_isbn_openlibrary(isbn)
        if result:
            return result

        # 如果首选失败，尝试备选
        if prefer_api != "google":
            result = lookup_isbn_google(isbn, google_api_key)
            if result:
                return result

    # 3. ISBN 策略失败，尝试书名搜索兜底
    # 延迟导入以避免循环依赖
    try:
        from .local_utils import parse_book_name

        filename = os.path.basename(file_path)
        parsed = parse_book_name(filename)
        title = parsed.get("title")

        if title:
            # 过滤掉过短或无意义的标题
            if len(title) >= 2 and not title.lower().startswith("unknown"):
                # 3.1 尝试 Open Library 书名搜索
                result = lookup_book_by_title(title)
                if result:
                    return result

                # 3.2 尝试 Calibre 命令行工具 (最后的兜底)
                parsed_author = parsed.get("author")
                result = lookup_via_calibre(title, parsed_author)
                if result:
                    return result

    except ImportError:
        pass
    except Exception as e:
        print(f"Fallback title search failed: {e}")

    return None
