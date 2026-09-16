# Incrément 2.6.1 — État Google partagé

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 2.6 — Redis partagé, quotas et durcissement |
| Incrément | 2.6.1 — État Google partagé |
| Version | 1.0 — validée |
| Statut | Spécifications validées — implémentation autorisée |
| Date | 25 août 2026 |
| Prérequis | Phase 2.6 validée ; amélioration d'identité prospect pré-2.6 validée ; Alembic `20260815_0013 (head)` |
| Résultat attendu | Deux applications partagent le même verrou et les mêmes jetons ; aucune mémoire dans le câblage de production |

Ce document précise le premier lot de 2.6. Il remplace l'état Google mono-processus par Redis sans modifier les
limites Google, le modèle PostgreSQL, les quotas quotidiens ou la présentation générale de l'interface.

## 1. Constat vérifié dans le code

Les abstractions applicatives existent déjà :

- `GenerationGuard.hold(owner)` protège une recherche ;
- `MapSnapshotGrantStore.issue/redeem` protège l'appel facturable Static Maps ;
- `GoogleSelectionGrantStore.issue/resolve` autorise l'ajout d'un `place_id` affiché par la recherche ;
- `GoogleAccessOwner` lie les trois mécanismes au couple utilisateur/organisation.

Le problème est dans les adaptateurs et l'assemblage :

- `build_container()` construit systématiquement `InMemoryGenerationGuard`, `InMemoryMapSnapshotGrantStore` et
  `InMemoryGoogleSelectionGrantStore`, même si `REDIS_URL` est renseignée ;
- les dictionnaires et verrous `asyncio` ne sont partagés ni entre processus ni entre machines ;
- `generation_lock.py` et `map_snapshot_grants.py` réexportent encore des implémentations mémoire par des façades
  historiques ;
- Redis est déjà utilisé pour les sessions et limites d'identité, mais pas pour les protections Google ;
- une recherche servie par l'instance A produit actuellement des jetons inconnus de l'instance B.

## 2. Objectifs

2.6.1 doit :

1. fournir les adaptateurs `RedisGenerationGuard`, `RedisMapSnapshotGrantStore` et
   `RedisGoogleSelectionGrantStore` ;
2. préserver les ports applicatifs existants afin de ne pas coupler les cas d'utilisation à Redis ;
3. garantir l'acquisition et la libération propriétaire du verrou entre plusieurs instances ;
4. rendre un jeton de carte émis par A réclamable exactement une fois par B ;
5. rendre un jeton de sélection émis par A résoluble par B pendant son TTL ;
6. supprimer tout choix automatique d'un adaptateur mémoire dans `build_container()` ;
7. échouer de façon fermée et compréhensible lorsque Redis ne peut pas garantir la protection ;
8. prouver le comportement avec Redis réel et deux conteneurs applicatifs indépendants.

## 3. Périmètre

### 3.1 Inclus

- adaptations minimales des ports si les annotations ou contrats d'erreur doivent être précisés ;
- trois adaptateurs sous `backend/app/infrastructure/redis/` ;
- scripts Redis atomiques de verrou, réclamation et finalisation ;
- sérialisation versionnée et bornée des charges éphémères ;
- préfixes de clés par environnement et hash de jeton ;
- nouveaux paramètres de TTL et validation des profils ;
- câblage Redis dans `bootstrap.py` ;
- contrat `503 google_protection_unavailable` ;
- tests unitaires, Redis réel et deux applications ;
- mise à jour du verrou local, d'Azure et de la documentation strictement nécessaire au lot.

### 3.2 Exclus

- quotas utilisateur et organisation, réservés à 2.6.2 ;
- politiques de futurs plans et droits commerciaux, hors interfaces déjà validées au niveau 2.6 ;
- métriques Prometheus et généralisation des journaux JSON, réservées à 2.6.3 ;
- nouveau tableau de bord, administration Redis ou écran de quotas ;
- nouvelle migration PostgreSQL ou modification RLS ;
- changement de la limite d'un Text Search et vingt résultats ;
- Place Details, téléphone, site Web, pagination ou export Google ;
- renommage des identifiants techniques historiques `prospect:*`.

