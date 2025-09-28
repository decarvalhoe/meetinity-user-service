# Service Utilisateur Meetinity

Service utilisateur basé sur Flask avec authentification OAuth via Google et LinkedIn,
adossé à SQLAlchemy et aux migrations Alembic.

## Vue d'ensemble

Le Service Utilisateur est un microservice complet d'authentification et de gestion des utilisateurs développé avec **Python Flask**. Il gère les flux d'authentification OAuth 2.0, la gestion des tokens JWT et les opérations de profil utilisateur pour la plateforme Meetinity.

## Fonctionnalités

- **Authentification OAuth 2.0** : Authentification sécurisée avec les fournisseurs Google et LinkedIn
- **Gestion des tokens JWT** : Capacités de génération, validation et rafraîchissement des tokens
- **Gestion des profils utilisateur** : Opérations CRUD complètes pour les profils
  utilisateur avec préférences et connexions sociales persistées
- **Sécurité** : Validation d'état, gestion des nonces et stockage sécurisé des tokens
- **Configuration flexible** : Configuration centralisée basée sur l'environnement
  pour différents scénarios de déploiement
- **Cache** : Prise en charge optionnelle de Redis pour les profils fréquemment consultés

## Stack Technique

- **Flask** : Framework web Python léger
- **PyJWT** : Implémentation JSON Web Token pour l'authentification sécurisée
- **Requests** : Client HTTP pour la communication avec les fournisseurs OAuth
- **Python-dotenv** : Gestion des variables d'environnement
- **Flask-CORS** : Support Cross-Origin Resource Sharing

## État du Projet

- **Avancement** : 90%
- **Fonctionnalités terminées** : Flux OAuth (Google/LinkedIn), gestion JWT,
  points de profil utilisateur, couche de persistance SQLAlchemy, migrations Alembic
- **Fonctionnalités en attente** : Réinitialisation de mot de passe, vérification d'email, journaux d'audit avancés

## Configuration

- `CORS_ORIGINS` : liste séparée par des virgules des origines autorisées pour CORS. Par défaut `*`.
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` : identifiants OAuth Google et URL de callback.
- `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` / `LINKEDIN_REDIRECT_URI` : identifiants OAuth LinkedIn et URL de callback.
- `DATABASE_URL` : URL SQLAlchemy de la base (ex. `postgresql+psycopg://user:pass@localhost:5432/meetinity`).
- `SQLALCHEMY_ECHO` : mettre à `true` pour logguer les requêtes SQL.
- `REDIS_URL` : URL Redis facultative pour la mise en cache des profils.
- `REDIS_CACHE_TTL` : durée de vie du cache en secondes (défaut : `300`).
- `ALLOWED_REDIRECTS` : liste optionnelle séparée par des virgules d'URI de redirection supplémentaires pour les flux OAuth.
- `JWT_SECRET` (`JWT_ALGO`, `JWT_TTL_MIN`) : configuration pour signer les JSON Web Tokens.
- Tous les horodatages sont retournés au format ISO 8601 avec fuseau horaire UTC.

## Développement

```bash
pip install -r requirements.txt
alembic upgrade head  # appliquer les migrations
flake8 src tests
pytest --cov=src --cov=tests --cov-report=term-missing --cov-fail-under=90
```

## Exécution

```bash
python src/main.py
```

## Provisionnement de la base & du cache

### PostgreSQL (développement)

```bash
docker run --name meetinity-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=meetinity \
  -e POSTGRES_DB=meetinity -p 5432:5432 -d postgres:15

export DATABASE_URL="postgresql+psycopg://meetinity:postgres@localhost:5432/meetinity"
alembic upgrade head
```

### Redis (cache optionnel)

```bash
docker run --name meetinity-redis -p 6379:6379 -d redis:7
export REDIS_URL="redis://localhost:6379/0"
```

### Stratégie de sauvegarde

- **Base de données** : planifier des sauvegardes `pg_dump` (complètes quotidiennes,
  incrémentales horaires via WAL). Stocker les archives chiffrées sur un stockage objet.
- **Redis** : activer les snapshots RDB (ex. toutes les 15 minutes) ou AOF selon le besoin
  de conserver les sessions mises en cache et coupler avec les sauvegardes infra habituelles.

## Points d'accès

- `POST /auth/<provider>` → `{ "auth_url": "https://..." }`
- `GET /auth/<provider>/callback?code=..&state=..` → `{ "token": "<jwt>", "user": {...} }`
- `POST /auth/verify` → `{ "valid": true, "sub": "<user_id>", "exp": 123 }`
- `GET /auth/profile` (Bearer token) → `{ "user": {...} }`
- `GET /health`

## Architecture

Le service suit un modèle d'architecture propre avec une séparation claire des préoccupations :

```
src/
├── main.py              # Point d'entrée & factory Flask
├── auth/
│   ├── jwt_handler.py   # Logique d'encodage/décodage JWT
│   └── oauth.py         # Intégration des fournisseurs OAuth
├── config.py            # Chargement de configuration centralisé
├── db/
│   └── session.py       # Gestion moteur/session SQLAlchemy
├── models/
│   ├── user.py          # Modèles SQLAlchemy du domaine utilisateur
│   └── user_repository.py  # Dépôt encapsulant la persistance
└── routes/
    └── auth.py          # Points d'authentification
alembic/
└── versions/            # Migrations de schéma
```

## Migrations de base

Alembic est configuré pour la gestion du schéma. Commandes utiles :

```bash
alembic revision -m "<description>"
alembic upgrade head
alembic downgrade -1
```
