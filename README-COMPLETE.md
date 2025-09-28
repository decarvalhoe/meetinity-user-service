# Meetinity User Service - Complete Documentation

The **Meetinity User Service** handles user authentication, profile management, and OAuth integration for the Meetinity professional networking platform. It provides secure user registration, login, and profile management capabilities.

## Architecture Overview

The User Service is a core component of the Meetinity microservices architecture:

### Core Services
- **API Gateway** - Request routing and authentication (Port: 8080)
- **User Service** (this service) - OAuth authentication and profile management (Port: 8081)
- **Event Service** - Event creation, discovery, and registration (Port: 8083)
- **Matching Service** - Professional matching algorithms (Port: 8082)
- **Mobile App** - React-based mobile application (Port: 3000)
- **Admin Portal** - React-based administration interface (Port: 3001)

### Infrastructure Services
- **PostgreSQL 15** - Primary database (Port: 5432)
- **Apache Kafka 3.5** - Event streaming (Port: 9092)
- **Redis** - Caching and session storage (Port: 6379)
- **Zookeeper** - Kafka coordination (Port: 2181)

## Technology Stack

- **Framework**: Flask 3.0
- **Language**: Python 3.11
- **Database**: PostgreSQL 15 with SQLAlchemy 2.0
- **Authentication**: OAuth 2.0 (Google, LinkedIn) + JWT
- **Caching**: Redis 5.0
- **Message Queue**: Apache Kafka 3.5
- **WSGI Server**: Gunicorn 21.2.0
- **Migrations**: Alembic 1.12

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15
- Redis
- Apache Kafka 3.5

### Installation

```bash
# Clone the repository
git clone https://github.com/decarvalhoe/meetinity-user-service.git
cd meetinity-user-service

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file with the following variables:

```env
# Service Configuration
APP_PORT=8081
LOG_LEVEL=INFO
FLASK_ENV=development

# Database Configuration
DATABASE_URL=postgresql://meetinity:meetinity@localhost:5432/meetinity

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# JWT Configuration
JWT_SECRET=your-jwt-secret-key
JWT_EXPIRATION_HOURS=24
JWT_REFRESH_EXPIRATION_DAYS=30

# OAuth Configuration - Google
OAUTH_GOOGLE_CLIENT_ID=your-google-client-id
OAUTH_GOOGLE_CLIENT_SECRET=your-google-client-secret
OAUTH_GOOGLE_REDIRECT_URI=http://localhost:8081/auth/oauth/google/callback

# OAuth Configuration - LinkedIn
OAUTH_LINKEDIN_CLIENT_ID=your-linkedin-client-id
OAUTH_LINKEDIN_CLIENT_SECRET=your-linkedin-client-secret
OAUTH_LINKEDIN_REDIRECT_URI=http://localhost:8081/auth/oauth/linkedin/callback

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_USER_TOPIC=user.events

# File Upload Configuration
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216  # 16MB
ALLOWED_EXTENSIONS=jpg,jpeg,png,gif

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:8080
```

### Database Setup

```bash
# Run database migrations
alembic upgrade head

# Create initial data (optional)
python scripts/seed_data.py
```

### Running the Service

#### Development Mode
```bash
# Start the development server
python src/main.py
```

#### Production Mode
```bash
# Start with Gunicorn
gunicorn --bind 0.0.0.0:8081 --workers 4 --timeout 120 "src.main:create_app()"
```

### Docker Deployment

```bash
# Build the Docker image
docker build -t meetinity-user-service .

# Run the container
docker run -p 8081:8081 --env-file .env meetinity-user-service
```

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    oauth_provider VARCHAR(50),
    oauth_id VARCHAR(255),
    profile_picture_url TEXT,
    bio TEXT,
    location VARCHAR(255),
    industry VARCHAR(100),
    job_title VARCHAR(255),
    company VARCHAR(255),
    linkedin_url VARCHAR(500),
    phone VARCHAR(20),
    date_of_birth DATE,
    gender VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_oauth ON users(oauth_provider, oauth_id);
CREATE INDEX idx_users_active ON users(is_active);
```

### User Preferences Table
```sql
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    age_min INTEGER DEFAULT 18,
    age_max INTEGER DEFAULT 65,
    location_radius INTEGER DEFAULT 50, -- in kilometers
    industries TEXT[],
    job_levels TEXT[],
    interests TEXT[],
    notification_email BOOLEAN DEFAULT TRUE,
    notification_push BOOLEAN DEFAULT TRUE,
    privacy_profile VARCHAR(20) DEFAULT 'public', -- public, private, connections
    privacy_location BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id)
);
```

### User Sessions Table
```sql
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    refresh_token VARCHAR(500) UNIQUE NOT NULL,
    device_info JSONB,
    ip_address INET,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_used TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_token ON user_sessions(refresh_token);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at);
```

## API Documentation

### Authentication Endpoints

#### Register User
```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "name": "John Doe",
  "password": "securepassword"
}
```

