# Meetinity User Service

Provides CRUD operations for user profiles with search and photo upload.

## Endpoints
- `GET /users` list users with pagination and filters
- `POST /users` create user
- `GET /users/<id>` retrieve user
- `PUT /users/<id>` update user
- `DELETE /users/<id>` delete user
- `POST /users/<id>/photo` upload profile photo
- `GET /users/search` search users

## Development
### Run & Test (dev)
```powershell
pip install -r requirements.txt
flake8 src tests
pytest
Copy-Item .env.example .env
$env:APP_PORT=5001
$env:CORS_ORIGINS="http://localhost:5173,http://localhost:5174"
$env:JWT_SECRET="dev-secret"
python src/main.py
```
