# Phase 2.3.4 — Rapport d’implémentation

| Métadonnée | Valeur |
| --- | --- |
| Produit | Prospect CRM |
| Incrément | 2.3.4 — Protection Google et transition de l’écran |
| Date | 2 août 2026 |
| Statut | Implémenté et validé localement par le responsable produit ; barrière infrastructure conservée avant déploiement |
| Migration | Aucune nouvelle migration ; tête attendue `20260802_0005` |
| Version API | `1.5.0` |
| Contrat | `PHASE_2_3_4_SPECIFICATIONS_DETAILLEES.md` version 1.0 |
| Validation produit | 2 août 2026 |

## 1. Résultat livré

Les seize décisions validées sont traduites dans le code. Les routes Google facturables ne font plus confiance à une
identité déclarée dans le corps HTTP. Elles exigent désormais une session valide, une organisation active, une
capacité explicite, une origine approuvée, le CSRF de la session et du JSON strict.

Le comportement Google reste volontairement inchangé :

- exactement un Text Search par action acceptée ;
- `pageSize=20`, vingt résultats au maximum et aucun suivi de `nextPageToken` ;
- aucun téléphone ni site Web dans la liste ;
- aucune persistance des résultats Google ;
- au maximum une tentative Maps Static par concession ;
- attribution Google Maps visible et export historique absent.

## 2. Backend

### 2.1 Autorisation et contexte

- `google:search` et `google:map` sont deux capacités distinctes attribuées aux rôles Admin, Manager et Sales.
- Le rôle `platform_admin` ne confère aucun accès Google implicite.
- `GoogleAccessContext` porte les identifiants internes de l’utilisateur, de l’organisation et de l’appartenance.
- `required_google_access` centralise JSON, origine, session, organisation active, capacité et CSRF.
- La configuration des clés n’est vérifiée qu’après l’autorisation d’une commande valide.
- Les erreurs Google utilisent l’enveloppe commune, un `request_id`, des messages contrôlés et `no-store`.

### 2.2 Commandes strictes

- `requester` a été supprimé du schéma et des mappers.
- `organization_id`, `user_id`, `membership_id` et tout champ inconnu sont refusés par Pydantic.
- La commande de carte refuse également les champs inconnus.
- Les réponses de validation Google ne recopient pas les valeurs reçues.

### 2.3 Verrou et concessions

- Le port de verrou reçoit un `GoogleAccessOwner` construit avec `(user_id, organization_id)`.
- Deux recherches concurrentes du même acteur locataire sont refusées avant le fournisseur.
- Des utilisateurs ou organisations différents possèdent des clés de verrou différentes.
- Une annulation ou une exception libère le verrou.
- Une concession contient au moins 256 bits aléatoires, expire au plus tard après cinq minutes en production et est
  liée à son utilisateur et à son organisation.
- Un acteur étranger ne consomme pas la concession du propriétaire.
- Une concession en cours n’est jamais évincée.
- Le premier essai Maps est terminal, y compris sur erreur du fournisseur ; aucun rejeu facturable n’est possible.

Les deux adaptateurs restent en mémoire et mono-instance conformément au périmètre validé. Ils ne permettent pas un
déploiement horizontal avant leur remplacement par un stockage partagé prévu dans un incrément ultérieur.

## 3. Frontend

- `IdentityModal`, `initialRequester`, ses états React et ses styles ont été retirés.
- Un clic lance directement la recherche avec les seuls paramètres Google autorisés.
- La route principale exige `google:search` avant de rendre l’écran.
- Un compte sans organisation et un Administrateur plateforme sans appartenance restent dans l’état restreint.
- Sans `google:map`, la recherche reste disponible mais aucun appel automatique de carte n’est exécuté.
- L’URL `blob:` de la carte est révoquée au démontage et aucune relance automatique n’est introduite.
- L’export reste visible et désactivé ; l’attribution Google Maps reste visible.

## 4. Documentation et exploitation

