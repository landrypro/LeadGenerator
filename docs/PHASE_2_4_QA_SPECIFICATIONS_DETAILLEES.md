# Phase 2.4-QA — Conteneurisation et déploiement de recette Oracle Always Free

## 1. Objectif

Mettre à disposition une instance de recette accessible à un QA externe avant l’itération 2.4.4, sans élargir le
périmètre fonctionnel déjà validé. Cette instance sert à tester les parcours CRM, l’audit, les invitations et la
recherche Google limitée dans un environnement proche d’un hébergement public.

## 2. Décisions validées

1. Le déploiement cible prioritaire est une VM Oracle Cloud Always Free gérée par Docker Compose.
2. L’application React est compilée dans l’image et servie par FastAPI sur une origine unique HTTPS.
3. Caddy termine TLS et renouvelle automatiquement les certificats.
4. PostgreSQL, Redis et SMTP Mailpit restent privés au réseau Docker.
5. L’interface Mailpit n’est pas exposée sur Internet ; elle est consultée par tunnel SSH.
6. L’environnement de recette utilise `APP_ENV=test` afin d’autoriser Mailpit, avec `PUBLIC_APP_URL` HTTPS.
7. Les cookies de session de recette utilisent `__Host-prospect_session` et `SESSION_COOKIE_SECURE=true`.
8. Les migrations Alembic s’exécutent avec le rôle propriétaire ; le serveur Web utilise le rôle `prospect_app`.
9. Les secrets sont fournis par `.env.qa`, ignoré par Git, à partir de `.env.qa.example`.
10. Les clés Google de recette sont dédiées, restreintes et soumises à des quotas bas.
11. Aucune base, Redis, SMTP ou interface interne n’est publiée directement par la VM.
12. Le provisioning PostgreSQL des rôles est idempotent et exécuté avant les migrations.
13. Les sauvegardes PostgreSQL de recette sont manuelles, datées UTC et stockées hors dépôt.
14. Les données QA sont considérées comme jetables et ne doivent contenir aucun secret réel ni donnée personnelle client.
15. Azure Pipelines reste le verrou final de la phase 2.4 ; cette recette ne le remplace pas.
16. Le retour à 2.4.4 est autorisé uniquement après preuve de démarrage, readiness et accès QA.

## 3. Critères d’acceptation

- `docker compose --env-file .env.qa -f compose.qa.yaml config` est valide.
- `scripts/qa-deploy.sh` construit l’image, démarre PostgreSQL, Redis, Mailpit, exécute le provisioning, applique les
  migrations, puis démarre l’application et Caddy.
- `https://<domaine>/api/health/ready` retourne `ready`.
- L’application est utilisable depuis le navigateur QA sur HTTPS.
- Les invitations arrivent dans Mailpit via tunnel SSH.
- PostgreSQL et Redis ne sont pas accessibles depuis Internet.
- La recherche Google reste limitée à vingt résultats, sans contact ni pagination.
- L’audit et les écrans validés en 2.4.3 restent disponibles.

## 4. Hors périmètre

- Déploiement de production.
- SMTP réel.
- Stockage objet, monitoring externe, autoscaling ou haute disponibilité.
- Renommage LeadGenerator/Marketteo et modules commerciaux prévus après 2.4.
