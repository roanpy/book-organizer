import sqlite3

from book_organizer import library_path_repair


def _init_path_tables(db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE books (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            file_path TEXT
        );
        CREATE TABLE enhanced_summaries (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            file_path TEXT
        );
        CREATE TABLE book_tocs (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            file_path TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def test_portable_library_path_stores_target_files_as_relative(monkeypatch, tmp_path):
    target = tmp_path / "Books"
    target.mkdir()
    book = target / "A" / "book.epub"
    book.parent.mkdir()
    book.write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        library_path_repair, "load_config", lambda: {"target_dir": str(target)}
    )

    assert library_path_repair.portable_library_path(str(book)) == "A/book.epub"


def test_portable_library_path_keeps_source_files_absolute(monkeypatch, tmp_path):
    target = tmp_path / "Books"
    source = tmp_path / "Downloads"
    target.mkdir()
    source.mkdir()
    book = source / "book.epub"
    book.write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        library_path_repair, "load_config", lambda: {"target_dir": str(target)}
    )

    assert library_path_repair.portable_library_path(str(book)) == str(book)


def test_repair_stale_library_paths_rewrites_unique_matches(tmp_path):
    target = tmp_path / "Books"
    (target / "01").mkdir(parents=True)
    current_book = target / "01" / "book.epub"
    current_book.write_text("x", encoding="utf-8")
    db_path = tmp_path / "book_data.db"
    _init_path_tables(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO books (filename, file_path) VALUES (?, ?)",
        ("book.epub", "/Old/Machine/Books/01/book.epub"),
    )
    conn.execute(
        "INSERT INTO enhanced_summaries (filename, file_path) VALUES (?, ?)",
        ("book.epub", "/Old/Machine/Books/01/book.epub"),
    )
    conn.execute(
        "INSERT INTO book_tocs (filename, file_path) VALUES (?, ?)",
        ("book.epub", "/Old/Machine/Books/01/book.epub"),
    )
    conn.commit()
    conn.close()

    result = library_path_repair.repair_stale_library_paths(
        db_path=db_path,
        target_dir=target,
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["stats"]["updates"] == 3
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT file_path FROM books").fetchone()[0] == "01/book.epub"
    assert (
        conn.execute("SELECT file_path FROM enhanced_summaries").fetchone()[0]
        == "01/book.epub"
    )
    assert (
        conn.execute("SELECT file_path FROM book_tocs").fetchone()[0] == "01/book.epub"
    )
    conn.close()


def test_repair_stale_library_paths_skips_ambiguous_matches(tmp_path):
    target = tmp_path / "Books"
    (target / "A").mkdir(parents=True)
    (target / "B").mkdir(parents=True)
    (target / "A" / "book.epub").write_text("x", encoding="utf-8")
    (target / "B" / "book.epub").write_text("x", encoding="utf-8")
    db_path = tmp_path / "book_data.db"
    _init_path_tables(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO books (filename, file_path) VALUES (?, ?)",
        ("book.epub", "/Old/Machine/Books/book.epub"),
    )
    conn.commit()
    conn.close()

    result = library_path_repair.repair_stale_library_paths(
        db_path=db_path,
        target_dir=target,
        dry_run=False,
    )

    assert result["stats"]["updates"] == 0
    assert result["stats"]["books_ambiguous"] == 1
    conn = sqlite3.connect(db_path)
    assert (
        conn.execute("SELECT file_path FROM books").fetchone()[0]
        == "/Old/Machine/Books/book.epub"
    )
    conn.close()


def test_scan_library_files_uses_configured_extensions(monkeypatch, tmp_path):
    target = tmp_path / "Books"
    target.mkdir()
    (target / "keep.pdf").write_text("x", encoding="utf-8")
    (target / "skip.docx").write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        library_path_repair,
        "get_configured_book_extensions",
        lambda: (".pdf",),
    )

    files = library_path_repair.scan_library_files(target)

    assert "keep.pdf" in files
    assert "skip.docx" not in files
