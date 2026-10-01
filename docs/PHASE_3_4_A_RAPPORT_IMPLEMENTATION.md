# Phase 3.4-A — Rapport d’implémentation : domaine et persistance des opportunités

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 3.4 — Opportunités |
| Sous-lot | 3.4-A — Domaine et persistance |
| Date | 10 septembre 2026 |
| Statut | Implémenté et techniquement validé ; verrou qualité local 3.4-A vert |
| Révision Alembic attendue | `20260910_0020` |

## Résultat livré

Le socle persistant des opportunités est en place, sans route HTTP ni écran :

- domaine immuable dans `backend/app/domain/opportunity.py` : six étapes, motifs, montants `Decimal`, devise ISO 4217,
  valeur pondérée dérivée, états terminaux et validations pures ;
- capacités `opportunities:*` ajoutées à la matrice des rôles ;
- modèles SQLAlchemy `OpportunityModel` et `OpportunityEventModel`, ports dédiés et dépôts PostgreSQL raccordés au
  `ProspectUnitOfWork` ;
- migration additive `20260910_0020_opportunity_foundation.py`, depuis `20260905_0019` ;
- RLS forcée sur les deux tables, références composites inter-organisation impossibles, privilèges minimaux et journal
  d’événements append-only ;
- contraintes SQL sur le montant, la devise, la probabilité, les états terminaux, les événements et l’idempotence ;
- tests de domaine et tests d’intégration PostgreSQL pour contraintes, rejouabilité et isolation locataire.

La modification du pipeline prospect, les cas d’utilisation, l’API, l’audit applicatif et le frontend restent strictement
hors périmètre. Ils appartiennent aux sous-lots 3.4-B à 3.4-D, qui n’ont pas démarré.

## Contrôles exécutés

| Contrôle | Résultat |
| --- | --- |
| Ruff, format Ruff et mypy | Verts |
| Tests backend réels | 289 verts, 0 échec, 0 erreur, 0 skip |
| Tests frontend Vitest/axe | 162 verts, 0 échec, 0 erreur, 0 skip |
| Tête Alembic | `20260910_0020 (head)` |
| Première exécution pytest réelle | 284 verts, 5 échecs ciblés, aucun skip ; correctifs appliqués |
| Vérification locale des correctifs | 19 tests de domaine et permissions verts ; Ruff et mypy verts |
| Deuxième exécution pytest réelle | 283 verts, 6 erreurs de création du temporaire pytest ; correctif appliqué |
| Reproduction ciblée du temporaire | 8 tests verts dans un répertoire système isolé |
| Verrou qualité local 3.4-A | **VERT**, le 10 septembre 2026 à 16:26:25 UTC |

Le rapport automatisé `test-results/quality-summary.md` confirme le verdict vert. Les rapports JUnit confirment
l’absence d’échec, d’erreur et de test ignoré.

## Incidents corrigés et validation finale

Lors de la seconde tentative, PostgreSQL, Redis et Mailpit sont devenus sains et le rôle applicatif a été provisionné.
Alembic s’est toutefois arrêté avant toute instruction SQL : le Python Windows ne pouvait pas joindre le port publié
par Docker dans WSL sur `127.0.0.1`. Le verrou détecte désormais l’adresse IPv4 de `Ubuntu-24.04`, y publie les quatre
ports de test, configure les URL PostgreSQL, Redis et Mailpit avec cette adresse et attend explicitement que PostgreSQL
soit joignable. Le mode Windows et Azure conservent une publication limitée à `127.0.0.1`.

L’exécution suivante a franchi Alembic et lancé toute la suite backend. Elle a révélé un verrou `FOR UPDATE` appliqué
indirectement au côté nullable d’un `LEFT JOIN`, une attente de test incorrecte sur la traduction d’une violation
d’idempotence et une matrice attendue antérieure aux capacités `opportunities:*`. Le verrou vise maintenant uniquement
`opportunities` avec `FOR UPDATE OF opportunities`, vérifie la cause SQL derrière l’erreur applicative, aligne les trois
rôles et place le temporaire pytest hors de OneDrive.

La tentative suivante a confirmé tous ces correctifs avec 283 tests verts. Les six dernières erreurs survenaient avant
les tests utilisant `tmp_path`, car le parent système du nouveau `--basetemp` n’était pas encore créé. Le verrou crée
désormais ce parent avant pytest ; les huit tests des modules concernés passent avec cette configuration.

La commande finalement validée est :

```powershell
.\scripts\Test-QualityGateLocal.ps1 `
  -DockerMode wsl `
  -WslDistribution "Ubuntu-24.04" `
  -TestPostgresPort 55434 `
  -TestRedisPort 56381 `
  -TestMailpitSmtpPort 51028 `
  -TestMailpitApiPort 58028
```

Le verrou a produit les migrations, `alembic check`, les tests PostgreSQL réels et les contrôles complets. L’application
locale peut maintenant recevoir la migration :

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini current
```

## Décision de suite

Le sous-lot 3.4-A est techniquement validé. Aucune recette fonctionnelle séparée n’est requise puisqu’il ne livre ni API
ni écran. Le passage à 3.4-B reste soumis à son GO explicite.
