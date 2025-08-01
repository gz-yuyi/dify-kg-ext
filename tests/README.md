# Tests for Dify Knowledge Graph Extension

This directory contains tests for the Dify Knowledge Graph Extension API.

## Setup

Install test dependencies:

```bash
pip install pytest pytest-asyncio httpx
```

## Running the Tests

To run all tests:

```bash
pytest
```

To run a specific test file:

```bash
pytest tests/test_api.py
```

To run a specific test:

```bash
pytest tests/test_api.py::test_update_knowledge
```

To run with verbosity:

```bash
pytest -v
```

## Test Structure

- `conftest.py`: Contains shared fixtures for all tests
- `test_api.py`: Tests for the API endpoints

## Mocking

The tests use `unittest.mock` to mock the Elasticsearch functions. This allows us to test the API endpoints without needing a real Elasticsearch instance.
