import json
import os
import sqlite3

import pytest

from book_organizer import config as config_module
from book_organizer.database import UNIFIED_DB_NAME
from book_organizer.routers import config as config_router


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_load_config_merges_cloud_preferences_and_ai_config(monkeypatch, tmp_path):
    local_dir = tmp_path / "local"
    sync_dir = tmp_path / "sync"
    local_dir.mkdir()
    sync_dir.mkdir()

    monkeypatch.setattr(config_module, "APP_DIR", str(local_dir))
    monkeypatch.setattr(
        config_module,
        "CONFIG_FILE",
        str(local_dir / "book_organizer_config.json"),
    )
    monkeypatch.setattr(config_module, "AI_CONFIG_FILE", config_module.CONFIG_FILE)

    write_json(
        local_dir / "book_organizer_config.json",
        {
            "source_dir": "/local/source",
            "target_dir": "/local/target",
            "data_dir": "/local/data",
            "sync": {"enabled": True, "path": str(sync_dir)},
            "beta_features": {"data_priority": "metadata"},
            "ai_config": {"gemini": {"model_name": "local-model"}},
        },
    )
    write_json(
        sync_dir / "preferences.json",
        {
            "source_dir": "/cloud/source",
            "target_dir": "/cloud/target",
            "data_dir": "/cloud/data",
            "beta_features": {"data_priority": "database"},
            "user_preferences": {"tocEnabled": True},
        },
    )
    write_json(
        sync_dir / "ai_config.json",
        {"gemini": {"model_name": "cloud-model"}},
    )

    loaded = config_module.load_config()

    assert loaded["source_dir"] == "/local/source"
    assert loaded["target_dir"] == "/local/target"
    assert loaded["data_dir"] == "/local/data"
    assert loaded["beta_features"]["data_priority"] == "database"
    assert loaded["user_preferences"]["tocEnabled"] is True
    assert loaded["ai_config"]["gemini"]["model_name"] == "cloud-model"


def test_save_config_syncs_only_portable_preferences(monkeypatch, tmp_path):
    local_dir = tmp_path / "local"
    sync_dir = tmp_path / "sync"
    local_dir.mkdir()
    sync_dir.mkdir()

    monkeypatch.setattr(config_module, "APP_DIR", str(local_dir))
    monkeypatch.setattr(
        config_module,
        "CONFIG_FILE",
        str(local_dir / "book_organizer_config.json"),
    )
    monkeypatch.setattr(config_module, "AI_CONFIG_FILE", config_module.CONFIG_FILE)

    config_module.save_config(
        {
            "source_dir": "/local/source",
            "target_dir": "/local/target",
            "data_dir": "/local/data",
            "sync": {"enabled": True, "path": str(sync_dir)},
            "beta_features": {"data_priority": "database"},
            "book_extensions": [".epub", ".pdf", ".txt"],
            "user_preferences": {"enhancedModeEnabled": True},
            "gemini": {"api_key": "secret-gemini", "model_name": "gemini-pro"},
            "deepseek": {"api_key": "secret-deepseek", "model_name": "deepseek-chat"},
            "custom_providers": {
                "demo": {
                    "api_key": "secret-custom",
                    "model_name": "demo-model",
                    "base_url": "https://example.test/v1",
                }
            },
            "ai_config": {"gemini": {"model_name": "saved-model"}},
        }
    )

    prefs = json.loads((sync_dir / "preferences.json").read_text(encoding="utf-8"))
    ai_config = json.loads((sync_dir / "ai_config.json").read_text(encoding="utf-8"))

    assert "source_dir" not in prefs
    assert "target_dir" not in prefs
    assert "data_dir" not in prefs
    assert prefs["beta_features"]["data_priority"] == "database"
    assert prefs["book_extensions"] == [".epub", ".pdf", ".txt"]
    assert prefs["user_preferences"]["enhancedModeEnabled"] is True
    assert prefs["gemini"]["model_name"] == "gemini-pro"
    assert "api_key" not in prefs["gemini"]
    assert "api_key" not in prefs["deepseek"]
    assert "api_key" not in prefs["custom_providers"]["demo"]
    assert not (sync_dir / "secrets.json").exists()
    assert ai_config["gemini"]["model_name"] == "saved-model"


