# Rapport d’implémentation — Incrément 2.5.3

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Incrément | 2.5.3 — Provenance, permissions et fournisseurs |
| Statut | Implémentation réalisée ; recette locale PostgreSQL à finaliser |
| Date | 14 août 2026 |
| Révision Alembic cible | `20260814_0010` |

## 1. Résultat livré

L’incrément ajoute le socle backend de conformité des sources d’acquisition :

- fournisseurs locataires avec cycle de vie `draft`, `active`, `suspended`, `retired` ;
- contrats, territoires, finalités, catégories de données et attestation de droits ;
- acquisitions déclaratives, idempotentes, approuvées ou mises en quarantaine sans données brutes ;
- provenance créée côté serveur pour les contacts et canaux ;
- permission `unknown` créée atomiquement pour chaque canal ;
- restriction `do_not_contact` ou `opted_out` propagée aux canaux identiques de l’organisation ;
- capacités applicatives 2.5.3 selon la matrice validée ;
- API backend sans changement visuel.

## 2. Fichiers principaux

- Domaine : `backend/app/domain/prospect.py`, `backend/app/domain/audit.py`, `backend/app/domain/identity.py`
- Cas d’utilisation : `backend/app/application/use_cases/prospect_compliance.py`
- Ports : `backend/app/application/ports/prospect.py`
- PostgreSQL : `backend/app/infrastructure/postgres/prospect_repository.py`, `backend/app/infrastructure/postgres/prospect_unit_of_work.py`
- Migration : `backend/app/infrastructure/postgres/migrations/versions/20260814_0010_prospect_compliance.py`
- API : `backend/app/presentation/api/routers/prospect_compliance.py`, `backend/app/presentation/api/schemas.py`
- Qualité : `scripts/Test-QualityGateLocal.ps1`, `azure-pipelines.yml`

## 3. API ajoutées

- `GET /api/source-providers`
- `POST /api/source-providers`
- `GET /api/source-providers/{provider_id}`
- `PATCH /api/source-providers/{provider_id}`
- `GET /api/acquisitions`
- `POST /api/acquisitions`
- `GET /api/acquisitions/{acquisition_id}`
- `POST /api/acquisitions/{acquisition_id}/decision`
- `POST /api/prospects/{prospect_id}/contacts`
- `GET /api/prospects/{prospect_id}/contacts`
- `POST /api/contact-channels`
- `GET /api/contact-channels/{channel_id}/permission`
- `PATCH /api/contact-channels/{channel_id}/permission`

Toutes ces réponses sont protégées par session, organisation active, capacités applicatives et `Cache-Control:
no-store`. Les mutations exigent origine fiable, CSRF et `application/json`.

## 4. Validation exécutée

Contrôles verts :

- `pytest` : 182 tests passés, 29 tests d’intégration ignorés faute d’URL PostgreSQL dans la session Codex ;
- tests ciblés 2.5.3 : 21 passés ;
- `ruff check` : vert ;
- `ruff format --check` : vert ;
- `mypy` : vert ;
- `alembic heads` : `20260814_0010 (head)` ;
- `alembic history -r 20260814_0009:head` : chaîne 0009 → 0010 conforme ;
- `npm.cmd run lint` : vert ;
- `npm.cmd run test:ci` : 31 fichiers, 135 tests passés ;
- `npm.cmd run build` : vert.

Contrôle non exécuté dans cette session :

- `alembic check`, bloqué par absence de `MIGRATION_DATABASE_URL` ou `DATABASE_URL` dans l’environnement Codex.

## 5. Double critique

### Critique 1 — Architecture et maintenabilité

Le découpage respecte l’intention Clean Architecture : le domaine porte les règles de source, le use case orchestre les
transactions, les routes restent minces et PostgreSQL applique les contraintes durables. La principale dette assumée
est que les repositories SQL grossissent ; ce sera acceptable jusqu’à l’écran 2.5.5, puis il faudra surveiller la taille
du fichier et extraire éventuellement des repositories par agrégat.

### Critique 2 — Conformité et risque produit

Le système bloque la confusion entre provenance et permission : un canal créé démarre à `unknown`, une acquisition non
conforme reste au niveau métadonnée, et Google demeure exclu des coordonnées persistantes. La limite restante est
volontaire : 2.5.3 ne traite pas encore le parsing CSV, la purge ni l’interface de revue. Ces sujets doivent rester dans
2.5.4 et 2.5.5 pour éviter un faux sentiment de conformité complète.

## 6. Recette locale minimale

1. Démarrer PostgreSQL et Redis.
2. Exporter `MIGRATION_DATABASE_URL` et `DATABASE_URL`.
3. Lancer `.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head`.
4. Vérifier `.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini current` : attendu `20260814_0010 (head)`.
5. Lancer `.\scripts\Test-QualityGateLocal.ps1 -DockerMode wsl -WslDistribution "Ubuntu-24.04"` si Docker Windows reste indisponible.
6. Vérifier que le rapport du verrou qualité ne contient aucun skip backend forcé hors configuration volontaire.
