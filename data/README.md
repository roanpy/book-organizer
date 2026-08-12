# Data Directory

This repository directory is only a placeholder. Runtime configuration and
history are stored outside the app bundle in:

```bash
~/.book_organizer/
```

## Files

### `book_organizer_config.json`
User configuration file containing:
- AI API settings (API key, model, etc.)
- Core rules for book organization
- Additional custom rules
- Historical data reference settings

**Important**: This file contains sensitive information (API keys) and is
excluded from Git.

### `book_organizer_history.json`
Historical record of book organization decisions:
- Previously organized books
- AI decisions and reasoning
- User corrections and feedback

**Important**: This file may contain personal data and is excluded from Git.

## Security Notes

1. **Never commit these files to Git** - They are listed in `.gitignore`
2. **Do not package local runtime files** - the app bundle should only include this README from `data/`
3. **Backup regularly** - these files contain personalized settings
4. **Keep API keys secure** - never share your configuration file

## Backup Recommendation

Consider backing up these files separately:
```bash
# Create a backup
cp ~/.book_organizer/book_organizer_config.json ~/Backups/book_organizer_config_$(date +%Y%m%d).json
cp ~/.book_organizer/book_organizer_history.json ~/Backups/book_organizer_history_$(date +%Y%m%d).json
```

## Initial Setup

On first run, these files will be created automatically with default values. You can then customize them through the web interface.