def test_save_config_syncs_secrets_only_when_enabled(monkeypatch, tmp_path):
    local_dir = tmp_path / "local"
    sync_dir = tmp_path / "sync"
    local_dir.mkdir()
    sync_dir.mkdir()

    monkeypatch.setattr(config_module, "APP_DIR", str(local_dir))
    monkeypatch.setattr(
        config_module,
        "CONFIG_FILE",
        str(local_dir / "book_organizer_config.json"),
    )
    monkeypatch.setattr(config_module, "AI_CONFIG_FILE", config_module.CONFIG_FILE)

    config_module.save_config(
        {
            "sync": {
                "enabled": True,
                "path": str(sync_dir),
                "sync_sensitive_credentials": True,
            },
            "gemini": {"api_key": "secret-gemini", "model_name": "gemini-pro"},
            "custom_providers": {
                "demo": {"api_key": "secret-custom", "model_name": "demo-model"}
            },
        }
    )

    prefs = json.loads((sync_dir / "preferences.json").read_text(encoding="utf-8"))
    secrets = json.loads((sync_dir / "secrets.json").read_text(encoding="utf-8"))

    assert "api_key" not in prefs["gemini"]
    assert secrets["providers"]["gemini"]["api_key"] == "secret-gemini"
    assert secrets["custom_providers"]["demo"]["api_key"] == "secret-custom"


@pytest.mark.parametrize("filename", ["preferences.json", "ai_config.json", "history.json"])
def test_sync_writes_reject_linked_files(monkeypatch, tmp_path, filename):
    local_dir = tmp_path / "local"
    sync_dir = tmp_path / "sync"
    local_dir.mkdir()
    sync_dir.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text('{"keep": true}', encoding="utf-8")
    (sync_dir / filename).symlink_to(outside)

    monkeypatch.setattr(config_module, "APP_DIR", str(local_dir))
    monkeypatch.setattr(
        config_module,
        "CONFIG_FILE",
        str(local_dir / "book_organizer_config.json"),
    )
    monkeypatch.setattr(config_module, "HISTORY_FILE", str(local_dir / "history.json"))

    config = {
        "sync": {"enabled": True, "path": str(sync_dir)},
        "ai_config": {"gemini": {"model_name": "test"}},
    }
    if filename == "history.json":
        config_module.save_config(config, sync_cloud=False)
        config_module.save_history({"book.epub": {"status": "processed"}})
    else:
        with pytest.raises(ValueError):
            config_module.save_synced_config_files(config, str(sync_dir))

    assert outside.read_text(encoding="utf-8") == '{"keep": true}'


def test_sync_writes_reject_hard_linked_file(tmp_path):
    sync_dir = tmp_path / "sync"
    sync_dir.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text('{"keep": true}', encoding="utf-8")
    os.link(outside, sync_dir / "preferences.json")

    with pytest.raises(ValueError):
        config_module.resolve_regular_file_path(sync_dir, "preferences.json")

    assert outside.read_text(encoding="utf-8") == '{"keep": true}'


def test_synced_preferences_drop_legacy_google_drive_config():
    prefs = config_module.build_synced_preferences(
        {
            "beta_features": {
                "data_priority": "database",
                "google_drive": {"auto_upload": True},
            }
        }
    )

    assert prefs["beta_features"] == {"data_priority": "database"}


