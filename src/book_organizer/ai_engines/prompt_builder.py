# -*- coding: utf-8 -*-
"""
Prompt building functions for AI analysis.

Contains:
- get_common_prompt(): Standard categorization prompt builder
- Prompt template/format string helpers
"""

import json
from typing import Any, Dict, List, Optional


def _get_deps():
    """Lazy import dependencies to avoid circular references."""
    from ..config import (
        get_content_search_config,
        get_historical_transfers,
        load_ai_config,
    )

    return {
        "load_ai_config": load_ai_config,
        "get_historical_transfers": get_historical_transfers,
        "get_content_search_config": get_content_search_config,
    }


def get_common_prompt(
    filename_info: str,
    categories: List[str],
    search_context: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Build AI analysis prompt.

    Args:
        filename_info: Parsed filename information string
        categories: Available category directory list
        search_context: Online search context string
        metadata: Book metadata dict

    Returns:
        Complete prompt string for AI analysis
    """
    deps = _get_deps()
    load_ai_config = deps["load_ai_config"]
    get_historical_transfers = deps["get_historical_transfers"]

    ai_config = load_ai_config()

    metadata_str = ""
    if metadata:
        metadata_str = f"内部元数据: {json.dumps(metadata, ensure_ascii=False)}"

    prompt_parts = []

    # Core rules
    core_rules = ai_config["core_rules"]["content"]
    prompt_parts.append(core_rules)

    # Additional rules
    if ai_config["additional_rules"]["enabled"]:
        enabled_additional_rules = [
            rule["content"]
            for rule in ai_config["additional_rules"]["rules"]
            if rule.get("enabled", True)
        ]
        if enabled_additional_rules:
            prompt_parts.append("\n**附加规则**")
            for i, rule_content in enumerate(enabled_additional_rules, 1):
                prompt_parts.append(f"{i}. {rule_content}")

    # Historical reference
    historical_context = ""
    if ai_config["historical_reference"]["enabled"]:
        days_range = ai_config["historical_reference"]["days_range"]
        recent_transfers = get_historical_transfers(days_range)
        if recent_transfers:
            historical_context = f"\n\n**历史转移参考** (最近{days_range}天):\n"
            for transfer in recent_transfers[:10]:
                historical_context += (
                    f"- {transfer['filename']} -> {transfer['destination']}\n"
                )
            historical_context += "\n请参考以上历史记录理解用户的分类习惯。"

    # Summary word count limit
    try:
        get_content_search_config = deps["get_content_search_config"]
        ctrl_config = get_content_search_config()
        summary_max_chars = int(ctrl_config.get("summary_max_chars", 100))
    except Exception:
        summary_max_chars = 100

    full_prompt = f"""
{chr(10).join(prompt_parts)}

# 图书文件名信息: {filename_info}
# 文件内部元数据 (非常重要): {metadata_str}
# 在线搜索到的补充信息 (如果提供): {search_context}
{historical_context}
# 【已有的分类目录列表】 (你必须从这个列表中选择): {json.dumps(categories, ensure_ascii=False, indent=2)}

# 任务:
1. **综合分析**: 结合所有信息，给出一份详尽、准确的图书介绍（{summary_max_chars}字以内）。
2. **严格挑选**: 基于你的深层理解和上述所有规则，从"已有的分类目录列表"中，选出最少1个、最多7个最匹配的目录路径，并按匹配度从高到低排序。

# 输出格式:
请严格按照以下JSON格式返回，不要添加任何额外的解释或文字：
{{ "summary": "详尽的图书介绍", "ai_category": "AI判断的图书分类", "suggestions": ["路径1", "路径2", ...] }}
"""
    return full_prompt
