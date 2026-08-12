from book_organizer import file_ops


def test_find_similar_files_excludes_current_relative_path(monkeypatch, tmp_path):
    root = tmp_path / "Books"
    current_dir = root / "01"
    other_dir = root / "02"
    current_dir.mkdir(parents=True)
    other_dir.mkdir(parents=True)
    (current_dir / "0次与10000次.epub").write_text("current", encoding="utf-8")
    (other_dir / "0次与10000次.pdf").write_text("other", encoding="utf-8")

    monkeypatch.setattr(
        file_ops,
        "_get_config",
        lambda: (
            lambda: {
                "book_extensions": [".epub", ".pdf"],
                "beta_features": {"enable_similar_search": True},
            },
            lambda: {},
        ),
    )

    matches = file_ops.find_similar_files(
        str(root),
        "0次与10000次",
        exclude_paths=["01/0次与10000次.epub"],
    )

    assert matches == [{"path": "02/0次与10000次.pdf", "filename": "0次与10000次.pdf"}]


def test_find_similar_files_excludes_current_absolute_path(monkeypatch, tmp_path):
    root = tmp_path / "Books"
    root.mkdir()
    current = root / "book.pdf"
    other = root / "book.epub"
    current.write_text("current", encoding="utf-8")
    other.write_text("other", encoding="utf-8")

    monkeypatch.setattr(
        file_ops,
        "_get_config",
        lambda: (
            lambda: {
                "book_extensions": [".epub", ".pdf"],
                "beta_features": {"enable_similar_search": True},
            },
            lambda: {},
        ),
    )

    matches = file_ops.find_similar_files(
        str(root),
        "book",
        exclude_paths=[str(current)],
    )

    assert matches == [{"path": "book.epub", "filename": "book.epub"}]
