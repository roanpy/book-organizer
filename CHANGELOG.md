# Changelog

## Unreleased

- Updated vulnerable pinned Python dependencies to patched compatible releases.
- Pinned GitHub Actions to immutable commits and grouped coordinated Dependabot updates.
- Added SQLite schema version tracking, sanitized AI errors, and frontend workflow contract checks.
- Restricted file resolution to configured book roots and included license notices in packaged artifacts.
- Separated CI test dependencies from the desktop build toolchain and made builds use the selected Python environment.

## 0.8.3

- Published a clean, history-free open-source edition.
- Added local English/Chinese UI adaptation and bilingual screenshots.
- Stabilized book-scoped asynchronous analysis and result refresh.
- Added local PDF/EPUB/TXT/Markdown preview with TOC navigation.
- Added portable library path repair and safer database/config synchronization.
- Kept API keys local by default.
- Removed the Google Drive SDK and automatic upload from the main branch; local PDF export remains available for manual import into external services.
- Made database identity path-based so same-name books in different folders retain separate summaries, TOCs, chapters, and insights.
- Added a read-only library health endpoint and safer ambiguous-path handling.
- Added explicit Developer ID signing and Apple notarization support to the release script.
- Added source and packaged-app privacy checks.