def test_load_config_drops_legacy_local_google_drive_config(monkeypatch, tmp_path):
    config_file = tmp_path / "book_organizer_config.json"
    write_json(
        config_file,
        {"beta_features": {"google_drive": {"auto_upload": True}}},
    )
    monkeypatch.setattr(config_module, "CONFIG_FILE", str(config_file))

    loaded = config_module.load_config(merge_cloud=False)

    assert "google_drive" not in loaded["beta_features"]


def test_load_config_imports_legacy_cloud_api_key_once(monkeypatch, tmp_path):
    local_dir = tmp_path / "local"
    sync_dir = tmp_path / "sync"
    local_dir.mkdir()
    sync_dir.mkdir()

    monkeypatch.setattr(config_module, "APP_DIR", str(local_dir))
    monkeypatch.setattr(
        config_module,
        "CONFIG_FILE",
        str(local_dir / "book_organizer_config.json"),
    )
    monkeypatch.setattr(config_module, "AI_CONFIG_FILE", config_module.CONFIG_FILE)

    write_json(
        local_dir / "book_organizer_config.json",
        {
            "sync": {"enabled": True, "path": str(sync_dir)},
            "gemini": {"model_name": "local-model"},
        },
    )
    write_json(
        sync_dir / "preferences.json",
        {
            "gemini": {
                "api_key": "legacy-cloud-key",
                "model_name": "cloud-model",
            }
        },
    )

    loaded = config_module.load_config()

    assert loaded["gemini"]["api_key"] == "legacy-cloud-key"
    assert loaded["gemini"]["model_name"] == "cloud-model"
    synced = config_module.build_synced_preferences(loaded)
    assert "api_key" not in synced["gemini"]


def test_load_config_does_not_overwrite_existing_local_secret(monkeypatch, tmp_path):
    local_dir = tmp_path / "local"
    sync_dir = tmp_path / "sync"
    local_dir.mkdir()
    sync_dir.mkdir()

    monkeypatch.setattr(config_module, "APP_DIR", str(local_dir))
    monkeypatch.setattr(
        config_module,
        "CONFIG_FILE",
        str(local_dir / "book_organizer_config.json"),
    )
    monkeypatch.setattr(config_module, "AI_CONFIG_FILE", config_module.CONFIG_FILE)

    write_json(
        local_dir / "book_organizer_config.json",
        {
            "sync": {"enabled": True, "path": str(sync_dir)},
            "gemini": {"api_key": "local-key", "model_name": "local-model"},
        },
    )
    write_json(
        sync_dir / "preferences.json",
        {
            "gemini": {
                "api_key": "legacy-cloud-key",
                "model_name": "cloud-model",
            }
        },
    )

    loaded = config_module.load_config()

    assert loaded["gemini"]["api_key"] == "local-key"
    assert loaded["gemini"]["model_name"] == "cloud-model"


def test_load_config_merges_synced_book_extensions(monkeypatch, tmp_path):
    local_dir = tmp_path / "local"
    sync_dir = tmp_path / "sync"
    local_dir.mkdir()
    sync_dir.mkdir()

    monkeypatch.setattr(config_module, "APP_DIR", str(local_dir))
    monkeypatch.setattr(
        config_module,
        "CONFIG_FILE",
        str(local_dir / "book_organizer_config.json"),
    )
    monkeypatch.setattr(config_module, "AI_CONFIG_FILE", config_module.CONFIG_FILE)

    write_json(
        local_dir / "book_organizer_config.json",
        {
            "sync": {"enabled": True, "path": str(sync_dir)},
            "book_extensions": [".epub", ".pdf", ".docx"],
        },
    )
    write_json(
        sync_dir / "preferences.json",
        {"book_extensions": [".epub", ".pdf", ".md"]},
    )

    loaded = config_module.load_config()

    assert loaded["book_extensions"] == [".epub", ".pdf", ".md"]


