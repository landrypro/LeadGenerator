# Architecture et choix techniques

## Vue d'ensemble

Marketteo CRM suit une architecture applicative separee en client React, API FastAPI, domaine metier, cas d'utilisation, ports applicatifs et adaptateurs d'infrastructure. Les dependances vont vers le domaine et l'application ; les frameworks et fournisseurs restent aux frontieres.

```text
Navigateur React/Vite
        |
        | HTTPS / JSON / cookie session / CSRF
        v
FastAPI presentation/api
        |
        v
Cas d'utilisation application
        |
        | ports applicatifs
        v
Domaine metier pur
        |
        v
Adaptateurs infrastructure
PostgreSQL / Redis / Google / Mailpit / Worker / Export CSV
```

## Architecture logicielle

Cette section consolide l'architecture decrite dans les specifications V1, l'audit technique et le dossier Automatisation. Elle sert de lecture de reference pour comprendre comment le logiciel est decoupe, comment les responsabilites circulent et quelles frontieres ne doivent pas etre contournees.

### Principes directeurs

- **Architecture Clean / hexagonale** : le domaine metier reste au centre, sans dependance aux frameworks, a la base de donnees ou aux fournisseurs externes.
- **Dependances dirigees vers le coeur** : la presentation et l'infrastructure dependent des cas d'utilisation et des ports applicatifs, jamais l'inverse.
- **Multi-tenancy defense en profondeur** : l'organisation active est portee par le contexte applicatif et renforcee par la Row Level Security PostgreSQL.
- **Effets metier controles** : toute creation, modification, import, export ou execution durable passe par un cas d'utilisation, avec autorisation, idempotence et audit.
- **Fournisseurs isoles** : Google, Meta, email, fichiers, cache et futurs connecteurs restent derriere des adaptateurs ; aucune regle metier ne depend directement de leur SDK.
- **IA sans droit d'ecriture direct** : les sorties IA, actuelles ou futures, restent des propositions structurees ; les decisions et effets passent par le moteur de regles, les capacites et les cas d'utilisation CRM.

### Vue logique des couches

| Couche | Role logiciel | Implementation principale | Regle de frontiere |
| --- | --- | --- | --- |
| Interface utilisateur | Presenter les parcours CRM, collecter les intentions et appliquer les gardes visuels. | `client/src/app/`, `client/src/features/`, `client/src/shared/` | Ne detient pas la securite finale ; elle appelle l'API. |
| Presentation HTTP | Traduire HTTP/JSON en commandes applicatives et reponses publiques. | `backend/app/presentation/api/` | Ne contient pas les regles metier centrales. |
| Application | Orchestrer les cas d'utilisation, verifier les capacites, ouvrir les transactions et appeler les ports. | `backend/app/application/use_cases/`, `backend/app/application/ports/` | Ne depend pas des adaptateurs concrets. |
| Domaine | Porter les invariants, transitions, decisions et objets metier purs. | `backend/app/domain/` | N'importe ni FastAPI, ni infrastructure, ni couche application. |
| Infrastructure | Implementer les ports vers PostgreSQL, Redis, Google, fichiers, worker, email et horloge. | `backend/app/infrastructure/` | Ne contourne pas les cas d'utilisation pour produire un effet metier. |
| Execution durable | Executer les travaux longs ou differes avec reprise, idempotence et audit. | `backend.app.cli.worker`, repositories et files PostgreSQL/Redis | Revalide les droits avant effet et evite les doublons au rejeu. |

### Flux logiciel nominal

```text
Utilisateur
  -> React/Vite
  -> API FastAPI
  -> dependances HTTP : session, CSRF, organisation active, locale
  -> cas d'utilisation applicatif
  -> domaine : invariants, transitions et decisions
  -> ports applicatifs
  -> adaptateurs infrastructure : PostgreSQL, Redis, Google, fichiers, worker
  -> audit transactionnel et reponse publique
```

Pour une operation durable, l'API admet la demande, verifie les capacites, enregistre une intention ou une demande de travail, puis le worker reprend l'execution. Le worker ne devient pas une seconde API metier : il repasse par les memes contrats, revalide le contexte et ecrit des traces auditables.

### Frontieres et controles anti-derive

| Frontiere | Controle attendu |
| --- | --- |
| Domaine vers framework | Le domaine ne doit pas importer FastAPI, SQLAlchemy, Redis, Google ou tout adaptateur externe. |
| Application vers infrastructure | Les cas d'utilisation consomment des ports ; les implementations concretes sont injectees au bootstrap. |
| Presentation vers metier | Les routes HTTP valident et traduisent, mais ne dupliquent pas les regles metier. |
| Infrastructure vers CRM | Les repositories et gateways persistent ou recuperent les donnees ; ils ne prennent pas seuls de decision metier. |
| Frontend vers securite | Le frontend masque ou desactive des actions, mais l'autorisation effective reste cote API. |
| Worker vers effets | Le worker execute uniquement des travaux admis, idempotents et revalides. |

