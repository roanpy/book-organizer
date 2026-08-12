# Security Policy

## Reporting a Vulnerability

Please use [GitHub's private vulnerability report](https://github.com/roanpy/book-organizer/security/advisories/new). If private reporting is unavailable, contact the maintainer through the method listed on the GitHub profile and ask for a private channel without including vulnerability details. Do not open a public issue containing credentials, personal library paths, or database content.

## Local Security Model

- The application listens on `127.0.0.1` by default.
- Configuration and databases live under `~/.book_organizer/` unless changed by the user.
- API keys and tokens are not included in releases and are excluded from portable preference sync by default.
- Preview endpoints are restricted to configured library locations and return `Cache-Control: no-store`.

Run `python scripts/check_public_safety.py` before publishing source and `scripts/verify_bundle.sh <app-path>` before distributing a desktop bundle.
