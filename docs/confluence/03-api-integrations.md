# API et integrations

## Conventions API

Les routes sont servies par FastAPI. Les conventions transversales sont :

- JSON UTF-8 pour les commandes.
- Cookie de session opaque cote serveur.
- Protection CSRF pour les mutations authentifiees.
- Validation stricte de l'origine ou du referer sur les mutations.
- Reponses sensibles avec `Cache-Control: no-store`.
- En-tete `X-Request-ID` sur les reponses.
- Erreurs structurees avec `code`, `message`, `request_id` et parfois `fields`.
- Identifiants d'une autre organisation masques par `404` lorsque necessaire.
- Pas de secrets, jetons, cles Google, corps fournisseur ou donnees personnelles brutes dans les logs.

## Domaines de routes

| Domaine | Prefixe / routes principales | Role |
| --- | --- | --- |
| Sante | `/api/health`, `/api/health/live`, `/api/health/ready` | Vivacite et disponibilite PostgreSQL/Redis. |
| Metrics | `/internal/metrics` | Export interne protege par bearer, absent si desactive. |
| Authentification | `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`, `/api/auth/switch-organization` | Session, restauration, deconnexion, changement d'organisation. |
| Invitations | `/api/auth/invitations/preview`, `/api/auth/invitations/accept` | Acceptation d'invitation et rattachement de compte. |
| Plateforme | `/api/platform/organizations` et actions de suspension, reactivation, renvoi, revocation | Provisioning et administration plateforme. |
| Organisation | `/api/organization`, `/api/organization/members`, `/api/organization/invitations` | Parametres, membres et invitations locataire. |
| Audit | `/api/audit-events`, `/api/platform/audit-events` | Journaux minimises locataire et plateforme. |
| Google Places | `/api/google/places/locations/suggest`, `/resolve`, `/search` | Suggestion/resolution de lieu, Text Search limite. |
| Carte | `/api/map/snapshot` | Generation Maps Static via jeton court lie a la recherche. |
| Prospects | `/api/prospects`, `/api/prospects/from-google`, timeline, pipeline, taches | Portefeuille, creation, Kanban, activites et taches. |
| Opportunites | `/api/opportunities`, `/api/prospects/{id}/opportunities` | Portefeuille, creation, modification, transitions, reouverture. |
| Conformite | `/api/source-providers`, `/api/acquisitions`, contacts, canaux, permissions | Fournisseurs, provenance et permission par canal. |
| Retention/import | `/api/retention/*`, `/api/import-declarations`, `/api/csv-imports/*` | Conservation, holds, declarations et assistant CSV. |
| Historique import | `/api/csv-import-sessions`, `/api/csv-import-runs` | Lecture des sessions, runs et quarantaines. |
| Exports | `/api/exports`, `/api/export-source-rules` | Demande, suivi, telechargement et regles d'export. |
| Dashboard | `/api/dashboard/summary` | Indicateurs CRM. |
| Usage | `/api/usage/current`, `/api/usage/report` | Quota courant et rapport d'usage. |
| Connecteurs | `/api/provider-connectors`, `/webhooks/meta/leadgen` | Registre fournisseur, revue, activation et webhook Meta pilote. |

## Integrations

### Google Places et Maps Static

Google est utilise pour des consultations explicites, limitees et non persistantes.

Regles :

- une action utilisateur produit au plus un Text Search ;
- `pageSize` limite a 20 ;
- pas de suivi de `nextPageToken` ;
- telephone et site Web exclus de la liste de resultats ;
- resultats conserves uniquement en memoire navigateur ;
- `place_id` est la seule reference Google durable admise ;
- la carte statique est protegee par un jeton Redis court, lie a l'utilisateur et a l'organisation ;
- quotas quotidiens serveur par utilisateur/organisation avant appel Google.

### Mailpit

Mailpit sert aux invitations locales et QA. Il ne doit pas etre expose publiquement. En staging documentee, l'interface est consultee via tunnel SSH local.

`INVITATION_DELIVERY_BACKEND=mailpit` est autorise uniquement en `development` ou `test`.

### PostgreSQL

PostgreSQL est la source de verite :

- migrations Alembic ;
- role proprietaire pour migrations ;
- role Web non proprietaire pour l'API ;
- role worker separe ;
- RLS forcee ;
- fonctions `SECURITY DEFINER` et `search_path` fixe.

### Redis

Redis porte :

- sessions opaques ;
- limitation des connexions et invitations ;
- verrous de recherche Google ;
- quotas Google ;
- concessions de carte et selections Google temporaires ;
- gardes d'idempotence et etats ephemeres.

### Worker durable

Le worker execute les operations longues :

- exports CSV ;
- imports et traitements asynchrones ;
- connecteur Meta pilote ;
- nettoyage et reprises controlees.

Les jobs doivent rester idempotents, auditables et lies a l'organisation.

### Meta Lead Ads pilote

Le connecteur Meta est separe en deux lignes :

- preuve interne avec simulateur et webhook signe ;
- activation externe bloquee tant que Meta, le contrat, les permissions et l'environnement autorise ne sont pas obtenus.

Etat consolide : le pilote technique local est valide avec doubles locaux ; l'activation reelle reste `BLOCKED_EXTERNAL`.

### Azure Pipelines

Azure est l'orchestrateur CI attendu pour la preuve de cloture globale. Le passage du commit de cloture 4.6 reste une condition avant phase 5.

## Routes volontairement absentes ou limitees

- Les anciennes routes d'export Google ne sont plus montees.
- Le bouton d'export Google historique peut etre visible selon les phases, mais reste desactive/hors edition.
- Aucune inscription publique autonome n'est documentee comme disponible.
- Aucun paiement, taxe, facture ou abonnement reel n'est expose en API V1 actuelle.
- Aucune communication externe autonome n'est autorisee par le volet Automatisation V2.1.

