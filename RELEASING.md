# Releasing

1. Update the version in `pyproject.toml`, `src/book_organizer/__init__.py`, and `BookOrganizer.spec`.
2. Confirm the distribution license policy for bundled EbookLib and PyMuPDF
   (AGPL, or a valid commercial license where applicable). Do not publish the
   application as MIT-only.
3. Run the test, lint, frontend syntax, and public safety checks.
4. Run the read-only database health endpoint or `scripts/repair_library_paths.py` in dry-run mode against a test library.
5. Build and verify with `./scripts/build_standalone.sh`.
6. Run `./scripts/smoke_bundle.sh` and test the installed app on a clean user account.
7. Sign, notarize, and package:

```bash
export BOOK_ORGANIZER_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
export BOOK_ORGANIZER_NOTARY_PROFILE="book-organizer-notary"
./scripts/package_release.sh
```

Create the notary profile once with `xcrun notarytool store-credentials`. Without
these variables, `package_release.sh` creates an ad-hoc signed local test package;
it must not be published as a formal release.

Release artifacts must not contain databases, local paths, API keys, OAuth tokens, client secrets, or user book files.
