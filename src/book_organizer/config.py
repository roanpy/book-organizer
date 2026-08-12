# -*- coding: utf-8 -*-
"""
配置管理模块 - 处理应用程序配置和历史记录

包含：
- 文件路径常量
- 配置加载/保存
- AI 配置管理
- 历史记录管理
"""

import json
import os
import shutil
import tempfile
import threading
from copy import deepcopy
from datetime import datetime, timedelta

# ==============================================================================
# 全局常量
# ==============================================================================

# 使用用户主目录存储配置和历史记录
APP_DIR = os.path.join(os.path.expanduser("~"), ".book_organizer")
if not os.path.exists(APP_DIR):
    os.makedirs(APP_DIR)

CONFIG_FILE = os.path.join(APP_DIR, "book_organizer_config.json")
HISTORY_FILE = os.path.join(APP_DIR, "book_organizer_history.json")
AI_CONFIG_FILE = CONFIG_FILE  # AI config is stored within main config
_config_write_lock = threading.RLock()

SYNC_PREFERENCE_KEYS = [
    "book_extensions",
    "beta_features",
    "display_priority",
    "google_drive",
    "user_preferences",
    "gemini",
    "deepseek",
    "volcengine",
    "ollama",
    "custom_providers",
]

DEFAULT_BOOK_EXTENSIONS = [
    ".epub",
    ".pdf",
    ".mobi",
    ".azw3",
    ".azw",
    ".txt",
    ".md",
    ".markdown",
]

SECRET_PROVIDER_KEYS = ("gemini", "deepseek", "volcengine")
SECRET_FIELD_KEYS = {
    "api_key",
    "api_key_masked",
    "configured",
    "access_token",
    "refresh_token",
    "client_secret",
    "token",
}


def _read_json_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json_file(path, data):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    with _config_write_lock:
        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=directory, delete=False
            ) as f:
                temp_path = f.name
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)


def _resolve_sync_path(config, sync_path=None):
    path = sync_path or config.get("sync", {}).get("path")
    return os.path.expanduser(path) if path else ""


def _sync_sensitive_credentials_enabled(config):
    """Return whether credentials are explicitly allowed to sync to cloud."""
    return bool(config.get("sync", {}).get("sync_sensitive_credentials") is True)


def _strip_sensitive_fields(value):
    """Return a copy safe for cloud preferences."""
    if isinstance(value, dict):
        return {
            key: _strip_sensitive_fields(item)
            for key, item in value.items()
            if key not in SECRET_FIELD_KEYS
        }
    if isinstance(value, list):
        return [_strip_sensitive_fields(item) for item in value]
    return value


def _merge_provider_preferences(existing, incoming):
    """Merge cloud provider prefs while preserving local credentials.

    Older versions wrote api_key into preferences.json. For compatibility, a
    legacy cloud key is imported only when the local provider has no key.
    Future writes strip the key, so this is a one-way migration path.
    """
    if not isinstance(incoming, dict):
        return existing if existing is not None else incoming

    merged = dict(existing or {})
    legacy_key = incoming.get("api_key")
    for key, value in incoming.items():
        if key in SECRET_FIELD_KEYS:
            continue
        merged[key] = value

    if legacy_key and not merged.get("api_key"):
        merged["api_key"] = legacy_key
    return merged


def _merge_custom_provider_preferences(existing, incoming):
    if not isinstance(incoming, dict):
        return existing if existing is not None else incoming

    merged = dict(existing or {})
    for name, provider_config in incoming.items():
        if isinstance(provider_config, dict):
            merged[name] = _merge_provider_preferences(
                merged.get(name, {}), provider_config
            )
        else:
            merged[name] = provider_config
    return merged


def build_synced_secrets(config):
    """Return explicitly synced credential payload.

    This is only written when sync.sync_sensitive_credentials is true.
    """
    secrets = {"schema_version": 1, "providers": {}, "custom_providers": {}}
    for provider in SECRET_PROVIDER_KEYS:
        api_key = (config.get(provider) or {}).get("api_key")
        if api_key:
            secrets["providers"][provider] = {"api_key": api_key}

    custom_providers = config.get("custom_providers") or {}
    if isinstance(custom_providers, dict):
        for name, provider_config in custom_providers.items():
            if isinstance(provider_config, dict) and provider_config.get("api_key"):
                secrets["custom_providers"][name] = {
                    "api_key": provider_config["api_key"]
                }

    secrets["updated_at"] = datetime.now().isoformat()
    return secrets


