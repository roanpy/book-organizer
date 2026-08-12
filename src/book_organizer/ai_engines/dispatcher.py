# -*- coding: utf-8 -*-
"""
Unified AI call dispatcher.

Contains:
- Engine configuration lookup
- LiteLLM and native SDK call paths
- dispatch_ai_request(): single entry point for all AI engine routing
  (replaces the repeated if/elif engine routing that was in each business function)
"""

import json
from typing import Any, Dict, Optional

from ..gemini_client import create_gemini_model

# LiteLLM as primary AI call library (needs tiktoken data at packaging time)
try:
    import litellm

    litellm.suppress_debug_info = True
except ImportError:
    litellm = None

try:
    import ollama
except ImportError:
    ollama = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def _get_engine_config(
    config: Dict[str, Any], engine_choice: str
) -> Optional[Dict[str, Any]]:
    """Get engine configuration, supporting built-in and custom providers.

    Args:
        config: Application config dict
        engine_choice: Engine name

    Returns:
        Engine config dict, or None if not found
    """
    # Built-in engines are at root level
    if engine_choice in ["gemini", "deepseek", "ollama"]:
        return config.get(engine_choice)

    # Check root level first (newer save format)
    if engine_choice in config and isinstance(config[engine_choice], dict):
        return config[engine_choice]

    # Then check custom_providers (compat with older versions)
    if "custom_providers" in config and engine_choice in config.get(
        "custom_providers", {}
    ):
        return config["custom_providers"][engine_choice]

    return None


def _call_ai_engine(
    engine_choice: str, config: Dict[str, Any], prompt: str, json_mode: bool = True
) -> Any:
    """Unified AI call helper - uses LiteLLM.

    Args:
        engine_choice: Engine name
        config: Application config dict
        prompt: Prompt text
        json_mode: Whether to request JSON response format

    Returns:
        Parsed JSON dict (if json_mode) or raw text string
    """
    try:
        # Find engine config: check root level, then custom_providers
        engine_config = None
        if engine_choice in config and isinstance(config[engine_choice], dict):
            engine_config = config[engine_choice]
        elif "custom_providers" in config and engine_choice in config.get(
            "custom_providers", {}
        ):
            engine_config = config["custom_providers"][engine_choice]

        if not engine_config:
            return {
                "error": f"未找到引擎配置: {engine_choice}。请先在设置中配置该模型。"
            }

        # Use LiteLLM for unified call
        if litellm:
            return _call_via_litellm(engine_choice, engine_config, prompt, json_mode)

        # Fallback to native SDK
        return _call_via_native_sdk(engine_choice, engine_config, prompt, json_mode)

    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        # Provide more context for common errors
        if "rate" in error_msg.lower() or "limit" in error_msg.lower():
            detail = f"API 限流: {error_msg}"
        elif (
            "auth" in error_msg.lower()
            or "key" in error_msg.lower()
            or "401" in error_msg
        ):
            detail = f"认证失败: {error_msg}"
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            detail = f"请求超时: {error_msg}"
        elif "connect" in error_msg.lower() or "network" in error_msg.lower():
            detail = f"网络连接错误: {error_msg}"
        else:
            detail = f"{error_type}: {error_msg}"

        print(f"❌ AI Call Error [{error_type}]: {error_msg}")
        return {"error": f"AI 调用失败 - {detail}"}


def _call_via_litellm(
    engine_choice: str,
    engine_config: Dict[str, Any],
    prompt: str,
    json_mode: bool = True,
) -> Any:
    """Call AI via LiteLLM unified interface."""
    model_options = build_litellm_model_options(engine_choice, engine_config)
    model_name = model_options["model"]
    api_key = model_options["api_key"]
    api_base = model_options["api_base"]
    supports_response_format = model_options["supports_response_format"]

    # Build call parameters
    call_params = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "api_key": api_key,
        "api_base": api_base,
        "temperature": 0.3,
    }

    # Only add response_format for supported providers
    if json_mode and supports_response_format:
        call_params["response_format"] = {"type": "json_object"}

    response = litellm.completion(**call_params)

    response_text = response.choices[0].message.content

    if json_mode:
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return json.loads(cleaned.strip(), strict=False)
    else:
        return response_text


