# Incrément 2.5.2 — Socle prospect et ajout Google

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 2.5 — Socle prospects, conformité et conservation |
| Incrément | 2.5.2 — Socle prospect et ajout Google |
| Version | 1.0 |
| Statut | Validé avec réserves — étapes 9 et 10 de la recette à solder |
| Date de proposition | 14 août 2026 |
| Validation produit | 14 août 2026 — validation des seize décisions de la section 16 |
| Implémentation | 14 août 2026 |
| Prérequis | 2.5.1 implémenté ; migration `20260814_0009 (head)` |
| Dépendances | Authentification 2.3, audit 2.4, recherche Google conforme et modèle prospect 2.5.1 |
| Recette produit | GO avec réserves accordé le 14 août 2026 ; verrou qualité vert |
| Hors périmètre | Contacts, canaux, fournisseurs, import CSV, Kanban, facturation et fiche prospect complète |

Ce document définit le premier parcours commercial persistant de Marketteo : créer un prospect manuellement ou
ajouter au CRM un résultat Google explicitement choisi. Il ne transforme pas la recherche Google en collecte
massive et ne permet de conserver durablement que la référence `place_id` issue de Google.

## 1. Objectifs

2.5.2 doit permettre de :

- créer un établissement prospect manuellement dans l’organisation active ;
- sélectionner un ou plusieurs résultats de la dernière recherche Google et les ajouter au CRM ;
- limiter chaque ajout Google à vingt références issues d’une seule action de recherche autorisée ;
- empêcher l’envoi arbitraire de `place_id` qui n’ont pas été remis par le serveur à l’utilisateur ;
- retourner un résultat idempotent lorsqu’un établissement Google est déjà suivi ;
- exposer une lecture minimale des prospects afin de vérifier la persistance et l’isolation ;
- afficher dans la recherche l’état « Ajouter au CRM », « Ajout en cours » ou « Déjà ajouté » ;
- auditer atomiquement les créations sans inscrire de contenu Google dans l’audit ;
- conserver toutes les protections existantes : session, organisation active, capacité, CSRF, RLS et `no-store`.

## 2. Périmètre fonctionnel

### 2.1 Inclus

- création manuelle minimale avec un nom interne fourni par l’utilisateur ;
- ajout Google individuel ou groupé, après sélection explicite de un à vingt résultats ;
- preuve serveur éphémère liant les références sélectionnables à la recherche courante ;
- déduplication exacte par `(organization_id, google_place_id)` pour les prospects actifs ;
- lecture paginée minimale et lecture d’un prospect par identifiant ;
- capacités `prospects:read` et `prospects:create` ;
- action d’ajout dans l’écran actuel de recherche Google, sans refonte du shell ;
- audit, erreurs structurées, tests backend, PostgreSQL réel et React/Vitest.

### 2.2 Exclus

- modification, affectation, archivage et restauration depuis l’interface ;
- fiche prospect CRM complète et navigation principale « Prospects » ;
- persistance du nom, de l’adresse, des coordonnées, du type, du statut, de la position ou de l’URL Google Maps ;
- appel Place Details lors de l’ajout ;
- enrichissement, recherche automatique ou pagination Google supplémentaire ;
- contacts, canaux, permissions de contact et fournisseurs ;
- import de fichiers ou connecteurs externes ;
- pipeline Kanban, activités, opportunités, tâches et rappels ;
- stockage navigateur des prospects ou des résultats Google.

La fiche, l’interface CRM complète et les fonctions de conformité des lots suivants pourront s’appuyer sur les API
de lecture créées ici, sans élargir le périmètre de cette livraison.

## 3. Invariants non négociables

