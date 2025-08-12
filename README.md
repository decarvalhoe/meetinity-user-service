# Meetinity User Service

Simple Flask application providing user-related endpoints.

## Configuration

- `CORS_ORIGINS`: comma-separated list of allowed origins for CORS. Defaults to `*`.
- All timestamps are returned in ISO 8601 format with UTC timezone.

## Development

```bash
pip install -r requirements.txt
flake8
pytest
```

