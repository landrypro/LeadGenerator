# Incrément 2.5.4 — Rapport d’implémentation

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Incrément | 2.5.4 — Conservation et déclarations d’import |
| Statut | Implémentation backend réalisée |
| Date | 14 août 2026 |
| Migration livrée | `20260814_0011_retention_import_declarations.py` |
| Recette humaine | Regroupée avec 2.5.3 et 2.5.5, selon décision produit |

## 1. Résultat livré

2.5.4 ajoute le socle backend de conservation sans changement visuel :

- politiques de conservation locataires, versionnées et activables sans durée par défaut ;
- file de revue calculée pour prospects, contacts, canaux, acquisitions, provenances et déclarations ;
- mises en attente de conservation idempotentes, multiples et libérables par version optimiste ;
- consultation détaillée des politiques et des mises en attente, avec note de hold visible uniquement au détail ;
- déclarations d’import strictement métadonnées, sans fichier, nom de fichier, ligne, cellule ou payload ;
- quarantaine de déclaration par codes contrôlés ;
- archivage logique de prospect, contact, canal et déclaration d’import ;
- capacités Admin/Manager/Sales alignées avec les décisions validées ;
- audit transactionnel avec métadonnées non personnelles ;
- RLS forcée et privilèges minimaux sur les nouvelles tables.

## 2. Fichiers principaux

- Domaine et règles : `backend/app/domain/prospect.py`, `backend/app/domain/audit.py`, `backend/app/domain/identity.py`
- Ports et cas d’usage : `backend/app/application/ports/prospect.py`, `backend/app/application/use_cases/retention.py`
- Adaptateurs PostgreSQL : `backend/app/infrastructure/postgres/prospect_repository.py`,
  `backend/app/infrastructure/postgres/prospect_unit_of_work.py`,
  `backend/app/infrastructure/postgres/models/prospect.py`
- API : `backend/app/presentation/api/routers/retention.py`, `backend/app/presentation/api/schemas.py`,
  `backend/app/presentation/api/mappers.py`
- Migration : `backend/app/infrastructure/postgres/migrations/versions/20260814_0011_retention_import_declarations.py`
- Tests : `tests/test_retention_use_cases.py`, `tests/test_retention_api.py`, `tests/test_organization_domain.py`

## 3. Points de conformité confirmés

- Aucune politique de conservation par défaut n’est créée.
- Aucune suppression physique, purge ou tâche planifiée n’est livrée.
- `import_declarations` ne contient aucune colonne de fichier, chemin, blob, ligne, cellule, aperçu ou nom libre.
- `multipart/form-data` est rejeté sur `/api/import-declarations` avant toute logique d’import.
- Les notes de hold ne sont pas incluses dans l’audit.
- Les listes de holds masquent les notes internes ; seule la lecture détaillée d’un hold les expose à un utilisateur autorisé.
- Les valeurs de canaux, noms de contacts, libellés d’import et empreintes déclarées ne sont pas journalisés.
- Les nouvelles routes retournent `Cache-Control: no-store, max-age=0`.

## 4. Contrôles exécutés

- `python -m compileall backend/app` : vert
- `ruff check .` : vert
- `ruff format --check .` : vert
- `mypy backend` : vert
- `alembic heads` : `20260814_0011 (head)`
- `pytest -q` : 193 passés, 29 skips d’intégration PostgreSQL sans URL réelles
- `pytest tests/test_retention_api.py tests/test_retention_use_cases.py tests/test_prospect_compliance_api.py tests/test_prospect_compliance_use_cases.py -q` : 18 passés
- `npm.cmd run lint` : vert
- `npm.cmd run test:ci` : 135 tests passés
- `npm.cmd run build` : vert

Note : `pytest` a terminé avec succès, puis Windows a émis un avertissement de nettoyage du lien temporaire
`pytest-current`. Cet avertissement n’affecte pas le verdict des tests.

## 5. Critique technique

### 5.1 Critique architecture

Le découpage reste conforme à Clean Architecture : le domaine ne dépend ni de FastAPI ni de SQLAlchemy, les cas
d’usage portent les décisions métier, et les repositories encapsulent les requêtes SQL. Le nouveau routeur `retention`
évite de surcharger le routeur de conformité source.

Limite assumée : l’idempotence complète des archives métier n’a pas encore son propre registre de commandes. Les
archives sont optimistes et transactionnelles, mais le rejeu exact par clé pourra être durci lorsque l’interface 2.5.5
stabilisera les parcours.

### 5.2 Critique données et conformité

La migration est additive et prudente : pas de backfill destructif, pas de valeur légale inventée, RLS forcée et
downgrade refusé si des données 2.5.4 existent. Le déclencheur PostgreSQL contrôle les cibles polymorphes des holds.

Limite assumée : l’unicité active des politiques est volontairement simple, une seule politique active par type de
ressource et organisation. C’est robuste pour V1, mais si Marketteo doit plus tard couvrir plusieurs territoires ou
finalités par politique, il faudra élargir la clé fonctionnelle.

### 5.3 Critique sécurité opérationnelle

Les routes de mutation exigent JSON, origine de confiance, CSRF, session et capacité. Les erreurs restent génériques
pour les ressources inexistantes ou hors locataire. Les tests prouvent le rejet d’un faux upload.

Limite assumée : la recette PostgreSQL réelle de 2.5.4 est différée avec 2.5.3 et 2.5.5. Les contrôles automatisés sont
verts, mais la validation finale RLS sur base réelle doit rester obligatoire avant de clôturer toute la phase 2.5.

## 6. Décision de sortie

L’incrément 2.5.4 est prêt pour la suite 2.5.5 côté développement. La clôture fonctionnelle complète de 2.5.4 reste
liée à la recette groupée 2.5.3–2.5.5 validée par le produit.