L'audit technique mentionne un test de frontieres d'architecture par AST (`tests/test_architecture_boundaries.py`). Ce test est un garde-fou important : il rend mecanique la separation Clean/hexagonale et evite que les couches se melangent progressivement.

### Composants logiciels principaux

| Composant | Responsabilites |
| --- | --- |
| Client React | Navigation, ecrans CRM, recherche Google temporaire, prospects, contacts, pipeline, taches, opportunites, dashboard, imports, exports, usage et surfaces de conformite. |
| API FastAPI | Authentification, sessions, CSRF, validation Pydantic, autorisations, appels aux cas d'utilisation, erreurs publiques uniformes et correlation des requetes. |
| Cas d'utilisation | Auth, organisation, invitations, recherche Google, prospects, pipeline, activites, taches, opportunites, imports CSV, exports CSV, audit, usage et fournisseurs. |
| Domaine CRM | Regles de cycle de vie, permissions, provenance, retention, archivage, transitions et invariants multi-organisation. |
| PostgreSQL | Source de verite CRM, migrations Alembic, contraintes, fonctions securisees, audit append-only et RLS forcee. |
| Redis | Sessions opaques, jetons courts, quotas, rate limits, verrous et donnees ephemeres. |
| Worker | Imports, exports, traitements differes, reprise apres erreur, expiration et travaux de maintenance. |
| Adaptateurs fournisseurs | Google Places/Maps, Mailpit en local/QA, connecteurs approuves et futurs fournisseurs contractuels. |

### Architecture logicielle de l'Automatisation

Le dossier Automatisation ajoute une architecture cible sans effet direct en production tant que la Porte 4 n'est pas prononcee. Le schema logiciel attendu est le suivant :

- une surface utilisateur unique pour formuler ou suivre une intention ;
- un interpreteur d'intention pouvant utiliser l'IA, mais sans acces direct aux ecritures CRM ;
- un plan structure soumis a un moteur de regles deterministe ;
- un Feu relationnel versionne : Vert, Jaune ou Rouge ;
- un Prevol sans effet, utilisant les memes regles que l'execution ;
- un orchestrateur durable pour les actions admises ;
- une revalidation des capacites et de l'organisation active avant chaque effet ;
- des brouillons, approbations, exceptions et journaux auditables ;
- aucun envoi externe autonome en V1.

Cette extension doit reutiliser les objets CRM canoniques. Elle ne doit pas creer un second CRM, ni dupliquer prospects, taches, opportunites, permissions ou journaux pour simplifier l'Automatisation.

### Sources consolidees

| Source locale | Apport principal |
| --- | --- |
| `docs/SPECIFICATION_CRM_V1.md` | Architecture technique cible, composants, API cible, conventions et modules V1. |
| `docs/Audit_LeadGenerator.md` | Validation de la Clean Architecture, frontieres testees, securite et CI/CD. |
| `docs/automatisation/ETAPE_3_ARCHITECTURE_DONNEES_SECURITE.md` | Architecture cible de l'Automatisation, invariants, donnees, regles, API, execution durable et securite. |
| `docs/automatisation/VAGUE_T2_DONNEES_REGLES_CONTRATS.md` | Modele logique, ADR, Feu, Prevol, contrats API et sequences. |
| `docs/automatisation/VAGUE_T3_SECURITE_IA_RESILIENCE.md` | Autorisations, encadrement IA, menace, resilience et retour arriere. |
| `docs/automatisation/VAGUE_T4_ESTIMATION_PORTE_3.md` | Capacite, couts, tranches, ADR consolidees et risques. |

## Stack technique

| Couche | Choix |
| --- | --- |
| Frontend | React 19, Vite, Vitest, Testing Library, axe-core, ESLint. |
| Backend | Python 3.12, FastAPI, Pydantic 2, SQLAlchemy async, Alembic, Uvicorn. |
| Base | PostgreSQL 17 avec roles separes, fonctions `SECURITY DEFINER` et RLS forcee. |
| Cache / etat ephemere | Redis 7 pour sessions, quotas, verrous, jetons et limites. |
| Worker | CLI Python `backend.app.cli.worker` pour traitements durables. |
| Emails locaux | Mailpit, uniquement en developpement/test/QA. |
| Google | Places API New, Maps Static API, avec cles serveur et quotas. |
| CI | Azure Pipelines avec ruff, mypy, Alembic, pytest, Vitest, build Vite, audit npm, recette navigateur. |
| Conteneurs | Dockerfile multi-stage Node/Python, Compose local, Compose QA avec Caddy. |

## Organisation backend

