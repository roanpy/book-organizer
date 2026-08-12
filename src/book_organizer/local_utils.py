# -*- coding: utf-8 -*-
"""
本地工具函数模块 - 不依赖 AI 的图书处理功能

包含：
- 版本比较
- 名称分组
- 文件名解析
- 重复检测

注意：此模块所有功能均不调用 AI API，可在离线环境使用。
"""

import json
import os
import re
import threading
from typing import Any, Dict, List, Optional


def compare_versions(v1: Optional[str], v2: Optional[str]) -> int:
    """
    比较两个版本号。

    Args:
        v1: 版本号1
        v2: 版本号2

    Returns:
        1 如果 v1 > v2, -1 如果 v1 < v2, 0 如果相等
    """
    if not v1 and not v2:
        return 0
    if not v1:
        return -1
    if not v2:
        return 1

    def parse_version(v: str) -> List[int]:
        return [int(x) for x in re.findall(r"\d+", v)]

    parts1 = parse_version(v1)
    parts2 = parse_version(v2)

    for p1, p2 in zip(parts1, parts2):
        if p1 > p2:
            return 1
        if p1 < p2:
            return -1

    return len(parts1) - len(parts2)


def group_by_name(
    items: List[Dict[str, Any]],
    key_field: str = "title",
    ignore_case: bool = True,
) -> Dict[str, List[Dict]]:
    """
    根据指定字段对项目进行本地分组（不调用 AI）。

    Args:
        items: 项目列表
        key_field: 用于分组的字段名
        ignore_case: 是否忽略大小写

    Returns:
        按名称分组的字典
    """
    groups: Dict[str, List[Dict]] = {}

    for item in items:
        key = item.get(key_field, "")
        if not key:
            key = item.get("filename", "unknown")

        if ignore_case:
            key = key.lower()

        if key not in groups:
            groups[key] = []
        groups[key].append(item)

    return groups


def parse_book_name(filename: str) -> Dict[str, Optional[str]]:
    """
    解析图书文件名，提取结构化信息。

    支持格式：
    - [作者] 书名.epub
    - 书名 - 作者.epub
    - [[国家]] 作者 - 书名.epub
    - 书名 (第X版).epub

    Args:
        filename: 文件名

    Returns:
        包含 title, author, edition 的字典
    """
    import os

    # 移除扩展名
    name_without_ext = os.path.splitext(filename)[0]

    title = None
    author = None
    edition = None

    # 模式 1: [作者] 书名
    match1 = re.match(r"\[([^\]]+)\]\s*(.+)", name_without_ext)
    if match1:
        author = match1.group(1).strip()
        title = match1.group(2).strip()
    else:
        # 模式 2: 书名 - 作者
        match2 = re.match(r"(.+?)\s*[-–—]\s*(.+)", name_without_ext)
        if match2:
            title = match2.group(1).strip()
            author = match2.group(2).strip()
        else:
            title = name_without_ext

    # 提取版本/版次
    edition_match = re.search(r"[（(]第?(\d+)版[）)]", title or "")
    if edition_match:
        edition = edition_match.group(1)
        title = re.sub(r"\s*[（(]第?\d+版[）)]", "", title or "").strip()

    return {"title": title, "author": author, "edition": edition}


def normalize_title(title: str) -> str:
    """
    标准化书名，用于比较和查重。

    处理：
    - 移除标点符号
    - 转换为小写
    - 移除多余空格

    Args:
        title: 原始书名

    Returns:
        标准化后的书名
    """
    if not title:
        return ""

    # 移除常见标点
    normalized = re.sub(
        r"[,，.。:：;；!！?？()（）\[\]【】《》<>\"'" "'']+", " ", title
    )
    # 转小写
    normalized = normalized.lower()
    # 合并多余空格
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def find_similar_titles(
    target_title: str,
    book_list: List[Dict[str, Any]],
    threshold: float = 0.8,
) -> List[Dict[str, Any]]:
    """
    查找相似书名的图书。

    Args:
        target_title: 目标书名
        book_list: 图书列表
        threshold: 相似度阈值 (0-1)

    Returns:
        相似图书列表
    """
    from difflib import SequenceMatcher

    normalized_target = normalize_title(target_title)
    if not normalized_target:
        return []

    similar = []
    for book in book_list:
        book_title = book.get("title", "") or book.get("filename", "")
        normalized_book = normalize_title(book_title)

        if not normalized_book:
            continue

        ratio = SequenceMatcher(None, normalized_target, normalized_book).ratio()
        if ratio >= threshold:
            similar.append({**book, "_similarity": ratio})

    # 按相似度排序
    similar.sort(key=lambda x: x.get("_similarity", 0), reverse=True)

    return similar


