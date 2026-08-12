from book_organizer.routers.models import (
    ISBNLookupRequest,
    LocalCategorizeRequest,
    LocalDuplicateRequest,
    LocalIdentifyRequest,
    LocalSuggestDirsRequest,
)


def test_local_tool_request_models_accept_frontend_payloads():
    isbn_request = ISBNLookupRequest(file_path="books/example.epub")
    assert isbn_request.file_path == "books/example.epub"
    assert isbn_request.isbn == ""
    assert isbn_request.api == "openlibrary"

    categorize_request = LocalCategorizeRequest(
        title="Designing Data-Intensive Applications",
        tags=["database", "distributed"],
    )
    assert categorize_request.tags == ["database", "distributed"]

    duplicate_request = LocalDuplicateRequest(title="Designing Data-Intensive Applications")
    assert duplicate_request.threshold == 0.8

    identify_request = LocalIdentifyRequest(file_path="books/example.pdf")
    assert identify_request.file_path == "books/example.pdf"

    suggest_request = LocalSuggestDirsRequest(title="Designing Data-Intensive Applications")
    assert suggest_request.author is None
