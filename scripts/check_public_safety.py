#!/usr/bin/env python3
"""Fail when a public source tree contains common private artifacts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "build", "dist", "__pycache__"}
FORBIDDEN_NAMES = {
    "book_data.db",
    "book_organizer.db",
    "book_organizer_config.json",
    "google_drive_token.json",
    "client_secrets.json",
}
TEXT_SUFFIXES = {
    ".bat", ".css", ".html", ".ini", ".js", ".json", ".md", ".py",
    ".sh", ".toml", ".txt", ".yaml", ".yml",
}
PATTERNS = {
    "personal macOS path": re.compile(r"/Users/(?!example\b|yourname\b|xxx\b)[^/\s`'\"]+"),
    "personal volume path": re.compile(r"/Volumes/(?!Example\b)[^/\s`'\"]+"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    "OpenAI-style secret": re.compile(r"\bsk-[0-9A-Za-z_-]{16,}"),
    "GitHub token": re.compile(r"\bgh[oprsu]_[0-9A-Za-z]{20,}"),
}


def iter_files():
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts) or not path.is_file():
            continue
        if path == Path(__file__).resolve():
            continue
        yield path


def main() -> int:
    errors: list[str] = []
    seen_inodes: dict[tuple[int, int], Path] = {}
    for path in iter_files():
        relative = path.relative_to(ROOT)
        if path.is_symlink():
            errors.append(f"symlink: {relative}")
            continue
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".zip"}:
            errors.append(f"private or generated artifact: {relative}")
        stat = path.stat()
        inode = (stat.st_dev, stat.st_ino)
        if stat.st_nlink > 1 and inode in seen_inodes:
            errors.append(f"hard link: {relative} -> {seen_inodes[inode].relative_to(ROOT)}")
        seen_inodes[inode] = path
        if path.suffix.lower() not in TEXT_SUFFIXES or stat.st_size > 2_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{label}: {relative}")

    if errors:
        print("Public safety check failed:")
        for error in sorted(set(errors)):
            print(f"- {error}")
        return 1
    print("Public safety check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
