# Rapport d’implémentation — Phase 2.4-QA

## Résumé

L’incrément ajoute une voie de déploiement de recette sans changement fonctionnel : image Docker multi-stage,
orchestration Docker Compose QA, terminaison HTTPS Caddy, scripts d’exploitation Linux et documentation Oracle Always
Free.

## Livrables

- `Dockerfile` : build React puis runtime FastAPI non-root.
- `compose.qa.yaml` : application, PostgreSQL, Redis, Mailpit privé, Caddy, migrations et provisioning de rôles.
- `.env.qa.example` : contrat de configuration QA sans secret réel.
- `deploy/qa/Caddyfile` : reverse proxy HTTPS avec en-têtes de sécurité.
- `scripts/qa-deploy.sh` : build, provisioning, migrations et démarrage.
- `scripts/qa-status.sh` : état Compose et readiness applicative.
- `scripts/qa-backup.sh` : sauvegarde PostgreSQL datée UTC.
- `scripts/qa-bootstrap-platform-admin.sh` : création interactive du premier administrateur plateforme.
- `docs/PHASE_2_4_QA_DEPLOIEMENT_ORACLE.md` : procédure de recette.

## Critique 1 — Sécurité

Le choix `APP_ENV=test` est assumé pour permettre Mailpit, mais il ne doit pas être confondu avec une production. Les
garde-fous compensatoires sont le HTTPS public, le cookie `__Host-*`, CORS strict, Mailpit privé, PostgreSQL/Redis
non exposés et données fictives. Avant production, un vrai backend SMTP devra remplacer Mailpit et `APP_ENV` devra
passer à `production`.

## Critique 2 — Exploitation

Docker Compose sur une VM gratuite est simple et robuste pour une recette, mais il n’apporte ni haute disponibilité,
ni restauration automatisée, ni supervision externe. Les sauvegardes manuelles suffisent pour QA ; elles ne suffiront
pas pour un client payant.

## Critique 3 — Coûts et conformité Google

La VM peut être gratuite, mais les appels Google restent facturables. La recette doit utiliser une clé dédiée avec
restrictions API, restriction serveur quand possible, quotas faibles et données fictives. Les limites fonctionnelles
validées, notamment vingt résultats et aucun contact, restent inchangées.

## Revue de code — Architecture

La conteneurisation n’introduit pas de nouveau chemin applicatif. FastAPI continue d’être le point d’entrée unique,
React reste un artefact statique, et Alembic conserve son rôle propriétaire séparé du rôle Web `prospect_app`.

## Revue de code — Opérations

Les services internes ne publient pas de port public. Caddy dépend d’une application saine, et les commandes
one-shot de provisioning/migration sont explicites. Le fichier `.env.qa` concentre les secrets et reste exclu de
l’image et de Git.

## Validation attendue

La configuration Compose a été validée localement avec `.env.qa.example` copié temporairement vers `.env.qa`.
Docker a émis un avertissement d’accès à `C:\Users\Admin\.docker\config.json`, mais `docker compose config --quiet`
a retourné un code succès. La syntaxe shell n’a pas pu être vérifiée depuis PowerShell parce que le Bash local tente
de démarrer WSL, actuellement désactivé sur la machine.

La validation complète nécessite une VM ou un Docker local fonctionnel. À exécuter avant remise au QA :

```bash
docker compose --env-file .env.qa -f compose.qa.yaml config
bash scripts/qa-deploy.sh
bash scripts/qa-status.sh
```