1. Un ajout Google est toujours déclenché explicitement par un utilisateur authentifié.
2. Le serveur accepte uniquement les `place_id` contenus dans une preuve éphémère qu’il a lui-même émise.
3. La preuve est liée à l’utilisateur, à l’organisation active et à une seule réponse de recherche.
4. La preuve ne contient durablement aucun nom, adresse, téléphone, site Web, position ou autre contenu Google.
5. Une action accepte entre un et vingt `place_id` distincts ; aucun découpage automatique n’est effectué.
6. L’ajout ne déclenche aucun nouvel appel Google, aucun Place Details et aucune pagination.
7. Seul `google_place_id` est copié dans le prospect ; les autres valeurs persistantes sont internes à Marketteo.
8. Un prospect Google actif est unique dans une organisation, y compris en cas de requêtes concurrentes.
9. Un même `place_id` peut être suivi par deux organisations différentes, sans fuite entre elles.
10. Le rejeu d’un ajout retourne le prospect actif existant sans nouvel enregistrement ni nouvel audit de création.
11. Une création manuelle n’accepte aucun `google_place_id` fourni par le client.
12. L’étape initiale est toujours `new` et ne constitue pas une activité commerciale.
13. Toute mutation est autorisée côté serveur par capacité, puis isolée en base par RLS.
14. La création du prospect et son événement d’audit sont validés dans la même transaction.
15. Toutes les réponses de ce module portent `Cache-Control: no-store`.
16. Aucune donnée CRM ou Google n’est écrite dans `localStorage`, `sessionStorage`, IndexedDB ou un cache applicatif navigateur.

## 4. Parcours utilisateur

### 4.1 Création manuelle

Le parcours manuel est exposé par l’API dans ce lot et sera intégré à la fiche/liste complète en 2.5.5. Pour la
recette 2.5.1–2.5.2, il peut être vérifié par le script local ou par l’interface de documentation API.

1. L’utilisateur authentifié choisit l’organisation active.
2. Il fournit un `internal_alias` explicite, propre à son organisation.
3. Le serveur normalise les espaces et valide la longueur sans modifier la casse d’affichage.
4. Le serveur crée un prospect d’origine `manual`, à l’étape `new`.
5. La réponse fournit l’identifiant, le nom interne, l’origine, l’étape, la version et les dates.
6. Un événement `prospect.created` est inscrit dans la même transaction.

Le serveur fixe `source_label=manual:user_entry`. Cette trace minimale identifie l’origine du prospect ; la
provenance détaillée par donnée et les permissions seront introduites en 2.5.3.

### 4.2 Ajout depuis Google

1. L’utilisateur exécute la recherche Google existante : exactement un Text Search, vingt résultats au maximum.
2. La réponse contient les résultats temporaires et un `selection_token` opaque, distinct du jeton de carte.
3. L’utilisateur sélectionne de un à vingt résultats encore visibles dans cette réponse.
4. Le client envoie uniquement le `selection_token` et les `place_id` sélectionnés.
5. Le serveur vérifie la session, le CSRF, la capacité, l’organisation, l’expiration et l’appartenance de chaque référence.
6. Pour chaque référence, il crée un prospect ou retrouve le prospect actif déjà présent.
7. La réponse indique `created` ou `existing` par référence, sans transformer un doublon en erreur.
8. L’interface marque immédiatement les lignes concernées « Ajouté au CRM ».

Le `selection_token` est réutilisable jusqu’à son expiration afin d’autoriser plusieurs ajouts individuels depuis une
même recherche. Cette réutilisation reste sûre : la déduplication et l’audit sont idempotents.

### 4.3 Nom interne d’un prospect Google

Le nom Google affiché reste temporaire et ne devient jamais implicitement un champ CRM. À la création, le serveur
génère un alias interne neutre et déterministe pour l’utilisateur, par exemple `Prospect Google · A1B2C3`, à partir
d’une empreinte non réversible de la référence. L’empreinte ne remplace pas le `place_id` et ne permet pas de le
reconstituer.

Le renommage manuel sera livré avec l’édition du prospect. L’interface ne préremplit pas le nom interne avec le nom
Google et ne transmet aucun champ descriptif à la route d’ajout.

## 5. Preuve éphémère de sélection Google

### 5.1 Contrat applicatif

Un nouveau port `GoogleSelectionGrantStore` est placé dans la couche applicative. Il expose au minimum :

- `issue(owner, place_ids, issued_at) -> token` ;
- `resolve(token, owner, now) -> allowed_place_ids` ;
- une expiration automatique et une capacité bornée par propriétaire.

`owner` comprend l’utilisateur et l’organisation active. La valeur reçue du navigateur est un jeton aléatoire opaque
d’au moins 256 bits ; elle n’embarque ni résultat descriptif, ni clé Google, ni état d’autorisation modifiable côté client.

### 5.2 Durée et stockage

- durée de validité : dix minutes après la recherche ;
- contenu serveur : ensemble ordonné de vingt `place_id` au maximum, propriétaire et expiration ;
- implémentation 2.5.2 : mémoire bornée derrière le port, cohérente avec les jetons de carte actuels ;
- cible 2.6 : stockage Redis partagé pour les déploiements multi-instance ;
- expiration ou redémarrage : une nouvelle recherche est nécessaire, sans perte de donnée CRM ;
- changement d’organisation : le jeton est refusé, même si sa durée n’est pas échue.

