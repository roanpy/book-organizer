from pathlib import Path

import fitz
from ebooklib import epub
from fastapi.testclient import TestClient

from server import app

client = TestClient(app, base_url="http://127.0.0.1:18000")


def _patch_book_roots(
    monkeypatch,
    source_dir: Path,
    target_dir: Path | None = None,
    pdf_export_dir: Path | None = None,
):
    config = {
        "source_dir": str(source_dir),
        "target_dir": str(target_dir or source_dir),
        "library_directories": [],
        "beta_features": {"pdf_export_dir": str(pdf_export_dir) if pdf_export_dir else ""},
    }
    monkeypatch.setattr("book_organizer.routers.library.load_config", lambda: config)


def _write_minimal_epub(path: Path):
    book = epub.EpubBook()
    book.set_identifier("preview-test")
    book.set_title("预览测试")
    book.set_language("zh")

    chapter = epub.EpubHtml(title="第一章", file_name="chapter.xhtml", lang="zh")
    chapter.content = """
    <html>
        <body>
            <h1>第一章</h1>
            <script>alert('blocked')</script>
            <p>正文内容</p>
        </body>
    </html>
    """

    book.add_item(chapter)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]
    book.toc = (epub.Link("chapter.xhtml", "第一章", "chapter"),)
    epub.write_epub(str(path), book)


def _write_minimal_pdf(path: Path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "PDF preview test")
    doc.new_page().insert_text((72, 72), "Second page")
    doc.set_toc([[1, "第一章", 1], [2, "第二节", 2]])
    doc.save(path)
    doc.close()


def test_preview_pdf_served_inline(monkeypatch, tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    pdf_path = source_dir / "sample.pdf"
    _write_minimal_pdf(pdf_path)
    _patch_book_roots(monkeypatch, source_dir)

    info_response = client.get("/api/preview/info", params={"path": "sample.pdf"})
    assert info_response.status_code == 200
    info = info_response.json()
    assert info["format"] == "pdf"
    assert info["page_count"] == 2
    assert info["toc"][0]["title"] == "第一章"
    assert info["toc"][0]["page"] == 1

    file_response = client.get("/api/preview/file", params={"path": "sample.pdf"})
    assert file_response.status_code == 200
    assert file_response.headers["content-type"].startswith("application/pdf")
    assert file_response.headers["content-disposition"].startswith("inline")

    page_response = client.get(
        "/api/preview/pdf/page", params={"path": "sample.pdf", "page": 1}
    )
    assert page_response.status_code == 200
    assert page_response.headers["content-type"].startswith("image/png")
    assert page_response.content.startswith(b"\x89PNG")


def test_preview_epub_extracts_sanitized_chapters(monkeypatch, tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    epub_path = source_dir / "sample.epub"
    _write_minimal_epub(epub_path)
    _patch_book_roots(monkeypatch, source_dir)

    response = client.get("/api/preview/epub", params={"path": "sample.epub"})
    assert response.status_code == 200

    data = response.json()
    assert data["format"] == "epub"
    assert data["chapters"]
    assert data["toc"]
    assert data["toc"][0]["title"] == "第一章"
    html = data["chapters"][0]["html"]
    assert "正文内容" in html
    assert "<script" not in html
    assert "alert(" not in html

    manifest_response = client.get(
        "/api/preview/epub/manifest", params={"path": "sample.epub"}
    )
    assert manifest_response.status_code == 200
    manifest = manifest_response.json()
    assert manifest["chapter_count"] == 1
    assert manifest["toc"][0]["target_index"] == 0

    chapter_response = client.get(
        "/api/preview/epub/chapter", params={"path": "sample.epub", "index": 0}
    )
    assert chapter_response.status_code == 200
    assert "正文内容" in chapter_response.json()["html"]


def test_preview_text_and_markdown_are_read_only_and_sanitized(monkeypatch, tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    txt_path = source_dir / "notes.txt"
    txt_path.write_text("第一章 开始\n正文\nChapter 2 More\n", encoding="gb18030")
    md_path = source_dir / "notes.md"
    md_path.write_text("# 标题\n<script>alert(1)</script>\n- item\n", encoding="utf-8")
    _patch_book_roots(monkeypatch, source_dir)

    txt_response = client.get("/api/preview/text", params={"path": "notes.txt"})
    assert txt_response.status_code == 200
    txt_data = txt_response.json()
    assert txt_data["format"] == "txt"
    assert txt_data["encoding"] == "gb18030"
    assert txt_data["toc"][0]["title"] == "第一章 开始"

    md_response = client.get("/api/preview/text", params={"path": "notes.md"})
    assert md_response.status_code == 200
    md_data = md_response.json()
    assert md_data["format"] == "markdown"
    assert md_data["toc"][0]["title"] == "标题"
    assert "<script" not in md_data["html"]
    assert "&lt;script&gt;" in md_data["html"]


def test_preview_resolve_uses_same_name_pdf_in_export_dir(monkeypatch, tmp_path):
    source_dir = tmp_path / "source"
    export_dir = tmp_path / "export"
    source_dir.mkdir()
    export_dir.mkdir()
    mobi_path = source_dir / "sample.mobi"
    mobi_path.write_bytes(b"mobi")
    pdf_path = export_dir / "sample.pdf"
    _write_minimal_pdf(pdf_path)
    _patch_book_roots(monkeypatch, source_dir, pdf_export_dir=export_dir)

    resolve_response = client.get("/api/preview/resolve", params={"path": "sample.mobi"})
    assert resolve_response.status_code == 200
    data = resolve_response.json()
    assert data["action"] == "preview"
    assert data["source"] == "same_name_pdf"
    assert data["preview_path"] == str(pdf_path)

    info_response = client.get(
        "/api/preview/info", params={"path": data["preview_path"]}
    )
    assert info_response.status_code == 200
    assert info_response.json()["format"] == "pdf"


def test_preview_resolve_requests_conversion_for_convertible_format(monkeypatch, tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    mobi_path = source_dir / "sample.mobi"
    mobi_path.write_bytes(b"mobi")
    _patch_book_roots(monkeypatch, source_dir)

    response = client.get("/api/preview/resolve", params={"path": "sample.mobi"})
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "convert"
    assert data["format"] == "mobi"


def test_preview_rejects_paths_outside_configured_roots(monkeypatch, tmp_path):
    source_dir = tmp_path / "source"
    outside_dir = tmp_path / "outside"
    source_dir.mkdir()
    outside_dir.mkdir()
    outside_pdf = outside_dir / "outside.pdf"
    outside_pdf.write_bytes(b"%PDF-1.4\n")
    _patch_book_roots(monkeypatch, source_dir)

    response = client.get("/api/preview/info", params={"path": str(outside_pdf)})
    assert response.status_code == 403
