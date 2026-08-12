import json
import sqlite3

from book_organizer import library_path_repair
from book_organizer.database import DB_SCHEMA_VERSION, UNIFIED_DB_NAME, KnowledgeCoreDB


def test_database_records_current_schema_version(tmp_path):
    db = KnowledgeCoreDB(db_dir=str(tmp_path / "data"))
    with sqlite3.connect(db.db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == DB_SCHEMA_VERSION


def test_database_does_not_downgrade_future_schema_version(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / UNIFIED_DB_NAME
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"PRAGMA user_version = {DB_SCHEMA_VERSION + 1}")

    db = KnowledgeCoreDB(db_dir=str(data_dir))
    with sqlite3.connect(db.db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == DB_SCHEMA_VERSION + 1


def test_same_name_books_keep_separate_summaries_and_tocs(monkeypatch, tmp_path):
    target = tmp_path / "Books"
    first = target / "A" / "book.epub"
    second = target / "B" / "book.epub"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    monkeypatch.setattr(
        library_path_repair, "load_config", lambda: {"target_dir": str(target)}
    )

    db = KnowledgeCoreDB(db_dir=str(tmp_path / "data"))
    assert db.save_summary(str(first), {"summary": "first summary"})
    assert db.save_summary(str(second), {"summary": "second summary"})
    assert db.save_toc(str(first), {"toc": [{"title": "First"}]})
    assert db.save_toc(str(second), {"toc": [{"title": "Second"}]})

    assert db.get_summary(str(first))["summary"] == "first summary"
    assert db.get_summary(str(second))["summary"] == "second summary"
    assert db.get_summary("book.epub") is None
    assert db.get_toc(str(first))["toc"][0]["title"] == "First"
    assert db.get_toc(str(second))["toc"][0]["title"] == "Second"
    assert db.get_toc("book.epub") is None

    conn = sqlite3.connect(db.db_path)
    rows = conn.execute(
        "SELECT filename, file_path FROM books ORDER BY file_path"
    ).fetchall()
    conn.close()
    assert rows == [("book.epub", "A/book.epub"), ("book.epub", "B/book.epub")]


def test_legacy_toc_table_migrates_to_path_identity(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / UNIFIED_DB_NAME
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE book_tocs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            file_path TEXT,
            toc_json TEXT NOT NULL,
            extraction_method TEXT,
            entry_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        "INSERT INTO book_tocs(filename, file_path, toc_json) VALUES (?, ?, ?)",
        ("book.epub", "A/book.epub", json.dumps([{"title": "Legacy"}])),
    )
    conn.commit()
    conn.close()

    db = KnowledgeCoreDB(db_dir=str(data_dir))
    assert db.get_toc("A/book.epub")["toc"][0]["title"] == "Legacy"
    assert db.save_toc("B/book.epub", {"toc": [{"title": "Second"}]})

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT filename, file_path FROM book_tocs ORDER BY file_path"
    ).fetchall()
    conn.close()
    assert rows == [("book.epub", "A/book.epub"), ("book.epub", "B/book.epub")]


def test_legacy_books_table_migrates_to_path_identity_without_changing_ids(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / UNIFIED_DB_NAME
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;
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
        );
        CREATE TABLE chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            title TEXT,
            FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE
        );
        INSERT INTO books(id, filename, file_path) VALUES (7, 'book.epub', 'A/book.epub');
        INSERT INTO chapters(book_id, title) VALUES (7, 'Chapter');
        """
    )
    conn.commit()
    conn.close()

    db = KnowledgeCoreDB(db_dir=str(data_dir))
    second_id = db.add_book("book.epub", "B/book.epub")

    conn = sqlite3.connect(db_path)
    books = conn.execute("SELECT id, file_path FROM books ORDER BY file_path").fetchall()
    chapter = conn.execute("SELECT book_id, title FROM chapters").fetchone()
    conn.close()
    assert books == [(7, "A/book.epub"), (second_id, "B/book.epub")]
    assert chapter == (7, "Chapter")
    assert (data_dir / f"{UNIFIED_DB_NAME}.before_path_identity.backup").exists()