La réponse Google existante conserve `Cache-Control: no-store`. Le jeton ne doit pas être journalisé, audité ni
placé dans une URL.

## 6. Contrats API

Toutes les routes exigent une session active, une organisation active non suspendue et les contrôles d’origine déjà
en vigueur. Les mutations exigent également l’en-tête CSRF. Les schémas refusent les champs supplémentaires.

### 6.1 Recherche Google enrichie

`POST /api/google/places/search`

Le comportement Google demeure inchangé : une seule requête Text Search et vingt résultats maximum. La réponse
ajoute :

```json
{
  "selection_token": "opaque-server-token"
}
```

Le jeton n’est émis que pour les `place_id` effectivement présents dans `places`. Aucun résultat descriptif n’est
copié dans le registre CRM ou dans le magasin de preuve.

### 6.2 Création manuelle

`POST /api/prospects`

Capacité requise : `prospects:create`.

```json
{
  "internal_alias": "Clinique du quartier"
}
```

Réponse `201 Created` : vue minimale du prospect. Un champ `google_place_id` absent ou `null` est toléré uniquement
en sortie ; il n’est pas accepté dans la commande manuelle.

### 6.3 Ajout de références Google

`POST /api/prospects/from-google`

Capacité requise : `prospects:create`.

```json
{
  "selection_token": "opaque-server-token",
  "place_ids": ["ChIJ..."]
}
```

Réponse `200 OK` pour l’ensemble de la commande :

```json
{
  "items": [
    {
      "place_id": "ChIJ...",
      "prospect_id": "00000000-0000-0000-0000-000000000000",
      "disposition": "created"
    }
  ],
  "created_count": 1,
  "existing_count": 0
}
```

`disposition` vaut uniquement `created` ou `existing`. La réponse conserve l’ordre de sélection, refuse les doublons
dans la commande et ne renvoie aucun champ descriptif Google.

### 6.4 Lecture minimale

- `GET /api/prospects?limit=25&cursor=...&include_archived=false` ;
- `GET /api/prospects/{prospect_id}`.

Capacité requise : `prospects:read`. La pagination utilise un curseur opaque stable composé côté serveur ; `limit`
vaut 25 par défaut et 100 au maximum. L’ordre est `created_at DESC, id DESC`.

La vue minimale contient : `id`, `internal_alias`, `origin`, `google_place_id`, `stage_code`, `priority`, `version`,
`created_at`, `updated_at` et `archived_at`. Elle ne tente aucune hydratation Google dans 2.5.2.

### 6.5 Codes d’erreur

| HTTP | Code | Situation |
| --- | --- | --- |
| 400 | `validation_failed` | Schéma, alias, liste vide, doublon dans la commande ou plus de vingt références |
| 401 | `authentication_required` | Session absente ou expirée |
| 403 | `insufficient_capability` | Capacité prospect absente |
| 403 | `csrf_failed` | Mutation sans preuve CSRF valide |
| 409 | `active_organization_required` | Aucune organisation active utilisable |
| 409 | `organization_suspended` | Organisation suspendue |
| 410 | `google_selection_expired` | Preuve expirée ou disparue après redémarrage |
| 422 | `google_selection_mismatch` | Une référence n’appartient pas à la recherche ou le propriétaire ne correspond pas |
| 404 | `prospect_not_found` | Prospect absent dans l’organisation active |
| 503 | `prospect_store_unavailable` | Dépendance persistante indisponible |

Les erreurs suivent l’enveloppe normalisée avec `request_id` et ne révèlent ni l’existence d’un prospect dans une
autre organisation, ni le contenu du jeton.

## 7. Transaction, idempotence et concurrence

### 7.1 Création manuelle

La création manuelle et son audit sont exécutés dans une unité de travail locataire. Une erreur avant le commit
annule les deux écritures.

### 7.2 Ajout Google groupé

- la validation complète du jeton et de la liste précède toute écriture ;
- les références existantes dans l’organisation sont chargées avant les insertions ;
- les nouveaux prospects et leurs audits sont écrits dans une transaction unique ;
- une contrainte d’unicité en base arbitre les courses concurrentes ;
- après un conflit d’unicité attendu, le cas d’utilisation relit le prospect gagnant et retourne `existing` ;
- une erreur technique inattendue annule tout le groupe ; aucun succès partiel silencieux n’est admis ;
- chaque prospect réellement créé produit exactement un événement `prospect.created` ;
- une référence déjà existante ne produit aucun nouvel événement de création.

