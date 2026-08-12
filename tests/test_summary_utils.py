from book_organizer.summary_utils import (
    ENHANCED_SUMMARY_SEPARATOR,
    choose_enhanced_summary,
    enhanced_summary_detail_score,
    extract_embedded_enhanced_summary,
    is_structured_enhanced_summary,
    normalize_enhanced_summary,
    should_sync_embedded_summary,
)

NEW_SUMMARY = "图书简介：新版\n\n详细要点：\n1. 要点\n\n具体应用：\n1. 应用"


def test_extracts_epub_direct_structured_description():
    assert extract_embedded_enhanced_summary({"description": NEW_SUMMARY}) == NEW_SUMMARY


def test_extracts_pdf_separator_summary():
    desc = f"原始说明\n\n{ENHANCED_SUMMARY_SEPARATOR}\n{NEW_SUMMARY}"
    assert extract_embedded_enhanced_summary({"description": desc}) == NEW_SUMMARY
    assert normalize_enhanced_summary(desc) == NEW_SUMMARY


def test_ignores_plain_book_description():
    assert extract_embedded_enhanced_summary({"description": "普通出版社简介"}) == ""


def test_embedded_structured_summary_replaces_stale_database_copy():
    old_summary = "旧版简介，没有三段结构"
    assert is_structured_enhanced_summary(NEW_SUMMARY)
    assert should_sync_embedded_summary(old_summary, NEW_SUMMARY)
    assert choose_enhanced_summary(old_summary, NEW_SUMMARY, "database") == NEW_SUMMARY


def test_richer_structured_summary_replaces_compact_database_copy():
    db_summary = "图书简介：数据库\n\n详细要点：一句话概括\n\n具体应用：一句话概括"
    embedded = (
        "图书简介：内置\n\n详细要点：\n"
        "1. 要点一\n2. 要点二\n3. 要点三\n4. 要点四\n\n"
        "具体应用：\n1. 应用一\n2. 应用二\n3. 应用三"
    )
    assert enhanced_summary_detail_score(embedded) > enhanced_summary_detail_score(db_summary)
    assert should_sync_embedded_summary(db_summary, embedded)
    assert choose_enhanced_summary(db_summary, embedded, "database") == embedded


def test_database_priority_keeps_equally_detailed_database_copy():
    db_summary = (
        "图书简介：数据库\n\n详细要点：\n1. 数据库\n2. 数据库\n3. 数据库\n\n"
        "具体应用：\n1. 数据库\n2. 数据库\n3. 数据库"
    )
    embedded = (
        "图书简介：内置\n\n详细要点：\n1. 内置\n2. 内置\n3. 内置\n\n"
        "具体应用：\n1. 内置\n2. 内置\n3. 内置"
    )
    assert not should_sync_embedded_summary(db_summary, embedded)
    assert choose_enhanced_summary(db_summary, embedded, "database") == db_summary
    assert choose_enhanced_summary(db_summary, embedded, "metadata") == embedded
