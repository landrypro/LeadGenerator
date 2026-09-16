# Phase 2.6 — Redis partagé, quotas et durcissement

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Incrément | 2.6 — Redis partagé, quotas et durcissement |
| Version | 1.0 — validée |
| Prérequis | Phase 2.5 clôturée avec GO, amélioration d'identité prospect pré-2.6 validée, migration `20260815_0013 (head)` |
| Statut | Spécifications validées — implémentation autorisée par sous-incrément |
| Date | 25 août 2026 |
| Résultat attendu | Une protection Google cohérente entre plusieurs instances API, bornée par quotas et observable |

Ce document définit le contrat fonctionnel et technique de 2.6. Il prolonge les protections Google de phase 1 et le
socle Redis déjà utilisé pour les sessions et les limites d’authentification. Il ne lance ni la facturation, ni les
plans commerciaux, ni un nouveau parcours visuel.

## 0. Constat de départ

L’audit du code au 25 août 2026 établit que :

- les ports `GenerationGuard`, `MapSnapshotGrantStore` et `GoogleSelectionGrantStore` sont déjà placés dans la couche
  application ;
- Redis est déjà injecté pour les sessions, les limites de connexion et les limites d’invitation ;
- `build_container()` câble encore `InMemoryGenerationGuard`, `InMemoryMapSnapshotGrantStore` et
  `InMemoryGoogleSelectionGrantStore`, même lorsqu’une URL Redis est configurée ;
- le verrou mémoire ne protège qu’une seule instance de processus ;
- un jeton émis par l’instance A est inconnu de l’instance B ;
- aucun quota quotidien de recherche Google n’est encore consommé par le cas d’utilisation ;
- le pipeline Azure possède déjà PostgreSQL et Redis réels, mais sa révision Alembic attendue doit être réalignée sur
  `20260815_0013` avant de pouvoir constituer une preuve de préproduction ;
- les journaux techniques ne sont pas encore uniformément structurés et aucun export de métriques applicatives n’est
  défini.

Le jeton de sélection Google ajouté en 2.5 ne figurait pas dans la formulation historique de 2.6. Il doit néanmoins
être migré vers Redis : sans cette correction, une recherche reçue par A puis un ajout au CRM reçu par B échouerait
derrière un répartiteur de charge. Cette extension reste éphémère et ne change pas la règle de conservation : la
commande d'ajout écrit le `place_id` explicitement sélectionné et le nom interne saisi séparément par l'utilisateur,
jamais le nom Google temporaire.

## 1. Objectifs

2.6 doit :

- garantir le verrou de recherche pour toutes les instances API partageant Redis ;
- rendre les jetons de carte et de sélection utilisables indépendamment de l’instance qui les a émis ;
- appliquer atomiquement les limites quotidiennes par utilisateur et par organisation ;
- refuser tout appel Google facturable lorsque la protection Redis ne peut pas être garantie ;
- préparer un port de politique d’usage remplaçable par les futurs droits de plan ;
- produire des métriques et journaux structurés sans secret, contenu Google ni donnée personnelle inutile ;
- prouver le comportement avec deux conteneurs applicatifs et un Redis réel ;
- maintenir toutes les protections de conformité Google déjà validées.

## 2. Périmètre

### 2.1 Inclus

- adaptateurs Redis des verrous de recherche, jetons de carte et jetons de sélection Google ;
- scripts Redis atomiques, noms de clés versionnés et expirations obligatoires ;
- quotas de recherche Text Search par utilisateur dans son organisation active et par organisation ;
- port applicatif de politique de quota et adaptateur de configuration initial ;
- réponses `409`, `429` et `503` déterministes, avec `Retry-After` lorsque pertinent ;
- câblage Redis obligatoire pour les parcours Google en environnement complet ;
- métriques Prometheus, journaux JSON et corrélation par `request_id` ;
- tests unitaires, tests Redis réels, tests avec deux applications et non-régression Google ;
- contrôles Azure, configuration exemple, guide opérateur et guide utilisateur actualisés.

### 2.2 Exclus

