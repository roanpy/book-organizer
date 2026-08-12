# Changelog

## Unreleased

- Stopped analysis APIs from returning raw provider responses or internal error details.

## 0.8.4

- Updated vulnerable pinned Python dependencies to patched compatible releases.
- Pinned GitHub Actions to immutable commits and grouped coordinated Dependabot updates.
- Added SQLite schema version tracking, sanitized AI errors, and frontend workflow contract checks.
- Restricted file resolution to configured book roots and included license notices in packaged artifacts.
- Separated CI test dependencies from the desktop build toolchain and made builds use the selected Python environment.
- Removed duplicate source-tree copies from the application bundle so ignored bytecode and local build paths cannot leak into releases.
- Defaulted LiteLLM to its bundled model map so importing AI support does not wait on an unrelated network request.
- Restricted the desktop API to trusted local hosts and browser origins.
- Validated analysis, cover, PDF conversion, and database-repair paths at their shared boundaries.
- Prevented synchronization requests from rewriting records outside the configured library or deleting the newest duplicate.
- Removed interpolated inline frontend handlers and kept provider errors and stack traces out of API responses.
- Rejected linked or multiply-linked synchronization files before database, preference, history, and ignore-list writes.
- Reduced local logs to operation results and exception types so book paths and provider details are not retained.

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
