# Phase 2.4.1 — Rapport d’implémentation du schéma d’audit append-only

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Incrément | 2.4.1 — Schéma et primitive append-only |
| Date | 9 août 2026 |
| Statut | Implémenté — preuves intégrées au verrou 2.4.2, recette manuelle cumulée après 2.4.3 |
| Migration | `20260809_0006_audit_append_only.py` |
| Tête attendue | `20260809_0006 (head)` |
| Contrat | `PHASE_2_4_SPECIFICATIONS_DETAILLEES.md` version 1.1 |

## 1. Résultat livré

2.4.1 introduit le socle transactionnel de l’audit sans brancher les mutations métier existantes et sans changement
visuel :

- objet immuable `AuditEventDraft` et registre fermé des dix-sept actions initiales ;
- port applicatif `AuditRecorder` indépendant de SQLAlchemy ;
- politique de métadonnées par liste blanche, types et valeurs autorisées ;
- adaptateur `SqlAlchemyAuditRecorder` utilisant exclusivement la session reçue, sans transaction ni `commit()` ;
- table PostgreSQL `audit_events`, contraintes, clés étrangères et cinq index ;
- fonction `SECURITY DEFINER` `app_private.append_audit_event` comme seule primitive d’ajout du rôle Web ;
- RLS forcée et politiques de lecture distinctes `tenant` et `platform` ;
- tests unitaires et tests PostgreSQL réels pour atomicité, isolation et privilèges.

Conformément au découpage validé, aucune mutation organisation, membre, invitation ou provisioning n’écrit encore
d’événement. Ce branchement atomique appartient à 2.4.2. Aucune API de lecture ni interface d’audit n’est exposée ;
elles appartiennent à 2.4.3.

## 2. Défense en profondeur

Le rôle `prospect_app` reçoit uniquement `SELECT` sur `audit_events` et `EXECUTE` sur la fonction append-only. Il ne
reçoit aucun privilège direct `INSERT`, `UPDATE`, `DELETE` ou `TRUNCATE`. La fonction :

- appartient à `prospect_rls_definer`, rôle non-login distinct du Web ;
- possède un `search_path` fixe et qualifie les objets SQL ;
- vérifie `request_id`, acteur, organisation et portée depuis les variables locales de transaction ;
- vérifie l’appartenance active pour une écriture locataire et le rôle réel `platform_admin` pour la plateforme ;
- refuse une source API avec acteur système ;
- laisse les contraintes PostgreSQL contrôler formats, objet JSON, taille de 8 Kio et version positive ;
- utilise l’horloge PostgreSQL pour `occurred_at`.

Le domaine ajoute une barrière préalable : action connue, portée correspondante, type d’entité attendu, UUID internes,
codes autorisés, absence de clé inconnue et métadonnées immuables. Les courriels, secrets, données Google et textes
libres ne possèdent aucun chemin accepté dans la politique.

## 3. Schéma et index

`audit_events` ne possède aucune colonne de modification ou suppression. Les clés étrangères vers `organizations`
et `users` utilisent `ON DELETE RESTRICT`. Les index couvrent :

- flux chronologique d’une organisation et d’une portée ;
- historique d’une entité ;
- historique d’un acteur ;
- recherche par `request_id` ;
- flux plateforme au moyen d’un index partiel.

La migration refuse un environnement où les rôles PostgreSQL ne respectent pas les attributs attendus. Son downgrade
refuse de supprimer une table contenant des événements.

## 4. Preuves automatiques du 9 août 2026

| Contrôle | Résultat |
| --- | --- |
| Génération SQL Alembic hors ligne | Verte jusqu’à `20260809_0006` |
| Ruff | Vert |
| Ruff format | Vert — 151 fichiers conformes avant ajout du rapport |
| mypy strict | Vert — 115 fichiers source |
| pytest hors infrastructure | Vert — 131 réussites, 37 scénarios réels désélectionnés |
| Tests unitaires audit dédiés | Verts — 12 scénarios dédiés |
| npm audit | Vert après verrouillage transitif de `nanoid` en `3.3.18` |
| ESLint | Vert |
| Vitest avec axe | Vert — 126 réussites dans 29 fichiers |
| Build Vite | Vert — 70 modules transformés |
| `git diff --check` | Vert avant finalisation documentaire |

