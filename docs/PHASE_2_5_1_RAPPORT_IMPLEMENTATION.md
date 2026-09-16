# Rapport d'implementation — Increment 2.5.1

| Metadonnee | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Increment | 2.5.1 — Modele de donnees et migrations |
| Date | 14 aout 2026 |
| Statut | Implemente et verifie localement |
| Migration | `20260814_0009` |

## 1. Resultat

L'increment 2.5.1 livre le socle persistant des prospects sans changement visuel ni nouvelle route publique.

Elements ajoutes :

- domaine prospects, contacts, canaux, provenance et validations serveur ;
- ports applicatifs `ProspectRepository`, `ContactRepository`, `ContactChannelRepository`, `ProvenanceRepository` et `ProspectUnitOfWork` ;
- adaptateurs PostgreSQL SQLAlchemy confines a l'infrastructure ;
- migration Alembic `20260814_0009_prospect_foundation.py` ;
- modeles ORM PostgreSQL ;
- politiques RLS, privileges limites et trigger de protection de provenance ;
- tests unitaires et integration PostgreSQL.

## 2. Schema livre

Tables creees :

- `source_providers`
- `acquisition_records`
- `provenance_records`
- `prospects`
- `contacts`
- `contact_channels`
- `contact_permissions`

Contraintes importantes :

- `organization_id` obligatoire sur toutes les tables locataires ;
- RLS forcee sur les sept tables ;
- unicite active `(organization_id, google_place_id)` pour les prospects non archives ;
- rattachement inter-organisation bloque par FK composites ;
- canal rattache a exactement une cible : prospect ou contact ;
- provenance obligatoire pour les contacts et canaux ;
- `google_maps` interdit comme provenance d'une coordonnee persistante via domaine et trigger PostgreSQL ;
- suppressions logiques preparees par `archived_at`.

## 3. Audit

Actions d'audit ajoutees :

- `prospect.created`
- `prospect.updated`
- `prospect.archived`
- `contact.created`
- `channel.created`
- `provenance.recorded`

Les metadonnees autorisees restent minimales. Les valeurs de canaux comme courriel ou telephone ne sont pas admises dans les evenements d'audit.

## 4. Verification executee

Commandes passees :

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini current
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini check
.\.venv\Scripts\python.exe -m ruff check backend\app tests scripts\quality_gate.py
.\.venv\Scripts\python.exe -m ruff format --check backend\app tests scripts\quality_gate.py
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -q
```

Resultats :

- Alembic current : `20260814_0009 (head)` ;
- Alembic check : aucun nouvel upgrade detecte ;
- Ruff check : vert ;
- Ruff format check : vert ;
- mypy : vert, 132 fichiers sources ;
- pytest : `188 passed, 7 skipped`.

Note locale : pytest a affiche un avertissement Windows `PermissionError` au nettoyage de `pytest-current` apres la fin de la session. Les tests etaient deja termines avec succes ; ce point releve du nettoyage temporaire Windows, pas du code applicatif.

## 5. Critique experte 1 — Architecture et domaine

Points solides :

- Le domaine ne depend pas de SQLAlchemy, FastAPI ni de l'infrastructure.
- Les ports applicatifs preservent la Clean Architecture et preparent 2.5.2 sans exposer l'ORM aux routes.
- L'interdiction de `google_maps` pour les coordonnees persistantes existe a deux niveaux : domaine et base.
- Les evenements d'audit sont types, ce qui evite les chaines libres non gouvernees.

Points a surveiller :

- Les repositories sont volontairement fins ; les vrais cas d'utilisation de 2.5.2 devront orchestrer audit + mutation de maniere systematique.
- Les statuts commerciaux sont prepares mais pas encore portes par un workflow Kanban complet.
- Les permissions de contact sont creees minimalement ; leur semantique devra etre precisee en 2.5.4.

## 6. Critique experte 2 — Base, RLS et exploitation

Points solides :

- Les FK composites limitent les erreurs inter-locataires meme en dehors des chemins applicatifs.
- Le role `prospect_app` n'obtient pas de droit `DELETE` sur les nouvelles tables.
- Les politiques RLS sont symetriques et basees sur `app_private.current_organization_id()`, pas sur un filtre client.
- L'unicite partielle du `google_place_id` permet de recreer un prospect apres archivage sans perdre l'historique.

Points a surveiller :

- Le downgrade refuse les tables non vides ; c'est volontaire, mais a documenter pour les environnements de recette.
- Les tables nouvellement creees ajoutent de la densite au schema ; les prochains increments devront eviter les duplications d'attributs entre acquisition, provenance et permission.
- Les anciens evenements d'audit plateforme rendent certains tests sensibles si l'on utilise une base de developpement persistante ; un test historique a ete rendu plus robuste.

## 7. Recette locale conseillee

1. Demarrer PostgreSQL et Redis.
2. Charger `.env`.
3. Executer `alembic upgrade head`.
4. Verifier `alembic current` : `20260814_0009 (head)`.
5. Executer `alembic check`.
6. Executer `pytest tests\integration\test_prospect_foundation.py -q`.
7. Executer le verrou backend complet : Ruff, mypy, pytest.

## 8. Decision de sortie

L'increment 2.5.1 est pret pour validation fonctionnelle technique et peut servir de base a 2.5.2 — Socle prospect et ajout Google.
