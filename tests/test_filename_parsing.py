import time

from book_organizer.file_ops import parse_filename, parse_filename_to_dict
from book_organizer.local_utils import parse_book_name


def test_supported_filename_shapes_keep_existing_results():
    assert parse_filename_to_dict("[Ada] Systems.epub") == {
        "title": "Systems",
        "author": "Ada",
    }
    assert parse_filename_to_dict("Systems - [Ada].pdf") == {
        "title": "Systems",
        "author": "Ada",
    }
    assert parse_filename_to_dict("Systems - [[UK]] Ada.epub") == {
        "title": "Systems",
        "author": "[UK] Ada",
    }
    assert parse_filename("Systems.epub") == "文件名: 'Systems'"
    assert parse_book_name("Systems (第2版).epub") == {
        "title": "Systems",
        "author": None,
        "edition": "2",
    }


def test_filename_parsing_is_bounded_for_long_untrusted_input():
    value = "x" * 100_000 + " - [author].epub"
    started = time.monotonic()

    parsed = parse_filename_to_dict(value)

    assert parsed["author"] == "author"
    assert time.monotonic() - started < 0.5


def test_parse_book_name_finds_edition_after_other_parentheses():
    assert parse_book_name("系统设计（套装）(第2版).epub") == {
        "title": "系统设计（套装）",
        "author": None,
        "edition": "2",
    }