# 分类关键词规则
CATEGORY_RULES: Dict[str, List[str]] = {
    "技术/编程": [
        "Python",
        "JavaScript",
        "Java",
        "编程",
        "开发",
        "算法",
        "数据结构",
        "机器学习",
        "深度学习",
        "人工智能",
        "AI",
        "Docker",
        "Kubernetes",
        "云计算",
        "大数据",
    ],
    "商业/管理": [
        "管理",
        "领导力",
        "创业",
        "商业模式",
        "战略",
        "营销",
        "金融",
        "投资",
        "经济学",
    ],
    "心理学": [
        "心理",
        "认知",
        "行为",
        "情绪",
        "思维",
        "心理学",
        "精神",
        "意识",
    ],
    "历史": [
        "历史",
        "传记",
        "纪实",
        "回忆录",
        "二战",
        "古代",
        "近代",
        "文明",
    ],
    "文学/小说": [
        "小说",
        "文学",
        "散文",
        "诗歌",
        "戏剧",
        "科幻",
        "奇幻",
        "悬疑",
        "推理",
    ],
}

# =============================================================================
# 动态规则学习系统（从历史记录自动进化）
# =============================================================================

# 缓存学习到的规则 (启动时延迟加载一次)
_learned_rules_cache: Dict[str, List[str]] = {}
_rules_initialized: bool = False
_rules_loading: bool = False
_rules_lock = threading.Lock()


def learn_rules_from_history(
    history: List[Dict[str, str]],
    min_occurrences: int = 2,
) -> Dict[str, List[str]]:
    """
    从历史转移记录中学习分类规则。

    分析文件名中的关键词与目标目录的对应关系，
    提取高频出现的模式作为新规则。

    Args:
        history: 历史转移记录 [{"filename": "...", "destination": "..."}]
        min_occurrences: 关键词最少出现次数才会被纳入规则

    Returns:
        学习到的规则字典 {"目录": ["关键词1", "关键词2", ...]}
    """
    from collections import defaultdict

    # 统计: 目录 -> 关键词 -> 出现次数
    dir_keywords: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # 中文分词简易实现 (无需jieba依赖)
    def extract_keywords(text: str) -> List[str]:
        """提取文本中的关键词（支持中英文）"""
        # 英文单词
        english_words = re.findall(r"[a-zA-Z]{3,}", text)
        # 中文词组 (2-4字)
        chinese_words = re.findall(r"[\u4e00-\u9fff]{2,4}", text)
        # 合并并转小写
        return [w.lower() for w in english_words] + chinese_words

    # 过滤停用词
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "epub",
        "pdf",
        "mobi",
        "的",
        "了",
        "是",
        "在",
        "和",
        "与",
        "等",
        "之",
        "个",
        "我",
        "有",
    }

    for record in history:
        filename = record.get("filename", "")
        destination = record.get("destination", "")

        if not filename or not destination:
            continue

        # 提取目录名 (取最后一级)
        dir_name = os.path.basename(destination.rstrip("/\\"))
        if not dir_name:
            continue

        # 从文件名提取关键词
        keywords = extract_keywords(filename)

        for kw in keywords:
            if kw not in stop_words and len(kw) >= 2:
                dir_keywords[dir_name][kw] += 1

    # 筛选高频关键词作为规则
    learned_rules: Dict[str, List[str]] = {}

    for dir_name, kw_counts in dir_keywords.items():
        # 只保留出现次数 >= min_occurrences 的关键词
        valid_keywords = [
            kw for kw, count in kw_counts.items() if count >= min_occurrences
        ]

        if valid_keywords:
            # 彻底放开限制：不再切片保留前 N 个，只要符合频次要求的关键词全部视为有效规则
            # 仅按出现次数降序排列，保证匹配时的优先级
            sorted_kw = sorted(valid_keywords, key=lambda k: kw_counts[k], reverse=True)
            learned_rules[dir_name] = sorted_kw

    return learned_rules


