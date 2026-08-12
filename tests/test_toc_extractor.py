import os
import sys

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from book_organizer.database import KnowledgeCoreDB
from book_organizer.routers.analysis import _toc_needs_ai_cleanup
from book_organizer.toc_extractor import (
    extract_toc,
    format_toc_text,
    sanitize_toc_result,
    strip_toc_storage_noise,
)


def test_extract_toc_accepts_max_pages_and_scans_pdf_text(tmp_path):
    fitz = pytest.importorskip("fitz")

    pdf_path = tmp_path / "toc_text.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Contents\nChapter 1 Start ........ 1\nChapter 2 Continue ........ 7\nChapter 3 End ........ 15",
    )
    doc.save(pdf_path)
    doc.close()

    result = extract_toc(str(pdf_path), max_pages=2)

    assert result["success"] is True
    assert result["method"] == "content_scan"
    assert result["entry_count"] >= 3
    assert result["toc"][0]["title"].startswith("Chapter 1")
    assert result["toc"][0]["page"] == 1


def test_toc_database_preserves_ai_text_payload(tmp_path):
    db = KnowledgeCoreDB(db_dir=str(tmp_path))
    file_path = str(tmp_path / "book.epub")

    assert db.save_toc(
        file_path,
        {
            "method": "ai",
            "toc": [],
            "toc_text": "第一章 开始\n第二章 继续",
            "ai_processed": True,
        },
    )

    result = db.get_toc(file_path)

    assert result["success"] is True
    assert result["method"] == "ai"
    assert result["toc"] == []
    assert result["toc_text"] == "第一章 开始\n第二章 继续"
    assert result["entry_count"] == 2


def test_toc_database_strips_epub_internal_paths(tmp_path):
    db = KnowledgeCoreDB(db_dir=str(tmp_path))
    file_path = str(tmp_path / "book.epub")

    assert db.save_toc(
        file_path,
        {
            "success": True,
            "method": "builtin",
            "toc": [
                {
                    "level": 1,
                    "title": "第一章",
                    "href": "text/part0001.html#toc_1",
                    "target_index": 3,
                }
            ],
        },
    )

    result = db.get_toc(file_path)
    assert result["toc"] == [{"level": 1, "title": "第一章"}]


def test_strip_toc_storage_noise_keeps_display_fields():
    cleaned = strip_toc_storage_noise(
        {
            "toc": [
                {
                    "level": 2,
                    "title": "第二节",
                    "page": 12,
                    "href": "Text/chapter.xhtml",
                    "anchor": "a1",
                    "target_index": 5,
                }
            ]
        }
    )

    assert cleaned["toc"] == [{"level": 2, "title": "第二节", "page": 12}]


def test_strip_toc_storage_noise_removes_internal_file_titles():
    cleaned = strip_toc_storage_noise(
        {
            "toc": [
                {"level": 1, "title": "part0001.html"},
                {"level": 1, "title": "Book_Name_split_003.xhtml"},
                {"level": 1, "title": "*"},
                {"level": 1, "title": "_"},
                {"level": 1, "title": "HTML 与网页设计"},
            ]
        }
    )

    assert cleaned["toc"] == [{"level": 1, "title": "HTML 与网页设计"}]
    assert cleaned["entry_count"] == 1


def test_toc_database_drops_file_name_only_titles(tmp_path):
    db = KnowledgeCoreDB(db_dir=str(tmp_path))
    file_path = str(tmp_path / "book.epub")

    assert db.save_toc(
        file_path,
        {
            "success": True,
            "method": "builtin",
            "toc": [
                {"level": 1, "title": "part0001.html"},
                {"level": 1, "title": "第一章 正文"},
            ],
        },
    )

    result = db.get_toc(file_path)
    assert result["toc"] == [{"level": 1, "title": "第一章 正文"}]
    assert result["entry_count"] == 1


def test_toc_sanitizes_surrogate_characters_for_json_and_db(tmp_path):
    bad_title = "Chapter \udce2 Broken"
    payload = {
        "success": True,
        "method": "builtin",
        "toc": [{"level": 1, "title": bad_title, "page": "1\udce2"}],
        "toc_text": f"{bad_title}\n",
    }

    sanitized = sanitize_toc_result(payload)

    assert "\udce2" not in sanitized["toc"][0]["title"]
    assert "\udce2" not in sanitized["toc"][0]["page"]
    assert "\udce2" not in sanitized["toc_text"]
    assert "\udce2" not in format_toc_text(payload["toc"])

    db = KnowledgeCoreDB(db_dir=str(tmp_path))
    file_path = str(tmp_path / "bad.pdf")
    assert db.save_toc(file_path, payload) is True
    saved = db.get_toc(file_path)
    assert "\udce2" not in saved["toc"][0]["title"]


def test_good_builtin_toc_does_not_need_ai_cleanup():
    raw_result = {
        "success": True,
        "toc": [
            {"title": "第一章 开始"},
            {"title": "第二章 继续"},
            {"title": "第三章 深入"},
            {"title": "第四章 实践"},
            {"title": "第五章 总结"},
            {"title": "附录"},
        ],
    }

    assert _toc_needs_ai_cleanup(raw_result) is False


def test_missing_or_weak_toc_needs_ai_cleanup():
    assert _toc_needs_ai_cleanup({"success": False, "toc": []}) is True
    assert (
        _toc_needs_ai_cleanup(
            {
                "success": True,
                "toc": [
                    {"title": "版权"},
                    {"title": "目录"},
                    {"title": "前言"},
                ],
            }
        )
        is True
    )