- Le README décrit le nouveau parcours utilisateur, les capacités, les contrats HTTP et la consommation terminale.
- Les conditions d’utilisation et la politique de confidentialité ne mentionnent plus l’identité déclarative.
- `TRANSITIONAL_FEATURES.md` marque l’identité temporaire et le verrou Unicode comme supprimés.
- `Test-GoogleProtectionLocal.ps1` exige la confirmation `RUN_ONE_GOOGLE_SEARCH`, demande le mot de passe de manière
  interactive et ne montre aucun cookie, CSRF, jeton de carte ou secret.
- L’option `-FetchMap` ajoute au maximum une tentative Maps Static et vérifie `no-store` sans sauvegarder l’image.
- Azure Pipelines contient déjà Ruff, formatage, mypy, Alembic, pytest avec infrastructure réelle, ESLint, Vitest et
  le build Vite ; aucun assouplissement n’a été ajouté.

## 5. Preuves automatiques du 2 août 2026

| Contrôle | Résultat |
| --- | --- |
| Ruff | Vert — `All checks passed!` |
| Ruff format | Vert — 142 fichiers formatés |
| mypy | Vert — 110 fichiers source |
| pytest complet sans variables d’infrastructure | 132 réussis, 17 ignorés |
| Tests hors marqueur intégration | 115 scénarios collectés et couverts par le passage complet |
| Intégration API Google simulée | 17 réussis |
| Intégration PostgreSQL/Redis/Mailpit | 17 ignorés : moteur Docker Linux indisponible dans cette session |
| ESLint | Vert, zéro avertissement |
| Vitest | Vert — 28 tests dans 9 fichiers |
| Build Vite | Vert — 48 modules transformés |
| Syntaxe PowerShell du script local | Verte |
| `git diff --check` | Vert |

Le moteur Docker Desktop a été lancé, mais son canal Linux est resté indisponible. Une nouvelle vérification Docker
n’a pas été autorisée. Par conséquent, ce rapport ne prétend pas que les 17 scénarios réels ni `alembic current/check`
ont été rejoués pendant cette session. La tête attendue reste celle validée en 2.3.3 : `20260802_0005`.

### 5.1 Validation locale du responsable produit

Le responsable produit a ensuite confirmé les deux parcours facturables contrôlés :

- Places seul : `GoogleCalls=1`, `MapCalls=0`, 20 résultats, contacts absents et `no-store` ;
- Places avec carte : `GoogleCalls=1`, `MapCalls=1`, 20 résultats, contacts absents et `no-store`.

Il a également obtenu Ruff, formatage, mypy, ESLint, 28 tests React et le build Vite au vert. Pytest a confirmé
`132 passed, 17 skipped` avec un avertissement de cache OneDrive sans effet fonctionnel. L’incrément est donc accepté
pour poursuivre la migration, mais les 17 tests d’infrastructure doivent encore passer sans `skip` avant tout
déploiement.

## 6. Trois critiques expertes

### Critique 1 — Sécurité offensive

Le changement ferme la faiblesse principale : le navigateur ne choisit plus l’acteur ni le locataire. Un jeton de
carte volé est inutilisable par un autre utilisateur de la même organisation, par une autre organisation ou après un
changement d’organisation. L’ordre session/organisation/capacité/CSRF et les réponses minimisées réduisent les
possibilités d’énumération et de fuite fournisseur.

Risque résiduel accepté : une commande déjà autorisée et en vol peut atteindre Google juste après une révocation
concurrente de session ou de rôle. Les requêtes suivantes sont refusées ; interrompre de manière distribuée un appel
HTTP déjà parti demanderait une coordination hors périmètre.

### Critique 2 — Concurrence, disponibilité et coût

Le verrou empêche deux Places simultanés pour un acteur locataire et le jeton terminal empêche un second Maps après
un échec ambigu. Les tests couvrent exception, annulation, concurrence, expiration, éviction et saturation.