def _load_learned_rules_sync() -> None:
    """同步加载学习规则（内部使用）"""
    global _learned_rules_cache, _rules_initialized, _rules_loading

    with _rules_lock:
        if _rules_initialized or _rules_loading:
            return
        _rules_loading = True

    try:
        from .config import APP_DIR, get_historical_transfers

        history = get_historical_transfers(days_range=180)
        rules = learn_rules_from_history(history, min_occurrences=2)

        try:
            rules_file = os.path.join(APP_DIR, "learned_rules.json")
            with open(rules_file, "w", encoding="utf-8") as f:
                json.dump(rules, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

        with _rules_lock:
            _learned_rules_cache = rules
            _rules_initialized = True
            _rules_loading = False
    except Exception as e:
        print(f"[LocalRules] 加载学习规则失败: {e}")
        with _rules_lock:
            _learned_rules_cache = {}
            _rules_initialized = True
            _rules_loading = False


def init_learned_rules_async(delay_seconds: float = 3.0) -> None:
    """
    异步初始化学习规则（延迟启动，不阻塞主线程）。

    建议在应用启动时调用此函数。

    Args:
        delay_seconds: 延迟秒数（默认 3 秒后开始加载）
    """
    import threading

    def delayed_load():
        import time

        time.sleep(delay_seconds)
        _load_learned_rules_sync()
        print("[LocalRules] 学习规则加载完成")

    thread = threading.Thread(target=delayed_load, daemon=True)
    thread.start()


def get_dynamic_rules(force_refresh: bool = False) -> Dict[str, List[str]]:
    """
    获取动态规则（基础规则 + 学习规则）。

    规则在首次访问时懒加载，之后使用缓存。

    Args:
        force_refresh: 是否强制刷新缓存

    Returns:
        合并后的分类规则
    """
    global _learned_rules_cache, _rules_initialized

    # 强制刷新或首次访问时懒加载
    if force_refresh or not _rules_initialized:
        _load_learned_rules_sync()

    # 合并基础规则和学习规则
    merged_rules = dict(CATEGORY_RULES)

    for dir_name, keywords in _learned_rules_cache.items():
        if dir_name in merged_rules:
            # 合并关键词 (去重)
            existing = set(merged_rules[dir_name])
            merged_rules[dir_name] = list(existing | set(keywords))
        else:
            # 新增目录规则
            merged_rules[dir_name] = keywords

    return merged_rules


def save_learned_rules_to_file(target_dir: str) -> bool:
    """
    将学习到的规则保存到文件（可选持久化）。

    Args:
        target_dir: 保存目录

    Returns:
        是否保存成功
    """
    import json

    try:
        rules = get_dynamic_rules(force_refresh=True)
        learned_only = {k: v for k, v in rules.items() if k not in CATEGORY_RULES}

        if not learned_only:
            return False

        rules_file = os.path.join(target_dir, ".bookorganizer_rules.json")
        with open(rules_file, "w", encoding="utf-8") as f:
            mtime = os.path.getmtime(__file__) if os.path.exists(__file__) else 0
            json.dump(
                {
                    "learned_rules": learned_only,
                    "base_rules_keys": list(CATEGORY_RULES.keys()),
                    "updated_at": str(mtime),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        return True
    except Exception:
        return False


def auto_categorize(
    title: str,
    tags: Optional[List[str]] = None,
    custom_rules: Optional[Dict[str, List[str]]] = None,
    use_learned_rules: bool = True,
) -> Optional[str]:
    """
    基于关键词的自动分类（无需 AI）。 (✅ 稳定方法)

    基于预定义的关键词映射表。
    此函数逻辑稳定，添加新关键词请修改 KEYWORD_MAP 而非逻辑本身。

    默认使用动态规则（基础规则 + 从历史记录学习的规则）。

    Args:
        title: 图书标题
        tags: 图书标签列表
        custom_rules: 自定义分类规则（优先使用）
        use_learned_rules: 是否使用从历史记录学习的规则

    Returns:
        匹配的分类名称，如果无匹配返回 None
    """
    # 确定使用的规则
    if custom_rules:
        rules = custom_rules
    elif use_learned_rules:
        rules = get_dynamic_rules()
    else:
        rules = CATEGORY_RULES

    # 构建搜索文本
    text_parts = [title]
    if tags:
        text_parts.extend(tags)
    text = " ".join(text_parts).lower()

    for category, keywords in rules.items():
        if any(kw.lower() in text for kw in keywords):
            return category

    return None


# =============================================================================
# 本地元数据识别（无需 AI）
# =============================================================================


def local_identify_metadata(file_path: str) -> Dict[str, Any]:
    """
    本地识别图书元数据（无需 AI）。

    优先级：
    1. 文件内置元数据 (EPUB/PDF)
    2. ISBN 查询 (OpenLibrary/Calibre)
    3. 文件名解析

    Args:
        file_path: 图书文件路径

    Returns:
        {
            "title": str,
            "author": str,
            "publisher": str,
            "source": str,  # 数据来源: "metadata", "isbn", "filename"
            "success": bool
        }
    """
    import os

    result = {
        "title": "",
        "author": "",
        "publisher": "",
        "source": "none",
        "success": False,
    }

    ext = os.path.splitext(file_path)[1].lower()

    # 1. 尝试从文件内置元数据提取
    try:
        if ext == ".epub":
            from ebooklib import epub

            book = epub.read_epub(file_path)

            # 获取标题
            title_meta = book.get_metadata("DC", "title")
            if title_meta:
                result["title"] = title_meta[0][0] if title_meta[0] else ""

            # 获取作者
            author_meta = book.get_metadata("DC", "creator")
            if author_meta:
                authors = [a[0] for a in author_meta if a[0]]
                result["author"] = ", ".join(authors)

            # 获取出版社
            pub_meta = book.get_metadata("DC", "publisher")
            if pub_meta:
                result["publisher"] = pub_meta[0][0] if pub_meta[0] else ""

            if result["title"]:
                result["source"] = "metadata"
                result["success"] = True

        elif ext == ".pdf":
            import fitz

            doc = fitz.open(file_path)
            metadata = doc.metadata
            doc.close()

            if metadata:
                result["title"] = metadata.get("title", "") or ""
                result["author"] = metadata.get("author", "") or ""
                # PDF 通常没有 publisher 字段

                if result["title"]:
                    result["source"] = "metadata"
                    result["success"] = True

    except Exception:
        pass

    # 2. 如果元数据不完整，尝试 ISBN 查询
    if not result["success"] or not result["title"]:
        try:
            from .isbn_lookup import auto_lookup_isbn

            isbn_result = auto_lookup_isbn(file_path)

            if isbn_result:
                if not result["title"] and isbn_result.get("title"):
                    result["title"] = isbn_result["title"]
                if not result["author"] and isbn_result.get("author"):
                    result["author"] = isbn_result["author"]
                if not result["publisher"] and isbn_result.get("publisher"):
                    result["publisher"] = isbn_result["publisher"]

                result["source"] = isbn_result.get("source", "isbn")
                result["success"] = True
        except Exception:
            pass

    # 3. 如果仍不完整，从文件名解析
    if not result["title"]:
        parsed = parse_book_name(os.path.basename(file_path))
        result["title"] = parsed.get("title", "")
        result["author"] = parsed.get("author", "") or result["author"]
        result["source"] = "filename"
        result["success"] = bool(result["title"])

    return result


def local_suggest_directories(
    title: str,
    author: Optional[str],
    available_dirs: List[str],
    history: Optional[List[Dict[str, str]]] = None,
) -> List[str]:
    """基于本地规则和历史记录推荐目录 (✅ 稳定方法)

    纯本地逻辑，不依赖 AI。
    包含学习规则的加载與应用。
    本地推荐目标目录（无需 AI）。

    策略：
    1. 关键词规则匹配
    2. 与目录名相似度匹配
    3. 历史记录相似文件的目标目录

    Args:
        title: 图书标题
        author: 作者
        available_dirs: 可用的目标目录列表
        history: 历史转移记录 [{"filename": "...", "destination": "..."}]

    Returns:
        推荐目录列表（按优先级排序）
    """
    from difflib import SequenceMatcher

    suggestions = []
    scores: Dict[str, float] = {}

    # 构建搜索文本
    search_text = title.lower()
    if author:
        search_text += " " + author.lower()

    # 策略 1: 关键词规则匹配（使用动态规则）
    category = auto_categorize(title)
    dynamic_rules = get_dynamic_rules()
    if category:
        # 查找包含分类关键词的目录
        for dir_path in available_dirs:
            dir_name = os.path.basename(dir_path).lower()
            # 检查目录名是否包含分类关键词
            for kw in dynamic_rules.get(category, []):
                if kw.lower() in dir_name:
                    scores[dir_path] = scores.get(dir_path, 0) + 1.0
                    break

    # 策略 2: 目录名相似度匹配
    for dir_path in available_dirs:
        dir_name = os.path.basename(dir_path)
        # 计算标题与目录名的相似度
        ratio = SequenceMatcher(None, title.lower(), dir_name.lower()).ratio()
        if ratio > 0.3:
            scores[dir_path] = scores.get(dir_path, 0) + ratio * 0.5

    # 策略 3: 历史记录匹配
    if history:
        for record in history:
            hist_filename = record.get("filename", "")
            hist_dest = record.get("destination", "")

            if not hist_filename or not hist_dest:
                continue

            # 计算与历史文件名的相似度
            ratio = SequenceMatcher(None, title.lower(), hist_filename.lower()).ratio()
            if ratio > 0.5 and hist_dest in available_dirs:
                scores[hist_dest] = scores.get(hist_dest, 0) + ratio * 0.8

    # 按分数排序
    sorted_dirs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    suggestions = [d[0] for d in sorted_dirs if d[1] > 0.2]

    # 最多返回 5 个建议
    return suggestions[:5]


def get_available_target_directories(target_dir: str) -> List[str]:
    """
    获取目标目录下的所有子目录（用于目录推荐）。

    Args:
        target_dir: 目标根目录

    Returns:
        子目录相对路径列表
    """
    import os

    dirs = []

    if not os.path.isdir(target_dir):
        return dirs

    for root, subdirs, _ in os.walk(target_dir):
        for subdir in subdirs:
            # 跳过隐藏目录
            if subdir.startswith("."):
                continue
            full_path = os.path.join(root, subdir)
            rel_path = os.path.relpath(full_path, target_dir)
            dirs.append(rel_path)

    return dirs