## 4. Invariants non négociables

1. Une action de recherche acceptée exécute au maximum un Text Search.
2. Le verrou porte sur `GoogleAccessOwner(user_id, organization_id)`.
3. Le détenteur d'un verrou reçoit un secret propriétaire distinct de la clé Redis.
4. Un verrou ne peut être supprimé que si le secret présenté correspond à la valeur stockée.
5. Toute clé créée possède un TTL positif dans la même opération atomique que sa création.
6. Un jeton brut n'apparaît jamais dans une clé, une valeur persistante secondaire, un journal ou une erreur.
7. La clé d'un jeton utilise uniquement le SHA-256 de son jeton opaque d'au moins 256 bits.
8. Un acteur différent ne peut ni lire, ni consommer, ni invalider le jeton du propriétaire.
9. Un jeton de carte devient terminal dès la première tentative facturable, succès ou échec Google.
10. Un jeton de sélection reste non destructif et résoluble pendant son TTL pour préserver l'idempotence CRM.
11. Un `place_id` peut apparaître dans la valeur éphémère du jeton de sélection, jamais dans son nom de clé ni un log.
12. La charge du jeton de carte ne contient aucun `place_id`, nom, adresse, téléphone ou site Web.
13. Une erreur Redis avant l'appel fournisseur empêche tout appel Google.
14. Une erreur Redis ne déclenche aucun repli mémoire silencieux.
15. Liveness reste indépendante de Redis ; readiness signale Redis indisponible.
16. Les implémentations mémoire ne sont utilisées que par injection explicite dans les tests unitaires.

## 5. Contrats applicatifs et erreurs

### 5.1 Ports conservés

Les signatures fonctionnelles restent :

```python
class GenerationGuard(Protocol):
    def hold(self, owner: GoogleAccessOwner) -> AbstractAsyncContextManager[None]: ...

class MapSnapshotGrantStore(Protocol):
    async def issue(self, payload: MapSnapshot, owner: GoogleAccessOwner) -> str: ...
    def redeem(self, token: str, owner: GoogleAccessOwner) -> AbstractAsyncContextManager[MapSnapshot]: ...

class GoogleSelectionGrantStore(Protocol):
    async def issue(self, place_ids: tuple[str, ...], owner: GoogleAccessOwner, *, now: datetime) -> str: ...
    async def resolve(self, token: str, owner: GoogleAccessOwner, *, now: datetime) -> tuple[str, ...]: ...
```

Le domaine, les routes et les cas d'utilisation n'importent jamais `redis.asyncio`, `RedisError` ou un script Lua.

### 5.2 Erreurs

Ajouter une erreur applicative `GoogleProtectionUnavailable`. Elle représente une impossibilité de garantir le
verrou ou les jetons, sans exposer Redis au contrat public.

| Erreur applicative | Route | HTTP | Code public | Appel Google |
| --- | --- | ---: | --- | :---: |
| `GoogleSearchInProgress` | recherche | 409 | `google_search_in_progress` | Non |
| `GoogleProtectionUnavailable` avant Text Search | recherche | 503 | `google_protection_unavailable` | Non |
| `GoogleProtectionUnavailable` pendant l'émission des jetons | recherche | 503 | `google_protection_unavailable` | Déjà effectué une fois |
| `InvalidMapSnapshotGrant` | carte | 403 | `invalid_map_grant` | Non |
| `MapSnapshotGrantInProgress` | carte | 409 | `map_grant_in_progress` | Non |
| `GoogleProtectionUnavailable` avant réclamation | carte | 503 | `google_protection_unavailable` | Non |
| `InvalidGoogleSelectionGrant` | ajout CRM | 400 | `google_selection_invalid` | Sans objet |
| `GoogleProtectionUnavailable` pendant la résolution | ajout CRM | 503 | `google_protection_unavailable` | Sans objet |

