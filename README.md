# 👥 Meetinity User Service

## ⚠️ **REPOSITORY ARCHIVED - MOVED TO MONOREPO**

**This repository has been archived and is now read-only.**

### 📍 **New Location**
All development has moved to the **Meetinity monorepo**:

**🔗 https://github.com/decarvalhoe/meetinity**

The User Service is now located at:
```
meetinity/services/user-service/
```

### 🔄 **Migration Complete**
- ✅ **All code** migrated with complete history
- ✅ **Latest security features** including encryption, GDPR compliance, and audit logging
- ✅ **Profile metrics** and discovery endpoints
- ✅ **Enhanced repository pattern** with transaction support
- ✅ **CI/CD pipeline** integrated with unified deployment

### 🛠️ **For Developers**

#### **Clone the monorepo:**
```bash
git clone https://github.com/decarvalhoe/meetinity.git
cd meetinity/services/user-service
```

#### **Development workflow:**
```bash
# Start all services including database
docker compose -f docker-compose.dev.yml up

# User Service specific development
cd services/user-service
alembic upgrade head  # Run migrations
pytest                # Run tests
```

### 📚 **Documentation**
- **Service Documentation**: `meetinity/services/user-service/README.md`
- **API Documentation**: `meetinity/services/user-service/docs/`
- **Database Migrations**: `meetinity/services/user-service/alembic/`
- **Infrastructure Guide**: `meetinity/docs/service-inventory.md`

### 🔐 **Security & Compliance Features**
Now available in the monorepo:
- **Data Encryption** for sensitive user information
- **GDPR Compliance** tools and data export/deletion
- **Audit Logging** for all user data operations
- **Profile Metrics** and automated discovery endpoints
- **Enhanced Authentication** with OAuth and JWT

### 🏗️ **Architecture Benefits**
The monorepo provides:
- **Unified CI/CD** for all Meetinity services
- **Cross-service integration** testing
- **Consistent security policies** across all services
- **Centralized user data** management and compliance
- **Simplified deployment** and configuration

---

**📅 Archived on:** September 29, 2025  
**🔗 Monorepo:** https://github.com/decarvalhoe/meetinity  
**📧 Questions:** Please open issues in the monorepo

---

## 📋 **Original Service Description**

The Meetinity User Service was a comprehensive Flask-based authentication and user management microservice with OAuth 2.0 authentication, JWT token management, and user profile operations.

**Key features now available in the monorepo:**
- OAuth 2.0 Authentication (Google, LinkedIn)
- JWT Token Management and validation
- User Profile Management with CRUD operations
- SQLAlchemy models with Alembic migrations
- Redis caching for performance
- Security features: state validation, nonce handling
- Profile discovery and search capabilities
- GDPR compliance and data protection tools
