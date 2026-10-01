# Phase 3.2 — Rapport d’implémentation Kanban

## Livré

- migration additive `20260904_0015` : étapes par organisation, historique append-only des transitions, élargissement contrôlé de `stage_code`, `stage_changed_at` et RLS forcé ;
- neuf étapes système, graphe de transitions, motifs contrôlés de perte et de réouverture, contrôle de version et clé d’idempotence ;
- capacités `pipeline:read`, `pipeline:move`, `pipeline:history:read`, `pipeline:reopen` et `pipeline:configure` ;
- API `GET /api/prospects/pipeline/stages`, `GET /api/prospects/pipeline/board`, `PATCH /api/prospects/pipeline/stages/{stage_code}`, `POST /api/prospects/{id}/stage-transitions`, `GET /api/prospects/{id}/stage-transitions` et `POST /api/prospects/{id}/reopen` ;
- audit métier minimisé, sans contenu de contacts, ni données Google ;
- écran « Pipeline » accessible par navigation et boutons de déplacement au clavier.

## Recette locale à effectuer

1. Démarrer PostgreSQL et Redis, puis exporter `DATABASE_URL` et `MIGRATION_DATABASE_URL` vers le port PostgreSQL local.
2. Exécuter `./.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head` et vérifier `20260904_0015 (head)`.
3. Se connecter avec un Administrateur, ouvrir **Pipeline**, puis vérifier les neuf colonnes.
4. Créer un prospect et le déplacer de `Nouveau` vers `Qualification`, puis `Qualifié` ; vérifier que son compteur et son étape changent.
5. Essayer un saut interdit ; vérifier le refus sans changement de carte.
6. Marquer un prospect perdu avec un motif ; vérifier le journal d’activité. Réouvrir avec un compte Administrateur ou Gestionnaire et vérifier le nouvel historique.
7. Ouvrir la même fiche ou le même board avec deux sessions ; déplacer depuis la première, puis rejouer la version devenue obsolète depuis la seconde ; vérifier le `409` sans deuxième historique.
8. Exécuter `./scripts/Test-QualityGateLocal.ps1 -DockerMode wsl -WslDistribution "Ubuntu-24.04"` avec des ports de test disponibles.

## Vérifications réalisées pendant l’implémentation

- Ruff et format Ruff : verts ;
- mypy backend : vert ;
- tests backend : `222 passed, 35 skipped` ;
- tests ciblés Kanban : transition versionnée, idempotence et motif de perte ;
- build Vite et test de routage : verts.

Le contrôle Alembic complet avec PostgreSQL réel reste à lancer dans l’environnement de recette, car aucune URL de base n’était configurée dans l’environnement de développement de l’agent.