Les réponses utilisent le composant d'erreur commun, conservent `request_id` et portent `Cache-Control: no-store`.
Un mauvais propriétaire reçoit la même erreur que pour un jeton absent ou expiré.

## 6. Nommage, secrets et sérialisation

### 6.1 Clés

```text
prospect:{environment}:v1:google:{<organization_uuid>}:search-lock:<user_uuid>
prospect:{environment}:v1:map-grant:<sha256_token>
prospect:{environment}:v1:selection-grant:<sha256_token>
```

Le préfixe `prospect` est un identifiant technique historique conservé. `environment` appartient à la liste fermée
`development`, `test`, `staging`, `production`. Aucun nom d'organisation, courriel, requête, `place_id` ou contenu
Google n'apparaît dans les clés.

### 6.2 Jetons et valeurs propriétaires

- `secrets.token_urlsafe(32)` ou une primitive équivalente produit au moins 256 bits aléatoires ;
- le jeton opaque est rendu au navigateur seulement dans la réponse `no-store` ;
- Redis reçoit le hash SHA-256 hexadécimal du jeton comme suffixe de clé ;
- chaque acquisition de verrou ou réclamation de carte utilise une valeur propriétaire aléatoire distincte ;
- toute comparaison de valeur propriétaire est effectuée dans Redis avant la mutation.

### 6.3 Format des valeurs

Les données utilisent JSON UTF-8 strict, avec `schema_version=1`. Les décodeurs refusent champ manquant, type
inattendu, UUID invalide, nombre non fini, point hors bornes ou plus de vingt éléments.

Valeur de carte minimale :

```json
{
  "schema_version": 1,
  "user_id": "uuid",
  "organization_id": "uuid",
  "state": "available",
  "claim_id": null,
  "center_latitude": 46.8139,
  "center_longitude": -71.208,
  "radius_km": 15,
  "points": [{"latitude": 46.81, "longitude": -71.20}]
}
```

Valeur de sélection minimale :

```json
{
  "schema_version": 1,
  "user_id": "uuid",
  "organization_id": "uuid",
  "place_ids": ["référence-google"]
}
```

Le nom Google et le nom interne CRM ne sont jamais contenus dans ces valeurs. Le nom interne continue d'être envoyé
séparément au moment de l'ajout CRM.

## 7. Verrou Redis de recherche

### 7.1 Acquisition

- classe : `RedisGenerationGuard` ;
- clé dérivée du couple organisation/utilisateur ;
- valeur : secret propriétaire d'au moins 256 bits ;
- commande atomique équivalente à `SET key owner NX PX ttl_ms` ;
- TTL par défaut : 45 secondes ;
- le TTL doit être au minimum égal à `GOOGLE_PLACES_TIMEOUT_SECONDS + 2 × DEPENDENCY_CONNECT_TIMEOUT_SECONDS + 5` afin de couvrir l'émission séquentielle des deux jetons ;
- échec `NX` : `GoogleSearchInProgress`, sans attente, quota ni appel Google ;
- erreur Redis : `GoogleProtectionUnavailable`.

Le lot n'introduit ni file d'attente, ni attente active, ni renouvellement automatique du verrou. Le délai Places est
borné et la marge est validée au démarrage. L'expiration protège contre un processus arrêté brutalement.

### 7.2 Libération

La sortie du contexte exécute un script compare-and-delete :

```text
si GET(key) == owner alors DEL(key), sinon ne rien modifier
```

Une instance ne peut donc pas effacer un verrou réacquis après expiration. La libération est tentée dans `finally`, y
compris après exception ou annulation. Son échec est signalé techniquement sans masquer l'exception métier initiale ;
le TTL demeure le filet de sécurité. Si le parcours a réussi, un échec de libération ne remplace pas la réponse utile
par une erreur et ne provoque jamais un rejeu du fournisseur.

## 8. Jeton Redis de carte

### 8.1 Émission

