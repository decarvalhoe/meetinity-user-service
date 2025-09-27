# Meetinity User Service

Flask-based user service with OAuth authentication via Google and LinkedIn.

## Overview

The User Service is a comprehensive authentication and user management microservice built with **Python Flask**. It handles OAuth 2.0 authentication flows, JWT token management, and user profile operations for the Meetinity platform.

## Features

- **OAuth 2.0 Authentication**: Secure authentication with Google and LinkedIn providers
- **JWT Token Management**: Token generation, validation, and refresh capabilities
- **User Profile Management**: Complete user profile CRUD operations
- **Security**: State validation, nonce handling, and secure token storage
- **Flexible Configuration**: Environment-based configuration for different deployment scenarios

## Tech Stack

- **Flask**: Lightweight Python web framework
- **PyJWT**: JSON Web Token implementation for secure authentication
- **Requests**: HTTP client for OAuth provider communication
- **Python-dotenv**: Environment variable management
- **Flask-CORS**: Cross-Origin Resource Sharing support

## Project Status

- **Progress**: 80%
- **Completed Features**: OAuth flows (Google/LinkedIn), JWT handling, user profile endpoints, security middleware
- **Pending Features**: Password reset, email verification, user preferences management

## Configuration

- `CORS_ORIGINS`: comma-separated list of allowed origins for CORS. Defaults to `*`.
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI`: Google OAuth credentials and callback URL.
- `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` / `LINKEDIN_REDIRECT_URI`: LinkedIn OAuth credentials and callback URL.
- `ALLOWED_REDIRECTS`: optional comma-separated list of additional redirect URIs for OAuth flows.
- `JWT_SECRET` (`JWT_ALGO`, `JWT_TTL_MIN`): configuration for signing JSON Web Tokens.
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

## Architecture

The service follows a clean architecture pattern with clear separation of concerns:

```
src/
├── main.py              # Application entry point
├── auth/
│   ├── jwt_handler.py   # JWT encoding/decoding logic
│   └── oauth.py         # OAuth provider integration
├── models/
│   └── user.py          # User data models
└── routes/
    └── auth.py          # Authentication endpoints
```
