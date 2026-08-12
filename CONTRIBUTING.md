# Contributing

1. Create a focused branch from `main`.
2. Keep behavior and UI changes scoped; Book Organizer is local-first and must not modify source books unless the user explicitly enables a write option.
3. Add or update the smallest test that proves non-trivial behavior.
4. Run:

```bash
python -m pip install -r requirements-dev.txt
PYTHONPATH=src python -m pytest
PYTHONPATH=src ruff check src tests
python scripts/check_public_safety.py
```

Never commit databases, book files, local configuration, OAuth files, API keys, or personal absolute paths.