def _merge_synced_secrets(config, sync_path):
    secrets_file = os.path.join(sync_path, "secrets.json")
    if not os.path.exists(secrets_file):
        return config

    try:
        cloud_secrets = _read_json_file(secrets_file)
    except Exception as e:
        print(f"Failed to load cloud secrets: {e}")
        return config

    providers = cloud_secrets.get("providers", {})
    if isinstance(providers, dict):
        for provider, provider_config in providers.items():
            if provider not in SECRET_PROVIDER_KEYS or not isinstance(
                provider_config, dict
            ):
                continue
            local_provider = dict(config.get(provider, {}))
            if provider_config.get("api_key") and not local_provider.get("api_key"):
                local_provider["api_key"] = provider_config["api_key"]
                config[provider] = local_provider

    custom_providers = cloud_secrets.get("custom_providers", {})
    if isinstance(custom_providers, dict):
        local_custom = dict(config.get("custom_providers", {}))
        for name, provider_config in custom_providers.items():
            if not isinstance(provider_config, dict):
                continue
            local_provider = dict(local_custom.get(name, {}))
            if provider_config.get("api_key") and not local_provider.get("api_key"):
                local_provider["api_key"] = provider_config["api_key"]
                local_custom[name] = local_provider
        config["custom_providers"] = local_custom

    return config


def build_synced_preferences(config):
    """Return the machine-independent preference payload for cloud sync."""
    prefs = {
        key: _strip_sensitive_fields(deepcopy(config.get(key)))
        for key in SYNC_PREFERENCE_KEYS
        if key in config and config.get(key) is not None
    }
    prefs.setdefault("display_priority", config.get("display_priority", "file"))
    prefs["schema_version"] = 2
    prefs["updated_at"] = datetime.now().isoformat()
    return prefs


def merge_synced_config_files(config, sync_path=None, include_sensitive=None):
    """Merge cloud preference and AI config files into a local config copy.

    This intentionally does not merge machine-specific paths such as source_dir,
    target_dir, or data_dir. Sensitive credentials are local-only by default.
    """
    path = _resolve_sync_path(config, sync_path)
    if not path or not os.path.exists(path):
        return config

    prefs_file = os.path.join(path, "preferences.json")
    if os.path.exists(prefs_file):
        try:
            cloud_prefs = _read_json_file(prefs_file)
            for key in SYNC_PREFERENCE_KEYS:
                if key in cloud_prefs:
                    if key in SECRET_PROVIDER_KEYS:
                        config[key] = _merge_provider_preferences(
                            config.get(key, {}), cloud_prefs[key]
                        )
                    elif key == "custom_providers":
                        config[key] = _merge_custom_provider_preferences(
                            config.get(key, {}), cloud_prefs[key]
                        )
                    else:
                        config[key] = _strip_sensitive_fields(cloud_prefs[key])
        except Exception as e:
            print(f"Failed to load cloud preferences: {e}")

    ai_config_file = os.path.join(path, "ai_config.json")
    if os.path.exists(ai_config_file):
        try:
            cloud_ai_config = _read_json_file(ai_config_file)
            if isinstance(cloud_ai_config, dict):
                config["ai_config"] = cloud_ai_config
        except Exception as e:
            print(f"Failed to load cloud AI config: {e}")

    should_include_sensitive = (
        _sync_sensitive_credentials_enabled(config)
        if include_sensitive is None
        else bool(include_sensitive)
    )
    if should_include_sensitive:
        config = _merge_synced_secrets(config, path)

    return config


def save_synced_config_files(config, sync_path=None):
    """Write cloud preference and AI config files."""
    path = _resolve_sync_path(config, sync_path)
    if not path or not os.path.exists(path):
        return False

    prefs_file = os.path.join(path, "preferences.json")
    _write_json_file(prefs_file, build_synced_preferences(config))

    ai_config = config.get("ai_config")
    if ai_config:
        ai_config_file = os.path.join(path, "ai_config.json")
        _write_json_file(ai_config_file, ai_config)

    if _sync_sensitive_credentials_enabled(config):
        secrets_file = os.path.join(path, "secrets.json")
        _write_json_file(secrets_file, build_synced_secrets(config))

    return True