| Repertoire | Responsabilite |
| --- | --- |
| `backend/app/domain/` | Entites, invariants et regles metier sans dependance framework. |
| `backend/app/application/use_cases/` | Orchestration metier : auth, prospects, pipeline, opportunites, imports, exports, usage. |
| `backend/app/application/ports/` | Interfaces vers persistance, sessions, Google, quotas, audit, fichiers et horloge. |
| `backend/app/infrastructure/postgres/` | SQLAlchemy, RLS, repositories, migrations, worker durable, exports, usage. |
| `backend/app/infrastructure/redis/` | Sessions opaques, limitations, quotas Google, verrous et jetons ephemeres. |
| `backend/app/infrastructure/google/` | Clients Google Places, resolution de lieu, cartes statiques et simulateur. |
| `backend/app/presentation/api/` | Routes FastAPI, schemas, mappers, erreurs et dependances HTTP. |
| `backend/app/config.py` | Configuration centralisee et validations d'environnement. |

## Organisation frontend

| Repertoire | Responsabilite |
| --- | --- |
| `client/src/app/` | Routes, navigation, layout authentifie, garde de capacites. |
| `client/src/features/auth/` | Connexion, session, acceptation d'invitation. |
| `client/src/features/lead-search/` | Recherche Google ponctuelle et affichage temporaire. |
| `client/src/features/prospects/` | Liste, creation, fiche, pipeline, activites et taches. |
| `client/src/features/opportunities/` | Portefeuille et cycles de vie des opportunites. |
| `client/src/features/compliance/` | Fournisseurs, acquisitions et connecteur Meta pilote. |
| `client/src/features/retention/` | Conservation, declarations d'import, CSV et historique. |
| `client/src/features/dashboard/` | Tableau de bord. |
| `client/src/features/usage/` | Quotas et rapports d'usage. |
| `client/src/features/exports/` | Exports CSV internes. |
| `client/src/shared/` | Client HTTP, erreurs, UI commune, hooks et utilitaires. |

## Donnees et persistance

Le modele de donnees s'est construit par phases :

- Phase 2 : identite, organisations, membres, invitations, audit, provenance, permissions, retention.
- Phase 3 : import CSV, pipeline, activites, taches, opportunites.
- Phase 4 : dashboard, worker, exports, usage, fournisseurs et connecteur pilote.
- Pre-Phase 5 Automatisation : modeles et contrats encore majoritairement documentaires.

Les migrations Alembic sont versionnees sous `backend/app/infrastructure/postgres/migrations/versions/`, avec une tete observee `20260929_0030`.

## Securite structurante

| Sujet | Choix |
| --- | --- |
| Sessions | Jetons opaques stockes cote serveur dans Redis ; cookie `HttpOnly`, `SameSite=Lax`, `Secure` en production. |
| CSRF | Jeton en memoire navigateur ; mutations authentifiees protegees par `X-CSRF-Token` et origine fiable. |
| Mots de passe | Argon2id ; longueur 12 a 128 caracteres ; jamais journalises. |
| Multi-tenant | Organisation deduite de la session ; RLS PostgreSQL ; identifiants cross-tenant masques en `404`. |
| Audit | Evenements append-only, minimises, transactionnels. |
| Secrets | Exclus des logs, reponses, captures et artefacts. |
| Google | Donnees descriptives non persistantes ; seul `place_id` peut devenir reference durable. |
| Exports | Colonnes en liste blanche, fichiers temporaires prives, telechargement recontrole. |

## Choix d'architecture majeurs

| Decision | Raison |
| --- | --- |
| Architecture domaine/application/infrastructure | Garder les regles testables et independantes des frameworks. |
| PostgreSQL + RLS | Garantir une barriere multi-organisation defense en profondeur. |
| Redis pour etat ephemere | Sessions, quotas, verrous et jetons courts ne doivent pas vivre dans le navigateur. |
| Google borne et non persistant | Respecter les contraintes Google Maps Platform et eviter une base de donnees derivee. |
| Worker durable | Decoupler exports/imports/connecteurs des requetes HTTP et rendre les reprises idempotentes. |
| Bilinguisme par routes/messages | Garantir `fr-CA` et `en-CA` pour les surfaces visibles. |
| Automatisation en mode Preparer | Eviter tout effet CRM ou externe silencieux avant preuve, droits et validation humaine. |

## Automatisation future

La reference fonctionnelle `RF-AUT-2.1` definit une architecture cible avec :

- un point d'entree IA unique dans `Aujourd'hui` ;
- un Feu relationnel deterministe : Vert, Jaune, Rouge ;
- un Prevol sans effet ;
- trois Playbooks : Nouveau prospect, Proposition en attente, Occasion oubliee ;
- le mode `Preparer` par defaut ;
- aucune communication externe autonome en V1 ;
- une exigence de trace, version, idempotence, audit et revalidation des droits avant effet.

Le controle final Automatisation conclut : preparation autorisee, construction active non autorisee tant que Porte 4 n'est pas prononcee.
