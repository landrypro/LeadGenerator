# Phase 3.3-B — Rapport d’implémentation API

## Livré

- cas d’utilisation transactionnels pour créer des activités et des tâches, modifier une tâche et corriger une
  activité ;
- idempotence persistée pour les créations de tâches et les événements de mutation, avec empreinte de commande et
  rejeu avant le contrôle de version ;
- contrôle de version optimiste des tâches, avec une erreur stable `task_version_conflict` (`409`) ;
- validation des transitions de tâche : une tâche finalisée ne peut plus être finalisée et une tâche ouverte ne peut
  pas être rouverte ;
- routes JSON protégées par session, origine de confiance, CSRF et `Cache-Control: no-store` :
  - `GET /api/prospects/{prospect_id}/timeline` ;
  - `POST /api/prospects/{prospect_id}/activities` ;
  - `POST /api/prospects/activities/{activity_id}/corrections` ;
  - `POST /api/prospects/{prospect_id}/tasks` ;
  - `GET /api/prospects/tasks` ;
  - `PATCH /api/prospects/tasks/{task_id}` ;
  - actions `complete`, `cancel`, `reopen`, `acknowledge-reminder` et `snooze-reminder`.
- audit minimisé des activités et tâches : aucun texte libre, identifiant externe ou contenu de note n’est copié dans
  le journal ;
- métriques bornées pour les commandes d’activité, de tâche, conflits de version et lectures de chronologie ;
- migration additive `20260905_0017`, succédant à `20260905_0016`, pour l’idempotence des tâches et événements.

## Contrôles exécutés

- Ruff : vert ;
- format Ruff : vert ;
- mypy complet : vert (`171` fichiers) ;
- tests backend ciblés : `9 passed` — domaine, transactions de création/rejeu, conflit de version et pipeline ;
- tête Alembic : `20260905_0017`.

## Limites volontairement reportées à 3.3-C / 3.3-D

- aucun écran ou libellé utilisateur n’est livré dans ce sous-lot ;
- les vues « Mes tâches », rappels dus, filtres avancés, curseurs signés de chronologie et la chronologie unifiée avec
  transitions seront finalisés avec les écrans de 3.3-C et 3.3-D ;
- la recette fonctionnelle demeure regroupée à la fin de 3.3, selon la décision validée.