- classe : `RedisMapSnapshotGrantStore` ;
- TTL par défaut et maximum hors test : 300 secondes ;
- création atomique avec absence préalable et TTL immédiat ;
- trois tentatives maximum en cas de collision cryptographique de clé ;
- aucune éviction d'un autre jeton ; une erreur de capacité/mémoire Redis devient `GoogleProtectionUnavailable` ;
- la charge est limitée au centre, rayon et vingt points cartographiques maximum.

### 8.2 Réclamation

Un script atomique retourne un résultat fermé :

- clé absente, expirée, version invalide ou mauvais propriétaire : `invalid` ;
- état `claimed` : `in_progress` ;
- état `available` du propriétaire : passage à `claimed`, écriture d'un `claim_id` aléatoire et retour de la charge ;
- le TTL existant est préservé et n'est jamais prolongé par la réclamation.

Le cas d'utilisation appelle Static Maps uniquement après le résultat `claimed`. Deux instances concurrentes ne
peuvent donc produire qu'un seul appel facturable.

### 8.3 Finalisation terminale

À la sortie du contexte, succès ou échec du fournisseur, un script supprime la clé uniquement si le propriétaire,
l'état et le `claim_id` correspondent. Si la finalisation échoue après une carte réussie, la carte peut être retournée
mais aucun second appel n'est tenté ; la clé reste `claimed` jusqu'à son expiration. Après arrêt brutal du détenteur,
le jeton expire et n'est jamais remis dans l'état `available`.

## 9. Jeton Redis de sélection

- classe : `RedisGoogleSelectionGrantStore` ;
- TTL par défaut : 600 secondes ; maximum staging/production : 900 secondes ;
- liste ordonnée, dédupliquée et bornée à vingt `place_id` ;
- aucune donnée descriptive Google et aucun nom interne ;
- liaison au propriétaire utilisateur/organisation ;
- résolution par script : Redis vérifie le propriétaire avant de retourner les `place_id`, afin qu'une requête d'un
  autre acteur ne fasse jamais sortir la charge de Redis ;
- `resolve` est une lecture non destructive et ne renouvelle jamais le TTL ;
- mauvais acteur, version invalide, expiration ou clé absente : `InvalidGoogleSelectionGrant` ;
- panne Redis ou valeur indécodable : `GoogleProtectionUnavailable` ;
- une valeur corrompue peut être supprimée en meilleur effort, mais ne doit jamais être retournée.

Une recherche sans résultat peut émettre un jeton contenant une liste vide afin de conserver le contrat de réponse
actuel ; ce jeton ne permet aucune création CRM.

## 10. Scripts et résultats incertains

- scripts courts et versionnés avec les sources ;
- chargement via `SCRIPT LOAD`/`EVALSHA` ou mécanisme équivalent de `redis-py` ;
- un seul rechargement/rejeu après `NOSCRIPT`, car le script absent n'a pas été exécuté ;
- aucun rejeu automatique après timeout ou rupture réseau lorsque l'effet est incertain ;
- pour le verrou, une acquisition incertaine répond `503` et le secret propriétaire/TTL empêchent une suppression
  étrangère ;
- pour la carte, une réclamation incertaine répond `503` et aucun appel Maps n'est effectué ;
- pour la sélection, `issue` incertain fait échouer la recherche après son unique Text Search et `resolve` incertain
  fait échouer l'ajout sans écriture CRM ;
- aucune situation incertaine ne déclenche un nouvel appel Google dans la même requête.

Les scripts multi-clés futurs devront utiliser le même hash slot. Les scripts de 2.6.1 n'ont qu'une clé chacun.

## 11. Câblage par profil

### 11.1 Règles

