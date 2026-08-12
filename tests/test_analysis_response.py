from book_organizer.routers import analysis
from book_organizer.routers.models import AnalyzeRequest


def test_analyze_full_does_not_expose_raw_provider_result(monkeypatch, tmp_path):
    book = tmp_path / "book.epub"
    book.write_bytes(b"test")
    provider_result = {
        "metadata": {"title": "Safe title"},
        "summary": "Safe summary",
        "suggestions": ["Library"],
        "provider_debug": "provider-internal-detail",
        "traceback": "private-stack-trace",
    }

    monkeypatch.setattr(analysis, "load_config", lambda: {"target_dir": str(tmp_path)})
    monkeypatch.setattr(analysis, "resolve_file_path", lambda *_: str(book))
    monkeypatch.setattr(analysis, "extract_metadata", lambda *_: {})
    monkeypatch.setattr(analysis, "get_content_search_config", lambda: {})
    monkeypatch.setattr(analysis, "extract_core_content", lambda *_, **__: "")
    monkeypatch.setattr(analysis, "get_target_categories", lambda *_: ["Library"])
    monkeypatch.setattr(analysis, "get_unified_analysis", lambda *_, **__: provider_result)

    result = analysis.analyze_full(
        AnalyzeRequest(filename=book.name, engine="test", metadata_identified=False)
    )

    assert result == {
        "metadata": {"title": "Safe title"},
        "summary": "Safe summary",
        "suggestions": ["Library"],
    }