def get_synced_config_status(sync_path):
    """Return existence, size, and latest mtime for synced config files."""
    path = os.path.expanduser(sync_path) if sync_path else ""
    files = [
        os.path.join(path, "preferences.json"),
        os.path.join(path, "ai_config.json"),
    ]
    existing_files = [file_path for file_path in files if os.path.exists(file_path)]
    if not existing_files:
        return {"exists": False, "size": 0, "mtime": 0}
    return {
        "exists": True,
        "size": sum(os.path.getsize(file_path) for file_path in existing_files),
        "mtime": max(os.path.getmtime(file_path) for file_path in existing_files),
    }


# 核心规则默认值
DEFAULT_CORE_RULES = """你是一位知识渊博、逻辑严谨、善于理解深层含义的图书分类专家。你的核心任务是【理解】书本的本质，然后从【给定的分类目录列表】中，挑选出【语义最贴切】的存放位置。

**核心原则：语义匹配 > 字面匹配**
你要深入理解书本的主题、目的和读者群体，然后寻找【分类目录名】的【深层含义】与之一致的路径，而不是仅仅寻找文字上的重叠。

**重要规则**
1. **适宜性规则 (分寸感)**: 警惕过度匹配！一本主题宽泛的系列丛书（例如'核心素养系列'），最适合放在能概括其主题的父目录下（例如 `04_个人修养` 或 `04_学习成长`），而**绝对不应该**被错误地放进一个以**另一本具体书名**命名的子目录下（例如 `不抱怨的世界`）。如果最合适的语义目录是一个父目录，就大胆地推荐这个父目录，不要盲目追求最深层级！
2. **绝对规则**: 你返回的 `suggestions` 列表中的每一个路径，都必须与下面"已有的分类目录列表"中给出的路径【完全一致】。绝对禁止创造或修改任何不存在的路径。
3. **具体性规则**: 只有在"适宜"的前提下，才应选择最具体、最深层的目录。
4. **优先规则**: 如果目录名中包含明确的作者名（如"东野圭吾"）、系列或出版社名（如"理想国"），这通常是强信号，应优先考虑。
5. **诚实原则**: 如果找不到任何一个合适的匹配项，请返回一个空的 `suggestions` 列表。"""


# ==============================================================================
# 配置管理函数
# ==============================================================================

# ==============================================================================
# 配置管理函数
# ==============================================================================


def load_config(merge_cloud=True):
    """加载主配置文件.

    支持 iCloud 同步逻辑:
    1. 始终加载本地 config.json (作为基础,包含路径信息)
    2. 如果开启了 sync.enabled, 尝试加载同步目录下的 preferences.json 并覆盖通用设置
    """
    config = {}

    # 1. 加载本地配置 (Base)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load config file: {e}")
            pass

    # 2. 检查同步设置并加载云端偏好/AI 配置
    sync_config = config.get("sync", {})
    if merge_cloud and sync_config.get("enabled") and sync_config.get("path"):
        sync_path = os.path.expanduser(sync_config["path"])  # 支持 ~ 路径
        config = merge_synced_config_files(config, sync_path)

        if _sync_sensitive_credentials_enabled(config):
            # 加载云端 Google Drive Token
            cloud_token_file = os.path.join(sync_path, "google_drive_token.json")
            local_token_file = os.path.join(APP_DIR, "google_drive_token.json")
            if os.path.exists(cloud_token_file) and not os.path.exists(
                local_token_file
            ):
                try:
                    shutil.copy2(cloud_token_file, local_token_file)
                    print("Synced Google Drive token from cloud")
                except Exception as e:
                    print(f"Failed to sync Google token: {e}")

            # 加载云端 Client Secrets
            cloud_secrets_file = os.path.join(sync_path, "client_secrets.json")
            local_secrets_file = os.path.join(APP_DIR, "client_secrets.json")
            if os.path.exists(cloud_secrets_file) and not os.path.exists(
                local_secrets_file
            ):
                try:
                    shutil.copy2(cloud_secrets_file, local_secrets_file)
                    print("Synced client secrets from cloud")
                except Exception as e:
                    print(f"Failed to sync client secrets: {e}")

    # 配置项迁移：enhanced_summary_dir -> data_dir
    if "enhanced_summary_dir" in config and "data_dir" not in config:
        config["data_dir"] = config.pop("enhanced_summary_dir")
        save_config(config)
    elif "enhanced_summary_dir" in config:
        del config["enhanced_summary_dir"]
        save_config(config)

    # 确保 beta_features 存在且包含所有默认值
    if "beta_features" not in config:
        config["beta_features"] = {}

    beta_defaults = {
        "enable_similar_search": False,
        "enable_metadata_write_epub": False,
        "enable_metadata_write_pdf": False,
        "enable_summary_write_epub": False,
        "enable_summary_write_pdf": False,
        "pdf_export_dir": "",
        "data_priority": "database",  # database | metadata
        "google_drive": {"target_folder_id": "", "auto_upload": False},
        "convert_formats": ["epub", "mobi", "azw", "azw3", "fb2", "lit", "lrf", "pdb"],
        # 本地功能开关 (无需 AI) - 2026-01-20 新增
        "local_categorization": False,  # 基于关键词的本地分类
        "isbn_lookup": False,  # ISBN API 查询
        "local_duplicate_check": False,  # 本地查重（无需 AI）
        "smart_source_organize": False,  # 智能源文件组织
    }

    for key, value in beta_defaults.items():
        if key not in config["beta_features"]:
            config["beta_features"][key] = value

    if not isinstance(config.get("book_extensions"), list):
        config["book_extensions"] = list(DEFAULT_BOOK_EXTENSIONS)

    # 确保 sync 配置存在默认值
    if "sync" not in config:
        config["sync"] = {
            "enabled": False,
            "path": "",
            "sync_sensitive_credentials": False,
        }
    else:
        config["sync"].setdefault("sync_sensitive_credentials", False)

    return config