def create_sync_test_db(path, title="same"):
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash TEXT,
            filename TEXT UNIQUE NOT NULL,
            file_path TEXT,
            title TEXT,
            author TEXT,
            publisher TEXT,
            meta_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE book_tocs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            file_path TEXT,
            toc_json TEXT NOT NULL,
            extraction_method TEXT,
            entry_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "INSERT INTO books(filename, title) VALUES (?, ?)",
        ("book.epub", title),
    )
    conn.commit()
    conn.close()


def test_database_compare_ignores_mtime_when_content_matches(tmp_path):
    local_db = tmp_path / "local.db"
    cloud_db = tmp_path / "cloud.db"
    create_sync_test_db(local_db)
    create_sync_test_db(cloud_db)

    newer_time = os.path.getmtime(cloud_db) + 600
    os.utime(local_db, (newer_time, newer_time))

    comparison = config_router._compare_database_files(str(local_db), str(cloud_db))

    assert comparison["same_content"] is True
    assert comparison["different"] is False
    assert comparison["reason"] == "same-logical-content"


def test_database_compare_detects_logical_content_difference(tmp_path):
    local_db = tmp_path / "local.db"
    cloud_db = tmp_path / "cloud.db"
    create_sync_test_db(local_db, title="local")
    create_sync_test_db(cloud_db, title="cloud")

    comparison = config_router._compare_database_files(str(local_db), str(cloud_db))

    assert comparison["same_content"] is False
    assert comparison["different"] is True
    assert comparison["reason"] == "logical-content-different"


def test_database_compare_keeps_primary_exact_when_cache_uses_fast_mode(
    monkeypatch, tmp_path
):
    local_db = tmp_path / "local.db"
    cloud_db = tmp_path / "cloud.db"
    create_sync_test_db(local_db, title="local")
    create_sync_test_db(cloud_db, title="cloud")

    monkeypatch.setattr(config_router, "DB_FULL_CACHE_FINGERPRINT_MAX_BYTES", 1)

    comparison = config_router._compare_database_files(str(local_db), str(cloud_db))

    assert comparison["fingerprint_mode"] == "primary-full/cache-fast"
    assert comparison["same_content"] is False
    assert comparison["different"] is True
    assert comparison["reason"] == "logical-content-different"


def test_database_compare_does_not_prompt_for_cache_only_difference(tmp_path):
    local_db = tmp_path / "local.db"
    cloud_db = tmp_path / "cloud.db"
    create_sync_test_db(local_db)
    create_sync_test_db(cloud_db)

    conn = sqlite3.connect(local_db)
    conn.execute(
        """
        INSERT INTO book_tocs(filename, toc_json, entry_count)
        VALUES (?, ?, ?)
        """,
        ("book.epub", '{"toc": []}', 0),
    )
    conn.commit()
    conn.close()

    comparison = config_router._compare_database_files(str(local_db), str(cloud_db))

    assert comparison["same_content"] is True
    assert comparison["different"] is False
    assert comparison["cache_different"] is True
    assert comparison["reason"] == "same-primary-content-cache-different"


def test_database_backup_consolidates_legacy_suffixes(tmp_path):
    db_path = tmp_path / UNIFIED_DB_NAME
    create_sync_test_db(db_path)
    legacy_backup = tmp_path / f"{UNIFIED_DB_NAME}.bak_sync"
    legacy_backup.write_bytes(b"legacy")

    config_router._backup_database(str(db_path))

    assert (tmp_path / f"{UNIFIED_DB_NAME}.backup").exists()
    assert not (tmp_path / f"{UNIFIED_DB_NAME}.bak").exists()
    assert not legacy_backup.exists()


def test_cleanup_sqlite_sidecars_removes_empty_wal_and_stale_shm(tmp_path):
    db_path = tmp_path / UNIFIED_DB_NAME
    db_path.write_bytes(b"database")
    wal_path = tmp_path / f"{UNIFIED_DB_NAME}-wal"
    shm_path = tmp_path / f"{UNIFIED_DB_NAME}-shm"
    wal_path.write_bytes(b"")
    shm_path.write_bytes(b"stale")

    config_router._cleanup_sqlite_sidecars(str(db_path))

    assert not wal_path.exists()
    assert not shm_path.exists()


