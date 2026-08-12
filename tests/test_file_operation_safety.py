import asyncio

import pytest
from fastapi import HTTPException

from book_organizer import sync_manager
from book_organizer.routers import analysis, book_ops, library
from book_organizer.routers.models import BatchOrganizeSingleRequest, MoveRequest


def test_move_rejects_destination_outside_library(monkeypatch, tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "library"
    source.mkdir()
    target.mkdir()
    book = source / "book.epub"
    book.write_text("book", encoding="utf-8")
    config = {"source_dir": str(source), "target_dir": str(target)}
    monkeypatch.setattr(book_ops, "load_config", lambda: config)
    monkeypatch.setattr(book_ops, "resolve_file_path", lambda *_: str(book))

    with pytest.raises(HTTPException) as exc:
        book_ops.move_book(MoveRequest(filename="book.epub", destination="../out"))

    assert exc.value.status_code == 400
    assert book.exists()


def test_move_does_not_overwrite_existing_book(monkeypatch, tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "library"
    source.mkdir()
    (target / "A").mkdir(parents=True)
    book = source / "book.epub"
    existing = target / "A" / "book.epub"
    book.write_text("new", encoding="utf-8")
    existing.write_text("existing", encoding="utf-8")
    config = {"source_dir": str(source), "target_dir": str(target)}
    monkeypatch.setattr(book_ops, "load_config", lambda: config)
    monkeypatch.setattr(book_ops, "resolve_file_path", lambda *_: str(book))

    with pytest.raises(HTTPException) as exc:
        book_ops.move_book(MoveRequest(filename="book.epub", destination="A"))

    assert exc.value.status_code == 409
    assert existing.read_text(encoding="utf-8") == "existing"
    assert book.exists()


def test_sync_delete_rejects_parent_traversal(monkeypatch, tmp_path):
    target = tmp_path / "library"
    target.mkdir()
    outside = tmp_path / "outside.epub"
    outside.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(
        sync_manager, "load_config", lambda: {"target_dir": str(target)}
    )
    manager = sync_manager.DBSyncManager.__new__(sync_manager.DBSyncManager)

    result = manager.delete_file("../outside.epub")

    assert result["success"] is False
    assert outside.exists()


def test_sync_delete_rejects_missing_library_configuration(monkeypatch, tmp_path):
    book = tmp_path / "book.epub"
    book.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(sync_manager, "load_config", lambda: {"target_dir": ""})
    manager = sync_manager.DBSyncManager.__new__(sync_manager.DBSyncManager)

    result = manager.delete_file(str(book))

    assert result["success"] is False
    assert book.exists()


def test_batch_organize_rejects_book_outside_source(monkeypatch, tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "library"
    source.mkdir()
    target.mkdir()
    book = target / "book.epub"
    book.write_text("book", encoding="utf-8")
    config = {"source_dir": str(source), "target_dir": str(target)}
    monkeypatch.setattr(analysis, "load_config", lambda: config)

    with pytest.raises(HTTPException) as exc:
        analysis.batch_organize_single_endpoint(
            BatchOrganizeSingleRequest(filename=str(book), engine="offline")
        )

    assert exc.value.status_code == 403


def test_cover_endpoints_reject_file_outside_book_roots(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.epub"
    outside.write_text("book", encoding="utf-8")
    monkeypatch.setattr(library, "load_config", lambda: {"source_dir": str(source)})

    assert library.get_cover(str(outside)).status_code == 404
    assert asyncio.run(library.get_book_cover(str(outside))).status_code == 404
