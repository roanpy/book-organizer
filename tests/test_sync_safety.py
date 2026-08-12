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
