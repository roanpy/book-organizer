from types import SimpleNamespace

from book_organizer import library_path_repair, sync_manager
from book_organizer.database import KnowledgeCoreDB


def _manager(monkeypatch, tmp_path):
    target = tmp_path / "Books"
    target.mkdir()
    monkeypatch.setattr(
        sync_manager, "load_config", lambda: {"target_dir": str(target)}
    )
    monkeypatch.setattr(
        library_path_repair, "load_config", lambda: {"target_dir": str(target)}
    )
    core = KnowledgeCoreDB(db_dir=str(tmp_path / "data"))
    wrapper = SimpleNamespace(_db=core, db_path=core.db_path)
    monkeypatch.setattr(sync_manager, "get_db", lambda: wrapper)
    manager = sync_manager.DBSyncManager()
    return manager, target, core


def test_sync_does_not_mark_same_name_different_paths_as_duplicates(monkeypatch, tmp_path):
    manager, target, db = _manager(monkeypatch, tmp_path)
    first = target / "A" / "book.epub"
    second = target / "B" / "book.epub"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    db.save_summary(str(first), {"summary": "first"})
    db.save_summary(str(second), {"summary": "second"})

    result = manager.analyze()

    assert result["success"] is True
    assert not any(op["type"] == "DELETE_DUPLICATE" for op in result["operations"])


def test_sync_skips_ambiguous_path_repairs(monkeypatch, tmp_path):
    manager, target, db = _manager(monkeypatch, tmp_path)
    for folder in ("A", "B"):
        path = target / folder / "book.epub"
        path.parent.mkdir()
        path.write_text(folder, encoding="utf-8")
    with db._get_conn() as conn:
        conn.execute(
            """INSERT INTO enhanced_summaries
               (file_path, filename, summary_json) VALUES (?, ?, ?)""",
            ("old/book.epub", "book.epub", "{}"),
        )

    result = manager.analyze()

    assert result["success"] is True
    assert result["operations"] == []


def test_sync_treats_absolute_and_relative_same_path_as_duplicate(monkeypatch, tmp_path):
    manager, target, db = _manager(monkeypatch, tmp_path)
    book = target / "A" / "book.epub"
    book.parent.mkdir()
    book.write_text("book", encoding="utf-8")
    with db._get_conn() as conn:
        conn.execute(
            """INSERT INTO enhanced_summaries
               (file_path, filename, summary_json) VALUES (?, ?, ?)""",
            ("A/book.epub", "book.epub", "{}"),
        )
        conn.execute(
            """INSERT INTO enhanced_summaries
               (file_path, filename, summary_json) VALUES (?, ?, ?)""",
            (str(book), "book.epub", "{}"),
        )

    result = manager.analyze()

    assert sum(op["type"] == "DELETE_DUPLICATE" for op in result["operations"]) == 1


def test_sync_execute_rejects_unmanaged_update_path(monkeypatch, tmp_path):
    manager, target, db = _manager(monkeypatch, tmp_path)
    book = target / "A" / "book.epub"
    book.parent.mkdir()
    book.write_text("book", encoding="utf-8")
    outside = tmp_path / "outside.epub"
    outside.write_text("outside", encoding="utf-8")
    db.save_summary(str(book), {"summary": "summary"})
    with db._get_conn() as conn:
        record_id, original_path = conn.execute(
            "SELECT id, file_path FROM enhanced_summaries"
        ).fetchone()
    monkeypatch.setattr(manager, "backup_db", lambda: None)

    result = manager.execute(
        [
            {
                "type": "UPDATE",
                "record_id": record_id,
                "data": {"new_path": str(outside), "new_filename": outside.name},
            }
        ]
    )

    assert result["success"] is True
    assert result["message"].endswith("Errors: 1")
    with db._get_conn() as conn:
        assert conn.execute(
            "SELECT file_path FROM enhanced_summaries WHERE id=?", (record_id,)
        ).fetchone()[0] == original_path


def test_sync_execute_rejects_deleting_unique_record(monkeypatch, tmp_path):
    manager, target, db = _manager(monkeypatch, tmp_path)
    book = target / "book.epub"
    book.write_text("book", encoding="utf-8")
    db.save_summary(str(book), {"summary": "summary"})
    with db._get_conn() as conn:
        record_id = conn.execute("SELECT id FROM enhanced_summaries").fetchone()[0]
    monkeypatch.setattr(manager, "backup_db", lambda: None)

    result = manager.execute(
        [{"type": "DELETE_DUPLICATE", "record_id": record_id}]
    )

    assert result["success"] is True
    assert result["message"].endswith("Errors: 1")
    with db._get_conn() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM enhanced_summaries WHERE id=?", (record_id,)
        ).fetchone()[0] == 1


def test_sync_execute_preserves_newest_duplicate(monkeypatch, tmp_path):
    manager, target, db = _manager(monkeypatch, tmp_path)
    book = target / "book.epub"
    book.write_text("book", encoding="utf-8")
    with db._get_conn() as conn:
        conn.execute(
            """INSERT INTO enhanced_summaries
               (file_path, filename, summary_json, updated_at) VALUES (?, ?, ?, ?)""",
            ("book.epub", book.name, '{"summary":"old"}', "2026-01-01 00:00:00"),
        )
        conn.execute(
            """INSERT INTO enhanced_summaries
               (file_path, filename, summary_json, updated_at) VALUES (?, ?, ?, ?)""",
            (str(book), book.name, '{"summary":"new"}', "2026-02-01 00:00:00"),
        )
        newest_id = conn.execute(
            "SELECT id FROM enhanced_summaries ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()[0]
    monkeypatch.setattr(manager, "backup_db", lambda: None)

    result = manager.execute(
        [{"type": "DELETE_DUPLICATE", "record_id": newest_id}]
    )

    assert result["message"].endswith("Errors: 1")
    with db._get_conn() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM enhanced_summaries WHERE id=?", (newest_id,)
        ).fetchone()[0] == 1
