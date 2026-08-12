import copy
import datetime
import json
import os
import shutil
import socket
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from book_organizer import db_fingerprint, optimize_additional_rules_with_ai
from book_organizer.ai_engines.dispatcher import (
    build_litellm_model_options,
    format_ai_error,
)
from book_organizer.config import (
    CONFIG_FILE,
    get_default_ai_config,
    get_synced_config_status,
    load_ai_config,
    load_config,
    merge_synced_config_files,
    save_ai_config,
    save_config,
)
from book_organizer.database import (
    UNIFIED_DB_NAME,
    get_db,
    move_database,
    reset_db_instances,
)
from book_organizer.db_fingerprint import _valid_database, _wal_has_pending_data
from book_organizer.file_ops import (
    get_configured_book_extensions,
    normalize_book_extensions,
)
from book_organizer.gemini_client import configure_genai

from .models import (
    ConfigUpdate,
    ModelRequest,
    OptimizeRulesRequest,
    SyncConfigUpdate,
    SyncValidateRequest,
    TestConnectionRequest,
    TestCustomProviderRequest,
    UserPreferencesUpdate,
)

try:
    import ollama as ollama_client
except ImportError:
    ollama_client = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

router = APIRouter()

DB_FULL_CACHE_FINGERPRINT_MAX_BYTES = (
    db_fingerprint.DB_FULL_CACHE_FINGERPRINT_MAX_BYTES
)
SECRET_PROVIDER_KEYS = ("gemini", "deepseek", "volcengine")


def _compare_database_files(local_path: str, cloud_path: str) -> Dict[str, Any]:
    """Compatibility wrapper around the extracted fingerprint helper.

    Tests and older extension code patch this router-level constant. Keep that
    behavior while the implementation lives in db_fingerprint.py.
    """
    original_limit = db_fingerprint.DB_FULL_CACHE_FINGERPRINT_MAX_BYTES
    db_fingerprint.DB_FULL_CACHE_FINGERPRINT_MAX_BYTES = (
        DB_FULL_CACHE_FINGERPRINT_MAX_BYTES
    )
    try:
        return db_fingerprint._compare_database_files(local_path, cloud_path)
    finally:
        db_fingerprint.DB_FULL_CACHE_FINGERPRINT_MAX_BYTES = original_limit