| Profil | `REDIS_URL` | Câblage Google | Démarrage/readiness |
| --- | --- | --- | --- |
| `production` | obligatoire | trois adaptateurs Redis | configuration absente refusée au démarrage ; panne ultérieure `not_ready` |
| `staging` | obligatoire | trois adaptateurs Redis | même règle que production |
| `development` | renseignée | trois adaptateurs Redis | readiness selon le ping Redis |
| `development` | absente | adaptateurs fermés explicitement indisponibles, jamais mémoire | application démarre, readiness `not_ready`, parcours Google `503` |
| `test` via `build_container()` | renseignée | trois adaptateurs Redis | Redis réel obligatoire pour l'intégration |
| test unitaire avec conteneur injecté | sans objet | fakes ou mémoire explicitement injectés | aucune sélection automatique par profil |

L'absence d'URL n'autorise jamais `build_container()` à construire une implémentation mémoire. En staging et
production, la validité de la configuration est contrôlée avant construction. Une indisponibilité après démarrage ne
tue pas la liveness : elle rend la readiness non prête et les opérations concernées indisponibles jusqu'au retour de
Redis.

Pour le développement sans Redis, `UnavailableGenerationGuard`, `UnavailableMapSnapshotGrantStore` et
`UnavailableGoogleSelectionGrantStore` implémentent les ports en levant immédiatement
`GoogleProtectionUnavailable`. Ce ne sont ni des stockages ni des replis ; aucune donnée ou concession n'y est créée.

### 11.2 Assemblage

- le même `RedisResource` et son pool sont injectés dans les adaptateurs d'une instance ;
- deux instances possèdent des pools distincts et partagent seulement l'URL/serveur Redis ;
- `bootstrap.py` n'importe plus `backend.app.infrastructure.memory` ;
- les façades `generation_lock.py` et `map_snapshot_grants.py` sont supprimées ou cessent de réexporter des classes
  mémoire ;
- les tests historiques migrent vers les ports ou les doublures explicites ;
- les classes mémoire peuvent rester sous `infrastructure/memory/` avec une docstring « tests unitaires uniquement ».

### 11.3 Paramètres

| Variable | Défaut | Validation 2.6.1 |
| --- | ---: | --- |
| `GOOGLE_SEARCH_LOCK_TTL_SECONDS` | `45` | au moins timeout Places + deux timeouts Redis + 5 s |
| `MAP_SNAPSHOT_GRANT_TTL_SECONDS` | `300` | positif ; maximum 300 hors test |
| `GOOGLE_SELECTION_GRANT_TTL_SECONDS` | `600` | positif ; maximum 900 en staging/production |
| `REDIS_MAX_CONNECTIONS` | `20` | positif ; pool partagé dans l'instance |
| `DEPENDENCY_CONNECT_TIMEOUT_SECONDS` | `2` | positif ; utilisé pour connexion et opérations de protection |

`MAP_SNAPSHOT_GRANT_MAX_ENTRIES` et `GOOGLE_SELECTION_GRANT_MAX_ENTRIES` ne pilotent pas Redis et sont retirés de la
configuration de production. Ils peuvent rester comme arguments de doublures mémoire dans les tests.

## 12. Ordre des parcours et compensations

### 12.1 Recherche

1. authentifier et valider l'organisation/capacité ;
2. vérifier la configuration Google ;
3. valider la commande ;
4. acquérir le verrou Redis ;
5. exécuter exactement un Text Search ;
6. construire les charges éphémères ;
7. émettre le jeton de carte puis le jeton de sélection ;
8. libérer le verrou ;
9. retourner la réponse `no-store`.

Si le second jeton échoue après émission du premier, la réponse est `503`. Le premier jeton, jamais communiqué au
client, reste inaccessible et expire automatiquement. Il n'est pas nécessaire d'introduire une transaction Redis
multi-clés ou un port composite dans 2.6.1.

### 12.2 Carte

1. authentifier et vérifier `google:map` ;
2. réclamer atomiquement le jeton ;
3. appeler Static Maps exactement une fois ;
4. finaliser le jeton dans `finally` ;
5. retourner l'image `no-store` ou l'erreur contrôlée.

### 12.3 Ajout CRM