L’idempotence est métier, fondée sur la clé unique active. Aucun identifiant d’idempotence supplémentaire n’est
introduit tant que la commande ne produit pas d’effet externe irréversible.

## 8. Capacités et isolation

La matrice cible de ce lot est :

| Rôle locataire | `prospects:read` | `prospects:create` |
| --- | --- | --- |
| Administrateur | Oui | Oui |
| Gestionnaire | Oui | Oui |
| Commercial | Oui | Oui |
| Administrateur plateforme sans adhésion active | Non | Non |

Les capacités servent à autoriser l’intention applicative ; la RLS reste le dernier verrou. Aucun identifiant
`organization_id` n’est accepté dans les commandes ou filtres publics. L’organisation provient exclusivement de la
session active.

Tests négatifs obligatoires : lecture par identifiant d’un autre locataire, réutilisation d’un jeton dans une autre
organisation, insertion inter-organisation, accès plateforme sans adhésion et organisation suspendue.

## 9. Audit et données sensibles

### 9.1 Événements

Le lot utilise `prospect.created` avec :

- `entity_type=prospect` ;
- `entity_id` égal au prospect créé ;
- cible d’organisation issue du contexte locataire ;
- acteur, `request_id`, `correlation_id`, source et horodatage déjà normalisés par 2.4 ;
- métadonnées limitées à `origin` et `stage_code`.

### 9.2 Interdictions

L’audit et les journaux techniques ne contiennent jamais :

- `place_id`, alias, nom ou adresse d’établissement ;
- résultat Google, position, URL Google Maps ou paramètres de recherche ;
- `selection_token`, jeton de carte, cookie, CSRF ou clé Google ;
- contenu du corps de la requête.

Les métriques autorisées sont agrégées : nombre créé, nombre déjà présent, erreur de sélection, latence et
organisation sous forme d’identifiant interne dans les journaux structurés autorisés.

## 10. Interface utilisateur attendue

L’écran de recherche actuel est modifié sans refonte visuelle majeure :

- une case de sélection par résultat pour les utilisateurs ayant `prospects:create` ;
- une action individuelle accessible « Ajouter au CRM » ;
- une action groupée « Ajouter la sélection au CRM (n) », désactivée lorsque `n=0` ou pendant l’appel ;
- sélection plafonnée à vingt et réinitialisée à chaque nouvelle recherche ;
- états de ligne : disponible, sélectionné, ajout en cours, ajouté, déjà ajouté et erreur ;
- message de synthèse après l’action : nombres créés et déjà présents ;
- libellé explicite indiquant que seul l’identifiant Google est conservé ;
- conservation de l’attribution visible `Google Maps` ;
- aucune action affichée si la capacité manque ;
- aucun nom Google envoyé à l’API d’ajout ;
- aucun résultat ou prospect conservé après rechargement de la page.

L’échec d’une ligne ne doit pas être inventé côté client puisque le serveur applique une transaction groupée. Une
erreur de commande laisse la sélection visible pour permettre une nouvelle tentative ; un jeton expiré invite à
relancer la recherche.

La création manuelle et la liste CRM complète restent accessibles par API pour la recette technique et seront
présentées dans l’interface dédiée de 2.5.5.

## 11. Architecture et changements attendus

### 11.1 Domaine et application

- cas d’utilisation `CreateManualProspect` ;
- cas d’utilisation `AddGoogleProspects` ;
- cas d’utilisation `ListProspects` et `GetProspect` ;
- commande et résultats indépendants de FastAPI/Pydantic ;
- port `GoogleSelectionGrantStore` ;
- réutilisation de `ProspectUnitOfWorkFactory`, `ProspectRepository` et du port d’audit 2.4 ;
- erreurs applicatives typées, traduites seulement dans la couche API.

### 11.2 Adaptateurs et composition

- adaptateur mémoire borné de preuve Google ;
- repositories PostgreSQL 2.5.1 complétés uniquement pour les lectures nécessaires ;
- injection des nouveaux cas d’utilisation dans le conteneur et `create_app()` ;
- aucun import FastAPI dans le domaine ou les cas d’utilisation ;
- aucun accès direct SQL depuis une route.

