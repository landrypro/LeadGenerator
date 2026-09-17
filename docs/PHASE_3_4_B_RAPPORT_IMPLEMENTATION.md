# Phase 3.4-B — Rapport d’implémentation

| Métadonnée | Valeur |
| --- | --- |
| Phase | 3.4 — Opportunités, sous-lot B |
| Date | 10 septembre 2026 |
| Révision Alembic attendue | `20260910_0020` |
| Migration ajoutée | Aucune |
| État | Techniquement validé — verrou qualité local vert |

## Livré

- commandes de création, mise à jour, transition, clôture gagnée/perdue et réouverture ;
- contrôle de capacité, responsabilité, prospect archivé, responsable inactif, version et clé d’idempotence ;
- événements métier append-only, audit minimisé et métriques de commande, transition et conflit ;
- portefeuille et liste par prospect avec tri stable, filtres, agrégats exacts par devise et curseur HMAC lié à la portée ;
- détail et historique d’une opportunité ;
- routes HTTP sous `/api/prospects/{prospect_id}/opportunities` et `/api/opportunities`, toutes protégées par session,
  origine, JSON, CSRF pour les mutations et `Cache-Control: no-store, max-age=0` ;
- erreurs publiques stables sans fuite de données inter-organisation.

## Vérifications exécutées

| Contrôle | Résultat |
| --- | --- |
| Ruff ciblé | Vert |
| Format Ruff ciblé | Vert |
| mypy ciblé (6 fichiers) | Vert |
| Tests ciblés Python initiaux | `36 passed`, `4 skipped` hors environnement PostgreSQL réel |
| Tests API opportunités, pagination et cas d’utilisation ajoutés | `5 passed` |
| Verrou qualité local complet | Vert : PostgreSQL, Redis, Mailpit, migrations, Alembic, tests backend, Vitest/axe, build Vite et contrôle Git |

## Validation finale

Après libération de l’espace disque temporaire, le verrou qualité local a terminé vert. Il a démarré puis arrêté ses
services isolés, exécuté les contrôles backend et frontend, et produit un artefact Vite conforme. Les avertissements
LF/CRLF de Git ne modifient pas le contenu et n’empêchent pas la validation.

La révision reste `20260910_0020 (head)` : 3.4-B ne requiert aucune migration supplémentaire. Les écrans et la recette
fonctionnelle des opportunités restent dans le périmètre des sous-lots ultérieurs 3.4-C et 3.4-D.
