# Phase 2.1 — Rapport d’implémentation

| Métadonnée | Valeur |
| --- | --- |
| Incrément | 2.1 — Socle PostgreSQL, Redis et migrations |
| Date | 23 juillet 2026 |
| Statut | Implémenté, double revue terminée, infrastructure locale validée |
| Changement fonctionnel de la phase 1 | Aucun |

## 1. Résultat livré

- dépendances SQLAlchemy 2, Alembic, asyncpg et redis-py figées ;
- configuration PostgreSQL et Redis centralisée et validée ;
- secrets masqués dans la représentation de `Settings` ;
- moteur PostgreSQL asynchrone avec pool borné, `pool_pre_ping`, délais de connexion et délai SQL ;
- client Redis asynchrone avec délais et nombre maximal de connexions ;
- port `UnitOfWork` et implémentation SQLAlchemy transactionnelle ;
- sondes injectables et routes `/api/health/live` et `/api/health/ready` ;
- fermeture des ressources par le cycle de vie FastAPI ;
- convention de nommage SQLAlchemy et révision Alembic de référence ;
- environnements Compose séparés pour développement et tests ;
- tests d’intégration PostgreSQL/Redis dédiés ;
- contrôle Alembic et services réels rendus obligatoires dans Azure Pipelines ;
- documentation locale et variables d’environnement actualisées.

La route historique `/api/health`, la recherche Google limitée, la carte protégée et l’interface de phase 1 restent inchangées.

## 2. Critique experte 1 — Architecture et sécurité

### Constats initiaux

1. L’URL du compte de migration était chargée dans le processus Web.
2. Les URL contenant des mots de passe et les clés Google pouvaient apparaître dans `repr(Settings)`.
3. La validation CORS de production reposait sur une recherche textuelle insuffisante.
4. Une erreur de fermeture Redis pouvait empêcher la fermeture PostgreSQL.
5. Une unité de travail déjà validée permettait encore d’accéder à sa session avant la sortie du contexte.

### Corrections appliquées

- Alembic lit `MIGRATION_DATABASE_URL` directement ; l’application Web ne la charge jamais ;
- les URL PostgreSQL/Redis et les clés Google sont marquées `repr=False` ;
- les origines de production sont analysées et doivent être des origines HTTPS publiques sans chemin, identifiants, requête ou fragment ;
- le conteneur tente de fermer toutes les ressources et agrège les erreurs ;
- l’accès à la session est refusé après `commit()` ou `rollback()` ;
- des tests protègent la fermeture complète, la confidentialité des secrets et les origines interdites.

### Conclusion de la revue 1

Les frontières Clean Architecture sont respectées : les protocoles de santé, de ressource et d’unité de travail restent dans l’application, tandis que SQLAlchemy et Redis restent dans l’infrastructure.

## 3. Critique experte 2 — Exploitation et maintenabilité

### Constats initiaux

1. Le pool Redis n’était pas borné.
2. Une requête SQL pouvait rester active sans limite serveur explicite.
3. Les tests réels pouvaient être ignorés si les URL disparaissaient accidentellement de la CI.
4. La CI démarrait Docker avant Ruff et mypy, augmentant inutilement le temps et les ressources en cas d’échec statique.

### Corrections appliquées

- `REDIS_MAX_CONNECTIONS=20` par défaut, configurable et validé ;
- `DATABASE_STATEMENT_TIMEOUT_MS=15000` par défaut, transmis à asyncpg ;
- `REQUIRE_INFRASTRUCTURE_TESTS=true` fait échouer la CI si PostgreSQL ou Redis manque ;
- Docker démarre après Ruff, formatage et mypy ;
- l’environnement de test utilise des volumes temporaires et est supprimé par une étape `always()` ciblée.

### Conclusion de la revue 2

Les ressources sont bornées, les pannes produisent une readiness négative sans fuite de détail, et la CI ne peut plus déclarer l’incrément valide en ayant silencieusement ignoré les tests d’infrastructure.

## 4. Résultats des contrôles locaux

| Contrôle | Résultat |
| --- | --- |
| Ruff | Vert |
| Ruff format | Vert, 76 fichiers |
| mypy strict | Vert, 61 fichiers |
| pytest au verrou 2.1 | 48 réussis, aucun test ignoré, avec PostgreSQL et Redis réels |
| Alembic réel | Base vide migrée jusqu’à `20260722_0001` et `alembic check` vert |
| Validation Compose | Fichiers développement et test valides |
| ESLint | Vert |
| Vitest | 4 fichiers, 9 tests réussis |
| Build Vite | Vert |

## 5. Validation d’infrastructure

Après le redémarrage de la machine, Docker Desktop et son moteur Linux sont devenus accessibles. PostgreSQL et Redis ont été démarrés avec `compose.test.yaml`, puis les contrôles ont été rejoués avec `REQUIRE_INFRASTRUCTURE_TESTS=true`.

Les validations portent notamment sur :

- la disponibilité conjointe PostgreSQL et Redis ;
- le rollback transactionnel PostgreSQL d’une unité de travail ;
- la migration d’une base réelle jusqu’à `head` ;
- l’absence de différence de schéma selon Alembic.

La validation locale d’infrastructure est donc levée. La première exécution Azure Pipelines reste requise pour confirmer la reproductibilité dans l’environnement CI.

## 6. Risques résiduels acceptables pour 2.1

- les rôles PostgreSQL propriétaire et applicatif ne sont pas encore séparés dans Compose ; cette séparation deviendra obligatoire avec les tables et RLS ;
- la readiness vérifie la connectivité, pas encore la compatibilité de la révision de schéma au démarrage ; les migrations sont actuellement un verrou de déploiement CI ;
- les adaptateurs mémoire des verrous de recherche et jetons de carte restent volontairement actifs jusqu’à l’incrément 2.6 ;
- aucun modèle métier n’est créé par la révision de référence, conformément au périmètre 2.1.

## 7. Condition de validation

L’incrément 2.1 est validé localement sur les plans fonctionnel, architectural et infrastructure. Le passage à 2.2 était autorisé ; la validation CI formelle reste conditionnée au premier pipeline Azure vert.
