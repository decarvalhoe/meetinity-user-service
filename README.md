# Meetinity User Service

Flask-based user service with OAuth authentication via Google and LinkedIn.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env  # then fill values
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

## Testing

```bash
flake8 src tests
pytest
```