def build_litellm_model_options(
    engine_choice: str, engine_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Normalize app engine config into LiteLLM call options.

    LiteLLM requires provider-qualified model names for most non-OpenAI
    models. Keep the rule in one place so validation and real calls behave the
    same way.
    """
    model_name = engine_config.get("model_name", "")
    supports_response_format = True

    if engine_choice == "gemini":
        provider_type = "gemini"
        api_key = engine_config.get("api_key")
        api_base = None
    elif engine_choice == "deepseek":
        provider_type = "deepseek"
        api_key = engine_config.get("api_key")
        api_base = "https://api.deepseek.com/v1"
    elif engine_choice == "ollama":
        provider_type = "ollama"
        api_key = None
        api_base = engine_config.get("url", "http://127.0.0.1:11434")
    else:
        provider_type = engine_config.get("type", engine_choice)
        api_key = engine_config.get("api_key")
        api_base = engine_config.get("base_url") or engine_config.get("url")
        if provider_type == "custom" and api_base:
            # Most user-entered custom endpoints are OpenAI-compatible proxies.
            provider_type = "openai"
        if "supports_json_mode" in engine_config:
            supports_response_format = engine_config["supports_json_mode"]

    provider_prefix = f"{provider_type}/"
    if model_name and not model_name.startswith(provider_prefix):
        model_name = f"{provider_type}/{model_name}"

    if "volcengine" in model_name.lower() or provider_type == "volcengine":
        supports_response_format = False

    return {
        "model": model_name,
        "api_key": api_key,
        "api_base": api_base,
        "provider_type": provider_type,
        "supports_response_format": supports_response_format,
    }


def _call_via_native_sdk(
    engine_choice: str,
    engine_config: Dict[str, Any],
    prompt: str,
    json_mode: bool = True,
) -> Any:
    """Fallback to native SDK call."""
    response_text = ""

    if engine_choice == "gemini":
        model = create_gemini_model(
            engine_config["api_key"], engine_config["model_name"]
        )
        if model is None:
            return {"error": "Gemini 库未安装"}
        response = model.generate_content(prompt)
        response_text = response.text

    elif engine_choice == "deepseek":
        if not OpenAI:
            return {"error": "OpenAI 库未安装"}
        client = OpenAI(
            api_key=engine_config["api_key"], base_url="https://api.deepseek.com/v1"
        )
        response = client.chat.completions.create(
            model=engine_config["model_name"],
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} if json_mode else None,
        )
        response_text = response.choices[0].message.content

    elif engine_choice == "ollama":
        if not ollama:
            return {"error": "Ollama 库未安装"}
        client = ollama.Client(host=engine_config["url"])
        response = client.chat(
            model=engine_config["model_name"],
            messages=[{"role": "user", "content": prompt}],
            format="json" if json_mode else None,
        )
        response_text = response["message"]["content"]

    if json_mode:
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.replace("```json", "", 1)
        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```", "", 1)
        if cleaned.endswith("```"):
            cleaned = cleaned.replace("```", "", 1)
        return json.loads(cleaned.strip(), strict=False)
    else:
        return response_text


def dispatch_ai_request(
    engine_choice: str,
    config: Dict[str, Any],
    prompt: str,
    json_mode: bool = True,
) -> Any:
    """Single entry point for all AI engine routing.

    This replaces the repeated if/elif engine routing that was previously
    duplicated in get_ai_analysis, get_unified_analysis, identify_book_metadata,
    and optimize_additional_rules_with_ai.

    For built-in engines (gemini, deepseek, ollama), this calls them directly
    with their native SDKs for maximum compatibility. For custom providers,
    it delegates to _call_ai_engine which uses LiteLLM.

    Args:
        engine_choice: Engine name (gemini, deepseek, ollama, or custom)
        config: Application config dict
        prompt: Prompt text
        json_mode: Whether to request JSON response format

    Returns:
        Parsed JSON dict (if json_mode) or raw text string.
        On error, returns {"error": "..."} dict.
    """
    engine_config = _get_engine_config(config, engine_choice)
    if not engine_config:
        return {"error": f"未找到引擎配置: {engine_choice}。请先在设置中配置该模型。"}

    try:
        if engine_choice == "gemini":
            model = create_gemini_model(
                engine_config["api_key"], engine_config["model_name"]
            )
            if model is None:
                return {"error": "Gemini 库未安装"}
            response = model.generate_content(prompt)
            if json_mode:
                from .response_parser import parse_json_response

                return parse_json_response(response.text)
            else:
                return response.text.strip()

        elif engine_choice == "deepseek":
            if not OpenAI:
                return {"error": "OpenAI 库未安装"}
            client = OpenAI(
                api_key=engine_config["api_key"], base_url="https://api.deepseek.com/v1"
            )
            response = client.chat.completions.create(
                model=engine_config["model_name"],
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"} if json_mode else None,
            )
            response_text = response.choices[0].message.content
            if json_mode:
                from .response_parser import parse_json_response

                return parse_json_response(response_text)
            else:
                return response_text.strip()

        elif engine_choice == "ollama":
            if not ollama:
                return {"error": "Ollama 库未安装"}
            client = ollama.Client(host=engine_config["url"])
            response = client.chat(
                model=engine_config["model_name"],
                messages=[{"role": "user", "content": prompt}],
                format="json" if json_mode else None,
            )
            response_text = response["message"]["content"]
            if json_mode:
                from .response_parser import parse_json_response

                return parse_json_response(response_text)
            else:
                return response_text.strip()

        else:
            # Custom provider - use unified _call_ai_engine (LiteLLM)
            return _call_ai_engine(engine_choice, config, prompt, json_mode=json_mode)

    except Exception as e:
        return {"error": f"API 调用失败: {e}"}
