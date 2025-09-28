# Meetinity User Service

Flask-based user service with OAuth authentication via Google and LinkedIn backed by
SQLAlchemy models and Alembic migrations.

## Overview

The User Service is a comprehensive authentication and user management microservice built with **Python Flask**. It handles OAuth 2.0 authentication flows, JWT token management, and user profile operations for the Meetinity platform.

## Features

- **OAuth 2.0 Authentication**: Secure authentication with Google and LinkedIn providers
- **JWT Token Management**: Token generation, validation, and refresh capabilities
- **User Profile Management**: Complete user profile CRUD operations with
  persisted preferences and social connections
- **Security**: State validation, nonce handling, and secure token storage
- **Flexible Configuration**: Environment-based configuration for different
  deployment scenarios with centralized config loading
- **Caching**: Optional Redis cache for frequently accessed user profiles

## Tech Stack

- **Flask**: Lightweight Python web framework
- **PyJWT**: JSON Web Token implementation for secure authentication
- **Requests**: HTTP client for OAuth provider communication
- **Python-dotenv**: Environment variable management
- **Flask-CORS**: Cross-Origin Resource Sharing support
- **SQLAlchemy**: ORM used for persistence and migrations
- **Marshmallow**: Declarative serialization layer for API responses

## Project Status

- **Progress**: 90%
- **Completed Features**: OAuth flows (Google/LinkedIn), JWT handling, user
  profile endpoints, SQLAlchemy persistence layer, Alembic migrations
- **Pending Features**: Password reset, email verification, extended audit logs

## Configuration

- `CORS_ORIGINS`: comma-separated list of allowed origins for CORS. Defaults to `*`.
- `APP_PORT`: TCP port used when running `python src/main.py`. Defaults to `5001`.
- `FLASK_SECRET`: secret key used for Flask session signing.
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI`: Google OAuth credentials and callback URL.
- `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` / `LINKEDIN_REDIRECT_URI`: LinkedIn OAuth credentials and callback URL.
- `DATABASE_URL`: SQLAlchemy database URL (e.g. `postgresql+psycopg://user:pass@localhost:5432/meetinity`).
- `SQLALCHEMY_ECHO`: set to `true` to log SQL queries.
- `REDIS_URL`: optional Redis connection string for profile caching.
- `REDIS_CACHE_TTL`: cache expiration (seconds) for Redis entries. Defaults to `300`.
- `ALLOWED_REDIRECTS`: optional comma-separated list of additional redirect URIs for OAuth flows.
- `JWT_SECRET` (`JWT_ALGO`, `JWT_TTL_MIN`): configuration for signing JSON Web Tokens.
- All timestamps are returned in ISO 8601 format with UTC timezone.

## Development

```bash
pip install -r requirements.txt
alembic upgrade head  # apply DB migrations
flake8 src tests
pytest
pytest --cov=src --cov=tests --cov-report=term-missing --cov-fail-under=90
```

## Running

```bash
python src/main.py
```

or using Flask's CLI:

```bash
export FLASK_APP=src.main:app
flask run --port ${APP_PORT:-5001}
```

## Database & Cache Provisioning

### PostgreSQL (development)

```bash
docker run --name meetinity-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=meetinity \
  -e POSTGRES_DB=meetinity -p 5432:5432 -d postgres:15

export DATABASE_URL="postgresql+psycopg://meetinity:postgres@localhost:5432/meetinity"
alembic upgrade head
```

### Redis (optional cache)

```bash
docker run --name meetinity-redis -p 6379:6379 -d redis:7
export REDIS_URL="redis://localhost:6379/0"
```

### Backup Strategy

- **Database**: schedule `pg_dump` backups (daily full backups, hourly
  incremental using WAL archiving). Store encrypted archives in object storage.
- **Redis**: enable RDB snapshots (e.g. every 15 minutes) or AOF persistence if
  cached sessions must be retained. Pair with standard infrastructure backups.

## Endpoints

- `POST /auth/<provider>` → `{ "auth_url": "https://..." }`
- `GET /auth/<provider>/callback?code=..&state=..` → `{ "token": "<jwt>", "user": {...} }`
- `POST /auth/verify` → `{ "valid": true, "sub": "<user_id>", "exp": 123 }`
- `GET /auth/profile` (Bearer token) → `{ "user": {...} }`
- `GET /health`

## Architecture

The service follows a clean architecture pattern with clear separation of concerns:

```
src/
├── main.py              # Application entry point & Flask factory
├── auth/
│   ├── jwt_handler.py   # JWT encoding/decoding logic
│   └── oauth.py         # OAuth provider integration
├── config.py            # Centralized configuration helper
├── db/
│   └── session.py       # SQLAlchemy engine/session helpers
├── models/
│   ├── user.py          # SQLAlchemy models for user domain
│   └── user_repository.py  # Repository encapsulating persistence logic
└── routes/
    └── auth.py          # Authentication endpoints
alembic/
└── versions/            # Database migrations
```

## Database Migrations

Alembic is configured for schema management. Typical commands:

```bash
alembic revision -m "<description>"
alembic upgrade head
alembic downgrade -1
```
