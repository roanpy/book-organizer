# -*- coding: utf-8 -*-
"""
Business entry points for AI analysis.

These functions orchestrate prompt building, AI dispatch, response parsing,
and offline fallback. Each function calls dispatcher.dispatch_ai_request()
instead of having its own engine routing logic.

Contains:
- get_ai_analysis()
- get_unified_analysis()
- identify_book_metadata()
- optimize_additional_rules_with_ai()
- get_enhanced_mode_analysis()
- get_batch_enhance_analysis()
- get_batch_organize_analysis()
- extract_core_content()
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from ..file_ops import resolve_file_path
from ..logger import logger

# Sub-module imports within the ai_engines package
from .dispatcher import (
    _call_ai_engine,
    _get_engine_config,
    dispatch_ai_request,
)
from .offline_fallback import (
    offline_batch_enhance,
    offline_batch_enhance_fallback,
    offline_batch_organize,
    offline_batch_organize_fallback,
    offline_identify_metadata,
    offline_identify_with_warning,
)
from .prompt_builder import get_common_prompt
from .response_parser import (
    _normalize_author,
    normalize_identify_result,
    normalize_metadata_fields,
)

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import ebooklib
    from ebooklib import epub
except ImportError:
    ebooklib = None
    epub = None


def _get_deps():
    """Lazy import dependencies to avoid circular references.

    Returns a dict instead of a tuple for clarity and maintainability.
    """
    from ..config import (
        get_content_search_config,
        get_historical_transfers,
        load_ai_config,
        load_config,
    )
    from ..file_ops import parse_filename, parse_filename_to_dict
    from ..metadata import extract_metadata
    from ..search import search_book_online

    return {
        "load_config": load_config,
        "load_ai_config": load_ai_config,
        "get_historical_transfers": get_historical_transfers,
        "parse_filename": parse_filename,
        "extract_metadata": extract_metadata,
        "search_book_online": search_book_online,
        "get_content_search_config": get_content_search_config,
        "parse_filename_to_dict": parse_filename_to_dict,
    }


def extract_core_content(
    file_path: str, max_chars: Optional[int] = None, strategy: Optional[str] = None
) -> str:
    """Extract core content from a file for AI identification.

    Args:
        file_path: File path
        max_chars: Maximum character count
        strategy: Extraction strategy ("adaptive" or "head_only")

    Returns:
        Extracted text content
    """
    deps = _get_deps()
    get_content_search_config = deps["get_content_search_config"]

    # Read parameters from config (auto-handles enabled switch)
    try:
        ctrl_config = get_content_search_config()

        # If content search control is disabled, skip content extraction
        if ctrl_config.get("skip", False):
            return ""

        pdf_max_pages = int(ctrl_config.get("pdf_max_pages", 10))
        epub_max_chapters = int(ctrl_config.get("epub_max_chapters", 10))
        raw_scan_limit = int(ctrl_config.get("raw_scan_char_limit", 3000))

        if max_chars is None:
            max_chars = int(ctrl_config.get("standard_mode_chars", 1500))

        if strategy is None:
            strategy = (
                "adaptive"
                if ctrl_config.get("adaptive_extraction", True)
                else "head_only"
            )

        head_len = int(ctrl_config.get("head_chars", 500))

    except Exception:
        pdf_max_pages = 10
        epub_max_chapters = 10
        raw_scan_limit = 3000
        if max_chars is None:
            max_chars = 1500
        if strategy is None:
            strategy = "adaptive"
        head_len = 500

    ext = os.path.splitext(file_path)[1].lower()

    try:
        raw_text = ""

        if ext == ".pdf" and PdfReader:
            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                num_pages = min(len(reader.pages), pdf_max_pages)
                for i in range(num_pages):
                    text = reader.pages[i].extract_text()
                    if text:
                        raw_text += text + "\n"
                        if strategy == "head_only" and len(raw_text) > max_chars:
                            break
                        if len(raw_text) > raw_scan_limit:
                            break

        elif ext == ".epub" and ebooklib:
            try:
                from bs4 import BeautifulSoup
            except ImportError:
                # Fallback to regex if bs4 not available (though we just installed it)
                import re

                BeautifulSoup = None

            book = epub.read_epub(file_path)
            count = 0
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    item_content = item.get_content()

                    if BeautifulSoup:
                        soup = BeautifulSoup(item_content, "html.parser")
                        text = soup.get_text(separator="\n", strip=True)
                    else:
                        text = re.sub(
                            "<[^<]+?>",
                            "",
                            item_content.decode("utf-8", errors="ignore"),
                        )

                    if text.strip():
                        raw_text += text + "\n"
                        count += 1

                    if strategy == "head_only" and len(raw_text) > max_chars:
                        break
                    if len(raw_text) > raw_scan_limit or count > epub_max_chapters:
                        break

        if not raw_text:
            return ""

        if len(raw_text) <= max_chars:
            return raw_text

        if strategy == "adaptive":
            tail_len = max_chars - head_len
            if tail_len > 0:
                return (
                    raw_text[:head_len]
                    + "\n...[中间内容省略]...\n"
                    + raw_text[-tail_len:]
                )
            else:
                return raw_text[:max_chars]
        else:
            return raw_text[:max_chars]

    except Exception as e:
        return f"无法提取内容: {e}"


def get_ai_analysis(
    engine_choice: str,
    config: Dict[str, Any],
    filename_info: str,
    categories: List[str],
    online_search_enabled: bool,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call AI model to analyze a book and get categorization suggestions.

    Args:
        engine_choice: AI engine selection
        config: Configuration dict
        filename_info: Filename information string
        categories: Available category directory list
        online_search_enabled: Whether to enable online search
        metadata: Book metadata

    Returns:
        Dict containing AI analysis results
    """
    deps = _get_deps()
    search_book_online = deps["search_book_online"]

    engine_config = _get_engine_config(config, engine_choice)
    if not engine_config:
        return {"error": f"未找到引擎配置: {engine_choice}。请先在设置中配置该模型。"}

    search_result = ""
    if online_search_enabled:
        search_result = search_book_online(filename_info)

    prompt = get_common_prompt(
        filename_info, categories, search_context=search_result, metadata=metadata
    )

    try:
        return dispatch_ai_request(engine_choice, config, prompt, json_mode=True)
    except Exception as e:
        return {"error": f"API 调用失败: {e}"}


