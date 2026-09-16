# Phase 2.6.2 — Quotas et droits préparatoires

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 2.6 — Redis partagé, quotas et durcissement |
| Sous-incrément | 2.6.2 — Quotas et droits préparatoires |
| Version | 1.0 — validée |
| Prérequis | 2.6.1 implémenté ; Redis partagé requis pour le parcours Google ; tête Alembic `20260815_0013` |
| Statut | Spécifications validées — implémentation autorisée |
| Date | 25 août 2026 |
| Résultat attendu | Une tentative Text Search autorisée réserve atomiquement un budget utilisateur et organisation, ou est refusée en `429` sans appel Google |

Ce document décline, pour le seul incrément 2.6.2, les décisions déjà validées dans la spécification parente
[`PHASE_2_6_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_6_SPECIFICATIONS_DETAILLEES.md). Il ne modifie ni les limites de
conformité Google, ni le modèle PostgreSQL, ni l'interface commerciale ou de facturation.

## 1. Constat et objectif

Depuis 2.6.1, les verrous et jetons Google sont partagés par Redis et le parcours échoue fermé sans Redis. Il manque
encore la borne de coût quotidienne : une organisation ou l'un de ses membres peut aujourd'hui effectuer autant de
recherches autorisées que le fournisseur le permet.

2.6.2 introduit donc une protection opérationnelle, non financière :

- **20** recherches Text Search par utilisateur dans son organisation active et par journée UTC ;
- **100** recherches Text Search par organisation et par journée UTC ;
- une réservation atomique de ces deux unités avant l'unique appel Google ;
- un refus explicite et non ambigu lorsque l'une des bornes est atteinte ;
- un port de politique qui pourra ultérieurement être alimenté par un abonnement, sans créer dès maintenant un
  catalogue, une souscription ou un prix.

Un compteur Redis n'est pas une facture, une mesure contractuelle ni un registre durable de consommation. Il protège
le budget technique Google en attendant le futur volet de facturation.

## 2. Périmètre

### 2.1 Inclus

- contrat applicatif de politique de recherche Google et adaptateur de paramètres serveur ;
- contrat applicatif de réservation de quota ;
- compteurs Redis par utilisateur et organisation, bornés par jour UTC ;
- opération serveur opaque et idempotente pour une réservation ;
- script Redis atomique compatible Redis Cluster ;
- intégration du quota dans le cas d'utilisation de recherche, après le verrou et avant Places ;
- erreur publique `429 google_quota_exceeded`, en-tête `Retry-After` et `Cache-Control: no-store` ;
- signal technique unique lors du franchissement de 80 % ;
- tests de concurrence réels : 20 acceptations utilisateur, 100 acceptations organisation et refus sans incrément
  partiel ;
- mise à jour des paramètres d'exemple, des guides et des contrôles ciblés.

### 2.2 Exclus

- plans Freemium, Starter, Business ou Sur mesure, prix, taxes, paiement, abonnement et webhooks ;
- stockage PostgreSQL d'une consommation, rapport client ou réconciliation financière ;
- écran d'administration des limites, dérogations, alertes par courriel ou bannière de consommation ;
- quota sur Static Maps, Place Details, résolution de ville, import, acquisition ou CRM ;
- remboursement/décrément après une erreur Google ;
- changement de la règle : un Text Search, vingt résultats, aucun téléphone/site Web et aucune pagination ;
- migration Alembic : aucune table relationnelle ne change dans cet incrément.

## 3. Invariants non négociables

1. Le navigateur ne fournit ni limite, ni compteur, ni identifiant d'opération de quota.
2. La fenêtre de référence est la journée **UTC**, indépendamment du fuseau de l'utilisateur ou de l'organisation.
3. Une recherche doit posséder le verrou distribué avant toute réservation de quota.
4. Une réservation accepte les deux portées ou aucune : aucun compteur utilisateur/organisation ne peut diverger.
5. Une réservation acceptée reste consommée après une erreur Places, une réponse Google `429`, une erreur réseau ou
   un échec ultérieur d'émission de jeton.
6. Un verrou refusé, une commande invalide, une session invalide ou une autorisation absente ne consomment rien.
7. Un quota refusé ne déclenche aucun appel Places, Maps ou jeton.
8. Redis indisponible ou résultat de réservation indéterminé produisent `503` avant Google ; aucun repli mémoire
   n'est autorisé.
9. Une même opération interne peut être rejouée au plus une fois et ne compte jamais deux unités.
10. Une opération différente compte une nouvelle unité, même si la requête utilisateur est similaire.
11. Les clés et valeurs de quota ne contiennent ni texte recherché, ni résultat, ni courriel, ni nom d'organisation,
    ni `place_id`, ni jeton.
12. Toute clé créée possède, dès sa création, une expiration à la prochaine minuit UTC.
13. `Retry-After` est un entier positif cohérent avec la même échéance UTC.
14. La politique est calculée côté serveur à partir de l'organisation active ; elle est immuable pendant une
    exécution.
15. Le seuil de 80 % avertit une seule fois par portée et jour ; il ne bloque pas et n'envoie aucun courriel dans
    2.6.2.
16. Les adaptateurs mémoire ne sont admis que comme fakes injectés dans les tests unitaires, jamais dans
    `build_container()`.

## 4. Modèle applicatif et ports

### 4.1 Politique immuable

Le domaine applicatif ajoute `GoogleSearchQuotaPolicy` :

```text
enabled: bool
user_daily_limit: int
organization_daily_limit: int
warning_threshold_percent: int
policy_code: str
```

Règles de validation :

- limites entières comprises entre `0` et `10_000` ; `0` désactive explicitement la portée ;
- seuil entier entre `1` et `100`, défaut `80` ;
- `policy_code` est une valeur technique courte, issue d'une liste contrôlée, par défaut
  `server_default_v1` ; il n'est ni un nom de plan commercial, ni une donnée client ;
- l'adaptateur de 2.6.2 retourne toujours `enabled=true` : le champ prépare les futurs droits, mais ne crée pas un
  nouveau motif de refus visible dans cet incrément.

Le port `GoogleSearchPolicyProvider` expose une opération de résolution à partir du contexte locataire. Il ne reçoit
ni corps HTTP, ni recherche Google. L'adaptateur de paramètres est synchrone et déterministe ; son remplacement futur
par un résolveur de droits d'abonnement ne doit pas modifier le cas d'utilisation.

### 4.2 Réservation de quota

Le port `GoogleSearchQuota` expose une réservation :

```text
reserve(owner, policy, operation_id, now) -> QuotaReservation
```

`QuotaReservation` contient uniquement :

- `allowed` ;
- `scope` (`user` ou `organization`) lorsque la réservation est refusée ;
- consommations et restants des portées de l'acteur courant ;
- `reset_at` UTC et `retry_after_seconds` ;
- `policy_code` ;
- les indicateurs internes d'avertissement, sans les rendre obligatoirement visibles au navigateur.

Le port lève `GoogleProtectionUnavailable` si Redis ne répond pas de manière certaine. Un résultat `allowed=false`
n'est pas une exception technique : le cas d'utilisation le traduit en erreur métier dédiée, puis la route en `429`.

### 4.3 Composition et dépendances

Les nouveaux contrats sont placés dans `application/ports/`. Les structures de données et les erreurs restent dans
`application/`. L'adaptateur `RedisGoogleSearchQuota` appartient à `infrastructure/redis/` ; l'adaptateur
`SettingsGoogleSearchPolicyProvider` appartient à `infrastructure/config/` ou à l'infrastructure déjà utilisée pour
la configuration. `bootstrap.py` réalise la seule composition concrète.

Le cas d'utilisation de recherche reçoit les deux ports, une horloge injectée et un générateur d'UUID injectable. Il
ne dépend jamais directement de `redis.asyncio`, Lua ou des paramètres d'environnement.

## 5. Politique initiale et préparation des futurs plans

Les variables initiales sont :

| Variable | Défaut | Validation |
| --- | ---: | --- |
| `GOOGLE_SEARCH_USER_DAILY_LIMIT` | `20` | entier de `0` à `10_000` |
| `GOOGLE_SEARCH_ORGANIZATION_DAILY_LIMIT` | `100` | entier de `0` à `10_000` |
| `GOOGLE_SEARCH_QUOTA_WARNING_PERCENT` | `80` | entier de `1` à `100` |
| `GOOGLE_SEARCH_QUOTA_POLICY_CODE` | `server_default_v1` | code technique `[a-z0-9_]{3,64}` |

En staging et production, ces quatre paramètres doivent être explicitement valides au démarrage. Les valeurs par
défaut restent possibles en développement et en test pour faciliter une exécution locale contrôlée. Une valeur
négative, flottante, vide ou hors borne empêche le démarrage ; aucune conversion silencieuse n'est autorisée.

Le futur module d'abonnement remplacera seulement le fournisseur de politique. Il devra calculer la valeur effective
la plus restrictive entre les droits de plan, les dérogations contractualisées et la limite de sécurité de
l'exploitant. Il ne doit pas réutiliser directement les compteurs temporaires Redis comme registre de facturation.

## 6. Contrat Redis atomique

### 6.1 Clés

Pour un environnement `environment`, une organisation `organization_id`, un utilisateur `user_id`, la date UTC
`YYYY-MM-DD` et l'opération serveur `operation_id` :

```text
prospect:{environment}:v1:google:{<organization_id>}:quota:<YYYY-MM-DD>:organization
prospect:{environment}:v1:google:{<organization_id>}:quota:<YYYY-MM-DD>:user:<user_id>
prospect:{environment}:v1:google:{<organization_id>}:quota:<YYYY-MM-DD>:operation:<operation_id>
prospect:{environment}:v1:google:{<organization_id>}:warning:<YYYY-MM-DD>:organization
prospect:{environment}:v1:google:{<organization_id>}:warning:<YYYY-MM-DD>:user:<user_id>
```

Les accolades de l'organisation sont le hash tag Redis Cluster commun à toutes les clés manipulées par un même
script. Les UUID sont internes ; aucune donnée commerciale ou personnelle ne figure dans les noms de clés.

### 6.2 Valeurs et expiration

- Les deux compteurs sont des entiers Redis non négatifs.
- L'opération est un petit JSON versionné contenant seulement résultat, portée de refus éventuelle, compteurs,
  limites, échéance UTC et `policy_code` ; elle ne contient ni requête ni identité personnelle.
- Une clé d'avertissement est une sentinelle de valeur constante. Elle ne porte pas de compteur ou de contenu.
- Toutes les clés sont créées avec `EX`/`PEXPIRE` atomiquement dans le script et expirent à la prochaine minuit UTC.
- À 23:59:59.500 UTC, `retry_after_seconds` vaut au moins `1` et les clés n'expirent jamais avant la réponse.
- Le TTL d'une clé existante n'est jamais prolongé au-delà de l'échéance de sa journée ; les opérations répétées de
  la même journée ne déplacent pas la remise à zéro.

### 6.3 Algorithme Lua

Un unique script court et déterministe reçoit les cinq clés, les limites, le seuil, l'expiration calculée côté
serveur et `operation_id`.

1. Il lit la clé d'opération. Si elle existe et est valide, il retourne exactement son résultat sans modifier les
   compteurs.
2. Il lit les compteurs utilisateur et organisation, en traitant une clé absente comme `0`.
3. Il vérifie d'abord la limite utilisateur, puis la limite organisation. Une double saturation retourne
   `user`, afin de ne pas révéler plus que nécessaire sur le budget partagé.
4. Si une limite serait dépassée, il enregistre le refus pour cette opération avec la même expiration et ne modifie
   aucun compteur.
5. Sinon il incrémente les deux compteurs, fixe leur expiration si nécessaire, puis mémorise le succès de
   l'opération avec la même expiration.
6. Après un succès, il calcule le franchissement du seuil sans approximation flottante
   (`used * 100 >= limit * threshold`). Il pose une sentinelle `SET NX` par portée concernée avec la même expiration
   et retourne seulement si la sentinelle vient d'être créée.
7. Il retourne un résultat compact, intégralement validé par l'adaptateur Python.

L'adaptateur utilise `SCRIPT LOAD` puis `EVALSHA`. Un `NOSCRIPT` autorise un seul rechargement/rejeu car le script
absent n'a pas été exécuté. Un timeout, une fermeture de connexion ou une erreur réseau n'est pas assimilé à
`NOSCRIPT` : l'adaptateur effectue au plus une lecture de la clé d'opération avec le même identifiant. Si son état
reste inconnu, il lève `GoogleProtectionUnavailable` ; l'API répond `503` et n'appelle pas Google. Au pire une unité
peut avoir été réservée, jamais deux.

### 6.4 Portées et exemples

- Avec 20/100, le 20e appel d'un membre est accepté ; son 21e est refusé `scope=user` même si l'organisation est à
  20/100.
- Cent appels de membres distincts ou non sont acceptés pour l'organisation ; le 101e est refusé
  `scope=organization` si son quota personnel le permet encore.
- Pour une limite utilisateur à `0`, toute réservation est refusée `scope=user`. Pour une limite organisation à `0`,
  elle est refusée `scope=organization`.
- Le même utilisateur dans deux organisations consomme deux compteurs indépendants.

## 7. Ordre du parcours de recherche

L'ordre strict dans `SearchGooglePlacesUseCase` est :

1. session, organisation active et capacité `google:search` ;
2. configuration Google et validation de la commande ;
3. résolution serveur de la politique ;
4. acquisition du verrou Redis utilisateur/organisation ;
5. génération de l'identifiant d'opération serveur ;
6. réservation atomique du quota ;
7. unique appel Places Text Search ;
8. construction des 20 résultats maximum et émission des deux jetons Redis ;
9. libération protégée du verrou dans le `finally` ;
10. réponse `no-store`.

Une politique ne peut être consultée ni un quota réservé pour une commande qui n'a pas passé les validations déjà
existantes. Le verrou est délibérément avant le quota : une seconde requête concurrente renvoie `409` sans consommer
un budget. Un refus de quota arrête le parcours avant le fournisseur et avant toute carte.

Il n'y a aucune compensation après le point 6. La consommation représente une tentative Google autorisée, pas une
réponse réussie du fournisseur. Les jetons, carte, sélection, masques de champs et règles Google de 2.6.1 restent
inchangés.

## 8. Contrat HTTP et interface

### 8.1 Réponse de quota

Un quota atteint produit :

```http
HTTP/1.1 429 Too Many Requests
Cache-Control: no-store
Retry-After: <secondes-jusqu-à-minuit-UTC>
X-Request-ID: <identifiant>
```

```json
{
  "error": {
    "code": "google_quota_exceeded",
    "message": "La limite quotidienne de recherches Google est atteinte. Réessayez après la remise à zéro.",
    "request_id": "…",
    "fields": { "scope": "user" }
  }
}
```

`scope` vaut exclusivement `user` ou `organization`. Le corps ne retourne ni limite brute, ni consommation, ni
`policy_code`, ni date détaillée d'un autre membre. `Retry-After` est l'information opérationnelle suffisante pour
le client. Le même format avec `scope=organization` est utilisé si le budget partagé est atteint.

`503 google_protection_unavailable` reste réservé aux pannes ou résultats Redis indéterminés. `409
google_search_in_progress` garde sa priorité lorsqu'un même acteur a déjà une recherche en cours.

### 8.2 Frontend

Le client API centralisé transforme `429 google_quota_exceeded` en un message français/anglais localisable. Le bouton
de recherche n'est désactivé que pendant une soumission en cours : il n'y a pas de stockage navigateur du compteur,
ni tentative locale d'estimer le solde ou l'heure de remise à zéro. Après `429`, l'utilisateur peut corriger ses
paramètres mais une nouvelle soumission restera soumise au serveur.

Il n'y a pas de tableau de bord de quota, de compteur affiché, de sélection de plan ou de changement visuel majeur
dans 2.6.2. L'attribution Google, l'export désactivé et le `place_id`/nom interne restent inchangés.

## 9. Stratégie de panne et confidentialité

| Situation | Réponse | Appel Google | Compteur |
| --- | --- | :---: | :---: |
| Validation/session/capacité invalide | existant `401`/`403`/`422` | Non | Non |
| Verrou concurrent | `409 google_search_in_progress` | Non | Non |
| Quota utilisateur atteint | `429` + `Retry-After`, scope `user` | Non | Inchangé |
| Quota organisation atteint | `429` + `Retry-After`, scope `organization` | Non | Inchangé |
| Redis indisponible avant réservation | `503 google_protection_unavailable` | Non | Non |
| Réservation indéterminée après résolution idempotente | `503 google_protection_unavailable` | Non | Zéro ou une unité |
| Places échoue après succès de quota | erreur fournisseur existante | Une fois | Conservé |
| Jeton échoue après Places | `503 google_protection_unavailable` | Une fois | Conservé |

Les erreurs, journaux temporaires et tests ne doivent jamais contenir la recherche, l'adresse, le courriel, un
cookie, une clé Google, un jeton, un `place_id` ou un nom d'organisation. L'audit métier PostgreSQL n'enregistre pas
non plus chaque recherche 2.6.2 : l'observabilité normalisée appartient à 2.6.3.

## 10. Tests obligatoires

### 10.1 Unitaires

- validation des quatre paramètres, bornes, valeur zéro et profils ;
- fournisseur de politique immuable et absent de l'autorité navigateur ;
- ordre exact : validation, verrou, quota, Places, jetons ;
- `409` sans réservation, `429` sans fournisseur, `503` sans fournisseur ;
- une réservation réussie demeure comptée après erreur Places ou jeton ;
- calcul de minuit UTC et `Retry-After` aux frontières ;
- format `429`, `no-store`, `scope` fermé et absence de données sensibles ;
- avertissement unique à 80 % sans notification utilisateur.

### 10.2 Redis réel et concurrence

Deux clients/pools Redis distincts doivent démontrer :

- exactement 20 réservations utilisateur concurrentes autorisées, puis la 21e refusée ;
- exactement 100 réservations organisation réparties entre au moins cinq utilisateurs, puis la 101e refusée ;
- aucune incrémentation partielle lors d'un refus utilisateur ou organisation ;
- deux opérations distinctes consomment deux unités ;
- le rejeu du même `operation_id` retourne le même résultat et consomme une seule unité ;
- après `SCRIPT FLUSH`, le rechargement `NOSCRIPT` conserve l'atomicité ;
- `PTTL` positif sur compteurs, opération et sentinelles, puis expiration dans une fenêtre de test dédiée ;
- le hash tag Redis Cluster des clés d'une réservation est identique ;
- Redis arrêté ou erreur simulée ferme le parcours avant Google.

### 10.3 API, frontend et non-régression

- deux applications FastAPI partagent Redis : une limite organisation est réellement commune ;
- un `429` ne fait aucune invocation du faux client Places et contient `Retry-After` ;
- l'interface affiche le message localisé, reste accessible et ne persiste aucun compteur ;
- 2.6.1 reste vert : verrou, carte, sélection inter-instance et `503` sans Redis ;
- conformité Google inchangée : un Text Search, 20 résultats, aucun `nextPageToken`, téléphone, site Web, export ou
  stockage navigateur ;
- identité Marketteo, `place_id` immuable et nom CRM séparé restent couverts.

## 11. CI, documentation et critères de sortie

La CI et le verrou local ajoutent les tests Redis de quota aux tests d'infrastructure obligatoires. `pytest` ne doit
tolérer aucun `skip` lorsque `REQUIRE_INFRASTRUCTURE_TESTS=true`. Les contrôles Ruff format/check, mypy, Alembic,
pytest, ESLint, Vitest/axe, build, `git diff --check` et contrôle de confidentialité restent requis.

La livraison met à jour :

- `.env.example` et README : limites initiales, UTC, variable de politique et stratégie de panne ;
- documentation technique : port, clé Redis, script, expiration, diagnostic d'un `429` ;
- manuel utilisateur : limite initiale non contractuelle, remise à zéro UTC et message de quota ;
- recette QA de clôture 2.6 : test de la 21e et de la 101e recherche avec deux instances ;
- rapport d'implémentation 2.6.2 : preuves de concurrence, versions et réserves.

2.6.2 sera prêt à être déclaré implémenté lorsque les bornes 20/100, l'atomicité, l'idempotence, les expirations,
les réponses `429` et l'absence d'appel Google sur refus seront prouvées sur Redis réel. La recette utilisateur
complète reste regroupée à la fin de 2.6.3, conformément à la décision de phase.

## 12. Risques et parades

| Risque | Criticité | Parade |
| --- | --- | --- |
| Double débit sous concurrence | Haute | Script unique, clés dans le même slot, `operation_id` serveur |
| Compteur utilisateur sans organisation | Haute | Vérification des deux limites avant toute mutation |
| Réponse Redis perdue puis double débit | Haute | Résultat d'opération mémorisé et résolution idempotente bornée |
| Quota traité comme facture | Haute | Redis éphémère, absence de prix/registre durable, documentation explicite |
| Fuite de consommation d'un autre membre | Haute | `scope` minimal, aucune valeur de compteur exposée |
| Déplacement de l'échéance | Moyenne | Date UTC, TTL fixé à minuit uniquement |
| Avertissements répétés | Moyenne | Sentinelle `SET NX` par portée/jour |
| Repli mémoire après panne | Haute | `503`, aucun adaptateur mémoire de production |
| Contournement frontend | Haute | Limites et opération exclusivement côté serveur |

## 13. Seize décisions validées

Les seize décisions ci-dessous ont été validées par le responsable produit le 25 août 2026.

1. 2.6.2 applique uniquement des quotas opérationnels Google ; il ne crée aucun plan, prix, abonnement, paiement ou registre de facturation.
2. La fenêtre de quota est une journée UTC et les limites initiales sont 20 recherches par utilisateur/organisation active et 100 par organisation.
3. Les limites `0` désactivent explicitement la portée ; les limites sont bornées à 10 000 et sont validées au démarrage.
4. `GoogleSearchQuotaPolicyProvider` et `GoogleSearchQuota` sont des ports applicatifs indépendants de Redis et des paramètres d'environnement.
5. La politique initiale est serveur, immuable pour une exécution, `enabled=true` et identifiée par `server_default_v1`; les futurs plans remplaceront seulement son fournisseur.
6. Une recherche valide prend le verrou avant de créer son identifiant d'opération et de réserver le quota ; un verrou refusé ne consomme rien.
7. Une opération UUID est générée côté serveur, n'est jamais transmise au navigateur ni aux métriques, et rend un rejeu technique idempotent sans fusionner deux actions utilisateur distinctes.
8. Un script Redis unique vérifie les limites utilisateur et organisation avant toute mutation, puis accepte les deux compteurs ou refuse les deux.
9. Les compteurs, résultat d'opération et sentinelles expirent à la prochaine minuit UTC ; leur TTL n'est jamais prolongé au-delà de cette fenêtre.
10. En cas de double saturation, le refus privilégie `scope=user`; le corps public ne divulgue que `user` ou `organization`, sans compteur ni droit commercial.
11. Une réservation acceptée reste consommée après toute erreur Google ou d'émission de jeton ; il n'existe ni remboursement ni décrément automatique.
12. Un quota atteint retourne `429 google_quota_exceeded`, `Cache-Control: no-store` et `Retry-After` positif ; aucun appel Google, Maps ou jeton ne suit.
13. Redis indisponible ou résultat indéterminé ferme le parcours en `503 google_protection_unavailable`, sans repli mémoire ; une unité au plus peut être réservée dans le cas indéterminé.
14. Le seuil de 80 % utilise une sentinelle atomique unique par portée et jour ; il ne produit ni courriel, ni bannière, ni écran de consommation dans 2.6.2.
15. Les tests Redis réels prouvent sous concurrence les bornes 20/100, absence d'incrément partiel, idempotence, `NOSCRIPT`, `PTTL`, deux instances et absence d'appel fournisseur après `429`.
16. La livraison actualise configuration, documentation, tests backend/frontend et CI ; le verrou qualité complet reste obligatoire avant la clôture de 2.6, tandis que la recette fonctionnelle est regroupée après 2.6.3.

## 14. Décision de sortie

- **GO d'implémentation 2.6.2** : accordé le 25 août 2026 ;
- la recette fonctionnelle reste regroupée à la clôture de la phase 2.6, après 2.6.3 ;
- **NO-GO de clôture** : une borne non atomique, un `429` provoquant un appel Google, une fuite de compteur ou un
  contrôle qualité rouge bloque la clôture de 2.6.2.

Toute évolution vers des plans commerciaux, une facturation, une persistance de consommation ou une interface de
gestion des quotas fera l'objet d'une spécification et d'une validation distinctes.