def _format_time(ts):
    if ts == 0:
        return None
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _mask_secret(value: str) -> str:
    """Return a display-only mask for stored credentials."""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def _is_masked_or_empty_secret(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return not text or text == "****" or "..." in text


def _redact_provider_config(config: Dict[str, Any]) -> Dict[str, Any]:
    public_config = dict(config or {})
    api_key = public_config.pop("api_key", "")
    public_config["configured"] = bool(api_key)
    if api_key:
        public_config["api_key_masked"] = _mask_secret(str(api_key))
    return public_config


def _public_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return configuration safe for the frontend and local API clients."""
    public_config = copy.deepcopy(config)

    for provider in SECRET_PROVIDER_KEYS:
        public_config[provider] = _redact_provider_config(
            public_config.get(provider, {})
        )

    custom_providers = public_config.get("custom_providers", {})
    if isinstance(custom_providers, dict):
        public_config["custom_providers"] = {
            name: _redact_provider_config(provider_config)
            if isinstance(provider_config, dict)
            else provider_config
            for name, provider_config in custom_providers.items()
        }

    return public_config


def _is_clear_provider_request(incoming: Dict[str, Any]) -> bool:
    return (
        "api_key" in incoming
        and not str(incoming.get("api_key") or "").strip()
        and not str(incoming.get("model_name") or "").strip()
    )


def _merge_secret_config(
    existing: Dict[str, Any], incoming: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge model config while preserving stored keys when the UI sends blanks."""
    merged = dict(existing or {})
    clear_secret = _is_clear_provider_request(incoming or {})
    for key, value in (incoming or {}).items():
        if key in {"configured", "api_key_masked"}:
            continue
        if key == "api_key" and _is_masked_or_empty_secret(value):
            if clear_secret:
                merged[key] = ""
            continue
        merged[key] = value
    return merged


def _merge_custom_provider_secrets(
    existing: Dict[str, Any], incoming: Dict[str, Any]
) -> Dict[str, Any]:
    merged = {}
    for name, provider_config in (incoming or {}).items():
        if isinstance(provider_config, dict):
            merged[name] = _merge_secret_config(
                (existing or {}).get(name, {}), provider_config
            )
        else:
            merged[name] = provider_config
    return merged


def _saved_custom_provider(provider: str) -> Dict[str, Any]:
    config = load_config()
    return config.get("custom_providers", {}).get(provider, {})


def _cleanup_sqlite_sidecars(db_path: str) -> None:
    """Remove stale SQLite sidecars when there is no pending WAL data."""
    wal_path = db_path + "-wal"
    shm_path = db_path + "-shm"
    if os.path.exists(wal_path) and os.path.getsize(wal_path) == 0:
        try:
            os.remove(wal_path)
        except OSError:
            pass
    if not _wal_has_pending_data(db_path) and os.path.exists(shm_path):
        try:
            os.remove(shm_path)
        except OSError:
            pass


def _resolve_local_database_path(config: Dict[str, Any]) -> str:
    data_dir = config.get("data_dir")
    if data_dir and os.path.exists(data_dir):
        return os.path.join(data_dir, UNIFIED_DB_NAME)
    local_app_dir = os.path.join(os.path.expanduser("~"), ".book_organizer")
    return os.path.join(local_app_dir, UNIFIED_DB_NAME)


def _checkpoint_database() -> None:
    try:
        db_instance = get_db()
        if db_instance and hasattr(db_instance, "_db"):
            core_db = db_instance._db
            with core_db._get_conn() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            print("[Sync Check] Database checkpoint executed successfully.")
    except Exception as e:
        print(f"[Sync Check] Warning: Database checkpoint failed: {e}")


def _configured_count_roots(config: Dict[str, Any]) -> list[tuple[str, str]]:
    roots: list[tuple[str, str]] = []
    for label, key in (("source", "source_dir"), ("target", "target_dir")):
        value = config.get(key)
        if value:
            roots.append((label, os.path.abspath(os.path.expanduser(value))))
    for value in config.get("library_directories") or []:
        if value:
            roots.append(("library", os.path.abspath(os.path.expanduser(value))))

    deduped: list[tuple[str, str]] = []
    seen = set()
    for label, path in roots:
        if path in seen:
            continue
        seen.add(path)
        deduped.append((label, path))
    return deduped


def _count_extensions(config: Dict[str, Any], extensions: list[str] | None = None):
    tracked = set(
        normalize_book_extensions(
            extensions if extensions is not None else get_configured_book_extensions(config)
        )
    )
    counts = {
        ext: {"total": 0, "source": 0, "target": 0, "library": 0}
        for ext in sorted(tracked)
    }

    for label, root in _configured_count_roots(config):
        if not os.path.isdir(root):
            continue
        for current_root, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for filename in files:
                if filename.startswith(".") or filename.startswith("~$"):
                    continue
                ext = os.path.splitext(filename)[1].lower()
                if ext not in tracked:
                    continue
                counts[ext][label] = counts[ext].get(label, 0) + 1
                counts[ext]["total"] += 1
    return counts



def _consolidate_database_backups(db_path: str) -> None:
    _cleanup_sqlite_sidecars(db_path)
    backup_path = db_path + ".backup"
    legacy_paths = [db_path + ".bak", db_path + ".bak_sync"]
    candidates = [p for p in [backup_path, *legacy_paths] if os.path.exists(p)]
    if candidates and not os.path.exists(backup_path):
        newest = max(candidates, key=os.path.getmtime)
        shutil.copy2(newest, backup_path)
    for legacy in legacy_paths:
        if os.path.exists(legacy):
            try:
                os.remove(legacy)
            except OSError:
                pass


def _backup_database(db_path: str) -> None:
    if not _valid_database(db_path):
        return
    _cleanup_sqlite_sidecars(db_path)
    backup_path = db_path + ".backup"
    shutil.copy2(db_path, backup_path)
    _consolidate_database_backups(db_path)


@router.get("/api/config")
def get_config() -> Dict[str, Any]:
    return _public_config(load_config())


@router.post("/api/book_extensions/counts")
def get_book_extension_counts(extensions: list[str] | None = Body(default=None)):
    config = load_config()
    return {
        "extensions": list(
            normalize_book_extensions(
                extensions if extensions is not None else get_configured_book_extensions(config)
            )
        ),
        "counts": _count_extensions(config, extensions),
    }


@router.post("/api/config")
def update_config(config_update: ConfigUpdate) -> Dict[str, Any]:
    # Ensure DB is initialized/cached with current config before any changes
    get_db()

    current_config = load_config()
    update_data = config_update.model_dump(exclude_unset=True)

    for provider in SECRET_PROVIDER_KEYS:
        if provider in update_data and isinstance(update_data[provider], dict):
            update_data[provider] = _merge_secret_config(
                current_config.get(provider, {}), update_data[provider]
            )

    if "custom_providers" in update_data and isinstance(
        update_data["custom_providers"], dict
    ):
        update_data["custom_providers"] = _merge_custom_provider_secrets(
            current_config.get("custom_providers", {}),
            update_data["custom_providers"],
        )

    if "book_extensions" in update_data:
        update_data["book_extensions"] = list(
            normalize_book_extensions(update_data["book_extensions"])
        )

    # Perform migration if data directory is being updated
    if "data_dir" in update_data:
        new_data_dir = update_data["data_dir"]
        if new_data_dir:  # 只有设置了新路径才迁移
            # 复制数据库到新目录（不删除原文件）
            success, msg = move_database(new_data_dir)
            if not success:
                raise HTTPException(
                    status_code=500, detail=f"Database migration failed: {msg}"
                )

    # Deep merge for nested configs if necessary, but simple update for now
    current_config.update(update_data)
    save_config(current_config)

    return _public_config(current_config)


@router.post("/api/models/{provider}")
def list_models(provider: str, request: ModelRequest) -> Dict[str, Any]:
    try:
        models = []
        if provider == "gemini":
            api_key = request.api_key
            if _is_masked_or_empty_secret(api_key):
                # Try to get from config if not provided
                config = load_config()
                api_key = config.get("gemini", {}).get("api_key")

            if not api_key:
                return {"models": []}  # Cannot list without key

            genai = configure_genai(api_key)
            if not genai:
                return {"error": "Google Generative AI library not installed"}
            models = [
                m.name.replace("models/", "")
                for m in genai.list_models()
                if "generateContent" in m.supported_generation_methods
            ]

        elif provider == "deepseek":
            if not OpenAI:  # type: ignore
                return {"error": "OpenAI library not installed"}
            api_key = request.api_key
            if _is_masked_or_empty_secret(api_key):
                config = load_config()
                api_key = config.get("deepseek", {}).get("api_key")

            if not api_key:
                return {"models": []}

            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")  # type: ignore
            models = [model.id for model in client.models.list().data]

        elif provider == "ollama":
            if not ollama_client:
                return {"error": "Ollama library not installed"}
            url = request.url
            if not url:
                config = load_config()
                url = config.get("ollama", {}).get("url", "http://127.0.0.1:11434")

            client = ollama_client.Client(host=url)
            models_info = client.list()["models"]
            models = [
                m.get("name") or m.get("model")
                for m in models_info
                if m.get("name") or m.get("model")
            ]

        else:
            # Check if it's a custom provider
            config = load_config()
            custom_providers = config.get("custom_providers", {})
            if provider in custom_providers:
                if not OpenAI:
                    return {"error": "OpenAI library not installed"}

                p_config = custom_providers[provider]
                api_key = request.api_key or p_config.get("api_key")
                if _is_masked_or_empty_secret(api_key):
                    api_key = p_config.get("api_key")
                base_url = request.url or p_config.get("base_url")

                if not api_key:
                    return {"models": [], "error": "Missing API Key"}

                # Try OpenAI compatible list
                client = OpenAI(api_key=api_key, base_url=base_url)
                models = [model.id for model in client.models.list().data]

        return {"models": models}
    except Exception as e:
        # Return empty list or error message instead of 500 to avoid breaking UI
        print(f"Error fetching models for {provider}: {e}")
        return {"models": [], "error": format_ai_error(e)}


@router.post("/api/test_connection_v2")
def test_connection_v2(request: TestConnectionRequest) -> Dict[str, Any]:
    try:
        # Reuse logic by calling list_models internally or just copying logic
        # For simplicity, let's copy the core check logic
        models = []
        if request.provider == "gemini":
            api_key = request.api_key
            if _is_masked_or_empty_secret(api_key):
                api_key = load_config().get("gemini", {}).get("api_key")
            if not api_key:
                return {"success": False, "message": "API Key is required"}
            genai = configure_genai(api_key)
            if not genai:
                return {
                    "success": False,
                    "message": "Google Generative AI library not installed",
                }
            models = [
                m.name.replace("models/", "")
                for m in genai.list_models()
                if "generateContent" in m.supported_generation_methods
            ]

        elif request.provider == "deepseek":
            if not OpenAI:  # type: ignore
                return {"success": False, "message": "OpenAI library not installed"}
            api_key = request.api_key
            if _is_masked_or_empty_secret(api_key):
                api_key = load_config().get("deepseek", {}).get("api_key")
            if not api_key:
                return {"success": False, "message": "API Key is required"}
            client = OpenAI(
                api_key=api_key, base_url="https://api.deepseek.com/v1"
            )  # type: ignore
            models = [model.id for model in client.models.list().data]

        elif request.provider == "ollama":
            if not ollama_client:
                return {"success": False, "message": "Ollama library not installed"}
            url = request.url if request.url else "http://127.0.0.1:11434"
            client = ollama_client.Client(host=url)
            models_info = client.list()["models"]
            models = [
                m.get("name") or m.get("model")
                for m in models_info
                if m.get("name") or m.get("model")
            ]

        return {
            "success": True,
            "message": f"Successfully connected! Found {len(models)} models.",
            "models": models,
        }
    except Exception as e:
        return {"success": False, "message": format_ai_error(e)}


@router.post("/api/test_custom_provider")
def test_custom_provider(request: TestCustomProviderRequest) -> Dict[str, Any]:
    """测试自定义 Provider 连接"""
    try:
        import litellm

        api_key = request.api_key
        base_url = request.base_url
        saved_provider = _saved_custom_provider(request.provider)
        if _is_masked_or_empty_secret(api_key):
            api_key = saved_provider.get("api_key")
        if not base_url:
            base_url = saved_provider.get("base_url")

        engine_config = {
            **saved_provider,
            "model_name": request.model_name,
            "api_key": api_key,
            "base_url": base_url,
            "supports_json_mode": request.supports_json_mode,
        }
        model_options = build_litellm_model_options(request.provider, engine_config)

        # 构建调用参数
        call_params = {
            "model": model_options["model"],
            "messages": [
                {
                    "role": "user",
                    "content": "Hi, just testing the connection. Reply with 'OK'.",
                }
            ],
            "api_key": model_options["api_key"],
            "max_tokens": 10,
            "temperature": 0.1,
        }

        if model_options["api_base"]:
            call_params["api_base"] = model_options["api_base"]

        response = litellm.completion(**call_params)
        return {
            "success": True,
            "message": f"连接成功！响应: {response.choices[0].message.content[:50]}...",
        }

    except Exception as e:
        return {"success": False, "message": format_ai_error(e)}


@router.get("/api/ai_config")
def get_ai_config() -> Dict[str, Any]:
    """获取AI配置"""
    ai_config = load_ai_config()
    return ai_config


@router.get("/api/ai_config/default")
def api_get_default_ai_config() -> Dict[str, Any]:
    """获取默认AI配置（用于重置）"""
    return get_default_ai_config()


@router.post("/api/ai_config")
def update_ai_config(ai_config: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """更新AI配置"""
    try:
        save_ai_config(ai_config)
        return {"success": True, "message": "AI配置已更新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/user_preferences")
def get_user_preferences() -> Dict[str, Any]:
    """获取用户界面偏好设置（Enhanced Mode、Model Selection、Web Search、TOC）"""
    config = load_config()
    preferences = config.get("user_preferences", {})

    # Provide defaults if not set
    return {
        "enhancedModeEnabled": preferences.get("enhancedModeEnabled", False),
        "selectedEngine": preferences.get("selectedEngine", "gemini"),
        "webSearchEnabled": preferences.get("webSearchEnabled", True),
        "tocEnabled": preferences.get("tocEnabled", False),
    }


@router.post("/api/user_preferences")
def update_user_preferences(prefs: UserPreferencesUpdate) -> Dict[str, Any]:
    """更新用户界面偏好设置"""
    try:
        config = load_config()

        # Get or create user_preferences section
        if "user_preferences" not in config:
            config["user_preferences"] = {}

        # Update only provided fields
        if prefs.enhancedModeEnabled is not None:
            config["user_preferences"]["enhancedModeEnabled"] = (
                prefs.enhancedModeEnabled
            )
        if prefs.selectedEngine is not None:
            config["user_preferences"]["selectedEngine"] = prefs.selectedEngine
        if prefs.webSearchEnabled is not None:
            config["user_preferences"]["webSearchEnabled"] = prefs.webSearchEnabled
        if prefs.tocEnabled is not None:
            config["user_preferences"]["tocEnabled"] = prefs.tocEnabled

        save_config(config)
        print(f"✓ User preferences saved: {config['user_preferences']}")

        return {"success": True, "message": "偏好设置已保存"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/ai_config/optimize_rules")
def optimize_rules(request: OptimizeRulesRequest) -> Dict[str, Any]:
    """使用AI优化附加规则"""
    try:
        config = load_config()
        optimized = optimize_additional_rules_with_ai(
            request.engine, config, request.existing_rules, request.rule_count
        )
        return {"success": True, "optimized_rules": optimized}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/config/sync/validate")
def validate_sync_config(request: SyncValidateRequest):
    """验证同步路径并返回对比信息，让用户选择同步方向"""
    path = os.path.expanduser(request.path) if request.path else ""

    if not path or not os.path.exists(path):
        return {"success": False, "message": f"无效的同步路径: {path}"}

    # [Sync Fix] 强制 Checkpoint 确保 WAL 内容写入 DB 文件。
    # 差异判断使用逻辑指纹，避免启动/打开数据库导致 mtime 变化而误报。
    _checkpoint_database()

    cloud_db_path = os.path.join(path, UNIFIED_DB_NAME)

    # 获取本地数据库路径
    current_config = load_config(merge_cloud=False)
    local_db_path = _resolve_local_database_path(current_config)

    # ===== 数据库对比 =====
    cloud_db_exists = os.path.exists(cloud_db_path)
    local_db_exists = os.path.exists(local_db_path)

    cloud_db_size = os.path.getsize(cloud_db_path) if cloud_db_exists else 0
    local_db_size = os.path.getsize(local_db_path) if local_db_exists else 0

    cloud_db_mtime = os.path.getmtime(cloud_db_path) if cloud_db_exists else 0
    local_db_mtime = os.path.getmtime(local_db_path) if local_db_exists else 0

    cloud_config_status = get_synced_config_status(path)
    local_config_exists = os.path.exists(CONFIG_FILE)
    local_config_size = os.path.getsize(CONFIG_FILE) if local_config_exists else 0
    local_config_mtime = os.path.getmtime(CONFIG_FILE) if local_config_exists else 0

    db_compare = _compare_database_files(local_db_path, cloud_db_path)
    if os.path.abspath(local_db_path) != os.path.abspath(cloud_db_path):
        _cleanup_sqlite_sidecars(cloud_db_path)

    # 判断是否需要用户确认：只看真实数据内容差异，不看 SQLite 文件修改时间。
    needs_confirmation = (
        cloud_db_exists
        and local_db_exists
        and cloud_db_size > 1024
        and local_db_size > 1024
        and db_compare["different"]
    )

    # ===== 最后同步记录 =====
    sync_meta_path = os.path.join(path, "sync_meta.json")
    last_sync = None
    if os.path.exists(sync_meta_path):
        try:
            with open(sync_meta_path, "r", encoding="utf-8") as f:
                last_sync = json.load(f)
        except Exception:
            pass

    return {
        "success": True,
        "needs_confirmation": needs_confirmation,
        "cloud": {
            "exists": cloud_db_exists,
            "size": cloud_db_size,
            "size_mb": round(cloud_db_size / 1024 / 1024, 2),
            "mtime": cloud_db_mtime,
        },
        "local": {
            "exists": local_db_exists,
            "size": local_db_size,
            "size_mb": round(local_db_size / 1024 / 1024, 2),
            "mtime": local_db_mtime,
        },
        "database": {
            "local": {
                "exists": local_db_exists,
                "size_mb": round(local_db_size / 1024 / 1024, 2),
                "mtime": _format_time(local_db_mtime),
            },
            "cloud": {
                "exists": cloud_db_exists,
                "size_mb": round(cloud_db_size / 1024 / 1024, 2),
                "mtime": _format_time(cloud_db_mtime),
            },
            "compare": db_compare,
        },
        "config": {
            "local": {
                "exists": local_config_exists,
                "size_kb": round(local_config_size / 1024, 1),
                "mtime": _format_time(local_config_mtime),
            },
            "cloud": {
                "exists": cloud_config_status["exists"],
                "size_kb": round(cloud_config_status["size"] / 1024, 1),
                "mtime": _format_time(cloud_config_status["mtime"]),
            },
        },
        "last_sync": last_sync,
        "current_device": socket.gethostname(),
    }


@router.post("/api/config/sync")
def update_sync_config(update: SyncConfigUpdate):
    """更新同步配置，并处理数据迁移逻辑"""
    messages = []
    current_config = load_config(merge_cloud=False)

    if update.enabled:
        if update.path:
            update.path = os.path.expanduser(update.path)

        if not update.path or not os.path.exists(update.path):
            return {
                "success": False,
                "message": f"无效的同步路径或目录不存在: {update.path}",
            }

        sync_settings = dict(current_config.get("sync", {}))
        sync_settings.update(
            {
                "enabled": update.enabled,
                "path": update.path,
                "auto_check": update.auto_check,
                "sync_sensitive_credentials": (
                    update.sync_sensitive_credentials
                    if update.sync_sensitive_credentials is not None
                    else sync_settings.get("sync_sensitive_credentials", False)
                ),
            }
        )
        current_config["sync"] = sync_settings

        cloud_db_path = os.path.join(update.path, UNIFIED_DB_NAME)

        source_db_path = _resolve_local_database_path(current_config)
        local_db_path = source_db_path

        cloud_valid = _valid_database(cloud_db_path)
        source_valid = _valid_database(source_db_path)

        # [CRITICAL] 强制合并 WAL 到主数据库，但不再用 mtime 判断同步方向。
        _checkpoint_database()

        # 1. 数据库同步逻辑
        db_action = update.sync_database or "auto"
        db_msg = ""

        if db_action == "skip":
            db_msg = "已跳过数据库同步"
        elif db_action == "upload" and source_valid:
            if cloud_valid:
                _backup_database(cloud_db_path)
            shutil.copy2(source_db_path, cloud_db_path)
            db_msg = (
                f"已将本地数据库上传至云端 "
                f"({os.path.getsize(source_db_path) / 1024 / 1024:.1f}MB)"
            )
        elif db_action == "download" and cloud_valid:
            os.makedirs(os.path.dirname(local_db_path), exist_ok=True)
            if local_db_path != cloud_db_path:
                _backup_database(local_db_path)
                shutil.copy2(cloud_db_path, local_db_path)
            db_msg = (
                f"已从云端下载数据库 "
                f"({os.path.getsize(cloud_db_path) / 1024 / 1024:.1f}MB)"
            )
        elif cloud_valid:
            if update.use_cloud is True:
                os.makedirs(os.path.dirname(local_db_path), exist_ok=True)
                if local_db_path != cloud_db_path:
                    _backup_database(local_db_path)
                    shutil.copy2(cloud_db_path, local_db_path)
                db_msg = (
                    f"已从云端下载数据库 "
                    f"({os.path.getsize(cloud_db_path) / 1024 / 1024:.1f}MB)"
                )
            elif update.use_cloud is False and source_valid:
                _backup_database(cloud_db_path)
                shutil.copy2(source_db_path, cloud_db_path)
                db_msg = (
                    f"已将本地数据库上传至云端 "
                    f"({os.path.getsize(source_db_path) / 1024 / 1024:.1f}MB)"
                )
            elif update.overwrite_cloud and source_valid:
                _backup_database(cloud_db_path)
                shutil.copy2(source_db_path, cloud_db_path)
                db_msg = "已将本地数据同步至云端"
            else:
                # Auto-sync logic
                should_download = not source_valid
                should_upload = False
                db_msg = "已启用同步，数据库将在云端创建"

                if source_valid:
                    local_size = os.path.getsize(source_db_path)
                    cloud_size = os.path.getsize(cloud_db_path)
                    local_mtime = os.path.getmtime(source_db_path)
                    cloud_mtime = os.path.getmtime(cloud_db_path)
                    db_compare = _compare_database_files(source_db_path, cloud_db_path)

                    if not db_compare["different"]:
                        should_download = False
                        should_upload = False
                        db_msg = (
                            "数据库核心内容一致（仅目录缓存存在差异，未按文件时间同步）"
                            if db_compare.get("cache_different")
                            else "数据库内容一致（文件时间可能不同，未同步）"
                        )
                    elif cloud_size < local_size * 0.1 and local_size > 1024 * 1024:
                        should_download = False
                        should_upload = True
                        db_msg = "安全检查: 云端数据库远小于本地，已上传本地数据"
                    elif local_size < cloud_size * 0.1 and cloud_size > 1024 * 1024:
                        should_download = True
                        should_upload = False
                        db_msg = "安全检查: 本地数据库远小于云端，已下载云端数据"
                    elif local_mtime > cloud_mtime + 2.0:
                        should_download = False
                        should_upload = True
                        db_msg = "本地数据较新，已同步上传至云端"
                    elif cloud_mtime > local_mtime + 2.0:
                        should_download = True
                        should_upload = False
                        db_msg = "云端数据较新，已下载同步至本地"
                    else:
                        should_download = False
                        should_upload = False
                        db_msg = "数据库内容不同，未能自动判断方向；请手动选择上传或下载"

                if should_upload:
                    _backup_database(cloud_db_path)
                    shutil.copy2(source_db_path, cloud_db_path)
                elif should_download:
                    os.makedirs(os.path.dirname(local_db_path), exist_ok=True)
                    if local_db_path != cloud_db_path:
                        _backup_database(local_db_path)
                        shutil.copy2(cloud_db_path, local_db_path)
        elif source_valid and db_action != "skip":
            shutil.copy2(source_db_path, cloud_db_path)
            db_msg = "已将本地数据同步至云端"
        else:
            db_msg = "已启用同步，数据库将在云端创建"

        _consolidate_database_backups(local_db_path)
        _consolidate_database_backups(cloud_db_path)

        if db_msg:
            messages.append(db_msg)

        # 2. 配置同步逻辑
        config_action = update.sync_config or "auto"
        config_saved = False

        if config_action == "skip":
            messages.append("已跳过配置同步")
        else:
            cloud_config = get_synced_config_status(update.path)
            local_config_mtime = (
                os.path.getmtime(CONFIG_FILE) if os.path.exists(CONFIG_FILE) else 0
            )

            should_download_config = False
            should_upload_config = False

            if config_action == "download":
                should_download_config = cloud_config["exists"]
            elif config_action == "upload":
                should_upload_config = True
            elif update.use_cloud is True and cloud_config["exists"]:
                should_download_config = True
            elif update.use_cloud is False:
                should_upload_config = True
            elif not cloud_config["exists"]:
                should_upload_config = True
            elif cloud_config["mtime"] > local_config_mtime + 2.0:
                should_download_config = True
            elif local_config_mtime > cloud_config["mtime"] + 2.0:
                should_upload_config = True

            if should_download_config:
                current_config = merge_synced_config_files(
                    current_config,
                    update.path,
                    include_sensitive=sync_settings.get(
                        "sync_sensitive_credentials", False
                    ),
                )
                current_config["sync"] = sync_settings
                save_config(current_config, sync_cloud=False)
                config_saved = True
                messages.append("已从云端下载配置")
            elif should_upload_config:
                current_config["sync"] = sync_settings
                save_config(current_config, sync_cloud=True)
                config_saved = True
                messages.append("已将本地配置上传至云端")
            else:
                messages.append("配置时间接近，未发现需要自动同步的变更")

        if not config_saved:
            save_config(current_config, sync_cloud=False)

        # ===== 保存同步元数据 =====
        try:
            msg = "；".join(messages) if messages else "sync"
            sync_meta = {
                "device": socket.gethostname(),
                "time": datetime.datetime.now().isoformat(),
                "action": msg[:50] if msg else "sync",
            }
            sync_meta_path = os.path.join(update.path, "sync_meta.json")
            with open(sync_meta_path, "w", encoding="utf-8") as f:
                json.dump(sync_meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving sync meta: {e}")
    else:
        sync_settings = dict(current_config.get("sync", {}))
        sync_settings.update(
            {
                "enabled": False,
                "path": update.path or sync_settings.get("path", ""),
                "auto_check": update.auto_check,
                "sync_sensitive_credentials": (
                    update.sync_sensitive_credentials
                    if update.sync_sensitive_credentials is not None
                    else sync_settings.get("sync_sensitive_credentials", False)
                ),
            }
        )
        current_config["sync"] = sync_settings
        save_config(current_config, sync_cloud=False)
        messages.append("已关闭同步")

    # 4. 重置数据库单例，使其在下次访问时使用新路径
    reset_db_instances()

    return {"success": True, "message": "；".join(messages) or "同步设置已更新"}
