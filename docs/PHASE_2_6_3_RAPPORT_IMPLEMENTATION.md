# Phase 2.6.3 — Rapport d’implémentation

| Élément | État au 25 août 2026 |
| --- | --- |
| Sous-incrément | 2.6.3 — Observabilité et verrou final |
| Migration Alembic | Aucune ; tête conservée `20260815_0013` |
| Changement visuel | Aucun |
| Verrou qualité local | Vert le 26 août 2026, avec Docker exécuté via WSL |
| Recette fonctionnelle 2.6 | Préparée ; différée à l’environnement de staging avec Redis et deux API réelles |
| Preuve Azure | À exécuter avant la préproduction |

## Livré

- Un port applicatif de métriques avec adaptateur nul et adaptateur Prometheus minimal, sans dépendance du domaine à
  une bibliothèque externe.
- Des compteurs à labels fermés pour le verrou Redis, le quota utilisateur/organisation, les concessions de carte et
  de sélection, ainsi que les résultats des appels Google. Aucun courriel, `place_id`, terme de recherche, adresse,
  jeton ou secret ne peut devenir un label.
- Des journaux structurés JSON configurables avec `request_id`, `instance_id`, route normalisée, classe de statut et
  durée. Ils excluent les données Google et les données personnelles.
- `GET /internal/metrics`, désactivé par défaut, protégé par bearer dédié et comparaison constante. Toute absence ou
  erreur d’autorisation répond `404`, avec `Cache-Control: no-store` et `X-Robots-Tag: noindex, nofollow`.
- Le refus explicite de démarrer en staging/production sans `LOG_FORMAT=json`, `METRICS_ENABLED=true` et bearer de
  métriques d’au moins 32 octets.
- L’instrumentation des adaptateurs Redis et des cas d’utilisation Google déjà présents : l’instrumentation ne peut
  ni ajouter un appel Google ni modifier la décision du verrou, du quota ou des jetons.
- Azure Pipelines publie désormais les preuves de qualité (`test-results`) même après un échec. Le répertoire est
  créé avant les contrôles afin que la publication reste fiable.
- Le guide opérateur, le README, le manuel utilisateur et la recette QA finale de phase sont mis à jour.

## Vérifications automatisées exécutées

- `pytest` unitaire, exécuté en deux lots : **198 passed** ;
- `pytest` d’intégration sans les services externes injectés : **18 passed, 35 skipped** ; ces skips sont attendus
  hors verrou réel et ne sont pas une preuve de clôture ;
- Ruff check et format : **verts** ;
- mypy : **vert** sur 154 fichiers source ;
- Vitest : **146 tests, 0 failure, 0 error, 0 skipped** ;
- verrou JUnit Vitest : **conforme** ;
- build Vite : **vert**.

La recette complète à infrastructure réelle et deux instances est différée au staging : elle fournira la preuve
opérationnelle de TTL, concurrence Redis et absence de `skip` requise pour clôturer officiellement la phase 2.6.

Le verrou qualité local complet a été exécuté avec succès le 26 août 2026. Il a démarré les dépendances réelles,
appliqué et vérifié Alembic, refusé les tests ignorés, puis exécuté les contrôles Python et frontend. Les ports de test
isolés ont évité tout conflit avec l’environnement de développement déjà actif.

## Réserves de clôture

1. Exécuter en staging [`PHASE_2_6_RECETTE_FINALE_QA.md`](PHASE_2_6_RECETTE_FINALE_QA.md) avec PostgreSQL, Redis
   et Mailpit, puis deux instances API distinctes.
2. Conserver le rapport local `test-results/quality-summary.md` issu du verrou vert ; ce verrou refuse les tests
   d’infrastructure ignorés.
3. Conserver une exécution Azure Pipelines verte, ses JUnit et l’artefact `MarketteoQualityEvidence` comme preuve de
   préproduction.