def save_config(config, sync_cloud=True):
    """保存主配置文件.

    支持 iCloud 同步逻辑:
    1. 始终保存所有配置到本地 config.json (作为备份和离线使用)
    2. 如果开启了 sync.enabled, 将通用配置分离保存到同步目录下的 preferences.json
    """
    # 1. 保存本地配置 (完整副本)
    _write_json_file(CONFIG_FILE, config)

    # 2. 如果开启同步，保存通用偏好到云端
    sync_config = config.get("sync", {})
    if sync_cloud and sync_config.get("enabled") and sync_config.get("path"):
        sync_path = os.path.expanduser(sync_config["path"])  # 支持 ~ 路径
        if os.path.exists(sync_path):  # 确保目录存在
            try:
                save_synced_config_files(config, sync_path)

                if _sync_sensitive_credentials_enabled(config):
                    # 同步 Google Drive Token
                    local_token = os.path.join(APP_DIR, "google_drive_token.json")
                    if os.path.exists(local_token):
                        shutil.copy2(
                            local_token,
                            os.path.join(sync_path, "google_drive_token.json"),
                        )

                    # 同步 Client Secrets
                    local_secrets = os.path.join(APP_DIR, "client_secrets.json")
                    if os.path.exists(local_secrets):
                        shutil.copy2(
                            local_secrets,
                            os.path.join(sync_path, "client_secrets.json"),
                        )

                # 同步去重忽略列表 (Deduplication Ignores)
                local_ignores = os.path.join(APP_DIR, "dedup_ignores.json")
                if os.path.exists(local_ignores):
                    shutil.copy2(
                        local_ignores, os.path.join(sync_path, "dedup_ignores.json")
                    )

            except Exception as e:
                print(f"Failed to save cloud preferences: {e}")


# ==============================================================================
# AI 配置管理
# ==============================================================================