### 11.3 Frontend

- client API prospect dédié ;
- hook d’ajout Google isolé de `useLeadSearch` ;
- état de sélection local au composant, détruit à la nouvelle recherche ou au démontage ;
- composants de tableau accessibles et testables sans dépendance réseau réelle ;
- erreurs centralisées via les mécanismes partagés existants.

## 12. Stratégie de tests

### 12.1 Tests unitaires backend

- validation et normalisation de la création manuelle ;
- génération d’un alias Google neutre sans copie du nom Google ;
- liste vide, doublons et limite supérieure à vingt ;
- jeton valide, expiré, inconnu et mauvais propriétaire ;
- idempotence créée/existante ;
- absence d’audit lors d’un rejeu ;
- rollback si l’audit ou le repository échoue.

### 12.2 Tests d’intégration FastAPI et PostgreSQL

- création manuelle `201`, lecture et `Cache-Control: no-store` ;
- recherche Google : toujours un seul appel, aucun `nextPageToken`, vingt résultats maximum ;
- preuve contenant exactement les références retournées ;
- ajout Google sans nouvel appel au fournisseur ;
- persistance du seul `google_place_id` parmi les données Google ;
- ajout groupé de vingt références, rejet de vingt-et-une ;
- rejeu et deux requêtes concurrentes sans doublon ;
- transaction et audit atomiques ;
- isolation de deux organisations et jeton non transférable ;
- refus sans session, capacité ou CSRF ;
- organisation suspendue ;
- inspection des colonnes et journaux pour les champs Google interdits.

### 12.3 Tests frontend

- action individuelle et groupée ;
- plafonnement, remise à zéro et état de chargement ;
- rendu créé/déjà présent ;
- jeton expiré et relance proposée ;
- absence d’action sans capacité ;
- requête ne contenant que `selection_token` et `place_ids` ;
- aucune utilisation de stockage navigateur ;
- navigation clavier, libellés, focus et contrôle axe des composants modifiés.

### 12.4 Non-régression et verrou qualité

Avant la recette humaine regroupée 2.5.1–2.5.2 :

- `alembic upgrade head`, `alembic current` et `alembic check` ;
- Ruff format/check et mypy ;
- pytest complet sans `skip` sur la composition de test propre ;
- ESLint, Vitest, contrôle axe et build Vite ;
- tests PostgreSQL/Redis/Mailpit réels du verrou qualité ;
- recherche statique interdisant stockage navigateur et champs Google prohibés ;
- confirmation que la route d’export Google historique reste absente.

## 13. Critères d’acceptation

L’incrément est acceptable si :

1. un utilisateur autorisé crée et relit un prospect manuel dans son organisation ;
2. un résultat Google sélectionné devient un prospect contenant durablement le seul `place_id` Google ;
3. un groupe de vingt références est accepté et vingt-et-une sont refusées avant écriture ;
4. aucun ajout ne provoque d’appel Google supplémentaire ;
5. une référence absente de la recherche est refusée ;
6. un jeton ne peut pas être transféré entre utilisateurs ou organisations ;
7. le rejeu et la concurrence ne créent aucun doublon ni audit supplémentaire ;
8. les créations et audits sont atomiques ;
9. les capacités, le CSRF et la RLS bloquent les accès non autorisés ;
10. l’interface permet la sélection accessible et reflète les résultats de l’ajout ;
11. aucun stockage navigateur ni champ descriptif Google persistant n’est détecté ;
12. le verrou qualité complet est vert sur une composition de test propre.

## 14. Recette locale regroupée 2.5.1–2.5.2

La recette utilisateur de 2.5.1 est volontairement reportée et fusionnée avec celle de 2.5.2, car 2.5.1 n’ajoute
aucun parcours frontend. Après l’implémentation, un guide ou script local doit couvrir dans cet ordre :

1. démarrage PostgreSQL, Redis et Mailpit puis vérification `/api/health/ready` ;
2. migration jusqu’à la révision postérieure à `20260814_0009` et contrôle `alembic check` ;
3. connexion d’un administrateur, gestionnaire ou commercial dans une organisation active ;
4. création manuelle et vérification dans l’API de lecture ;
5. recherche Google de vingt résultats maximum ;
6. ajout individuel puis rejeu du même résultat ;
7. nouvelle recherche, sélection multiple et ajout groupé ;
8. vérification de la persistance après actualisation de la page ;
9. test négatif avec un rôle/capacité insuffisant et avec une seconde organisation ;
10. consultation de l’audit sans contenu Google ;
11. exécution du verrou qualité local complet.

