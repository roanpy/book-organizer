# -*- coding: utf-8 -*-
"""
搜索模块 - 处理在线搜索功能

包含：
- DuckDuckGo 在线搜索
"""

# 可选库导入
try:
    from ddgs import DDGS
except ImportError:
    DDGS = None


def search_book_online(query: str) -> str:
    """使用 DuckDuckGo 搜索图书相关信息。

    Args:
        query: 搜索查询字符串

    Returns:
        搜索结果的文本摘要，或错误信息
    """
    if not DDGS:
        return "在线搜索功能未启用 (缺少 ddgs 库)。"

    # 从配置读取搜索结果数量（使用新的辅助函数，自动处理 enabled 开关）
    try:
        from .config import get_content_search_config

        ctrl_config = get_content_search_config()

        # 如果内容与搜索控制已禁用，跳过在线搜索
        if ctrl_config.get("skip", False):
            return ""

        max_results = int(ctrl_config.get("search_result_count", 3))
        if max_results <= 0 or max_results > 10:
            max_results = 3
    except Exception:
        max_results = 3

    print(f"  🔎 正在在线搜索: '{query}'...")
    try:
        results = DDGS().text(query=query, max_results=max_results)
        if not results:
            return "未找到相关在线信息。"

        context = "在线搜索到的相关信息如下:\n"
        for i, result in enumerate(results):
            context += (
                f"- 结果{i + 1}: {result.get('title', '')} - {result.get('body', '')}\n"
            )
        return context
    except Exception as e:
        print(f"  ⚠️ 在线搜索时发生错误: {e}")
        return "在线搜索时发生错误。"