def get_default_ai_config():
    """获取默认 AI 配置"""
    return {
        "core_rules": {"enabled": True, "content": DEFAULT_CORE_RULES},
        "additional_rules": {"enabled": False, "rules": []},
        "historical_reference": {"enabled": False, "days_range": 30},
        "field_extraction_rules": {
            "title_prompt": "请提取完整书名，包含副标题（如有）。",
            "author_prompt": "请提取作者名。如果有多个作者，请为每个作者单独标注国别（如[美]、[英]、[中]等），然后用 & 分隔。例如：'[美] 白德瑞 & 王锐 & [美] 罗伯特S.韦斯特曼'。注意：1) 不要在整个作者列表外再加国别标记；2) 外国人名中的间隔号请统一使用中文间隔号'·'（如：罗伯特·史密斯），不要使用'•'或其他符号。",
            "publisher_prompt": "请提取出版社名称。",
            "tags_prompt": "请提取3-5个最相关的标签，用逗号分隔。",
            "series_prompt": "如果这本书属于某个系列，请提取系列名称，否则留空。",
            "filename_prompt": "请根据提取的信息生成标准文件名，格式为：书名 - 作者。多作者时的示例：'书名 - [美] 作者1 & 作者2 & [英] 作者3'。特别注意：1) 每个作者的国别标记应紧跟在该作者名前；2) 绝对不要在整个作者列表外再加一层国别标记；3) 不要出现 [[美]] 这样的双层括号。",
        },
        "enhanced_rules": {
            "summary_prompt": "图书简介: 对书籍核心内容和主题的概述（200字左右）。",
            "details_prompt": "详细要点: 列出书中的关键论点、概念或章节精华。请务必使用数字列表格式，并对每个要点的核心词进行加粗。格式示例：1. **核心观点**: 详细解释...",
            "applications_prompt": "具体应用: 说明书中的知识或方法如何在实际工作或生活中应用。请务必使用数字列表格式，并对每个场景进行加粗。格式示例：1. **工作应用**: 详细说明...",
        },
        "content_and_search_control": {
            "enabled": True,
            "pdf_max_pages": 10,
            "epub_max_chapters": 10,
            "raw_scan_char_limit": 3000,
            "standard_mode_chars": 1500,
            "search_mode_chars": 800,
            "adaptive_extraction": True,
            "head_chars": 500,
            "tail_chars": 500,
            "search_result_count": 3,
            "summary_max_chars": 100,
        },
        "toc_rules": {
            "organize_existing": {
                "enabled": True,
                "prompt": """请将以下图书目录整理成清晰的层级格式。

要求：
1. 如果原目录已有明确的章节标记（如"第一章"、"Chapter 1"）或使用缩进表示层级，可保留原有格式
2. 如果原目录格式混乱，则使用数字编号格式（如 1. / 1.1 / 1.1.1）
3. 保持原有的层级结构，正确识别章、节、小节关系
4. 删除页码信息
5. 排除非正文内容，如：版权信息、目录、前言、序言、致谢、鸣谢、附录、参考文献、索引等
6. 只保留正式章节内容
7. 确保格式统一、层次清晰

原始目录：
{toc_content}""",
            },
            "extract_from_content": {
                "enabled": False,
                "pages": 10,
                "prompt": """请从以下图书内容中识别并提取目录结构。

要求：
1. 识别章节、小节等层级关系
2. 如果能识别到明确的章节标记（如"第一章"、"Chapter 1"），保留原有格式并用缩进表示层级
3. 如果无法识别明确格式，使用数字编号格式（如 1. / 1.1 / 1.1.1）
4. 只提取正式章节标题，排除：版权页、目录页、前言、序、致谢、附录、参考文献等
5. 不要包含正文内容，只输出目录结构
6. 如果无法识别有效目录，返回"无法识别目录"

图书内容：
{content}""",
            },
        },
    }


def load_ai_config():
    """加载 AI 配置.

    支持 iCloud 同步: 优先读取同步目录下的 ai_config.json
    """
    config = load_config()
    default_ai_config = get_default_ai_config()
    user_ai_config = {}

    # 1. 尝试从同步目录加载
    sync_config = config.get("sync", {})
    loaded_from_sync = False

    if sync_config.get("enabled") and sync_config.get("path"):
        sync_path = os.path.expanduser(sync_config["path"])  # 支持 ~ 路径
        sync_file = os.path.join(sync_path, "ai_config.json")
        if os.path.exists(sync_file):
            try:
                with open(sync_file, "r", encoding="utf-8") as f:
                    user_ai_config = json.load(f)
                    loaded_from_sync = True
            except Exception:
                pass

    # 2. 如果同步失败或未开启，回退到本地配置
    if not loaded_from_sync:
        user_ai_config = config.get("ai_config", {})

    if not user_ai_config:
        return default_ai_config

    # 递归合并默认配置到用户配置（补全缺失的配置项）
    def merge_defaults(user_conf, default_conf):
        for key, value in default_conf.items():
            if key not in user_conf:
                user_conf[key] = value
            elif isinstance(value, dict) and isinstance(user_conf.get(key), dict):
                merge_defaults(user_conf[key], value)

    merge_defaults(user_ai_config, default_ai_config)
    return user_ai_config


def save_ai_config(ai_config):
    """保存 AI 配置.

    支持 iCloud 同步: 优先保存到同步目录下的 ai_config.json, 同时也更新本地 config 以作备份
    """
    config = load_config()

    # 1. 更新本地 config 对象并保存（备份）
    config["ai_config"] = ai_config
    save_config(config)

    # 2. 如果开启同步，保存到云端文件
    sync_config = config.get("sync", {})
    if sync_config.get("enabled") and sync_config.get("path"):
        sync_path = os.path.expanduser(sync_config["path"])  # 支持 ~ 路径
        if os.path.exists(sync_path):
            try:
                sync_file = os.path.join(sync_path, "ai_config.json")
                with open(sync_file, "w", encoding="utf-8") as f:
                    json.dump(ai_config, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"Failed to save cloud AI config: {e}")