1. authentifier et vérifier `prospects:create` ;
2. résoudre le jeton de sélection sans le consommer ;
3. vérifier tous les `place_id` de la commande ;
4. enregistrer uniquement le `place_id` et le nom interne CRM saisi séparément ;
5. conserver l'idempotence par organisation et `place_id`.

## 13. Tests obligatoires

### 13.1 Unitaires

- validation des paramètres et bornes de TTL ;
- sérialisation/désérialisation valide, version inconnue et charge corrompue ;
- hash du jeton sans jeton brut dans la clé ;
- traduction de `RedisError` en `GoogleProtectionUnavailable` ;
- aucune libération aveugle ;
- aucun appel Google après refus ou résultat incertain Redis ;
- ports et cas d'utilisation sans import Redis ;
- aucune implémentation mémoire importée par `bootstrap.py`.

### 13.2 Redis réel

Avec deux `RedisResource` et deux pools :

- même verrou acquis simultanément : exactement un détenteur ;
- propriétaires différents : deux acquisitions possibles ;
- non-propriétaire incapable de libérer ;
- verrou disponible après libération et après TTL court ;
- jeton de carte émis par A et réclamé par B ;
- deux réclamations concurrentes : une charge rendue et un `MapSnapshotGrantInProgress` ;
- mauvais acteur : refus sans consommation ;
- succès et échec Maps rendent le jeton terminal ;
- jeton de sélection émis par A, résolu plusieurs fois par B, refusé à un autre acteur puis expiré ;
- chaque clé possède immédiatement un `PTTL` positif et disparaît ;
- aucune clé ne contient jeton brut, `place_id`, requête ou donnée descriptive ;
- arrêt Redis : erreurs fermées et aucun appel fournisseur.

Les TTL de test sont courts ; aucun test n'attend 45, 300 ou 600 secondes.

### 13.3 Deux applications FastAPI

- deux `AppContainer`, deux `RedisResource`, deux clients HTTP et un même Redis ;
- une même session peut être restaurée sur A et B ;
- deux recherches concurrentes du même acteur produisent un `200`, un `409` et exactement un appel au faux Places ;
- le jeton de carte reçu de A fonctionne sur B et devient ensuite invalide sur A ;
- le jeton de sélection reçu de A permet l'ajout CRM sur B ;
- aucune sticky session n'est requise ;
- `no-store`, `request_id` et codes publics sont vérifiés.

### 13.4 Non-régression

- un Text Search, vingt résultats, aucun `nextPageToken` suivi ;
- aucun téléphone/site Web et aucune route d'export ;
- attribution Google Maps et bouton d'export inaccessible ;
- aucun stockage navigateur ;
- `place_id` visible/immuable séparé du nom interne ;
- tests React des messages `409` et `503` ;
- toutes les suites 2.5 restent vertes.

## 14. CI, documentation et exploitation

- `compose.test.yaml` conserve Redis réel et fournit des ports configurables ;
- les tests Redis/two-instance sont inclus dans pytest et deviennent obligatoires avec
  `REQUIRE_INFRASTRUCTURE_TESTS=true` ;
- le verrou local refuse tout `skip` ;
- Azure corrige la révision attendue à `20260815_0013` et publie les JUnit même en échec ;
- `.env.example` documente les TTL et le caractère obligatoire de Redis ;
- le README Windows/WSL documente démarrage, readiness et panne Redis ;
- un guide technique décrit clés, valeurs, scripts, rotation/expiration et procédure de diagnostic ;
- le manuel utilisateur explique le message de protection temporairement indisponible sans citer Redis ;
- aucune clé ou valeur Redis réelle n'est incluse dans une capture, un rapport ou un artefact.

Références techniques officielles :

