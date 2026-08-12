# 🧪 Tests Directory

This directory is reserved for unit tests and integration tests.

## Planned Test Coverage

### Unit Tests
- [ ] Book metadata extraction
- [ ] AI model integration
- [ ] Configuration management
- [ ] File operations

### Integration Tests
- [ ] End-to-end book organization workflow
- [ ] API endpoints testing
- [ ] Web interface functionality

### Test Framework
We plan to use:
- **pytest** for Python unit tests
- **pytest-asyncio** for async tests
- **httpx** for API testing

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

## Contributing Tests

When adding new features, please include corresponding tests.

---

**Status**: Tests are planned but not yet implemented.  
**Priority**: Medium - Will be added in future versions.
