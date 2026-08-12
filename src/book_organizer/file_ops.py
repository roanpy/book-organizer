# -*- coding: utf-8 -*-
"""
文件操作模块 - 处理图书文件的扫描、读取和移动

包含：
- 文件扫描
- 目录遍历
- 封面提取
- 文件名解析
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

# ==============================================================================
# 通用文件查找逻辑
# ==============================================================================


def resolve_file_path(filename: str, config: Dict[str, Any]) -> Optional[str]:
    """解析并验证文件绝对路径 (✅ 稳定方法)

    此函数用于在 source_dir, target_dir 和当前路径中查找文件。
    逻辑经过严格测试，除 Bug 修复外不建议修改。

    1. Source Dir (入库整理源目录)
    2. Target Dir (Library 主目录)
    3. Library Directories (Library 子目录)
    4. Absolute Path (绝对路径)

    ⚠️ 核心参考方法：所有 API 端点的路径解析都应使用此函数，
    请勿随意修改。如需修改，请确保全面测试所有模式。

    返回找到的绝对路径，如果未找到则返回 None。
    """
    if not filename:
        return None

    # 1. Check Source Dir
    source_dir = config.get("source_dir")
    if source_dir:
        candidate = os.path.join(source_dir, filename)
        if os.path.exists(candidate):
            return candidate
        else:
            print(f"DEBUG: Not found in source_dir: {candidate}")

    # 2. Check Target Dir
    target_dir = config.get("target_dir")
    if target_dir:
        candidate = os.path.join(target_dir, filename)
        if os.path.exists(candidate):
            return candidate
        else:
            print(f"DEBUG: Not found in target_dir: {candidate}")

    # 3. Check Library Directories
    lib_dirs = config.get("library_directories", [])
    for lib_dir in lib_dirs:
        candidate = os.path.join(lib_dir, filename)
        if os.path.exists(candidate):
            return candidate

    # 4. Check Absolute Path
    if os.path.exists(filename):
        return filename

    # 5. Fallback: Recursive Search (for when frontend sends basename only)
    # Search Source Dir
    if source_dir:
        for root, _, files in os.walk(source_dir):
            if filename in files:
                found = os.path.join(root, filename)
                print(f"DEBUG: Resolved via recursive source_dir search: {found}")
                return found

    # Search Target Dir
    if target_dir:
        for root, _, files in os.walk(target_dir):
            if filename in files:
                found = os.path.join(root, filename)
                print(f"DEBUG: Resolved via recursive target_dir search: {found}")
                return found

    print(f"DEBUG: resolve_file_path failed for: '{filename}'")
    return None


from typing import Any, Dict, List, Optional  # noqa: E402


# 延迟导入避免循环依赖
def _get_config():
    from .config import load_ai_config, load_config

    return load_config, load_ai_config


# 默认支持的图书格式。运行时实际识别范围由 config["book_extensions"] 控制。
BOOK_EXTENSIONS = (
    ".epub",
    ".pdf",
    ".mobi",
    ".azw3",
    ".azw",
    ".txt",
    ".md",
    ".markdown",
)


def normalize_book_extensions(extensions: Any) -> tuple[str, ...]:
    """Return normalized extension tuple such as (".epub", ".pdf")."""
    if not isinstance(extensions, (list, tuple, set)):
        return BOOK_EXTENSIONS

    normalized: list[str] = []
    seen = set()
    for value in extensions:
        text = str(value or "").strip().lower()
        if not text:
            continue
        if not text.startswith("."):
            text = f".{text}"
        if not re.fullmatch(r"\.[a-z0-9][a-z0-9_-]{0,15}", text):
            continue
        if text not in seen:
            normalized.append(text)
            seen.add(text)

    return tuple(normalized) or BOOK_EXTENSIONS


def get_configured_book_extensions(config: Optional[Dict[str, Any]] = None) -> tuple[str, ...]:
    """Return the configured recognition formats, falling back to legacy defaults."""
    if config is None:
        try:
            load_config, _ = _get_config()
            config = load_config()
        except Exception:
            config = {}
    return normalize_book_extensions((config or {}).get("book_extensions"))

# 可选库导入
try:
    import ebooklib
    from ebooklib import epub
except ImportError:
    ebooklib = None
    epub = None


def get_book_files(source_dir: str, extensions: Optional[Any] = None) -> List[str]:
    """获取源目录下的所有图书文件（包括子文件夹），并忽略隐藏文件。

    ✅ 稳定方法：自 v0.3.23 创建以来未经修改，逻辑简单可靠。

    Args:
        source_dir: 源目录路径

    Returns:
        图书文件路径列表
    """
    books = []
    allowed_extensions = (
        normalize_book_extensions(extensions)
        if extensions is not None
        else get_configured_book_extensions()
    )
    for root, dirs, files in os.walk(source_dir):
        # 忽略隐藏文件夹
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        # 添加符合格式的文件
        for f in files:
            # 排除隐藏文件 (以 . 开头) 和 Office 临时文件 (以 ~$ 开头)
            if f.startswith(".") or f.startswith("~$"):
                continue
            # 只添加符合格式的图书文件
            if f.lower().endswith(allowed_extensions):
                books.append(os.path.join(root, f))
    return books


def get_target_categories(target_dir: str) -> List[str]:
    """递归扫描目标目录，获取所有文件夹的相对路径作为分类。

    ✅ 稳定方法：自 v0.3.23 创建以来未经修改，核心目录遍历逻辑。

    Args:
        target_dir: 目标目录路径

    Returns:
        分类目录相对路径列表
    """
    categories = []
    for root, dirs, _ in os.walk(target_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        relative_path = os.path.relpath(root, target_dir)
        categories.append(relative_path)
    return sorted(list(set(categories)))


def parse_filename(filename: str) -> str:
    """尝试从文件名中用正则表达式提取书名和作者。

    ✅ 稳定方法：自 v0.3.23 创建以来未经修改，经过充分测试的正则解析逻辑。

    支持多种格式：
    - [作者] 书名
    - 书名 - [作者]
    - [[国家]] 作者 - 书名

    Args:
        filename: 文件名

    Returns:
        解析后的信息字符串
    """
    name_only = Path(filename).stem

    # 模式1: [[国家]] 作者 - 书名 或 书名 - [[国家]] 作者
    match = re.search(r"^(.+?)\s*-\s*\[\[(.+?)\]\]\s*(.+)$", name_only)
    if match:
        title = match.group(1).strip()
        country = match.group(2).strip()
        author = match.group(3).strip()
        return f"书名: '{title}', 作者: '[{country}] {author}'"

    # 模式2: 书名 - [作者]
    match = re.search(r"^(.+?)\s*-\s*\[(.+?)\]$", name_only)
    if match:
        title = match.group(1).strip()
        author = match.group(2).strip()
        return f"书名: '{title}', 作者: '{author}'"

    # 模式3: [作者] 书名
    match = re.search(r"^[\[\(](.+?)[\]\)](.+)", name_only)
    if match:
        author = match.group(1).strip()
        title = match.group(2).strip()
        return f"书名: '{title}', 作者: '{author}'"

    return f"文件名: '{name_only}'"


def parse_filename_to_dict(filename: str) -> Dict[str, Any]:
    """从文件名中尝试提取书名和作者 (✅ 稳定方法)

    使用启发式正则表达式解析常见格式。
    注意：此函数仅用于离线/本地处理的兜底。

    Args:
        filename: 文件名

    Returns:
        dict: 包含 title, author 的字典
    """
    name_only = Path(filename).stem

    # Cleaning: remove common garbage suffix/prefix if needed
    # (Optional)

    # 模式1: [[国家]] 作者 - 书名 或 书名 - [[国家]] 作者
    match = re.search(r"^(.+?)\s*-\s*\[\[(.+?)\]\]\s*(.+)$", name_only)
    if match:
        return {
            "title": match.group(1).strip(),
            "author": f"[{match.group(2).strip()}] {match.group(3).strip()}",
        }

    # 模式2: 书名 - [作者]
    match = re.search(r"^(.+?)\s*-\s*\[(.+?)\]$", name_only)
    if match:
        return {"title": match.group(1).strip(), "author": match.group(2).strip()}

    # 模式3: [作者] 书名
    match = re.search(r"^[\[\(](.+?)[\]\)](.+)", name_only)
    if match:
        return {"title": match.group(2).strip(), "author": match.group(1).strip()}

    # 模式4: 书名 作者 (最后尝试)
    # 书名 - 作者
    if " - " in name_only:
        parts = name_only.split(" - ")
        if len(parts) == 2:
            return {"title": parts[0].strip(), "author": parts[1].strip()}

    # 默认: 整个文件名作为标题
    return {"title": name_only}


def get_cover_image(file_path: str) -> Optional[bytes]:
    """从 EPUB 或 PDF 文件中提取封面图片。

    ✅ 稳定方法：自 v0.3.23 创建以来未经修改，多种封面提取策略已充分验证。

    Args:
        file_path: EPUB 或 PDF 文件路径

    Returns:
        封面图片的字节数据，如果未找到则返回 None
    """
    ext = os.path.splitext(file_path)[1].lower()

    # EPUB 封面提取
    if ext == ".epub" and ebooklib:
        try:
            book = epub.read_epub(file_path)
            cover_item = None

            # 方法 1: 检查元数据
            covers = book.get_metadata("OPF", "cover")
            if covers:
                cover_id = covers[0][1].get("content")
                if cover_id:
                    cover_item = book.get_item_with_id(cover_id)

            # 方法 2: 遍历查找封面类型的项目
            if not cover_item:
                for item in book.get_items():
                    if item.get_type() == ebooklib.ITEM_COVER:
                        cover_item = item
                        break

            # 方法 3: 根据文件名猜测
            if not cover_item:
                for item in book.get_items():
                    name = item.get_name().lower()
                    if item.get_type() == ebooklib.ITEM_IMAGE and (
                        "cover" in name or "jacket" in name
                    ):
                        cover_item = item
                        break

            if cover_item:
                return cover_item.get_content()

        except Exception as e:
            print(f"  ⚠️ 读取EPUB封面失败 [{os.path.basename(file_path)}]: {e}")

    # PDF 封面提取（使用第一页作为封面）
    elif ext == ".pdf":
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            if doc.page_count > 0:
                page = doc[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(150 / 72, 150 / 72))
                img_bytes = pix.tobytes("png")
                doc.close()
                return img_bytes
            doc.close()
        except ImportError:
            pass
        except Exception as e:
            print(f"  ⚠️ 读取PDF封面失败 [{os.path.basename(file_path)}]: {e}")

    return None


def _normalize_relative_path_for_match(path: str, root_dir: str) -> Optional[str]:
    """Normalize an absolute or relative book path for comparisons under root_dir."""
    if not path:
        return None

    root_abs = os.path.abspath(os.path.expanduser(root_dir))
    raw_path = os.path.expanduser(path)

    if os.path.isabs(raw_path):
        path_abs = os.path.abspath(raw_path)
        try:
            if os.path.commonpath([root_abs, path_abs]) != root_abs:
                return None
            rel_path = os.path.relpath(path_abs, root_abs)
        except ValueError:
            return None
    else:
        rel_path = raw_path

    return os.path.normcase(os.path.normpath(rel_path))


def find_similar_files(
    target_dir: str,
    query: str,
    exclude_paths: Optional[Iterable[str]] = None,
) -> List[Dict[str, str]]:
    """在目标目录中递归查找与查询字符串相似的文件。

    Args:
        target_dir: 目标根目录
        query: 查询字符串（通常是书名的一部分）
        exclude_paths: 需要从结果中排除的当前图书路径，可为绝对路径或相对路径

    Returns:
        匹配文件列表 [{"path": "相对路径", "filename": "文件名"}, ...]
    """
    load_config, _ = _get_config()
    matches: List[Dict[str, str]] = []

    if not query or not target_dir or not os.path.exists(target_dir):
        return matches

    # 检查 Beta Feature Flag
    try:
        config = load_config()
        beta_enabled = config.get("beta_features", {}).get(
            "enable_similar_search", False
        )
        if not beta_enabled:
            return matches
    except Exception:
        return matches

    query = query.lower().strip()
    allowed_extensions = set(get_configured_book_extensions(config))
    normalized_excludes = {
        normalized
        for normalized in (
            _normalize_relative_path_for_match(path, target_dir)
            for path in (exclude_paths or [])
        )
        if normalized
    }

    from difflib import SequenceMatcher

    scored_matches = []

    try:
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                name, ext = os.path.splitext(file)
                if ext.lower() not in allowed_extensions:
                    continue

                rel_path = os.path.relpath(os.path.join(root, file), target_dir)
                if os.path.normcase(os.path.normpath(rel_path)) in normalized_excludes:
                    continue

                filename_clean = name.lower()

                # 1. 优先检查子串包含 (Score 1.0)
                if query in filename_clean:
                    score = 1.0
                else:
                    # 2. 模糊相似度计算
                    score = SequenceMatcher(None, query, filename_clean).ratio()

                if score >= 0.6:  # 相似度阈值
                    scored_matches.append(
                        {"path": rel_path, "filename": file, "score": score}
                    )

        # 按相似度从高到低排序
        scored_matches.sort(key=lambda x: x["score"], reverse=True)
        # 取前 10 个
        return [
            {"path": m["path"], "filename": m["filename"]} for m in scored_matches[:10]
        ]

    except Exception as e:
        print(f"Error in find_similar_files: {e}")
        return []


def truncate_filename_smart(filename_stem: str, ext: str, max_bytes: int = 255) -> str:
    """智能截断文件名，确保总长度不超过指定字节数。

    截断策略（按优先级）：
    1. 如果有多个作者（用&分隔），保留前几个，其余用"等"代替
    2. 删除副标题（冒号、破折号后的内容）
    3. 删除括号及其内容
    4. 截断主标题

    Args:
        filename_stem: 文件名主体（不含扩展名）
        ext: 文件扩展名（含点号）
        max_bytes: 最大字节数，默认255

    Returns:
        截断后的文件名主体
    """

    def get_bytes_length(name):
        return len((name + ext).encode("utf-8"))

    if get_bytes_length(filename_stem) <= max_bytes:
        return filename_stem

    # 策略1: 处理多作者
    if " & " in filename_stem or " - " in filename_stem:
        parts = filename_stem.split(" - ", 1)
        if len(parts) == 2:
            title_part = parts[0]
            author_part = parts[1]

            if " & " in author_part:
                authors = [a.strip() for a in author_part.split(" & ")]
                if len(authors) > 2:
                    for keep_count in range(2, 0, -1):
                        truncated_authors = " & ".join(authors[:keep_count]) + " 等"
                        new_stem = f"{title_part} - {truncated_authors}"
                        if get_bytes_length(new_stem) <= max_bytes:
                            filename_stem = new_stem
                            break

                    if get_bytes_length(filename_stem) > max_bytes:
                        first_author = authors[0] + " 等"
                        new_stem = f"{title_part} - {first_author}"
                        if get_bytes_length(new_stem) <= max_bytes:
                            filename_stem = new_stem

    # 策略2: 删除副标题
    if get_bytes_length(filename_stem) > max_bytes:
        for separator in ["：", ":", "——", "—"]:
            if separator in filename_stem:
                main_title = filename_stem.split(separator)[0]
                if get_bytes_length(main_title) <= max_bytes:
                    filename_stem = main_title
                    break

    # 策略3: 删除括号内容
    if get_bytes_length(filename_stem) > max_bytes:
        patterns = [r"[（(].*?[）)]", r"[\[].*?[\]]"]
        for pattern in patterns:
            temp_stem = re.sub(pattern, "", filename_stem)
            temp_stem = re.sub(r"\s+", " ", temp_stem).strip()
            if get_bytes_length(temp_stem) <= max_bytes and temp_stem:
                filename_stem = temp_stem
                break

    # 策略4: 直接截断
    if get_bytes_length(filename_stem) > max_bytes:
        available_bytes = max_bytes - len(ext.encode("utf-8")) - 3
        truncated = ""
        for char in filename_stem:
            test_str = truncated + char
            if len(test_str.encode("utf-8")) <= available_bytes:
                truncated += char
            else:
                break
        filename_stem = truncated.rstrip() + "..."

    return filename_stem
