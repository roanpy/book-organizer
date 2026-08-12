from book_organizer.routers import metadata as metadata_router

NEW_SUMMARY = "图书简介：新版\n\n详细要点：\n1. 要点\n\n具体应用：\n1. 应用"


class FakeDB:
    def __init__(self):
        self.summary = "旧简介"

    def get_summary(self, _path):
        return {"summary": self.summary, "metadata": {}}

    def save_summary(self, _path, data):
        self.summary = data["summary"]
        return True


def test_enhanced_summary_response_reflects_embedded_sync(monkeypatch, tmp_path):
    book = tmp_path / "book.epub"
    book.write_text("book", encoding="utf-8")
    db = FakeDB()
    monkeypatch.setattr(
        metadata_router,
        "load_config",
        lambda: {"beta_features": {"data_priority": "database"}},
    )
    monkeypatch.setattr(metadata_router, "resolve_file_path", lambda *_: str(book))
    monkeypatch.setattr(metadata_router, "get_db", lambda: db)
    monkeypatch.setattr(
        metadata_router,
        "extract_metadata",
        lambda _path: {"description": NEW_SUMMARY},
    )

    result = metadata_router.get_existing_enhanced_summary("book.epub")

    assert result["summary"] == NEW_SUMMARY
    assert result["database_summary"] == NEW_SUMMARY
    assert result["embedded_summary"] == NEW_SUMMARY
    assert result["source"] == "metadata"
