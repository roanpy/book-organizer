# Engineering Hardening

The core book workflow is intentionally unchanged. This work closes reliability
and release gaps without introducing new service layers or a plugin framework.

## Phase 1: Data and Runtime Reliability

Status: complete.

- Use portable file paths as database identity so same-name books remain separate.
- Keep summary and TOC source selection consistent on the first API response.
- Skip ambiguous path repairs and never delete a record because an update collides.
- Close active Gemini transports before Python shutdown.
- Validate legacy database migration against a read-only production database copy.

## Phase 2: Maintenance and Release Readiness

Status: complete, except external Apple credentials.

- Cover PDF, EPUB, TXT, and Markdown with local generated test samples.
- Expose a read-only database health check and show its result in the existing sync dialog.
- Verify packaged-app startup, local API availability, and normal shutdown.
- Support Developer ID signing and Apple notarization through environment variables.

Formal notarization still requires the maintainer's Apple Developer certificate
and a local `notarytool` keychain profile. These credentials are never stored in
the repository.

## Maintenance Follow-up

- Record schema version `3` with SQLite `PRAGMA user_version`; migrations remain
  small and idempotent without an external migration framework.
- Run lightweight CI contracts for analysis cleanup, first-detail rendering,
  settings persistence, and database sync entry points.
- Keep the native Gemini, OpenAI-compatible, and Ollama clients because built-in
  model calls and settings validation still use them; custom providers use LiteLLM.
- Log provider exception details locally while returning short actionable UI errors.
