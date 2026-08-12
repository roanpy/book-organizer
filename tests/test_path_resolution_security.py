from book_organizer.file_ops import resolve_file_path


def test_resolve_file_path_rejects_absolute_and_parent_paths_outside_roots(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    inside = source / "book.epub"
    outside = tmp_path / "outside.epub"
    inside.write_text("inside", encoding="utf-8")
    outside.write_text("outside", encoding="utf-8")
    config = {"source_dir": str(source), "target_dir": ""}

    assert resolve_file_path(str(inside), config) == str(inside.resolve())
    assert resolve_file_path(str(outside), config) is None
    assert resolve_file_path("../outside.epub", config) is None


def test_resolve_file_path_rejects_symlink_that_escapes_root(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.epub"
    outside.write_text("outside", encoding="utf-8")
    link = source / "linked.epub"
    link.symlink_to(outside)

    assert resolve_file_path("linked.epub", {"source_dir": str(source)}) is None
