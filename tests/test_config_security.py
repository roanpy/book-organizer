import os
import sys

import pytest
from fastapi import HTTPException

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from book_organizer.database import move_database
from book_organizer.routers import analysis
from book_organizer.routers import config as config_router
from book_organizer.routers.models import IdentifyMetadataRequest, SyncConfigUpdate
from book_organizer.sync_manager import DBSyncManager


def test_public_config_redacts_api_keys():
    public_config = config_router._public_config(
        {
            "gemini": {"api_key": "example-gemini-secret", "model_name": "gemini"},
            "deepseek": {"api_key": "example-deepseek-secret", "model_name": "chat"},
            "ollama": {"url": "http://127.0.0.1:11434"},
            "custom_providers": {
                "demo": {"api_key": "custom-secret-value", "model_name": "demo"}
            },
        }
    )

    assert "api_key" not in public_config["gemini"]
    assert "api_key" not in public_config["deepseek"]
    assert "api_key" not in public_config["custom_providers"]["demo"]
    assert public_config["gemini"]["configured"] is True
    assert public_config["custom_providers"]["demo"]["configured"] is True
    assert "api_key_masked" in public_config["gemini"]


def test_merge_secret_config_preserves_existing_key_for_blank_or_masked_input():
    existing = {"api_key": "existing-key", "model_name": "old"}

    blank_merged = config_router._merge_secret_config(
        existing, {"api_key": "", "model_name": "new"}
    )
    masked_merged = config_router._merge_secret_config(
        existing, {"api_key": "exis...-key", "model_name": "newer"}
    )

    assert blank_merged["api_key"] == "existing-key"
    assert blank_merged["model_name"] == "new"
    assert masked_merged["api_key"] == "existing-key"
    assert masked_merged["model_name"] == "newer"


def test_merge_secret_config_allows_explicit_clear():
    merged = config_router._merge_secret_config(
        {"api_key": "existing-key", "model_name": "old"},
        {"api_key": "", "model_name": ""},
    )

    assert merged["api_key"] == ""
    assert merged["model_name"] == ""


def test_identify_metadata_hides_provider_details(monkeypatch):
    monkeypatch.setattr(analysis, "load_config", lambda: {})
    monkeypatch.setattr(
        analysis,
        "identify_book_metadata",
        lambda *_args, **_kwargs: {
            "error": "503 provider stack /Users/example/private key=example"
        },
    )

    with pytest.raises(HTTPException) as exc:
        analysis.identify_metadata_endpoint(
            IdentifyMetadataRequest(filename="book.epub", engine="gemini")
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "AI 服务暂时繁忙（503），请稍后重试或切换其他模型。"
    assert "/Users/" not in exc.value.detail


def test_database_move_rejects_linked_destination(monkeypatch, tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    source_db = source / "book_data.db"
    source_db.write_bytes(b"database")
    outside = tmp_path / "outside.db"
    outside.write_bytes(b"keep")
    (destination / "book_data.db").symlink_to(outside)

    class FakeDb:
        db_path = str(source_db)

    monkeypatch.setattr("book_organizer.database.get_db", lambda: FakeDb())

    success, message = move_database(str(destination))

    assert success is False
    assert message == "目标目录中的数据库文件不安全"
    assert outside.read_bytes() == b"keep"


def test_database_backup_rejects_linked_destination(tmp_path):
    db_path = tmp_path / "book_data.db"
    db_path.write_bytes(b"database")
    outside = tmp_path / "outside.db"
    outside.write_bytes(b"keep")
    (tmp_path / "book_data.db.backup").symlink_to(outside)

    manager = DBSyncManager.__new__(DBSyncManager)
    manager.db = type("FakeDb", (), {"db_path": str(db_path)})()

    assert manager.backup_db() is None
    assert outside.read_bytes() == b"keep"


def test_database_backup_failure_preserves_previous_backup(monkeypatch, tmp_path):
    db_path = tmp_path / "book_data.db"
    db_path.write_bytes(b"database")
    backup = tmp_path / "book_data.db.backup"
    backup.write_bytes(b"previous")

    manager = DBSyncManager.__new__(DBSyncManager)
    manager.db = type("FakeDb", (), {"db_path": str(db_path)})()
    monkeypatch.setattr(
        "book_organizer.sync_manager.shutil.copy2",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("failed")),
    )

    assert manager.backup_db() is None
    assert backup.read_bytes() == b"previous"


def test_sync_endpoint_hides_file_operation_details(monkeypatch):
    monkeypatch.setattr(
        config_router,
        "_update_sync_config",
        lambda _update: (_ for _ in ()).throw(
            OSError("/Users/example/private/book_data.db permission denied")
        ),
    )

    with pytest.raises(HTTPException) as exc:
        config_router.update_sync_config(
            SyncConfigUpdate(enabled=True, path="/tmp/example")
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == "同步失败，未完成操作"
    assert "/Users/" not in exc.value.detail