def get_unified_analysis(
    engine_choice: str,
    config: Dict[str, Any],
    filename: str,
    file_content: str,
    internal_metadata: Dict[str, Any],
    user_metadata: Optional[Dict[str, Any]],
    categories: List[str],
    online_search_enabled: bool,
    metadata_identified: bool = False,
) -> Dict[str, Any]:
    """One-shot AI call: simultaneously perform metadata identification/correction
    and categorization analysis.

    Args:
        engine_choice: AI engine
        config: Configuration
        filename: Filename
        file_content: File core content
        internal_metadata: File internal metadata
        user_metadata: User-provided metadata from UI
        categories: Category directory list
        online_search_enabled: Whether to enable search
        metadata_identified: Whether metadata is locked

    Returns:
        dict: { "metadata": {...}, "summary": "...", "suggestions": [...] }
    """
    deps = _get_deps()
    load_ai_config = deps["load_ai_config"]
    get_historical_transfers = deps["get_historical_transfers"]
    parse_filename = deps["parse_filename"]
    search_book_online = deps["search_book_online"]

    filename_info = parse_filename(filename)

    ai_config = load_ai_config()
    field_rules = ai_config.get("field_extraction_rules", {})
    core_rules = ai_config["core_rules"]["content"]

    # Search context
    search_context = ""
    if online_search_enabled and DDGS:
        query = filename_info
        if user_metadata and user_metadata.get("title"):
            query = f"{user_metadata.get('title')} {user_metadata.get('author', '')}"
        search_context = search_book_online(query)

    # Additional rules
    additional_rules_str = ""
    if ai_config["additional_rules"]["enabled"]:
        enabled_rules = [
            r["content"]
            for r in ai_config["additional_rules"]["rules"]
            if r.get("enabled", True)
        ]
        if enabled_rules:
            additional_rules_str = "\n**附加分类规则**:\n" + "\n".join(
                [f"{i + 1}. {r}" for i, r in enumerate(enabled_rules)]
            )

    # Historical reference
    history_str = ""
    if ai_config["historical_reference"]["enabled"]:
        recent = get_historical_transfers(
            ai_config["historical_reference"]["days_range"]
        )
        if recent:
            history_str = "\n**历史参考**:\n" + "\n".join(
                [f"- {t['filename']} -> {t['destination']}" for t in recent[:5]]
            )

    filename_template = field_rules.get("filename_prompt", "{title} - {author}")
    if "格式" in filename_template or "模板" in filename_template:
        template_match = re.search(r"\{[^}]+\}.*", filename_template)
        if template_match:
            filename_template = template_match.group(0)

    if metadata_identified:
        task_description = """
1. **元数据确认**: 用户已确认元数据，请【严格使用】提供的"用户当前输入的元数据"，**不要**进行任何修改或重新提取。直接将这些元数据原样返回。
2. **分类建议**: 根据确认的元数据和图书内容，将图书归类到给定的【分类目录列表】中。
"""
    else:
        task_description = f"""
1. **元数据完善**: 提取或修正图书的元数据（书名、作者等）。请基于用户提供的元数据进行**完善和规范化**（例如：添加缺失的国别标记、修正错别字、补充缺失信息），而不仅仅是原样保留。
2. **分类建议**: 根据（修正后的）元数据和图书内容，将图书归类到给定的【分类目录列表】中。

# 任务一：元数据提取规则
- 书名: {field_rules.get("title_prompt", "准确的书名")}
- 作者: {field_rules.get("author_prompt", "作者名。外国作者用[国别]标记，中国作者不加标记。多个作者用 & 分隔，格式如：[美] 作者1 & [英] 作者2")}
- 出版社: {field_rules.get("publisher_prompt", "出版社")}
- 丛书: {field_rules.get("series_prompt", "丛书名")}
- 标签: {field_rules.get("tags_prompt", "3-5个标签")}
- 新文件名模板: {filename_template}
"""

    user_meta_label = (
        "**用户当前输入的元数据** (最高优先级, 请原样保留)"
        if metadata_identified
        else "**用户当前输入的元数据** (作为基础参考，请基于此进行完善和规范化)"
    )

    prompt = f"""
你是一个全能的图书整理专家。请根据提供的所有信息，完成以下任务：
{task_description}

# 输入信息
- **文件名**: {filename}
- **文件名解析**: {filename_info}
- {user_meta_label}: {json.dumps(user_metadata, ensure_ascii=False) if user_metadata else "无"}
- **文件内部元数据**: {json.dumps(internal_metadata, ensure_ascii=False)}
- **在线搜索结果**: {search_context}
- **书籍核心内容**:
{file_content}

# 任务二：分类规则
{core_rules}
{additional_rules_str}
{history_str}

# 【分类目录列表】 (必须从中选择):
{json.dumps(categories, ensure_ascii=False, indent=2)}

# 输出格式
请严格返回以下 JSON 格式：
{{
    "metadata": {{
        "title": "书名",
        "author": "作者",
        "publisher": "出版社",
        "series": "丛书",
        "tags": "标签",
        "new_filename": "建议文件名"
    }},
    "summary": "图书简介 (100字以内)",
    "suggestions": ["最匹配路径1", "路径2", ...]
}}
"""

    try:
        result = dispatch_ai_request(engine_choice, config, prompt, json_mode=True)

        # Post-process: normalize author format
        if isinstance(result, dict) and "metadata" in result and "author" in result["metadata"]:
            result["metadata"]["author"] = _normalize_author(result["metadata"]["author"])

        return result

    except Exception as e:
        return {"error": f"AI 分析失败: {e}"}