Le moteur Docker local n’est pas accessible depuis le bac à sable. L’autorisation d’exécuter le verrou hors bac à
sable n’a pas été accordée pendant cette session. En conséquence, le rapport ne prétend pas que la migration en ligne,
`alembic current/check` ou les trois tests PostgreSQL de ce lot sont verts. Ils restent une barrière explicite avant
le GO de 2.4.2.

## 5. Tests PostgreSQL préparés

`tests/integration/test_audit_append_only.py` contient trois preuves réelles :

1. un événement réussi est validé avec la mutation, tandis qu’un échec d’audit annule la mutation métier ;
2. RLS sépare deux organisations, refuse Sales et sépare strictement plateforme et locataire ;
3. les privilèges et tentatives réelles prouvent l’absence de DML direct, le propriétaire de la fonction, son
   `search_path`, l’absence de droit `PUBLIC` et la présence des deux politiques forcées.

## 6. Critique experte 1 — Sécurité et confidentialité

Point fort : l’append-only ne repose pas sur une convention Python. Il est matérialisé par les privilèges PostgreSQL,
une fonction au propriétaire séparé et RLS forcée. Un oubli de route ou une erreur React ne peut donc pas accorder une
modification du journal.

Point renforcé pendant la revue : le domaine lie maintenant chaque action à sa portée et à son type d’entité. Sans
cette règle, un événement valide syntaxiquement aurait pu être classé dans le mauvais flux.

Risque résiduel : le propriétaire de migration et un administrateur PostgreSQL conservent naturellement des pouvoirs
élevés. Le scellement cryptographique, WORM et l’ancrage externe restent explicitement hors V1. La procédure d’accès
aux rôles privilégiés devra être documentée avant production.

## 7. Critique experte 2 — Architecture et exploitabilité

Point fort : le port demeure dans l’application, le modèle et la politique dans le domaine, et SQLAlchemy dans
l’adaptateur. L’adaptateur n’ouvre aucune transaction et ne valide jamais la session, ce qui rend possible l’atomicité
exigée en 2.4.2.

Point fort : le registre fermé empêche une route de fournir un dictionnaire ou un code d’action arbitraire. L’ajout
d’une future action impose une modification explicite, des métadonnées typées et un test.

Risque résiduel : aucun cas d’utilisation existant n’emploie encore le port. Cette absence est intentionnelle en
2.4.1, mais elle signifie que le journal restera vide tant que 2.4.2 n’aura pas branché chaque transition. Il ne faut
donc pas présenter l’audit comme fonctionnel à l’utilisateur avant 2.4.3.

## 8. Procédure de validation locale

Le verrou complet utilise uniquement la composition de test isolée et supprime ses volumes à la fin :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test-QualityGateLocal.ps1
```

Pour contrôler uniquement 2.4.1 :

```powershell
$project = "marketteo-audit-241"
docker compose -p $project -f compose.test.yaml up -d --wait
docker compose -p $project -f compose.test.yaml run --rm database-role-provisioner

$env:TEST_DATABASE_URL = "postgresql+asyncpg://prospect_app:prospect-app-test-only@127.0.0.1:55432/prospect_test"
$env:TEST_MIGRATION_DATABASE_URL = "postgresql+asyncpg://prospect_test:prospect-test-only@127.0.0.1:55432/prospect_test"
$env:MIGRATION_DATABASE_URL = $env:TEST_MIGRATION_DATABASE_URL
$env:REQUIRE_INFRASTRUCTURE_TESTS = "true"

.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini current
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini check
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests\integration\test_audit_append_only.py

docker compose -p $project -f compose.test.yaml down --volumes --remove-orphans
```

Résultats attendus : `20260809_0006 (head)`, aucune opération Alembic nouvelle et `3 passed` sans `skip`.

## 9. Décision de passage

Le code de 2.4.1 est prêt pour la validation. Le responsable produit a ensuite choisi de regrouper sa recette manuelle
avec celles de 2.4.2 et 2.4.3, lorsque le journal sera consultable. Les trois preuves PostgreSQL de 2.4.1 et
`alembic check` restent intégrés au verrou automatisé de l’implémentation 2.4.2 ; ils ne sont ni supprimés ni déclarés
validés par anticipation.