- catalogue Freemium, Starter, Business ou Sur mesure ;
- prix, taxes, paiement, abonnement, portail de facturation et webhooks ;
- compteur financier opposable, facture ou registre durable de consommation ;
- écran d’administration des quotas et dérogations contractuelles ;
- Place Details, résolution de ville, autocomplétion et quotas associés ;
- modification des limites Google de phase 1 : un Text Search, vingt résultats, aucun contact, aucune pagination ;
- persistance de la requête, des résultats, des coordonnées ou de la carte Google ;
- changement visuel majeur du parcours de recherche.

Les compteurs Redis de 2.6 constituent une protection opérationnelle de coût, pas une preuve de facturation. Le futur
module d’abonnement devra disposer de son propre registre durable et auditable si une consommation devient facturable
au client.

## 3. Découpage d’implémentation proposé

| Sous-incrément | Objet | Sortie testable |
| --- | --- | --- |
| **2.6.1 — État Google partagé** | Verrou Redis, jeton de carte, jeton de sélection, câblage par profil et stratégie de panne | Deux applications partagent le même verrou et les mêmes jetons ; aucune mémoire en production |
| **2.6.2 — Quotas et droits préparatoires** | Port de politique, compteurs utilisateur/organisation, `429`, seuil à 80 % | Consommation atomique et bornes 20/100 vérifiées sous concurrence |
| **2.6.3 — Observabilité et verrou final** | Métriques, journaux JSON, CI/Azure, documentation et régression complète | Rapport final, deux instances, expirations, zéro skip et tous les contrôles verts |

Les spécifications détaillées sont déclinées par sous-incrément :

- [`PHASE_2_6_1_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_6_1_SPECIFICATIONS_DETAILLEES.md) — état Google partagé,
  validé et implémenté ;
- [`PHASE_2_6_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_6_2_SPECIFICATIONS_DETAILLEES.md) — quotas et droits
  préparatoires, validé et implémenté ;
