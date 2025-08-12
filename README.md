# Meetinity User Service

Flask-based user service with OAuth authentication via Google and LinkedIn.

## Configuration

- `CORS_ORIGINS`: comma-separated list of allowed origins for CORS. Defaults to `*`.
- All timestamps are returned in ISO 8601 format with UTC timezone.

## Development

```bash
pip install -r requirements.txt
flake8 src tests
pytest
```

## Running

```bash
python src/main.py
```

## Endpoints

- `POST /auth/<provider>` → `{ "auth_url": "https://..." }`
- `GET /auth/<provider>/callback?code=..&state=..` → `{ "token": "<jwt>", "user": {...} }`
- `POST /auth/verify` → `{ "valid": true, "sub": "<user_id>", "exp": 123 }`
- `GET /auth/profile` (Bearer token) → `{ "user": {...} }`
- `GET /health`