#### Login User
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword"
}
```

#### OAuth Login (Google)
```http
GET /auth/oauth/google
```

#### OAuth Login (LinkedIn)
```http
GET /auth/oauth/linkedin
```

#### Refresh Token
```http
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "your-refresh-token"
}
```

#### Logout
```http
POST /auth/logout
Authorization: Bearer <jwt-token>
```

### User Profile Endpoints

#### Get User Profile
```http
GET /users/profile
Authorization: Bearer <jwt-token>
```

#### Update User Profile
```http
PUT /users/profile
Authorization: Bearer <jwt-token>
Content-Type: application/json

{
  "name": "John Doe",
  "bio": "Software Engineer passionate about networking",
  "location": "San Francisco, CA",
  "industry": "Technology",
  "job_title": "Senior Software Engineer",
  "company": "Tech Corp",
  "linkedin_url": "https://linkedin.com/in/johndoe"
}
```

#### Upload Profile Picture
```http
POST /users/profile/avatar
Authorization: Bearer <jwt-token>
Content-Type: multipart/form-data

file: <image-file>
```

#### Get User Preferences
```http
GET /users/preferences
Authorization: Bearer <jwt-token>
```

#### Update User Preferences
```http
PUT /users/preferences
Authorization: Bearer <jwt-token>
Content-Type: application/json

{
  "age_min": 25,
  "age_max": 45,
  "location_radius": 30,
  "industries": ["Technology", "Finance"],
  "interests": ["AI", "Blockchain", "Startups"],
  "notification_email": true,
  "privacy_profile": "public"
}
```

### Admin Endpoints

#### Get All Users (Admin)
```http
GET /admin/users?page=1&limit=20&search=john
Authorization: Bearer <admin-jwt-token>
```

#### Get User Details (Admin)
```http
GET /admin/users/{user_id}
Authorization: Bearer <admin-jwt-token>
```

#### Update User Status (Admin)
```http
PUT /admin/users/{user_id}/status
Authorization: Bearer <admin-jwt-token>
Content-Type: application/json

{
  "is_active": false,
  "reason": "Terms violation"
}
```

## Service Integration

### Inter-Service Communication

#### Kafka Events Published
```python
# User created event
{
  "event_type": "user.created",
  "user_id": "uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "timestamp": "2025-09-28T16:30:00Z"
}

# User updated event
{
  "event_type": "user.updated",
  "user_id": "uuid",
  "updated_fields": ["name", "bio", "location"],
  "timestamp": "2025-09-28T16:30:00Z"
}

