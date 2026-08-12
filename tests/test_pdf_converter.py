import os
import stat

from book_organizer import pdf_converter


def test_find_calibre_tool_checks_homebrew_bin(monkeypatch, tmp_path):
    tool_dir = tmp_path / "homebrew" / "bin"
    tool_dir.mkdir(parents=True)
    tool = tool_dir / "ebook-convert"
    tool.write_text("#!/bin/sh\nprintf 'ebook-convert test'\n", encoding="utf-8")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)

    monkeypatch.setattr(pdf_converter.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        pdf_converter,
        "CALIBRE_BIN_DIRS",
        {"Darwin": [str(tool_dir)]},
    )
    monkeypatch.setattr(pdf_converter.shutil, "which", lambda _name: None)

    installed, path = pdf_converter.find_calibre_tool("ebook-convert")

    assert installed is True
    assert path == str(tool)


def test_find_calibre_tool_honors_explicit_env(monkeypatch, tmp_path):
    tool = tmp_path / "ebook-convert"
    tool.write_text("#!/bin/sh\n", encoding="utf-8")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)

    monkeypatch.setenv("BOOK_ORGANIZER_EBOOK_CONVERT", str(tool))
    monkeypatch.setattr(pdf_converter.shutil, "which", lambda _name: None)

    installed, path = pdf_converter.find_calibre_tool("ebook-convert")

    assert installed is True
    assert path == str(tool)


def test_find_calibre_tool_rejects_unknown_tool_name():
    installed, message = pdf_converter.find_calibre_tool("arbitrary-tool")

    assert installed is False
    assert message == "不支持的 Calibre 工具"


def test_convert_to_pdf_rejects_unknown_paper_size(tmp_path):
    source = tmp_path / "book.epub"
    source.write_text("book", encoding="utf-8")

    result = pdf_converter.convert_to_pdf(str(source), paper_size="--help")

    assert result == {"success": False, "message": "不支持的 PDF 纸张尺寸"}


def test_calibre_status_detail_is_backward_compatible(monkeypatch):
    monkeypatch.setattr(
        pdf_converter, "check_calibre_installed", lambda: (True, os.devnull)
    )
    monkeypatch.setattr(
        pdf_converter, "get_calibre_tool_version", lambda _path: "ebook-convert 7.0"
    )

    status = pdf_converter.get_calibre_status_detail()

    assert status["installed"] is True
    assert status["path"] == os.devnull
    assert status["version"] == "ebook-convert 7.0"
    assert ".mobi" in status["convertible_formats"]
