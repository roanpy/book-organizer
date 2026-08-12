# Releasing

1. Update the version in `pyproject.toml`, `src/book_organizer/__init__.py`, and `BookOrganizer.spec`.
2. Run the test, lint, frontend syntax, and public safety checks.
3. Build with `./scripts/build_standalone.sh`.
4. Run `./scripts/verify_bundle.sh dist/BookOrganizer.app`.
5. Test the installed app on a clean user account before publishing a tag.

Release artifacts must not contain databases, local paths, API keys, OAuth tokens, client secrets, or user book files.