# User deleted event
{
  "event_type": "user.deleted",
  "user_id": "uuid",
  "timestamp": "2025-09-28T16:30:00Z"
}
```

#### API Gateway Integration
The User Service is accessed through the API Gateway:

```python
# Routes handled by API Gateway
POST /api/auth/*          -> User Service
GET  /api/users/*         -> User Service
PUT  /api/users/*         -> User Service
POST /api/admin/users/*   -> User Service (Admin only)
```

#### Event Service Integration
User events are consumed by the Event Service for:
- Event creator validation
- Attendee management
- User activity tracking

#### Matching Service Integration
User profile updates trigger matching recalculation:
- Profile completeness scoring
- Compatibility algorithm updates
- Recommendation refresh

## Complete Infrastructure Setup

### All Service Repositories
```bash
# Clone all repositories
git clone https://github.com/decarvalhoe/meetinity.git
git clone https://github.com/decarvalhoe/meetinity-api-gateway.git
git clone https://github.com/decarvalhoe/meetinity-user-service.git
git clone https://github.com/decarvalhoe/meetinity-event-service.git
git clone https://github.com/decarvalhoe/meetinity-matching-service.git
git clone https://github.com/decarvalhoe/meetinity-mobile-app.git
git clone https://github.com/decarvalhoe/meetinity-admin-portal.git
```

### Docker Compose Setup
```bash
# From main repository
cd meetinity
make dev-up    # Start all services
make dev-logs  # View logs
make dev-down  # Stop all services
```

### Service Dependencies
```mermaid
graph TD
    A[Mobile App] --> B[API Gateway]
    C[Admin Portal] --> B
    B --> D[User Service]
    D --> E[PostgreSQL]
    D --> F[Redis]
    D --> G[Kafka]
    H[Event Service] --> G
    I[Matching Service] --> G
```

## Security Features

### OAuth 2.0 Implementation
```python
# Google OAuth Flow
1. User clicks "Login with Google"
2. Redirect to Google OAuth endpoint
3. User authorizes application
4. Google redirects with authorization code
5. Exchange code for access token
6. Fetch user profile from Google API
7. Create/update user in database
8. Generate JWT token
9. Return JWT to client
```

### JWT Token Structure
```json
{
  "header": {
    "alg": "HS256",
    "typ": "JWT"
  },
  "payload": {
    "user_id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "role": "user",
    "exp": 1640995200,
    "iat": 1640908800,
    "jti": "token-id"
  }
}
```

### Password Security
- **Hashing**: bcrypt with salt rounds
- **Validation**: Minimum 8 characters, complexity requirements
- **Reset**: Secure token-based password reset flow

### Data Privacy
- **GDPR Compliance**: User data export and deletion
- **Privacy Settings**: Granular privacy controls
- **Data Encryption**: Sensitive data encrypted at rest

## Monitoring and Observability

### Health Check Response
```json
{
  "status": "ok",
  "service": "user-service",
  "version": "1.0.0",
  "dependencies": {
    "database": "up",
    "redis": "up",
    "kafka": "up"
  },
  "metrics": {
    "active_users": 1250,
    "total_users": 5000,
    "oauth_providers": {
      "google": 3000,
      "linkedin": 2000
    }
  }
}
```

### Logging Configuration
```python
LOGGING_CONFIG = {
    "version": 1,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "json": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json"
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": "logs/user-service.log",
            "formatter": "json"
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"]
    }
}
```

## Development

### Project Structure
```
src/
├── main.py              # Application entry point
├── config.py            # Configuration management
├── auth/
│   ├── jwt_handler.py   # JWT token management
│   └── oauth.py         # OAuth providers
├── models/
│   ├── user.py          # User model
│   ├── preferences.py   # User preferences model
│   └── session.py       # User session model
├── routes/
│   ├── auth.py          # Authentication routes
│   ├── users.py         # User management routes
│   └── admin.py         # Admin routes
├── services/
│   ├── user_service.py  # User business logic
│   ├── auth_service.py  # Authentication logic
│   └── kafka_service.py # Kafka event publishing
├── utils/
│   ├── validators.py    # Input validation
│   ├── decorators.py    # Custom decorators
│   └── helpers.py       # Utility functions
└── db/
    └── session.py       # Database session management
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_auth.py

# Run linting
flake8 src/
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "Add user preferences table"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# View migration history
alembic history
```

## Performance Optimization

### Redis Caching Strategy
```python
# Cache user profiles for 1 hour
CACHE_KEYS = {
    "user_profile": "user:profile:{user_id}",
    "user_preferences": "user:preferences:{user_id}",
    "oauth_state": "oauth:state:{state_id}"
}

CACHE_TIMEOUTS = {
    "user_profile": 3600,      # 1 hour
    "user_preferences": 7200,   # 2 hours
    "oauth_state": 600         # 10 minutes
}
```

### Database Optimization
```sql
-- Indexes for common queries
CREATE INDEX CONCURRENTLY idx_users_email_active ON users(email) WHERE is_active = true;
CREATE INDEX CONCURRENTLY idx_users_created_at ON users(created_at DESC);
CREATE INDEX CONCURRENTLY idx_users_last_login ON users(last_login DESC) WHERE last_login IS NOT NULL;

-- Partial indexes for OAuth users
CREATE INDEX CONCURRENTLY idx_users_google_oauth ON users(oauth_id) WHERE oauth_provider = 'google';
CREATE INDEX CONCURRENTLY idx_users_linkedin_oauth ON users(oauth_id) WHERE oauth_provider = 'linkedin';
```

## Troubleshooting

### Common Issues

#### Database Connection Issues
```bash
# Test PostgreSQL connection
psql -h localhost -U meetinity -d meetinity -c "SELECT version();"

# Check database tables
psql -h localhost -U meetinity -d meetinity -c "\dt"

# View recent migrations
alembic current
alembic history
```

#### OAuth Configuration Issues
```bash
# Verify OAuth environment variables
echo $OAUTH_GOOGLE_CLIENT_ID
echo $OAUTH_LINKEDIN_CLIENT_ID

# Test OAuth endpoints
curl "http://localhost:8081/auth/oauth/google"
curl "http://localhost:8081/auth/oauth/linkedin"
```

#### Redis Connection Issues
```bash
# Test Redis connection
redis-cli ping

# Check Redis keys
redis-cli keys "user:*"

# Monitor Redis commands
redis-cli monitor
```

#### JWT Token Issues
```bash
# Decode JWT token (without verification)
echo "your-jwt-token" | cut -d. -f2 | base64 -d | jq

# Verify token signature
python -c "
import jwt
token = 'your-jwt-token'
secret = 'your-jwt-secret'
print(jwt.decode(token, secret, algorithms=['HS256']))
"
```

## Related Services Documentation

- **API Gateway**: [meetinity-api-gateway](https://github.com/decarvalhoe/meetinity-api-gateway)
- **Event Service**: [meetinity-event-service](https://github.com/decarvalhoe/meetinity-event-service)
- **Matching Service**: [meetinity-matching-service](https://github.com/decarvalhoe/meetinity-matching-service)
- **Mobile App**: [meetinity-mobile-app](https://github.com/decarvalhoe/meetinity-mobile-app)
- **Admin Portal**: [meetinity-admin-portal](https://github.com/decarvalhoe/meetinity-admin-portal)
- **Main Repository**: [meetinity](https://github.com/decarvalhoe/meetinity)

---

**Status**: 80% Complete - Complete OAuth and profiles  
**Last Updated**: September 2025  
**Maintainer**: decarvalhoe