Risque résiduel accepté : si Places réussit puis que le registre mémoire est totalement occupé par des concessions en
cours, l’appel Places a été facturé alors que la réponse finale devient `503 map_grant_unavailable`. Une réservation
de capacité distribuée avant Places sera préférable lors du passage à Redis.

### Critique 3 — Exploitabilité et expérience utilisateur

L’écran est plus simple et les refus sont contrôlés. Le script local rend les appels réels explicites et évite les
fuites de secrets. La documentation est cohérente avec l’interface.

Limites assumées : le sélecteur visuel d’organisation et l’administration des capacités n’appartiennent pas à 2.3.4 ;
le message d’accès refusé reste générique. La validation manuelle doit donc utiliser les scripts et plusieurs comptes
jusqu’à la livraison des écrans d’administration.

## 7. Deux revues de code

### Revue A — Architecte sécurité et identité

Périmètre relu : routes Google, contexte d’accès, matrice de capacités, origine/CSRF, erreurs, verrou et concessions.

Conclusion : aucun défaut bloquant identifié. Les invariants sont appliqués côté serveur et non seulement dans React.
Les tests prouvent le refus sans session, sans organisation, sans capacité, avec origine/CSRF invalides, ainsi que les
vols inter-utilisateur et inter-organisation. Les détails du fournisseur ne sont pas renvoyés.

Décision : acceptable pour une instance unique et une validation locale ; non autorisé en réplication horizontale tant
que les adaptateurs mémoire n’ont pas été remplacés.

### Revue B — Architecte Clean Architecture et fiabilité

Périmètre relu : dépendances entre couches, ports, cas d’utilisation, adaptateurs mémoire, composants/hooks React,
tests, pipeline et documentation.

Conclusion : aucun défaut bloquant identifié. Le domaine et l’application restent indépendants de FastAPI, React et
des adaptateurs. Les ports expriment le propriétaire sans dépendre du transport HTTP. Les cas d’utilisation ne lisent
ni cookie ni capacité et reçoivent un contexte déjà autorisé. Le test de frontières architecturales reste vert.

Décision : cohérent avec SOLID et Clean Architecture. Le prochain durcissement structurel est le remplacement des deux
adaptateurs mémoire et l’ajout de métriques opérationnelles de refus, saturation et coût, sans changer les ports.

## 8. Protocole local de validation

### 8.1 Infrastructure et migration

```powershell
docker compose up -d --wait
docker compose ps
docker compose run --rm database-role-provisioner
$env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://prospect:prospect-development-only@127.0.0.1:5432/prospect"
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini current
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini check
```

Attendu : `20260802_0005 (head)`, sans nouvelle révision.

### 8.2 Backend et frontend

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://prospect_app:prospect-app-development-only@127.0.0.1:5432/prospect"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000 --env-file .env
```

Dans un second terminal :

```powershell
Set-Location client
npm run dev
```

Vérifier `http://127.0.0.1:8000/api/health/ready`, puis se connecter sur `http://localhost:5173` avec un membre actif.

### 8.3 Parcours Google contrôlé

```powershell
.\scripts\Test-GoogleProtectionLocal.ps1 `
  -AdministratorEmail "membre@example.ca" `
  -ConfirmGoogleCall RUN_ONE_GOOGLE_SEARCH `
  -FetchMap
```

Vérifier ensuite dans le navigateur : absence du dialogue d’identité, vingt résultats maximum, attribution visible,
export désactivé, aucun stockage navigateur et une seule requête Places/Maps. Changer d’organisation avant de tenter
une ancienne concession doit produire un refus sans appel Maps.

### 8.4 Matrice qualité

```powershell
.\.venv\Scripts\python.exe -m ruff check backend/app tests
.\.venv\Scripts\python.exe -m ruff format --check backend/app tests
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -q
Set-Location client
npm run lint
npm test
npm run build
```

La validation fonctionnelle 2.3.4 est acquise. La barrière de déploiement reste fermée jusqu’au passage des 17 tests
d’infrastructure sans `skip`, au contrôle Alembic et au parcours manuel multi-organisation.