def test_cleanup_sqlite_sidecars_keeps_shm_when_wal_has_data(tmp_path):
    db_path = tmp_path / UNIFIED_DB_NAME
    db_path.write_bytes(b"database")
    wal_path = tmp_path / f"{UNIFIED_DB_NAME}-wal"
    shm_path = tmp_path / f"{UNIFIED_DB_NAME}-shm"
    wal_path.write_bytes(b"pending")
    shm_path.write_bytes(b"active")

    config_router._cleanup_sqlite_sidecars(str(db_path))

    assert wal_path.exists()
    assert shm_path.exists()


def test_sync_validate_cleans_cloud_empty_sidecars(monkeypatch, tmp_path):
    local_dir = tmp_path / "local"
    sync_dir = tmp_path / "sync"
    local_dir.mkdir()
    sync_dir.mkdir()

    local_db = local_dir / UNIFIED_DB_NAME
    cloud_db = sync_dir / UNIFIED_DB_NAME
    create_sync_test_db(local_db)
    create_sync_test_db(cloud_db)

    cloud_wal = sync_dir / f"{UNIFIED_DB_NAME}-wal"
    cloud_shm = sync_dir / f"{UNIFIED_DB_NAME}-shm"
    cloud_wal.write_bytes(b"")
    cloud_shm.write_bytes(b"stale")

    local_config = local_dir / "book_organizer_config.json"
    write_json(local_config, {"data_dir": str(local_dir)})

    monkeypatch.setattr(config_router, "CONFIG_FILE", str(local_config))
    monkeypatch.setattr(
        config_router,
        "load_config",
        lambda merge_cloud=True: {"data_dir": str(local_dir)},
    )
    monkeypatch.setattr(config_router, "_checkpoint_database", lambda: None)

    result = config_router.validate_sync_config(
        config_router.SyncValidateRequest(path=str(sync_dir))
    )

    assert result["success"] is True
    assert result["database"]["compare"]["reason"] == "same-logical-content"
    assert not cloud_wal.exists()
    assert not cloud_shm.exists()


def test_sync_validate_rejects_linked_cloud_database(monkeypatch, tmp_path):
    local_dir = tmp_path / "local"
    sync_dir = tmp_path / "sync"
    local_dir.mkdir()
    sync_dir.mkdir()
    outside = tmp_path / "outside.db"
    outside.write_bytes(b"keep")
    (sync_dir / UNIFIED_DB_NAME).symlink_to(outside)

    monkeypatch.setattr(
        config_router,
        "load_config",
        lambda merge_cloud=True: {"data_dir": str(local_dir)},
    )

    result = config_router.validate_sync_config(
        config_router.SyncValidateRequest(path=str(sync_dir))
    )

    assert result == {
        "success": False,
        "message": "同步目录包含不安全的链接文件",
    }
    assert outside.read_bytes() == b"keep"


def test_database_replacement_closes_local_connection_before_copy(
    monkeypatch, tmp_path
):
    source = tmp_path / "cloud.db"
    destination = tmp_path / "local.db"
    source.write_bytes(b"cloud")
    destination.write_bytes(b"local")
    calls = []

    monkeypatch.setattr(config_router, "_valid_database", lambda _path: True)
    monkeypatch.setattr(
        config_router, "_backup_database", lambda _path: calls.append("backup")
    )
    monkeypatch.setattr(
        config_router, "reset_db_instances", lambda: calls.append("close")
    )
    monkeypatch.setattr(
        config_router,
        "_copy_database_file",
        lambda _source, _destination: calls.append("copy"),
    )

    config_router._replace_database_file(
        str(source), str(destination), close_local_connection=True
    )

    assert calls == ["backup", "close", "copy"]
