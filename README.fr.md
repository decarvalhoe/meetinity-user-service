# Service Utilisateur Meetinity

Service utilisateur basé sur Flask avec authentification OAuth via Google et LinkedIn.

## Vue d'ensemble

Le Service Utilisateur est un microservice complet d'authentification et de gestion des utilisateurs développé avec **Python Flask**. Il gère les flux d'authentification OAuth 2.0, la gestion des tokens JWT et les opérations de profil utilisateur pour la plateforme Meetinity.

## Fonctionnalités

- **Authentification OAuth 2.0** : Authentification sécurisée avec les fournisseurs Google et LinkedIn
- **Gestion des tokens JWT** : Capacités de génération, validation et rafraîchissement des tokens
- **Gestion des profils utilisateur** : Opérations CRUD complètes pour les profils utilisateur
- **Sécurité** : Validation d'état, gestion des nonces et stockage sécurisé des tokens
- **Configuration flexible** : Configuration basée sur l'environnement pour différents scénarios de déploiement

## Stack Technique

- **Flask** : Framework web Python léger
- **PyJWT** : Implémentation JSON Web Token pour l'authentification sécurisée
- **Requests** : Client HTTP pour la communication avec les fournisseurs OAuth
- **Python-dotenv** : Gestion des variables d'environnement
- **Flask-CORS** : Support Cross-Origin Resource Sharing

## État du Projet

- **Avancement** : 80%
- **Fonctionnalités terminées** : Flux OAuth (Google/LinkedIn), gestion JWT, points de profil utilisateur, middleware de sécurité
- **Fonctionnalités en attente** : Réinitialisation de mot de passe, vérification d'email, gestion des préférences utilisateur

## Configuration

- `CORS_ORIGINS` : liste séparée par des virgules des origines autorisées pour CORS. Par défaut `*`.
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` : identifiants OAuth Google et URL de callback.
- `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` / `LINKEDIN_REDIRECT_URI` : identifiants OAuth LinkedIn et URL de callback.
- `ALLOWED_REDIRECTS` : liste optionnelle séparée par des virgules d'URI de redirection supplémentaires pour les flux OAuth.
- `JWT_SECRET` (`JWT_ALGO`, `JWT_TTL_MIN`) : configuration pour signer les JSON Web Tokens.
- Tous les horodatages sont retournés au format ISO 8601 avec fuseau horaire UTC.

## Développement

```bash
pip install -r requirements.txt
flake8 src tests
pytest
```

## Exécution

```bash
python src/main.py
```

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
├── main.py              # Point d'entrée de l'application
├── auth/
│   ├── jwt_handler.py   # Logique d'encodage/décodage JWT
│   └── oauth.py         # Intégration des fournisseurs OAuth
├── models/
│   └── user.py          # Modèles de données utilisateur
└── routes/
    └── auth.py          # Points d'authentification
```