def get_content_search_config() -> dict:
    """获取内容与搜索控制配置。

    当 enabled=False 时返回 skip=True 标志，调用方应跳过内容提取和搜索。

    Returns:
        dict: 包含所有内容与搜索控制参数的字典
              - skip: True 表示应跳过内容提取和搜索功能
    """
    # 硬编码默认值
    defaults = {
        "enabled": True,
        "skip": False,
        "pdf_max_pages": 10,
        "epub_max_chapters": 10,
        "raw_scan_char_limit": 3000,
        "standard_mode_chars": 1500,
        "search_mode_chars": 800,
        "adaptive_extraction": True,
        "head_chars": 500,
        "tail_chars": 500,
        "search_result_count": 3,
        "summary_max_chars": 100,
    }

    # 跳过配置：当 enabled=False 时使用
    skip_config = {
        "enabled": False,
        "skip": True,
        "pdf_max_pages": 0,
        "epub_max_chapters": 0,
        "raw_scan_char_limit": 0,
        "standard_mode_chars": 0,
        "search_mode_chars": 0,
        "adaptive_extraction": False,
        "head_chars": 0,
        "tail_chars": 0,
        "search_result_count": 0,
        "summary_max_chars": 100,  # 保留简介字数限制，因为这不影响内容提取
    }

    try:
        ai_config = load_ai_config()
        ctrl_config = ai_config.get("content_and_search_control", {})

        # 如果开关关闭，返回跳过配置
        if not ctrl_config.get("enabled", True):
            return skip_config

        # 否则返回用户配置（合并默认值以确保完整性）
        ctrl_config["skip"] = False
        for key, value in defaults.items():
            if key not in ctrl_config:
                ctrl_config[key] = value

        return ctrl_config
    except Exception:
        return defaults


# ==============================================================================
# 历史记录管理
# ==============================================================================


def load_history():
    """加载历史记录.

    支持 iCloud 同步: 优先读取同步目录下的 history.json
    """
    # 1. 尝试从同步目录加载
    try:
        config = load_config()
        sync_config = config.get("sync", {})
        if sync_config.get("enabled") and sync_config.get("path"):
            sync_path = os.path.expanduser(sync_config["path"])  # 支持 ~ 路径
            sync_file = os.path.join(sync_path, "history.json")
            if os.path.exists(sync_file):
                with open(sync_file, "r", encoding="utf-8") as f:
                    return json.load(f)
    except Exception:
        pass

    # 2. 回退到本地
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_history(history):
    """保存历史记录.

    支持 iCloud 同步:
    1. 始终保存到本地 history.json (备份)
    2. 如果开启同步，也保存到云端 history.json
    """
    # 1. 保存本地
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

    # 2. 保存云端
    try:
        config = load_config()
        sync_config = config.get("sync", {})
        if sync_config.get("enabled") and sync_config.get("path"):
            sync_path = os.path.expanduser(sync_config["path"])  # 支持 ~ 路径
            if os.path.exists(sync_path):
                sync_file = os.path.join(sync_path, "history.json")
                with open(sync_file, "w", encoding="utf-8") as f:
                    json.dump(history, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save cloud history: {e}")


def save_history_item(filename, status, details=None):
    """保存单条历史记录"""
    history = load_history()
    history[filename] = {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "details": details or {},
    }
    save_history(history)


def get_book_status(filename):
    """获取图书处理状态"""
    history = load_history()
    return history.get(filename, {}).get("status", "pending")


def get_historical_transfers(days_range=30):
    """获取历史转移记录用于参考"""
    history = load_history()
    cutoff_date = datetime.now() - timedelta(days=days_range)

    recent_transfers = []
    for filename, record in history.items():
        if record.get("status") == "processed":
            try:
                record_date = datetime.fromisoformat(record["timestamp"])
                if record_date >= cutoff_date:
                    recent_transfers.append(
                        {
                            "filename": filename,
                            "destination": record.get("details", {}).get(
                                "destination", ""
                            ),
                            "timestamp": record["timestamp"],
                        }
                    )
            except Exception:
                pass

    return recent_transfers
