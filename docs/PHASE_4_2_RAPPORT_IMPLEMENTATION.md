# Phase 4.2 — Rapport d’implémentation du worker

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Contrat | [`PHASE_4_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_2_SPECIFICATIONS_DETAILLEES.md) |
| Date | 23 septembre 2026 |
| Autorisation | Décisions `P4.2-01` à `P4.2-08` validées ; GO d’implémentation donné |
| État | Socle 4.2 implémenté ; verrou qualité local VERT le 24 septembre 2026 à 00:11 UTC ; recette fonctionnelle en 4.6 |

## 1. Réalisation

| Contrat | Réalisation |
| --- | --- |
| File durable | Migration `20260923_0022` : `jobs`, `job_scheduler_state`, `job_attempts`, `job_events`, `worker_heartbeats`, contraintes, index et RLS forcée. |
| Isolation du planificateur | Rôle de connexion `prospect_worker` distinct du Web ; fonctions `claim_job`, `purge_jobs` et consultation opérateur détenues par un rôle non connectable, sans privilège CRM ni `BYPASSRLS`. |
| Admission | `PostgresJobQueue.enqueue` rejoint la transaction du producteur, contrôle organisation/adhésion, capacité de 100 travaux et clé idempotente HMAC. Aucun producteur métier de 4.3/4.5 n’est encore activé. |
| Exécution | Processus `backend.app.cli.worker` séparé de l’API ; réservation équitable, un travail actif par organisation, bail de 90 s, renouvellement à 20 s, trois tentatives et reprise après perte de bail. |
| Sûreté | Jeton de possession vérifié avant transition, fermeture atomique des tentatives, refus d’une confirmation tardive, nouvelle vérification de l’adhésion et de l’organisation avant effet. |
| Exploitation | Santé du processus par heartbeat, compteurs de file, latences et codes de tentative, détection des contrats inconnus, inspection des travaux en échec, relance interne motivée avec nouvel ID et lien vers l’échec, balayage borné des métadonnées et CSV expirés. |
| QA | Même image que l’API, service worker sans port public, deux processus via Compose, volume privé partagé pour les CSV ; provisionnement du rôle worker avant migration. |

Le seul gestionnaire enregistré en 4.2 est `internal_probe:1`, sans effet métier et sans route HTTP publique. Les
exports, imports massifs et connecteurs enregistreront leurs propres types, contrôles d’autorisation et effets
idempotents dans leurs lots. L’import CSV 3.1 demeure synchrone.

## 2. Configuration et mise en service QA

Avant de lancer `scripts/qa-deploy.sh`, renseigner dans `.env.qa` les variables
`POSTGRES_WORKER_PASSWORD`, `WORKER_DATABASE_URL` et `JOB_IDEMPOTENCY_HMAC_KEY` à partir de
[`.env.qa.example`](../.env.qa.example), avec deux secrets distincts de ceux du rôle Web. Le script arrête l’API et
les workers, provisionne les rôles, applique la migration, puis redémarre l’API et deux workers. Le volume
`prospect-qa-import-temp` est privé et monté uniquement sur l’API et les workers.

Le contrôle opérateur se fait dans le conteneur worker avec `python -m backend.app.cli.worker health`, `status`,
`failures` ou `inspect <job_id>`. `enqueue-probe <organization_id> <actor_id> <membership_id>` vérifie le parcours
durable sans effet métier. `replay-probe <old_job_id> <actor_id> <membership_id> <reason_code>` exige un ancien travail
échoué, un motif codifié (`dependency_recovered`, `authorization_restored` ou `operator_verified`) et une adhésion
Admin active ; il crée un nouvel ID et conserve le lien et le motif de relance. Ces commandes nécessitent l’accès
opérateur au conteneur et ne sont pas exposées par l’API.

Le déploiement multi-hôte de travaux à fichiers reste interdit tant qu’un stockage privé partagé ou objet, ses
garanties de chiffrement et sa suppression vérifiable ne sont pas contractualisés. Aucun fichier d’export n’est
produit en 4.2.

## 3. Vérifications et verdict technique

| Contrôle | Résultat |
| --- | --- |
| Ruff sur le backend et les tests 4.2 | VERT |
| mypy sur le projet | VERT — 189 fichiers source |
| Format Ruff sur le backend et les tests 4.2 | VERT |
| Alembic `heads` | `20260923_0022 (head)` |
| Génération SQL Alembic hors ligne pour `0021 → 0022` | VERT ; ne valide pas l’exécution sur PostgreSQL |
| Tests backend hors intégration | 255 réussis, 60 tests d’intégration exclus |
| Frontend | ESLint VERT ; Vitest 44 fichiers et 193 tests réussis ; compilation Vite VERT |
| Collecte du test `tests/integration/test_durable_jobs.py` | 1 test collecté |
| Analyse YAML de `compose.yaml`, `compose.qa.yaml`, `compose.test.yaml` et `azure-pipelines.yml` | Quatre fichiers valides |
| Migrations et test 4.2 sur PostgreSQL réel | VERT — migration `20260923_0022` appliquée ; 315 tests backend réussis, zéro échec et zéro skip |
| Verrou qualité complet | **VERT** — [rapport automatisé](../test-results/quality-summary.md) du 24 septembre 2026 à 00:11 UTC ; 193 tests frontend réussis, zéro échec |

Le test PostgreSQL ajouté couvre l’admission annulée par `ROLLBACK`, la déduplication, le refus d’une clé réutilisée,
la lecture RLS, le refus de la fonction privilégiée au rôle Web, deux réservations concurrentes, la perte de bail,
le refus de l’ancien jeton, la limite de 100 admissions, 20 réservations concurrentes, deux reprises temporisées,
l’épuisement des trois tentatives, un échec permanent, une relance Admin motivée, l’annulation, la révocation
d’adhésion, la détection d’un contrat inconnu et la purge. Son exécution réelle est validée par le verrou local VERT.

Le premier passage réel a confirmé le provisionnement et l’application de la migration, puis a révélé deux défauts :
un paramètre `state` utilisé avec deux types SQL dans la clôture d’un travail, et une attente de politiques RLS restée
à l’état antérieur à 4.2. La clôture utilise désormais deux paramètres booléens pour ses conditions ; le test RLS
inclut les deux politiques worker et vérifie qu’elles restent limitées à `SELECT` pour ce rôle. Les contrôles hors
intégration sont restés verts ; le troisième passage a validé leur correction sur PostgreSQL réel.

Au second passage, les deux défauts précédents sont levés. Une réservation immédiate après admission restait parfois
invisible, car `available_at` était fixée par l’horloge Python et comparée à l’horloge PostgreSQL. Les dates
d’admission et de disponibilité sont désormais fixées dans la transaction PostgreSQL. Le troisième passage du verrou
a confirmé ce correctif et les 315 tests backend.

La recette fonctionnelle reste regroupée au lot 4.6 conformément à la décision produit ; elle n’est pas présumée
par les contrôles techniques de 4.2.

## 4. Suites de mise en service

Le [verrou local](../test-results/quality-summary.md) a confirmé le provisionnement du rôle worker, l’application
réelle de `20260923_0022`, la concordance Alembic, les tests d’intégration, la suite complète sans skip et le build.
La configuration QA, le déploiement et la surveillance externe restent des opérations distinctes avant mise en service
sur l’environnement QA. La recette fonctionnelle globale reste au lot 4.6.

L’absence totale de workers doit être surveillée depuis l’hôte ou l’outil de supervision de Compose : un worker
arrêté ne peut pas émettre lui-même cette alerte. Le healthcheck du service échoue lorsque sa présence en base
devient obsolète ; le branchement d’une notification externe doit être confirmé pendant la qualification QA.