- [`PHASE_2_6_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_6_3_SPECIFICATIONS_DETAILLEES.md) — observabilité et verrou
  final, proposée pour validation.

Chaque sous-incrément exige ses tests unitaires et Redis réels avant le suivant. La recette utilisateur peut être
regroupée à la fin de 2.6.3 car aucun nouveau module visuel n’est livré ; les preuves multi-instance ne sont pas
différées.

## 4. Invariants non négociables

1. Une action utilisateur produit au maximum un appel Places Text Search.
2. La réponse Google reste limitée à vingt résultats et ne suit aucun `nextPageToken`.
3. Aucun téléphone ni site Web n’est demandé ou exposé par la liste.
4. Un utilisateur ne peut avoir qu’une recherche Google en cours dans une organisation donnée.
5. Une indisponibilité Redis bloque le parcours avant l’appel Google lorsque le verrou ou le quota n’est pas garanti.
6. Un verrou n’est libéré que par son détenteur ; aucun `DEL` aveugle n’est permis.
7. Toute clé temporaire possède une expiration définie dès sa création atomique.
8. Un jeton brut n’est jamais placé dans une clé Redis, un journal, une métrique ou une erreur.
9. Un jeton de carte est lié à l’utilisateur et à l’organisation qui ont déclenché la recherche.
10. Un jeton présenté par un autre acteur n’est ni révélé ni consommé.
11. Une seule exécution peut réserver un jeton de carte ; toute tentative concurrente est refusée.
12. Une réservation de quota acceptée reste comptée même si Google échoue ensuite.
13. Un refus de verrou, d’autorisation ou de quota ne consomme aucun appel Google.
14. Les compteurs ne contiennent ni requête, ni résultat, ni courriel, ni nom d’organisation.
15. Les droits et quotas sont calculés côté serveur ; le navigateur n’est jamais une autorité.
16. Les adaptateurs mémoire ne sont autorisés que comme doublures injectées explicitement dans les tests unitaires.

## 5. Architecture applicative

### 5.1 Ports

Les ports existants sont conservés pour le verrou et les jetons. Deux contrats complètent le cas d’utilisation :

- `GoogleSearchQuota` : réserve atomiquement une unité pour l’utilisateur et l’organisation, puis retourne la
  consommation, les restants et l’échéance ;
- `GoogleSearchPolicyProvider` : retourne une politique immuable contenant `enabled`, `user_daily_limit`,
  `organization_daily_limit`, `warning_threshold_percent` et `policy_code`.

Le domaine et les cas d’utilisation ne dépendent ni de `redis.asyncio`, ni de scripts Lua, ni de Prometheus. Les
adaptateurs concrets appartiennent à `infrastructure/redis/` et l’assemblage à `bootstrap.py`.

### 5.2 Politique initiale et futurs plans

L’adaptateur initial lit des paramètres serveur :

- `GOOGLE_SEARCH_USER_DAILY_LIMIT=20` ;
- `GOOGLE_SEARCH_ORGANIZATION_DAILY_LIMIT=100` ;
- `GOOGLE_SEARCH_QUOTA_WARNING_PERCENT=80`.

Une limite égale à zéro désactive la recherche pour la portée concernée. Une limite illimitée est interdite en
staging et production. Le futur module d’abonnement remplacera l’adaptateur de configuration par un résolveur de
droits calculant :

1. les droits du plan ;
2. une éventuelle dérogation contractuelle ;
3. la limite de sécurité de l’exploitant ;
4. la plus restrictive de ces valeurs.

2.6 ne crée pas encore de table de plan, de colonne d’abonnement ou d’interface de facturation. Aucune migration
Alembic artificielle n’est requise ; `20260815_0013` reste la tête attendue tant qu’aucun modèle PostgreSQL ne change.

### 5.3 Ordre du cas d’utilisation de recherche

L’ordre obligatoire est :

1. restaurer la session et l’organisation active ;
2. vérifier `google:search`, le statut de l’organisation et la configuration Google ;
3. valider la commande ;
4. acquérir le verrou distribué utilisateur/organisation ;
5. réserver atomiquement le quota utilisateur et organisation ;
6. exécuter exactement un appel Text Search ;
7. construire la réponse éphémère ;
8. émettre les jetons Redis de carte et de sélection ;
9. libérer le verrou dans un `finally` protégé ;
10. retourner la réponse `no-store`.

Le verrou refusé ne consomme pas de quota. La réservation de quota est volontairement conservatrice : elle mesure
une tentative Google autorisée et protège le budget, même si le fournisseur répond ensuite `4xx`, `5xx` ou dépasse
son délai. Si l’émission des jetons échoue après l’appel, la réponse est `503`, l’appel et le quota restent comptés,
et l’incident est métriqué sans contenu Google.

## 6. Contrats Redis

### 6.1 Nommage des clés

Le préfixe technique existant est conservé pour ne pas invalider silencieusement les sessions :

```text
prospect:{environment}:v1:google:{<organization_uuid>}:search-lock:<user_uuid>
prospect:{environment}:v1:google:{<organization_uuid>}:quota:<YYYY-MM-DD>:organization
prospect:{environment}:v1:google:{<organization_uuid>}:quota:<YYYY-MM-DD>:user:<user_uuid>
prospect:{environment}:v1:google:{<organization_uuid>}:quota:<YYYY-MM-DD>:operation:<operation_uuid>
prospect:{environment}:v1:map-grant:<sha256_token>
prospect:{environment}:v1:selection-grant:<sha256_token>
prospect:{environment}:v1:google:{<organization_uuid>}:warning:<YYYY-MM-DD>:organization
prospect:{environment}:v1:google:{<organization_uuid>}:warning:<YYYY-MM-DD>:user:<user_uuid>
```

Les accolades autour de l’organisation constituent un hash tag Redis Cluster : les deux compteurs de quota d’une
même consommation restent dans le même slot et peuvent être modifiés par un seul script. Les UUID sont des
identifiants internes ; les courriels, noms, requêtes et `place_id` ne figurent jamais dans les noms de clés. Les
jetons sont indexés uniquement par SHA-256.

### 6.2 Verrou distribué

Acquisition :

- valeur propriétaire aléatoire d’au moins 256 bits ;
- commande équivalente à `SET key owner NX PX ttl` ;
- durée par défaut `GOOGLE_SEARCH_LOCK_TTL_SECONDS=45` ;
- la durée doit être au minimum égale au délai Places, à deux délais d'opération Redis et à une marge de cinq
  secondes, afin de couvrir l'émission séquentielle des deux jetons ;
- contention traduite en `409 google_search_in_progress`.

Libération :

- script atomique comparant la valeur propriétaire avant `DEL` ;
- libération tentée dans `finally`, y compris après annulation ;
- expiration comme filet de sécurité après arrêt brutal du processus ;
- échec de libération journalisé sans faire croire que le verrou a été supprimé.

Il n’existe pas de verrou global d’organisation : deux membres distincts peuvent rechercher simultanément, sous la
borne atomique du quota de l’organisation.

### 6.3 Jeton de carte

- jeton opaque généré avec au moins 256 bits d’aléa ;
- valeur Redis contenant uniquement propriétaire, instant d’émission, statut et charge `MapSnapshot` éphémère ;
- TTL de cinq minutes, plafonné à cinq minutes en production ;
- script atomique vérifiant le propriétaire puis passant `available` à `claimed` ;
- un autre acteur reçoit `403 invalid_map_grant` sans détruire le jeton légitime ;
- un second appel simultané du propriétaire reçoit `409 map_grant_in_progress` ;
- la clé est supprimée par comparaison à la sortie du contexte, que l’appel Maps réussisse ou échoue ;
- après une tentative Maps, le jeton est terminal afin d’interdire un deuxième appel facturable ;
- après arrêt brutal du détenteur, l’expiration rend le jeton invalide sans le remettre en circulation.

Le paramètre de capacité de l’ancien dictionnaire mémoire n’est pas transposé en éviction applicative. Une erreur
Redis de mémoire produit `503` et aucune éviction arbitraire d’une session ou d’un jeton n’est autorisée.

### 6.4 Jeton de sélection Google

- stockage Redis obligatoire dès qu’une URL Redis est configurée ;
- TTL de dix minutes par défaut ;
- liaison au même utilisateur et à la même organisation ;
- ensemble dédupliqué de vingt `place_id` maximum, sans donnée descriptive ;
- résolution possible depuis une autre instance API ;
- résolution non destructive pendant le TTL afin de conserver l’idempotence de « Ajouter au CRM » ;
- expiration automatique et rejet uniforme après expiration ou changement d’acteur.

### 6.5 Quotas atomiques

La journée de quota est une journée UTC, indépendante du fuseau de l’instance API. Le client peut afficher
l’échéance dans le fuseau de l’organisation, mais le serveur et Redis restent l’autorité.

Un script unique :

1. reçoit un identifiant d'opération UUID généré par le serveur et indépendant du `request_id` public ;
2. retourne le résultat déjà enregistré si cette opération a déjà été évaluée ;
3. lit le compteur utilisateur et le compteur organisation ;
4. vérifie les deux limites avant modification ;
5. refuse sans incrément partiel si l’une serait dépassée ;
6. incrémente les deux compteurs si les deux limites l’autorisent ;
7. enregistre le résultat de l'opération avec la même échéance ;
8. pose l'expiration de chaque clé à la prochaine minuit UTC dès sa création ;
9. retourne la portée éventuelle du refus, les compteurs et le nombre de secondes avant remise à zéro.

L'identifiant d'opération rend un rejeu technique idempotent après une perte de réponse Redis : une réservation ne
peut être comptée qu'une fois. Il n'est ni envoyé au navigateur, ni utilisé comme label métrique, ni réutilisé pour
une autre action. Une réponse incertaine peut être rejouée une seule fois avec le même identifiant ; si l'issue reste
inconnue, le serveur répond `503` et n'appelle pas Google. Une unité de protection peut alors avoir été réservée, mais
jamais deux ; ces compteurs ne constituent pas une facturation client.

Le quota « utilisateur » est évalué dans l’organisation active : un même compte membre de deux organisations utilise
le budget de chaque organisation séparément. Cette règle suit le futur modèle de facturation par organisation.

Au franchissement de 80 %, une clé sentinelle `SET NX` ayant la même échéance évite de répéter le journal
d’avertissement. Elle ne déclenche ni courriel ni blocage dans 2.6.

### 6.6 Cycle de vie des scripts Redis

- les scripts Lua sont versionnés avec le code, courts, déterministes et couverts par des tests de résultat ;
- l'adaptateur utilise `SCRIPT LOAD` et `EVALSHA` ou l'équivalent fourni par `redis-py` ;
- après `NOSCRIPT`, il recharge le script et rejoue une seule fois, car le script absent n'a pas été exécuté ;
- un timeout ou une rupture réseau n'est jamais traité comme `NOSCRIPT` ; seules les opérations portant un identifiant idempotent peuvent être résolues ou rejouées sans double effet ;
- les clés passées à un même script Redis Cluster appartiennent obligatoirement au même hash slot ;
- aucune erreur de script ne déclenche un repli mémoire.

## 7. Stratégie de panne et contrat HTTP

| Situation | Réponse | Appel Google | Quota consommé |
| --- | --- | :---: | :---: |
| Autorisation, organisation ou commande invalide | `401`, `403` ou `422` existant | Non | Non |
| Verrou déjà détenu | `409 google_search_in_progress` | Non | Non |
| Quota utilisateur atteint | `429 google_quota_exceeded` + `Retry-After` | Non | Non |
| Quota organisation atteint | `429 google_quota_exceeded` + `Retry-After` | Non | Non |
| Redis indisponible avant toute réservation | `503 google_protection_unavailable` | Non | Non |
| Résultat de réservation Redis toujours incertain après rejeu idempotent | `503 google_protection_unavailable` | Non | Zéro ou une unité de protection, jamais deux |
| Google refuse ou échoue après réservation | `429` ou `502` existant | Oui, une fois | Oui |
| Émission des jetons impossible après Google | `503 google_protection_unavailable` | Oui, une fois | Oui |
| Jeton de carte absent, expiré, consommé ou mauvais acteur | `403 invalid_map_grant` | Non | Sans objet |
| Jeton de carte déjà réservé | `409 map_grant_in_progress` | Non | Sans objet |

Toutes ces réponses portent `Cache-Control: no-store` et le `request_id`. `Retry-After` est un nombre entier de
secondes, au minimum égal à un. Le corps peut indiquer `scope` avec les seules valeurs `user` ou `organization`, mais
ne révèle ni compteur d’un autre utilisateur, ni droit commercial futur.

La stratégie est fermée : il n’existe aucun repli mémoire silencieux après une erreur Redis. La liveness reste
indépendante de Redis ; la readiness devient `503` lorsque Redis est indisponible.

## 8. Profils et configuration

### 8.1 Câblage

- `staging` et `production` : Redis obligatoire, adaptateurs Redis obligatoires, échec de démarrage si le câblage de
  protection ne peut pas être construit ;
- `development` avec `REDIS_URL` : mêmes adaptateurs Redis que la production ;
- environnement complet sans Redis : readiness non prête et parcours Google indisponible ;
- tests unitaires : doublures mémoire ou fakes injectés explicitement, jamais sélectionnés automatiquement par
  `build_container()` ;
- tests d’intégration : Redis réel obligatoire, sans `skip` toléré dans le verrou final.

Les façades de compatibilité pointant directement vers les classes mémoire sont supprimées du chemin de production.
Les anciennes classes peuvent rester dans `infrastructure/memory/` uniquement comme doublures de test documentées.

### 8.2 Variables proposées

| Variable | Défaut | Règle |
| --- | ---: | --- |
| `GOOGLE_SEARCH_LOCK_TTL_SECONDS` | `45` | Au moins timeout Places + deux timeouts Redis + 5 s |
| `GOOGLE_SEARCH_USER_DAILY_LIMIT` | `20` | Entier positif ; `0` désactive explicitement |
| `GOOGLE_SEARCH_ORGANIZATION_DAILY_LIMIT` | `100` | Entier positif ; `0` désactive explicitement |
| `GOOGLE_SEARCH_QUOTA_WARNING_PERCENT` | `80` | Entier entre 1 et 100 |
| `MAP_SNAPSHOT_GRANT_TTL_SECONDS` | `300` | Maximum 300 en production |
| `GOOGLE_SELECTION_GRANT_TTL_SECONDS` | `600` | Maximum 900 en staging et production |
| `METRICS_ENABLED` | `false` en développement | Activation explicite |
| `METRICS_BEARER_TOKEN` | aucun | Secret obligatoire en staging/production si métriques activées |
| `LOG_FORMAT` | `text` en développement, `json` hors développement | `json` obligatoire en staging/production |
| `INSTANCE_ID` | généré au démarrage | Identifiant non secret, unique par instance |

`REDIS_URL` utilise `rediss://` hors réseau local lorsqu’un chiffrement applicatif est requis. Redis n’est jamais
exposé publiquement. Le service de production doit être authentifié, sauvegardé selon les besoins de session,
surveillé et configuré avec une politique `noeviction` ou une garantie équivalente ; une saturation doit échouer
explicitement plutôt qu’évincer une protection de sécurité.

## 9. Observabilité

### 9.1 Journaux structurés

En staging et production, chaque ligne est un objet JSON UTF-8. Champs communs :

- `timestamp`, `level`, `event`, `request_id`, `instance_id` ;
- `route`, `method`, `status_code`, `duration_ms` pour une requête ;
- identifiants UUID internes d’utilisateur et d’organisation uniquement lorsqu’ils sont nécessaires au diagnostic ;
- `outcome`, `quota_scope`, `policy_code`, classe de statut fournisseur et durée Redis pour les événements concernés.

Événements minimaux :

- `google_search_lock_acquired`, `google_search_lock_contended`, `google_search_lock_release_failed` ;
- `google_search_quota_consumed`, `google_search_quota_rejected`, `google_search_quota_warning` ;
- `map_grant_issued`, `map_grant_claimed`, `map_grant_rejected` ;
- `selection_grant_issued`, `selection_grant_resolved`, `selection_grant_rejected` ;
- `redis_operation_failed`, `google_upstream_completed`.

Sont interdits : corps de requête, texte recherché, courriel, cookie, CSRF, clé API, jeton brut, `place_id`, adresse,
coordonnées, URL Google et image. Le journal d’audit métier reste distinct du journal technique.

### 9.2 Métriques

Un port de métriques permet un adaptateur Prometheus et un adaptateur nul pour les tests unitaires. Séries minimales :

```text
marketteo_redis_operation_duration_seconds{operation,outcome}
marketteo_google_search_lock_total{outcome}
marketteo_google_search_quota_total{scope,outcome,policy_code}
marketteo_google_map_grant_total{action,outcome}
marketteo_google_selection_grant_total{action,outcome}
marketteo_google_upstream_calls_total{api,outcome}
```

Les identifiants utilisateur/organisation, `request_id`, jetons et codes d’établissement sont interdits comme labels
pour éviter fuite et cardinalité non bornée. `policy_code` provient d’une liste technique bornée et ne contient aucun
nom de client, identifiant de contrat ou valeur libre.

L’export Prometheus proposé est `GET /internal/metrics`, hors de l’API utilisateur. En staging et production il exige
un bearer token dédié comparé en temps constant et doit aussi être filtré par le réseau ou le reverse proxy. La route
n’est pas incluse dans la navigation, n’utilise pas la session utilisateur et ne publie aucun secret.

## 10. Stratégie de tests

### 10.1 Tests unitaires

- validation des paramètres et profils ;
- ordre autorisation, verrou, quota, fournisseur et jetons ;
- refus de verrou sans quota ;
- refus de quota sans fournisseur ;
- erreur Redis traduite en `503` sans appel Google ;
- réservation autorisée comptée après erreur Google ;
- erreurs et logs sans secret ni contenu interdit ;
- politique à zéro refusant la recherche ;
- calcul de fenêtre UTC et `Retry-After` avec horloge contrôlée.

### 10.2 Intégration Redis réelle

Deux clients Redis et deux conteneurs applicatifs indépendants partagent la même URL :

- deux acquisitions concurrentes du même verrou donnent exactement un détenteur ;
- des propriétaires différents peuvent détenir leurs verrous ;
- un non-propriétaire ne peut pas libérer le verrou ;
- le verrou redevient disponible après libération et après TTL ;
- un jeton de carte émis par A peut être réservé par B ;
- deux réservations concurrentes produisent un seul détenteur ;
- un mauvais acteur ne consomme pas le jeton ;
- le jeton devient terminal après le premier appel Maps, y compris en échec ;
- un jeton de sélection émis par A est résolu par B, lié à son propriétaire et expire ;
- vingt consommations utilisateur sont acceptées et la vingt-et-unième est refusée ;
- cent consommations organisation réparties entre au moins cinq utilisateurs sont acceptées sous concurrence et la
  cent-unième est refusée ;
- un refus atomique ne laisse aucun des deux compteurs partiellement incrémenté ;
- la perte simulée de la première réponse puis le rejeu du même identifiant d'opération ne compte qu'une unité ;
- deux identifiants d'opération distincts comptent deux unités ;
- toutes les clés créées ont un `PTTL` strictement positif et disparaissent après leur durée de test ;
- l’arrêt de Redis produit le comportement fermé attendu.

Les délais de test sont courts et dédiés ; aucun test n’attend les TTL de production.

### 10.3 Intégration API à deux instances

- deux applications FastAPI possèdent des conteneurs et pools distincts mais partagent PostgreSQL et Redis ;
- une même session Redis est acceptée par les deux ;
- deux requêtes simultanées de recherche pour le même acteur déclenchent exactement un appel au faux fournisseur ;
- un jeton de réponse de l’instance A est utilisable sur l’instance B ;
- aucun sticky session n’est nécessaire ;
- les statuts, `Retry-After`, `Cache-Control: no-store` et `X-Request-ID` sont vérifiés.

### 10.4 Régression conformité Google et frontend

Restent obligatoires :

- exactement un Text Search par action acceptée ;
- `pageSize` et réponse limités à vingt ;
- aucun suivi de `nextPageToken` ;
- aucun téléphone ni site Web dans le masque, le schéma ou l’interface ;
- aucune route d’export historique ;
- aucun stockage navigateur des résultats ou jetons ;
- le nom Google reste temporaire ; le `place_id` visible et immuable est distinct du nom interne CRM obligatoire ;
- attribution visible `Google Maps` ;
- bouton d’export toujours désactivé ;
- marque visible `Marketteo` ou `Marketteo CRM`, sans migration implicite des identifiants techniques historiques ;
- message utilisateur compréhensible pour `409`, quota `429` et protection `503` ;
- tests React et accessibilité sans changement visuel régressif.

## 11. CI et critères de sortie

Azure et le verrou local doivent :

1. démarrer PostgreSQL et Redis réels, sans port déjà occupé ;
2. provisionner les rôles PostgreSQL ;
3. appliquer Alembic et vérifier `20260815_0013` tant qu’aucune migration 2.6 n’est justifiée ;
4. exécuter les tests Redis et deux instances sans `skip` ;
5. exécuter le groupe explicite de non-régression Google phase 1 ;
6. vérifier qu’un profil production ne peut pas sélectionner un adaptateur mémoire ;
7. rechercher les secrets et données interdites dans les journaux de test ;
8. publier les JUnit backend et frontend même en cas d’échec ;
9. exécuter Ruff check/format, mypy, pytest et `alembic check` ;
10. exécuter `npm ci`, audit, ESLint, Vitest/axe et build ;
11. refuser tout test ignoré ;
12. exécuter `git diff --check` et le contrôle de confidentialité de l’artefact.

Le pipeline Azure actuel doit notamment remplacer sa révision attendue `20260814_0012` par la tête réelle validée.
Cette correction ne remplace pas l’exécution Azure : une exécution verte conservée comme preuve est obligatoire avant
la préproduction.

## 12. Documentation et recette utilisateur

La livraison met à jour :

- `.env.example` et les règles de secrets ;
- le README de démarrage local Windows/WSL ;
- le guide technique des clés, TTL, scripts, profils et panne Redis ;
- le guide utilisateur expliquant le quota quotidien, l’heure de remise à zéro et les messages `409`/`429`/`503` ;
- la recette QA avec deux instances API, un Redis commun et une procédure de vérification des expirations ;
- le rapport d’implémentation 2.6 avec versions, résultats, réserves et preuve Azure.

La documentation utilisateur ne promet pas encore un plan commercial ni un nombre contractuel définitif. Elle
présente 20/100 comme limites initiales de sécurité susceptibles d’être ajustées avant commercialisation.

## 13. Risques et parades

| Risque | Criticité | Parade spécifiée |
| --- | --- | --- |
| Deux instances facturent deux appels pour le même utilisateur | Haute | Verrou Redis propriétaire avant quota et fournisseur |
| Compteurs utilisateur et organisation divergent | Haute | Script atomique, clés dans le même hash slot |
| Réponse Redis perdue puis quota compté deux fois | Haute | Identifiant d'opération, résultat mémorisé et rejeu idempotent borné |
| Redis indisponible et repli mémoire | Haute | Échec fermé `503`, aucun fallback silencieux |
| Mauvais acteur détruit un jeton | Haute | Vérification du propriétaire dans le script avant mutation |
| Processus meurt avec un verrou/claim | Haute | TTL obligatoire dès la création |
| Ajout CRM échoue derrière le load balancer | Haute | Jeton de sélection migré vers Redis |
| Quota Redis interprété comme facturation | Moyenne | Distinction explicite ; futur registre durable séparé |
| Labels métriques explosifs ou sensibles | Haute | Liste fermée de labels, aucun identifiant comme label |
| Redis évince des sessions ou protections | Haute | Service privé surveillé, `noeviction`, `503` explicite |
| Décalage d’horloge autour de minuit | Moyenne | Fenêtre UTC, synchronisation NTP, tests de frontière |
| Jeton de carte rejoué après erreur fournisseur | Haute | Jeton terminal après la première tentative Maps |
| CI verte sans vraie concurrence | Haute | Test obligatoire avec deux applications et Redis réel |

## 14. Seize décisions validées

Les seize décisions ci-dessous ont été validées par le responsable produit le 25 août 2026.

1. 2.6 est découpée en 2.6.1 état partagé, 2.6.2 quotas/droits, puis 2.6.3 observabilité/verrou final.
2. Redis devient obligatoire pour les parcours Google en environnement complet, sans repli mémoire silencieux.
3. Les adaptateurs mémoire restent uniquement des doublures injectées explicitement dans les tests unitaires.
4. Le jeton de sélection Google de 2.5 est inclus dans la migration Redis pour garantir « Ajouter au CRM » entre deux instances ; il contient seulement les `place_id`, tandis que le nom interne demeure une saisie CRM distincte.
5. Le verrou porte sur le couple utilisateur/organisation, utilise une valeur propriétaire aléatoire, un TTL de 45 secondes et une libération compare-and-delete.
6. Une contention conserve la réponse `409` et ne consomme ni quota ni appel Google.
7. Le jeton de carte est opaque, indexé par hash, lié au propriétaire, réclamé atomiquement, limité à cinq minutes et terminal après une tentative Maps.
8. Le jeton de sélection est partagé, lié au propriétaire, limité à dix minutes et résoluble plusieurs fois pour préserver l’idempotence.
9. Les limites initiales restent 20 recherches par utilisateur dans son organisation active et 100 par organisation, par journée UTC.
10. Les deux compteurs sont réservés dans un script atomique idempotent par opération ; un refus ne modifie aucun compteur, un rejeu ne compte pas deux fois et une réservation acceptée reste comptée après erreur Google.
11. L’ordre obligatoire est autorisation, verrou, quota, un Text Search, puis émission des jetons.
12. Un quota atteint produit `429` avec `Retry-After` ; une protection Redis indisponible produit `503` avant tout appel Google.
13. Un port de politique prépare les futurs plans, mais 2.6 ne crée ni catalogue, ni abonnement, ni prix, ni registre de facturation.
14. Les clés sont versionnées par environnement, utilisent des identifiants internes/hash, expirent automatiquement et Redis de production est privé, authentifié et sans éviction arbitraire.
15. Les journaux JSON et métriques Prometheus excluent secrets/contenus Google et identifiants à forte cardinalité ; l’audit métier reste séparé.
16. Le GO final exige Redis réel, deux instances, expirations, non-régression Google et des améliorations pré-2.6, zéro skip, documentation à jour et Ruff, mypy, pytest, Alembic, ESLint, Vitest, build et Azure verts.

## 15. Décision de sortie

- **GO spécifications détaillées 2.6.1** accordé le 25 août 2026 ;
- les seize décisions propres à 2.6.1 sont validées et son **GO d’implémentation** est accordé ;
- les seize décisions propres à 2.6.2 sont validées et son **GO d’implémentation** est accordé ;
- les seize décisions propres à 2.6.3 sont validées et son **GO d’implémentation** est accordé ;
- le verrou qualité local 2.6.3 est **VERT** le 26 août 2026 ;
- la recette fonctionnelle de 2.6 est regroupée à la clôture de la phase, après 2.6.3 ; elle est différée à
  l’environnement de staging, où Redis et plusieurs instances API seront disponibles.