La validation produit de 2.5.1 et 2.5.2 sera prononcée ensemble après cette recette. Les preuves automatisées de
2.5.1 restent néanmoins obligatoires pendant l’implémentation de 2.5.2.

## 15. Risques et mesures de maîtrise

| Risque | Mesure |
| --- | --- |
| Client forgeant un `place_id` | Preuve opaque liée à la recherche et au propriétaire |
| Copie accidentelle d’un nom/adresse Google | Schéma d’ajout limité au jeton et aux `place_id`, tests de persistance |
| Doublon concurrent | Index unique partiel PostgreSQL et gestion explicite du conflit |
| Audit contenant une référence Google | Liste blanche stricte des métadonnées d’audit |
| Jeton mémoire perdu au redémarrage | Erreur explicite et nouvelle recherche ; migration Redis prévue en 2.6 |
| Utilisation multi-instance prématurée | Déploiement 2.5.2 limité à une instance applicative ou affinité documentée |
| Alias interne peu lisible | Alias neutre temporaire, renommage manuel prévu avec l’édition CRM |
| Confusion entre résultat temporaire et prospect | États de ligne et message sur la conservation du seul identifiant |

## 16. Seize décisions proposées à validation

1. 2.5.2 livre la création manuelle, l’ajout Google et une lecture minimale ; la fiche CRM complète reste en 2.5.5.
2. La création manuelle exige un nom interne et n’accepte jamais de `google_place_id` client.
3. L’ajout Google reçoit uniquement un jeton opaque et de un à vingt `place_id` distincts.
4. Le jeton est émis par la recherche, lié à l’utilisateur et à l’organisation, et valable dix minutes.
5. Le jeton est réutilisable jusqu’à expiration pour permettre plusieurs ajouts depuis la même recherche.
6. Le magasin de jetons reste en mémoire derrière un port en 2.5.2 ; Redis partagé est reporté à 2.6.
7. L’ajout ne déclenche aucun appel Google supplémentaire et ne suit aucune pagination.
8. Seul le `place_id` est persisté depuis Google ; tous les champs descriptifs restent temporaires.
9. Le serveur génère un alias interne neutre et non réversible au lieu de copier le nom Google.
10. L’ajout groupé est transactionnel : une erreur inattendue annule toutes les nouvelles créations.
11. Un doublon actif retourne `existing`, sans erreur et sans nouvel événement `prospect.created`.
12. L’idempotence repose sur l’unicité métier `(organization_id, google_place_id)` sans registre supplémentaire.
13. Administrateurs, gestionnaires et commerciaux disposent de `prospects:read` et `prospects:create`.
14. Les réponses prospect et Google restent `no-store` et aucune donnée n’est placée dans le stockage navigateur.
15. L’interface de recherche reçoit l’ajout individuel/groupé ; la liste et la création manuelle complètes restent en 2.5.5.
16. La recette produit de 2.5.1 et 2.5.2 est regroupée après l’implémentation de 2.5.2, avec verrou qualité complet.

## 17. Décision de sortie

- **Go implémentation 2.5.2** : les seize décisions de la section 16 sont validées ;
- **No-Go** : une décision reste ouverte ou contredit les règles Google, de sécurité, d’isolation ou d’audit ;
- **Go incrément suivant** : la recette regroupée 2.5.1–2.5.2 et le verrou qualité sont conformes.

## 18. Exigence reportée à ne pas perdre

La création réalisée en 2.5.2 doit servir de point d’entrée à une fiche établissement enrichissable. Les incréments
suivants doivent impérativement reprendre les éléments suivants :

- **2.5.3** : contacts, canaux de l’établissement, provenance par donnée et permission de contact séparée ;
- **2.5.5** : interface d’édition du profil avec nom interne, secteur, segment, taille, adresse indépendante,
  étiquettes, propriétaire et priorité ;
- **incrément pipeline** : notes, activités, rappels et suivi Kanban.

Ces informations sont des données CRM propres à l’organisation ou provenant d’une source autorisée. Depuis Google,
seul le `place_id` reste persisté ; les informations descriptives Google sont relues en direct et ne peuvent pas être
présentées comme une saisie manuelle afin de contourner leur règle de conservation.