def identify_book_metadata(
    engine_choice: str,
    config: Dict[str, Any],
    filename: str,
    online_search_enabled: bool = False,
    user_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Identify a single book's metadata.

    Args:
        engine_choice: AI engine selection
        config: Configuration dict
        filename: Filename
        online_search_enabled: Whether to enable online search
        user_metadata: User-provided metadata

    Returns:
        Dict containing identified metadata
    """
    deps = _get_deps()
    load_ai_config = deps["load_ai_config"]
    parse_filename = deps["parse_filename"]
    extract_metadata = deps["extract_metadata"]
    search_book_online = deps["search_book_online"]
    get_content_search_config = deps["get_content_search_config"]

    file_path = resolve_file_path(filename, config)

    if not file_path or not os.path.exists(file_path):
        return {"error": "文件不存在"}

    metadata = extract_metadata(file_path)

    # [OFFLINE MODE HANDLING]
    if engine_choice == "offline":
        return offline_identify_metadata(filename, user_metadata, metadata)

    # [ONLINE LOGIC]
    try:
        ctrl_config = get_content_search_config()

        if online_search_enabled:
            content_max_chars = int(ctrl_config.get("search_mode_chars", 800))
        else:
            content_max_chars = int(ctrl_config.get("standard_mode_chars", 1500))
    except Exception:
        content_max_chars = 800 if online_search_enabled else 1500

    core_content = extract_core_content(
        file_path, max_chars=content_max_chars, strategy="adaptive"
    )
    filename_info = parse_filename(filename)

    ai_config = load_ai_config()
    field_rules = ai_config.get("field_extraction_rules", {})

    search_context = ""
    if online_search_enabled and DDGS:
        query = filename_info
        if user_metadata and user_metadata.get("title"):
            query = f"{user_metadata.get('title')} {user_metadata.get('author', '')}"
        search_context = search_book_online(query)

    prompt = f"""
你是一个专业的图书信息提取助手。请根据提供的文件信息、元数据和内容片段，提取图书的关键信息。

# 文件信息
文件名: {filename}
解析信息: {filename_info}

# 用户提供的元数据 (最高优先级，请基于此进行完善)
{json.dumps(user_metadata, ensure_ascii=False) if user_metadata else "无"}

# 内部元数据
{json.dumps(metadata, ensure_ascii=False)}

# 在线搜索信息
{search_context}

# 书籍核心内容片段
{core_content}

# 提取要求
1. 书名: {field_rules.get("title_prompt", "提取准确的书名")}
2. 作者: {field_rules.get("author_prompt", "提取准确的作者名")}
3. 出版社: {field_rules.get("publisher_prompt", "提取出版社")}
4. 标签: {field_rules.get("tags_prompt", "提取3-5个标签")}
5. 丛书: {field_rules.get("series_prompt", "提取丛书名")}
6. 文件名: {field_rules.get("filename_prompt", "生成标准文件名")}

# 输出格式
请严格按照以下JSON格式返回：
{{
    "title": "书名",
    "author": "作者",
    "publisher": "出版社",
    "tags": "标签1, 标签2",
    "series": "丛书名",
    "new_filename": "建议的新文件名"
}}
"""

    try:
        result = dispatch_ai_request(engine_choice, config, prompt, json_mode=True)

        # Post-process: normalize author and filename
        normalize_identify_result(result)

        return result

    except Exception as e:
        # AI identification failed, auto-degrade to local identification
        logger.warning("AI 识别失败 (%s)，自动降级到本地识别", type(e).__name__)
        return offline_identify_with_warning(filename, user_metadata, metadata, e)


def optimize_additional_rules_with_ai(
    engine_choice: str,
    config: Dict[str, Any],
    existing_rules: Optional[List[Dict[str, Any]]] = None,
    rule_count: int = 7,
) -> List[str]:
    """Use AI to optimize additional rules.

    Args:
        engine_choice: AI engine selection
        config: Configuration dict
        existing_rules: Existing rules to optimize
        rule_count: Number of rules to generate

    Returns:
        List of optimized rule strings
    """
    deps = _get_deps()
    get_historical_transfers = deps["get_historical_transfers"]

    historical_data = get_historical_transfers(30)

    # [OFFLINE MODE HANDLING]
    if engine_choice == "offline":
        print("⚠️ 离线模式：跳过 AI 规则优化")
        return [r.get("content", "") for r in (existing_rules or [])]

    existing_rules_text = ""
    if existing_rules:
        existing_rules_text = "现有附加规则:\n"
        for i, rule in enumerate(existing_rules, 1):
            existing_rules_text += f"{i}. {rule.get('content', '')}\n"

    historical_text = "历史转移记录:\n"
    for transfer in historical_data[:20]:
        historical_text += f"- {transfer['filename']} -> {transfer['destination']}\n"

    prompt = f"""你是图书分类专家。请根据以下历史转移记录分析用户的分类习惯和偏好，生成或优化图书分类的附加规则。

{existing_rules_text}

{historical_text}

要求：
1. 如果有现有规则，优化它们使其更准确、更具体
2. 如果没有规则或规则不足，根据历史数据生成新规则
3. 规则总数必须为{rule_count}条
4. 每条规则应该简洁明确，50字以内
5. 规则应该补充核心规则，关注用户的个性化分类习惯

请以JSON格式返回：
{{"optimized_rules": ["规则1", "规则2", ...]}}
"""

    try:
        result = dispatch_ai_request(engine_choice, config, prompt, json_mode=True)
        if isinstance(result, dict) and "error" not in result:
            return result.get("optimized_rules", [])
        return []
    except Exception as e:
        print(f"❌ AI 优化规则失败 ({type(e).__name__})")
        return []


def get_enhanced_mode_analysis(
    engine_choice: str,
    config: Dict[str, Any],
    filename: str,
    file_content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call AI to generate enhanced mode detailed summary.

    Args:
        engine_choice: AI engine
        config: Configuration
        filename: Filename
        file_content: File content
        metadata: Existing metadata

    Returns:
        dict: { "summary": "...", "title": "...", "author": "...", "category": "..." }
    """
    deps = _get_deps()
    load_ai_config = deps["load_ai_config"]
    get_content_search_config = deps["get_content_search_config"]

    try:
        ai_config = load_ai_config()
        ctrl_config = get_content_search_config()
        summary_word_count = int(ctrl_config.get("summary_max_chars", 500))
        # Ensure a reasonable minimum for enhanced mode
        if summary_word_count < 300:
            summary_word_count = 300

        enhanced_rules = ai_config.get("enhanced_rules", {})
        summary_prompt = enhanced_rules.get(
            "summary_prompt", "图书简介: 对书籍核心内容和主题的概述（200字左右）。"
        )
        details_prompt = enhanced_rules.get(
            "details_prompt",
            "详细要点: 列出书中的关键论点、概念或章节精华。请务必使用数字列表格式，并对每个要点的核心词进行加粗。格式示例：1. **核心观点**: 详细解释...",
        )
        applications_prompt = enhanced_rules.get(
            "applications_prompt",
            "具体应用: 说明书中的知识或方法如何在实际工作或生活中应用。请务必使用数字列表格式，并对每个场景进行加粗。格式示例：1. **工作应用**: 详细说明...",
        )

    except Exception:
        summary_word_count = 500
        summary_prompt = "图书简介: 对书籍核心内容和主题的概述（200字左右）。"
        details_prompt = "详细要点: 列出书中的关键论点、概念或章节精华。请务必使用数字列表格式，并对每个要点的核心词进行加粗。格式示例：1. **核心观点**: 详细解释..."
        applications_prompt = "具体应用: 说明书中的知识或方法如何在实际工作或生活中应用。请务必使用数字列表格式，并对每个场景进行加粗。格式示例：1. **工作应用**: 详细说明..."

    prompt = f"""
请根据以下书籍识别信息和核心内容片段，识别书籍的详细信息。

识别信息："{filename}"
元数据参考：{json.dumps(metadata, ensure_ascii=False) if metadata else "无"}

核心内容片段：
{file_content}

请分析此信息并利用你的知识库，务必提供以下所有信息：
1.  **title**: 准确的书籍标题。
2.  **author**: 书籍的作者。
3.  **category**: 书籍的主要分类 (例如：思维方法、心理学、小说、历史、编程等)。
4.  **summary**: 一段详细的书籍内容摘要，**总字数不少于 {summary_word_count} 字**，且必须包含以下三个部分：
    *   **{summary_prompt}**
    *   **{details_prompt}**
    *   **{applications_prompt}**

请严格按照以下 JSON 格式返回结果，确保所有字段都被填充，请务必使用简体中文进行回答，不要包含任何 markdown 标记（除了summary字段内部的格式）或其它额外解释：
{{
  "title": "书籍标题",
  "author": "作者姓名",
  "category": "书籍分类",
  "summary": "图书简介：...\\n\\n详细要点：\\n1. **要点一**: ...\\n2. **要点二**: ...\\n\\n具体应用：\\n1. **应用一**: ...\\n2. **应用二**: ..."
}}
"""

    return _call_ai_engine(engine_choice, config, prompt)


def get_batch_enhance_analysis(
    engine_choice: str,
    config: Dict[str, Any],
    filename: str,
    file_content: str,
    internal_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Batch enhance: one AI call returns both metadata and enhanced summary.

    Combines identify_book_metadata and get_enhanced_mode_analysis functionality,
    reducing ~30-40% Token consumption.

    Args:
        engine_choice: AI engine selection
        config: Configuration dict
        filename: Filename
        file_content: File core content
        internal_metadata: Metadata extracted from the file

    Returns:
        dict: {
            "metadata": {"title", "author", "publisher", "series", "tags", "new_filename"},
            "summary": "Enhanced summary text"
        }
    """
    deps = _get_deps()
    load_ai_config = deps["load_ai_config"]
    parse_filename = deps["parse_filename"]

    # [OFFLINE MODE HANDLING]
    if engine_choice == "offline":
        return offline_batch_enhance(filename, internal_metadata)

    filename_info = parse_filename(filename)

    # Load AI config
    try:
        ai_config = load_ai_config()
        field_rules = ai_config.get("field_extraction_rules", {})
        get_content_search_config = deps["get_content_search_config"]
        ctrl_config = get_content_search_config()

        # Enhanced summary config
        summary_word_count = int(ctrl_config.get("summary_max_chars", 500))
        if summary_word_count < 300:
            summary_word_count = 300

        enhanced_rules = ai_config.get("enhanced_rules", {})
        summary_prompt = enhanced_rules.get(
            "summary_prompt", "图书简介: 对书籍核心内容和主题的概述（200字左右）。"
        )
        details_prompt = enhanced_rules.get(
            "details_prompt",
            "详细要点: 列出书中的关键论点、概念或章节精华。请务必使用数字列表格式，并对每个要点的核心词进行加粗。格式示例：1. **核心观点**: 详细解释...",
        )
        applications_prompt = enhanced_rules.get(
            "applications_prompt",
            "具体应用: 说明书中的知识或方法如何在实际工作或生活中应用。请务必使用数字列表格式，并对每个场景进行加粗。格式示例：1. **工作应用**: 详细说明...",
        )

    except Exception:
        field_rules = {}
        summary_word_count = 500
        summary_prompt = "图书简介: 对书籍核心内容和主题的概述（200字左右）。"
        details_prompt = "详细要点: 列出书中的关键论点、概念或章节精华。"
        applications_prompt = (
            "具体应用: 说明书中的知识或方法如何在实际工作或生活中应用。"
        )

    # Build merged Prompt
    prompt = f"""你是一个专业的图书信息提取和分析助手。请根据提供的所有信息，一次性完成以下两项任务：

# 任务一：元数据提取
请提取并规范化以下字段：
- 书名: {field_rules.get("title_prompt", "准确的书名")}
- 作者: {field_rules.get("author_prompt", "作者名。外国作者用[国别]标记，中国作者不加标记。")}
- 出版社: {field_rules.get("publisher_prompt", "出版社")}
- 丛书: {field_rules.get("series_prompt", "丛书名")}
- 标签: {field_rules.get("tags_prompt", "3-5个标签")}
- 新文件名: {field_rules.get("filename_prompt", "{{title}} - {{author}}")}

# 任务二：生成增强简介
生成一段详细的书籍内容摘要，**总字数不少于 {summary_word_count} 字**，且必须包含以下三个部分：
1. **{summary_prompt}**
2. **{details_prompt}**
3. **{applications_prompt}**

# 输入信息
- **文件名**: {filename}
- **文件名解析**: {filename_info}
- **文件内部元数据**: {json.dumps(internal_metadata, ensure_ascii=False) if internal_metadata else "无"}
- **书籍核心内容**:
{file_content}

# 输出格式
请严格按照以下 JSON 格式返回，确保所有字段都被填充，使用简体中文：
{{
    "metadata": {{
        "title": "书名",
        "author": "作者",
        "publisher": "出版社",
        "series": "丛书",
        "tags": "标签1, 标签2",
        "new_filename": "建议的新文件名"
    }},
    "summary": "图书简介：...\\n\\n详细要点：\\n1. **要点一**: ...\\n\\n具体应用：\\n1. **应用一**: ..."
}}
"""

    try:
        result = _call_ai_engine(engine_choice, config, prompt, json_mode=True)

        if isinstance(result, dict) and "error" in result:
            return result

        # Post-process: normalize author and filename
        normalize_metadata_fields(result)

        return result

    except Exception as e:
        # AI call failed, auto-degrade to offline logic
        logger.warning("批量增强 AI 失败 (%s)，自动降级到离线模式", type(e).__name__)
        return offline_batch_enhance_fallback(filename, internal_metadata, e)


def get_batch_organize_analysis(
    engine_choice: str,
    config: Dict[str, Any],
    filename: str,
    file_content: str,
    internal_metadata: Optional[Dict[str, Any]],
    categories: List[str],
    enable_enhanced_summary: bool = True,
    enable_online_search: bool = False,
) -> Dict[str, Any]:
    """Batch organize: one AI call returns metadata + directory suggestions + enhanced summary (optional).

    Combines identify_book_metadata, get_ai_analysis, get_enhanced_mode_analysis functionality,
    reducing ~20-30% Token consumption.

    Args:
        engine_choice: AI engine selection
        config: Configuration dict
        filename: Filename
        file_content: File core content
        internal_metadata: Metadata extracted from the file
        categories: Target directory list
        enable_enhanced_summary: Whether to generate enhanced summary
        enable_online_search: Whether to enable online search

    Returns:
        dict: {
            "metadata": {"title", "author", ...},
            "suggestions": ["path1", "path2", ...],
            "summary": "Short summary",
            "enhancedSummary": "Enhanced summary" (only when enable_enhanced_summary=True)
        }
    """
    deps = _get_deps()
    load_ai_config = deps["load_ai_config"]
    get_historical_transfers = deps["get_historical_transfers"]
    parse_filename = deps["parse_filename"]
    search_book_online = deps["search_book_online"]

    # [OFFLINE MODE HANDLING]
    if engine_choice == "offline":
        return offline_batch_organize(
            filename, config, internal_metadata, enable_enhanced_summary
        )

    filename_info = parse_filename(filename)

    # Load AI config
    try:
        ai_config = load_ai_config()
        field_rules = ai_config.get("field_extraction_rules", {})
        get_content_search_config = deps["get_content_search_config"]
        ctrl_config = get_content_search_config()
        core_rules = ai_config.get("core_rules", {}).get("content", "")

        # Summary word count
        summary_max_chars = int(ctrl_config.get("summary_max_chars", 100))

        # Additional rules
        additional_rules_str = ""
        if ai_config.get("additional_rules", {}).get("enabled"):
            enabled_rules = [
                r["content"]
                for r in ai_config["additional_rules"].get("rules", [])
                if r.get("enabled", True)
            ]
            if enabled_rules:
                additional_rules_str = "\n**附加分类规则**:\n" + "\n".join(
                    [f"{i + 1}. {r}" for i, r in enumerate(enabled_rules)]
                )

        # Historical reference
        history_str = ""
        if ai_config.get("historical_reference", {}).get("enabled"):
            recent = get_historical_transfers(
                ai_config["historical_reference"].get("days_range", 30)
            )
            if recent:
                history_str = "\n**历史参考**:\n" + "\n".join(
                    [f"- {t['filename']} -> {t['destination']}" for t in recent[:5]]
                )

        # Enhanced summary config
        enhanced_rules = ai_config.get("enhanced_rules", {})
        enhanced_summary_prompt = enhanced_rules.get(
            "summary_prompt", "图书简介: 对书籍核心内容和主题的概述（200字左右）。"
        )
        enhanced_details_prompt = enhanced_rules.get(
            "details_prompt", "详细要点: 列出书中的关键论点、概念或章节精华。"
        )
        enhanced_applications_prompt = enhanced_rules.get(
            "applications_prompt",
            "具体应用: 说明书中的知识或方法如何在实际工作或生活中应用。",
        )
        enhanced_word_count = int(ctrl_config.get("summary_max_chars", 500))
        if enhanced_word_count < 300:
            enhanced_word_count = 300

    except Exception:
        field_rules = {}
        core_rules = ""
        additional_rules_str = ""
        history_str = ""
        summary_max_chars = 100
        enhanced_word_count = 500
        enhanced_summary_prompt = "图书简介"
        enhanced_details_prompt = "详细要点"
        enhanced_applications_prompt = "具体应用"

    # Online search (optional)
    online_search_context = ""
    if enable_online_search:
        try:
            search_result = search_book_online(filename_info)
            if search_result:
                online_search_context = f"\n**在线搜索结果**:\n{search_result}"
        except Exception as e:
            print(f"联网搜索失败 ({type(e).__name__})")

    # Build enhanced summary task description (optional)
    enhanced_task = ""
    enhanced_output = ""
    if enable_enhanced_summary:
        enhanced_task = f"""
# 任务三：生成增强简介
生成一段详细的书籍内容摘要，**总字数不少于 {enhanced_word_count} 字**，包含：
1. **{enhanced_summary_prompt}**
2. **{enhanced_details_prompt}**
3. **{enhanced_applications_prompt}**
"""
        enhanced_output = ',\n    "enhancedSummary": "图书简介：...\\n\\n详细要点：\\n1. **要点一**: ...\\n\\n具体应用：\\n1. **应用一**: ..."'

    # Build merged Prompt
    prompt = f"""你是一个专业的图书整理专家。请根据提供的所有信息，一次性完成以下任务：

# 任务一：元数据提取
请提取并规范化以下字段：
- 书名: {field_rules.get("title_prompt", "准确的书名")}
- 作者: {field_rules.get("author_prompt", "作者名。外国作者用[国别]标记，中国作者不加标记。")}
- 出版社: {field_rules.get("publisher_prompt", "出版社")}
- 丛书: {field_rules.get("series_prompt", "丛书名")}
- 标签: {field_rules.get("tags_prompt", "3-5个标签")}
- 新文件名: {field_rules.get("filename_prompt", "{{title}} - {{author}}")}

# 任务二：分类建议
根据元数据和图书内容，从【分类目录列表】中选择最匹配的 1-7 个路径，按匹配度排序。

分类核心规则：
{core_rules}
{additional_rules_str}
{history_str}
{online_search_context}

【分类目录列表】（必须从中选择）:
{json.dumps(categories, ensure_ascii=False, indent=2)}
{enhanced_task}
# 输入信息
- **文件名**: {filename}
- **文件名解析**: {filename_info}
- **文件内部元数据**: {json.dumps(internal_metadata, ensure_ascii=False) if internal_metadata else "无"}
- **书籍核心内容**:
{file_content}

# 输出格式
请严格按照以下 JSON 格式返回，使用简体中文：
{{
    "metadata": {{
        "title": "书名",
        "author": "作者",
        "publisher": "出版社",
        "series": "丛书",
        "tags": "标签1, 标签2",
        "new_filename": "建议的新文件名"
    }},
    "summary": "{summary_max_chars}字以内的简介",
    "suggestions": ["最匹配路径1", "路径2", ...]{enhanced_output}
}}
"""

    try:
        result = _call_ai_engine(engine_choice, config, prompt, json_mode=True)

        if isinstance(result, dict) and "error" in result:
            return result

        # Post-process: normalize author and filename
        normalize_metadata_fields(result)

        # Validate suggestions against categories
        if "suggestions" in result:
            result["suggestions"] = [
                s for s in result["suggestions"] if s in categories
            ]

        return result

    except Exception as e:
        # AI call failed, auto-degrade to offline logic
        logger.warning("入库批量 AI 失败 (%s)，自动降级到离线模式", type(e).__name__)
        return offline_batch_organize_fallback(
            filename, config, internal_metadata, enable_enhanced_summary, e
        )