- [Redis — SET](https://redis.io/docs/latest/commands/set/)
- [Redis — Distributed Locks](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/)
- [Redis — Scripting with Lua](https://redis.io/docs/latest/develop/interact/programmability/eval-intro/)
- [Redis — EXPIRE](https://redis.io/docs/latest/commands/expire/)

## 15. Critères de sortie

2.6.1 est terminé lorsque :

1. `build_container()` ne référence aucun adaptateur mémoire Google ;
2. staging/production sans Redis sont refusés et développement sans Redis échoue fermé ;
3. deux instances partagent effectivement verrou, jeton de carte et jeton de sélection ;
4. un seul détenteur existe pour chaque verrou/réclamation concurrente ;
5. les mauvais acteurs n'altèrent aucune concession ;
6. les expirations sont prouvées sur Redis réel ;
7. aucun test d'infrastructure n'est ignoré dans le verrou ;
8. les protections Google et l'identité prospect pré-2.6 restent vertes ;
9. Ruff, format Ruff, mypy, pytest, Alembic, ESLint, Vitest et build sont verts ;
10. la documentation, le rapport d'implémentation et les preuves locales sont à jour.

L'exécution Azure verte finale reste exigée à la clôture de 2.6.3, mais le pipeline modifié par 2.6.1 ne doit pas
être laissé volontairement rouge.

## 16. Seize décisions validées

Les seize décisions ci-dessous ont été validées par le responsable produit le 25 août 2026.

1. 2.6.1 reste un lot backend/infrastructure sans migration PostgreSQL, quota quotidien ni changement visuel majeur.
2. Les signatures des trois ports existants sont conservées ; Redis reste strictement un adaptateur d'infrastructure.
3. Les adaptateurs concrets sont `RedisGenerationGuard`, `RedisMapSnapshotGrantStore` et `RedisGoogleSelectionGrantStore`, construits avec le même pool Redis par instance.
4. Les clés conservent le préfixe technique `prospect:{environment}:v1`, utilisent le couple utilisateur/organisation pour le verrou et le SHA-256 du jeton opaque pour les concessions.
5. Le verrou utilise `SET NX PX`, un propriétaire aléatoire d'au moins 256 bits, un TTL de 45 secondes sans renouvellement et une libération compare-and-delete.
6. Une contention retourne immédiatement `409` sans attente ni appel Google ; une panne Redis retourne `503` sans repli mémoire.
7. Le jeton de carte dure au maximum cinq minutes, contient uniquement centre/rayon/points et est lié à l'utilisateur et à l'organisation.
8. La réclamation de carte est atomique, préserve le TTL, distingue invalidité et concurrence, et devient terminale après une tentative Maps, succès ou échec.
9. Le jeton de sélection dure dix minutes, contient au maximum vingt `place_id`, reste non destructif et ne renouvelle pas son TTL.
10. Les jetons sont aléatoires, jamais stockés en clair dans les clés ou journaux ; les valeurs JSON portent `schema_version=1` et des charges strictement validées.
11. `NOSCRIPT` autorise un seul rechargement/rejeu ; timeout et rupture réseau ne sont jamais rejoués lorsque l'effet Redis est incertain.
12. Production et staging exigent `REDIS_URL` ; développement sans Redis utilise trois adaptateurs fermés sans stockage, peut démarrer mais reste `not_ready` et refuse les parcours Google en `503`.
13. `build_container()` ne sélectionne jamais la mémoire ; les adaptateurs mémoire restent uniquement des doublures explicitement injectées dans les tests unitaires.
14. Une émission partielle des deux jetons répond `503`; un jeton non communiqué n'est pas compensé mais expire automatiquement et ne provoque aucun second appel Google.
15. La validation impose Redis réel, deux pools, deux applications, concurrence, mauvais acteur, panne, `PTTL`, absence de fuite et non-régression Google/Marketteo.
16. Le lot met à jour configuration, verrou local, Azure, documentation technique/utilisateur et exige tous les contrôles qualité verts avant GO 2.6.2.

## 17. Décision de sortie

- **GO implémentation 2.6.1** : accordé le 25 août 2026 ;
- la recette fonctionnelle sera regroupée à la clôture de la phase 2.6 ;
- **NO-GO** : une régression des protections Google, un test Redis multi-instance absent ou un contrôle qualité rouge
  bloque la clôture de 2.6.1.
