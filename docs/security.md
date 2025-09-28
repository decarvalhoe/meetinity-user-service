# Sécurité et conformité RGPD

## Chiffrement applicatif

- Le service expose un chiffreur applicatif `ApplicationEncryptor` (`src/utils/encryption.py`).
- Configurez la clé primaire via `APP_ENCRYPTION_KEY` et, si besoin, les clés de rotation via `APP_ENCRYPTION_FALLBACK_KEYS` (séparées par des virgules) dans l'environnement ou `.env`.
- La durée maximale d'utilisation d'un jeton chiffré est définie par `APP_ENCRYPTION_ROTATION_DAYS` (90 jours par défaut).
- Les jetons de session et les `active_tokens` utilisateur sont hachés avant stockage afin de ne jamais être conservés en clair.
- Pour générer une nouvelle clé : `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

## Journaux d'audit

- Toute opération sensible d'authentification (démarrage OAuth, callback, vérification de jeton, demandes/confirmations de vérification) et les exports/suppressions RGPD sont tracés dans la table `audit_logs` (`src/models/audit.py`).
- Les événements contiennent l'identifiant utilisateur (si disponible), l'adresse IP, l'agent utilisateur et un dictionnaire de détails métier.
- Les appels de logging persistent automatiquement via `log_audit_event` (`src/services/audit.py`).
- Les journaux doivent être sauvegardés avec la même stratégie que la base principale et être conservés selon la politique interne (minimum 12 mois recommandé).

## Droits RGPD

- **Export** : `GET /users/<id>/export` retourne le profil complet, les sessions actives, activités, connexions et vérifications, accompagné d'un horodatage `exported_at`.
- **Effacement** : `POST /users/<id>/erase` pseudonymise immédiatement le compte, révoque/vidange les données associées et planifie la destruction en fonction de `ACCOUNT_RETENTION_DAYS` (30 jours par défaut). Les champs `pseudonymized_at` et `scheduled_purge_at` sont exposés pour suivi.
- Les procédures d'effacement remplacent l'adresse e‑mail par une valeur anonymisée, purgent les descriptions d'activités, nettoient les préférences et révoquent les sessions/jetons.

## Politique de rétention et sauvegardes

- `ACCOUNT_RETENTION_DAYS` définit la durée de conservation post-désactivation avant destruction définitive.
- Les sauvegardes chiffrées doivent être effectuées sur le même rythme que la base de production. Utilisez une destination sécurisée (`DATABASE_BACKUP_URL`) et chiffrez les dumps (ex : `gpg --symmetric`).
- Les restaurations doivent respecter les contrôles d'accès et utiliser `DATABASE_RESTORE_URL` si défini.
- Vérifiez régulièrement la rotation des clés d'application et mettez à jour la documentation lorsque les variables d'environnement changent.
