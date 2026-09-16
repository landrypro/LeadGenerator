# Phase 2.6.3 — Observabilité et verrou final

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 2.6 — Redis partagé, quotas et durcissement |
| Sous-incrément | 2.6.3 — Observabilité et verrou final |
| Version | 1.0 — validée et implémentée |
| Prérequis | 2.6.1 et 2.6.2 implémentés ; tête Alembic `20260815_0013` |
| Statut | Implémenté — recette fonctionnelle différée au staging ; preuve Azure à exécuter |
| Date | 25 août 2026 |
| Résultat attendu | Une preuve reproductible que deux instances API protègent les appels Google partagés, que Redis expire les états temporaires et que tous les contrôles qualité sont verts sans test ignoré |

Ce document clôture la phase 2.6. Il transforme les protections déjà implémentées en éléments exploitables :
journaux techniques structurés et sûrs, métriques privées, pipeline Azure reproductible, rapport de preuve et recette
QA finale. Il n’introduit ni forfait commercial, ni facturation, ni écran de métriques, ni changement visuel du CRM.

## 1. Constat et objectif

Les incréments 2.6.1 et 2.6.2 ont mis le verrou, les concessions éphémères et les quotas Google dans Redis. Ils
protègent le coût et le parcours multi-instance, mais leur fonctionnement doit encore être observable sans recopier de
données Google ou personnelles dans des outils techniques.

Le verrou local possède déjà un chemin Docker Windows/WSL, des dépendances réelles isolées et des rapports JUnit.
L’expérience locale a toutefois montré deux risques à traiter explicitement :

- le démon Docker Windows peut être indisponible alors qu’un moteur Docker existe dans une distribution WSL ;
- un test lancé sans PostgreSQL, Redis et Mailpit configurés peut légitimement être ignoré pendant le développement,
  mais ne peut pas constituer une preuve de clôture.

2.6.3 doit donc fournir une preuve unique et lisible : deux applications indépendantes partagent Redis, les clés
temporaires disparaissent par TTL, aucune protection ne repasse en mémoire, et le même jeu de contrôles passe dans
Azure sans aucun `skip`.

## 2. Périmètre

### 2.1 Inclus

- configuration centralisée des journaux texte et JSON, corrélés par `request_id` et `instance_id` ;
- port applicatif de métriques, adaptateurs nul et Prometheus, sans dépendance de domaine à Prometheus ;
- instrumentation des verrous, quotas, jetons et appels Google déjà livrés ;
- endpoint interne de métriques explicitement activé, protégé par bearer dédié et non navigable ;
- tests de confidentialité des journaux et des labels de métriques ;
- test d’intégration avec deux conteneurs applicatifs/pools indépendants et Redis partagé ;
- contrôles Azure Pipelines, artefacts JUnit, rapport d’état Alembic et rapport final de clôture ;
- recette QA finale, guide opérateur et documentation utilisateur/technique actualisés.

### 2.2 Exclus

- collecte centralisée imposée (Application Insights, Datadog, ELK, Grafana Cloud ou équivalent) ;
- trace distribuée complète, OpenTelemetry, profilage ou APM payant ;
- interface utilisateur de statistiques, tableau de quota ou page d’administration des métriques ;
- suivi individuel des recherches, des résultats, des `place_id` ou des dépenses client ;
- alerte courriel/SMS, facturation, plans Freemium/Starter/Business, taxes ou paiement ;
- modification des règles Google : un seul Text Search, vingt résultats, sans téléphone/site Web et sans pagination ;
- nouvelle migration PostgreSQL : la tête reste `20260815_0013` si les modèles relationnels ne changent pas.

## 3. Invariants de clôture

1. Aucun journal, label de métrique, nom de fichier de rapport ou message d’erreur ne contient une clé, un secret,
   cookie, CSRF, mot de passe, jeton brut, courriel, texte recherché, `place_id`, nom Google, adresse, coordonnée,
   URL Google ou réponse fournisseur.
2. `request_id` et `instance_id` permettent de corréler un incident, mais ne sont jamais des labels Prometheus.
3. Les journaux techniques restent distincts de l’audit métier PostgreSQL ; ils ne modifient ni l’intégrité append-only
   ni la visibilité RLS de l’audit.
4. Les métriques ne sont accessibles ni à une session navigateur ni depuis la navigation React ; elles sont désactivées
   tant qu’elles ne sont pas explicitement configurées.
5. En staging et production, l’application refuse de démarrer si les métriques sont activées sans bearer secret ou si
   le format de journaux n’est pas JSON.
6. Une erreur de métrique ou de journalisation ne transforme jamais une recherche Google autorisée en second appel,
   ne consomme aucun jeton supplémentaire et ne contourne aucun quota.
7. Deux applications ayant des conteneurs, clients Redis et pools PostgreSQL distincts obtiennent exactement le même
   comportement de verrou, quota et jeton que derrière un répartiteur de charge.
8. Chaque clé Redis créée pour un verrou, un quota, une concession de carte ou une sélection possède un TTL positif ;
   aucune clé temporaire ne survit à son échéance attendue.
9. Le verrou de qualité final exécute les tests d’infrastructure avec PostgreSQL, Redis et Mailpit réels et refuse tout
   test ignoré, côté Python comme côté React.
10. Le résultat Azure publié est une preuve obligatoire de préproduction ; un résultat local vert le complète mais ne
    le remplace pas.

## 4. Architecture d’observabilité

### 4.1 Séparation des responsabilités

Un port `MetricsRecorder` est ajouté dans `application/ports/`. Ses méthodes sont typées et fermées, par exemple :

- `record_redis_operation(operation, outcome, duration_seconds)` ;
- `record_google_search_lock(outcome)` ;
- `record_google_search_quota(scope, outcome, policy_code)` ;
- `record_map_grant(action, outcome)` ;
- `record_selection_grant(action, outcome)` ;
- `record_google_upstream(api, outcome, duration_seconds)`.

Le domaine et les cas d’utilisation appellent le port, jamais `prometheus_client`, une API HTTP ou un logger concret.
L’adaptateur `NullMetricsRecorder` est injecté dans les tests unitaires qui ne vérifient pas les métriques. L’adaptateur
Prometheus est assemblé exclusivement dans `bootstrap.py`.

Un petit service de journalisation structurée est également assemblé au démarrage. Les couches application et
infrastructure lui transmettent uniquement un événement technique connu et des attributs validés. Aucun appel
`logger.info(..., payload)` ou interpolation d’une entrée utilisateur n’est admis dans les parcours sensibles.

### 4.2 Cardinalité et vocabulaire fermé

Les valeurs de labels sont limitées aux ensembles suivants :

| Label | Valeurs autorisées |
| --- | --- |
| `operation` | `lock_acquire`, `lock_release`, `quota_reserve`, `map_claim`, `map_finalize`, `selection_issue`, `selection_resolve` |
| `outcome` | `accepted`, `rejected`, `failed`, `expired`, `contended`, `unavailable` |
| `scope` | `user`, `organization` |
| `action` | `issued`, `claimed`, `rejected`, `resolved` |
| `api` | `places_text_search`, `maps_static` |
| `policy_code` | expression technique validée `[a-z0-9_]{3,64}` ; jamais une valeur libre client |

Tout nouvel événement, label ou valeur doit être ajouté à cette liste, documenté et couvert par un test. Les UUID,
routes brutes, `request_id`, adresse IP, noms d’organisation, noms de prospect, identifiants de fournisseur, jetons,
compteurs individuels et valeurs HTTP brutes sont interdits comme labels.

## 5. Journaux structurés et sûrs

### 5.1 Configuration et format

`LOG_FORMAT=text` est toléré en `development` et `test` pour faciliter le diagnostic local. `LOG_FORMAT=json` est
obligatoire en `staging` et `production`. `INSTANCE_ID` peut être fourni par le déploiement ; s’il est absent, une
valeur non secrète est générée une fois au démarrage et demeure constante pendant toute la vie du processus.

Chaque ligne JSON est UTF-8 et contient au minimum :

```json
{
  "timestamp": "2026-08-25T20:15:34.123Z",
  "level": "INFO",
  "event": "google_search_quota_consumed",
  "request_id": "opaque-request-id",
  "instance_id": "api-a",
  "outcome": "accepted"
}
```

Une fin de requête ajoute `route` **normalisée**, `method`, une classe de statut (`2xx`, `4xx`, `5xx`) et
`duration_ms`. Les routes `/api/health/*` et `/internal/metrics` ne génèrent pas de journal de succès de requête afin
de limiter le bruit ; leurs erreurs restent journalisées. Les exceptions applicatives produisent un code technique
contrôlé, sans message ou corps provenant d’un fournisseur.

Des UUID internes d’acteur ou d’organisation ne peuvent être ajoutés qu’à un événement de sécurité nécessitant une
investigation, jamais à une métrique, et restent interdits dans les événements Google courants. Le journal d’audit
demeure la source officielle pour savoir quel utilisateur a modifié une donnée CRM.

### 5.2 Événements obligatoires

Les événements ci-dessous constituent le minimum à instrumenter :

- `http_request_completed` et `http_request_failed` ;
- `google_search_lock_acquired`, `google_search_lock_contended`, `google_search_lock_release_failed` ;
- `google_search_quota_consumed`, `google_search_quota_rejected`, `google_search_quota_warning` ;
- `map_grant_issued`, `map_grant_claimed`, `map_grant_rejected` ;
- `selection_grant_issued`, `selection_grant_resolved`, `selection_grant_rejected` ;
- `redis_operation_failed` et `google_upstream_completed` ;
- `metrics_access_denied` (sans bearer ni adresse IP).

Les tests injectent volontairement chaque type de donnée interdite dans une commande et vérifient qu’elle ne se
retrouve ni dans les enregistrements capturés ni dans les erreurs publiques.

## 6. Métriques Prometheus privées

### 6.1 Séries exposées

L’export comporte exclusivement les séries suivantes, plus les métriques de processus/collecteur fournies par la
bibliothèque si elles ne contiennent aucun label applicatif :

```text
marketteo_redis_operation_duration_seconds{operation,outcome}
marketteo_google_search_lock_total{outcome}
marketteo_google_search_quota_total{scope,outcome,policy_code}
marketteo_google_map_grant_total{action,outcome}
marketteo_google_selection_grant_total{action,outcome}
marketteo_google_upstream_calls_total{api,outcome}
marketteo_google_upstream_duration_seconds{api,outcome}
```

Les durées sont des histogrammes à bornes raisonnables pour les délais Redis et HTTP ; elles n’incluent ni corps ni
taille de réponse. `outcome` est normalisé et ne reçoit jamais le message d’exception fournisseur.

### 6.2 Endpoint et protection

L’endpoint est `GET /internal/metrics`. Il n’appartient pas à `/api`, ne possède aucun lien ou appel React, n’accepte
ni cookie ni session, ne porte jamais de CORS permissif et répond avec le format Prometheus.

- `METRICS_ENABLED=false` : la route répond `404`, y compris avec un bearer ;
- `METRICS_ENABLED=true` : le bearer `Authorization: Bearer <METRICS_BEARER_TOKEN>` est obligatoire ; l’absence ou
  l’invalidité retourne le même `404` sans indication ;
- la comparaison du bearer utilise `secrets.compare_digest` (ou équivalent à temps constant) ;
- les réponses portent `Cache-Control: no-store`, `X-Robots-Tag: noindex, nofollow` et n’écrivent pas le bearer dans
  les journaux ;
- staging et production exigent un bearer d’au moins 32 octets, stocké dans le gestionnaire de secrets ;
- le réseau/reverse proxy autorise seulement le collecteur de métriques. Cette restriction réseau est documentée et
  vérifiée lors du déploiement, car l’application seule ne connaît pas la topologie d’hébergement.

La métrique d’un refus d’accès ne doit pas exposer le fait qu’un secret a été presque correct ; seul le journal
contrôlé `metrics_access_denied` est permis, sans en-tête ni valeur de réseau.

### 6.3 Défaillance de l’observabilité

L’adaptateur de métriques ne doit pas appeler de service externe dans le chemin de requête : l’incrémentation reste
locale au processus et l’export est lu par le collecteur. Une erreur interne de métrique est absorbée, comptée dans un
compteur interne non sensible lorsque possible et journalisée de façon minimale. Elle ne provoque ni repli mémoire,
ni second appel Google, ni refus artificiel après qu’un quota a été réservé.

## 7. Configuration, profils et exploitation

Les paramètres suivants sont ajoutés à `Settings`, validés au démarrage et documentés dans `.env.example` :

| Variable | Développement/test | Staging/production | Règle |
| --- | --- | --- | --- |
| `LOG_FORMAT` | `text` par défaut | `json` obligatoire | `text` ou `json` seulement |
| `INSTANCE_ID` | généré si absent | fourni ou généré si absent | non secret, longueur bornée, sans contrôle |
| `METRICS_ENABLED` | `false` par défaut | `true` exigé par le profil de déploiement | booléen explicite |
| `METRICS_BEARER_TOKEN` | vide si métriques désactivées | obligatoire si métriques actives | au moins 32 octets ; jamais dans le dépôt |

Le profil `test` peut activer un collecteur Prometheus isolé et un bearer de test fourni par la fixture. L’instance de
test ne partage pas le registre Prometheus global avec une autre application dans le même processus : un registre par
conteneur évite les doublons de séries et rend les tests à deux instances déterministes.

L’image/déploiement définit l’horloge UTC et NTP. Redis reste privé, authentifié et en politique `noeviction` (ou une
garantie équivalente). Le guide opérateur explique comment faire passer le collector via reverse proxy sans rendre
`/internal/metrics` public.

## 8. CI, Azure Pipelines et rapports

### 8.1 Verrou local unique

`scripts/Test-QualityGateLocal.ps1` reste la commande de référence. Il doit :

1. détecter Docker Windows puis, à défaut, un moteur Docker dans une distribution WSL non `docker-desktop` ;
2. démarrer la composition `compose.test.yaml` sous un nom de projet isolé et avec des ports paramétrables ;
3. provisionner le rôle PostgreSQL, exécuter upgrade, downgrade/reconstruction, `current` et `alembic check` ;
4. définir `REQUIRE_INFRASTRUCTURE_TESTS=true`, exécuter Pytest et refuser tout `skip` dans le JUnit ;
5. exécuter Ruff check/format, mypy, npm ci dans une copie temporaire, audit npm, ESLint, Vitest/axe, build et les
   contrôles de confidentialité source/artefact ;
6. exécuter les tests Redis de deux instances, les tests d’expiration et les tests métriques/journaux ;
7. toujours arrêter les conteneurs de test et publier localement les rapports, même si une étape échoue.

Le rapport `test-results/quality-summary.md` est renommé pour indiquer **2.6.3** et liste au minimum la date UTC,
le mode Docker réellement choisi, la distribution WSL le cas échéant, la révision Alembic observée, les fichiers
JUnit et le verdict. Il ne contient aucun secret, URL interne complète ou donnée de test personnelle.

### 8.2 Azure Pipelines

Azure Pipelines exécute le même contrat sans dépendre de Docker Desktop local :

- Python 3.12 et Node 22 sont épinglés comme actuellement ;
- PostgreSQL, Redis et Mailpit de `compose.test.yaml` sont démarrés, sains puis détruits en `always()` ;
- le rôle Web PostgreSQL est provisionné avant les tests ;
- Alembic vérifie la tête `20260815_0013`, son downgrade de reconstruction et `alembic check` ;
- toutes les suites Python, Redis réel, deux instances, confidentialité, React et axe sont exécutées ;
- les JUnit backend et frontend, le rapport Alembic et le rapport qualité sont publiés même en cas d’échec ;
- `junit-no-skips`, Ruff, mypy, ESLint, Vitest, build, audit npm et `git diff --check` sont bloquants ;
- le code et l’artefact Vite sont soumis au contrôle de confidentialité avant publication.

Une exécution Azure finale conserve son lien, son numéro de build, le commit, les dates UTC et le résultat dans le
rapport d’implémentation 2.6.3. Un échec de disponibilité d’Azure doit être identifié comme une réserve de
déploiement, jamais masqué par un rapport local.

## 9. Stratégie de tests et preuves attendues

### 9.1 Unitaire

- validation des quatre nouvelles variables, dont les refus de production/staging ;
- format JSON strict, `instance_id` stable et `request_id` présent ;
- aucune valeur interdite dans les attributs sérialisés ;
- ensembles de labels fermés et refus d’une valeur libre ;
- adaptateur nul sans effet et adaptateur Prometheus isolé ;
- métrique correctement émise sur succès/refus du verrou, quota, carte, sélection et fournisseur ;
- métriques désactivées ou bearer absent/invalide retournent toutes `404` ;
- bearer valide retourne le type Prometheus, `no-store` et aucune série contenant un identifiant utilisateur,
  organisation, demande ou établissement.

### 9.2 Intégration Redis et deux applications

Deux `create_app()` reçoivent deux conteneurs et registries de métriques distincts, mais partagent les URLs de
PostgreSQL et Redis. Les tests prouvent :

- une seule acquisition concurrente du verrou pour le même utilisateur/organisation ;
- deux requêtes concurrentes déclenchent exactement un faux Text Search ;
- une concession de carte et un jeton de sélection émis par A sont consommables/résolus par B selon leurs règles ;
- vingt réservations utilisateur et cent réservations organisation passent sous concurrence, puis une seule réponse
  `429` sans appel Google ni incrément partiel ;
- les événements et compteurs correspondants sont visibles dans les deux exports privés, sans labels interdits ;
- `PTTL` est positif dès la création, puis les clés de verrou, concessions et sélections disparaissent avec des TTL de
  test courts ;
- l’arrêt de Redis retourne `503 google_protection_unavailable` avant Google et génère le seul événement technique
  permis.

### 9.3 Régression et confidentialité

La suite finale conserve explicitement les contrôles de phase 1 et 2.5 : un appel Text Search, vingt résultats,
aucun `nextPageToken`, aucun téléphone/site Web, aucune exportation historique, `Cache-Control: no-store`, aucune
persistance navigateur de résultats/jetons, attribution Google Maps, `place_id` distinct et immuable, et marque
Marketteo visible.

Une recherche statique des JUnit, journaux capturés, artefacts Vite et rapport de qualité échoue si elle détecte une
valeur volontairement injectée ressemblant à une clé Google, un bearer, un courriel, un `place_id`, une adresse ou
des coordonnées. Le test n’utilise que des canaris synthétiques, jamais une clé ou donnée réelle.

## 10. Recette QA finale et documentation

L’implémentation ajoute un document dédié `docs/PHASE_2_6_RECETTE_FINALE_QA.md`, utilisable sans lire les tests
automatiques. Il distingue :

1. préparation de deux API locales ou conteneurisées partageant le même PostgreSQL/Redis ;
2. vérification des healthchecks et de la configuration Google sans afficher les secrets ;
3. double soumission contrôlée : une recherche acceptée, une contention `409`, un seul appel fournisseur simulé ;
4. émission d’un jeton via A puis ajout CRM et carte via B ;
5. quota réduit uniquement dans l’environnement QA : seuil d’avertissement, `429`, `Retry-After` et absence d’appel
   Google après le refus ;
6. attente de TTL de test réduit et confirmation d’un refus propre après expiration ;
7. accès collecteur aux métriques avec bearer QA, puis confirmation qu’un navigateur/session ne peut pas y accéder ;
8. exécution du verrou local et saisie du lien Azure, du commit et du verdict dans le rapport de recette.

La documentation utilisateur explique des limites quotidiennes de sécurité et les messages `409`, `429` et `503`,
sans promesse de forfait ou de facturation. Le guide technique documente les variables, les labels fermés, l’accès
réseau des métriques, la procédure WSL et le caractère obligatoire du rapport Azure.

## 11. Critères Go / No-Go

Le GO de clôture 2.6 nécessite simultanément :

- le rapport d’implémentation 2.6.3 complété avec la révision Alembic, le commit et les preuves ;
- deux applications indépendantes ayant prouvé le verrou, les jetons et les quotas partagés avec Redis réel ;
- une preuve de TTL pour chaque famille de clé temporaire ;
- des journaux JSON validés sans donnée interdite et des métriques privées à labels bornés ;
- l’endpoint métriques inaccessible sans configuration/bearer et accessible au collecteur QA autorisé ;
- un verrou local complet vert, avec JUnit backend/frontend sans `skip` ;
- une exécution Azure verte sur le même commit, avec artefacts et nettoyage des dépendances ;
- toutes les régressions de conformité Google, Ruff, mypy, Pytest, Alembic, ESLint, Vitest/axe, audit npm et build
  vertes ;
- recette QA finale exécutée ou réserve explicitement documentée et acceptée par le responsable produit.

Un seul échec, test ignoré, secret détecté, dépendance réelle absente, métrique publique ou preuve Azure manquante
est un **No-Go** de préproduction. Les difficultés Docker Desktop locales peuvent être contournées par le moteur WSL
documenté, mais ne permettent pas de réduire le périmètre du verrou.

## 12. Risques et parades

| Risque | Parade |
| --- | --- |
| Journal JSON contenant une donnée Google ou personnelle | Liste d’attributs fermée, sérialiseur central, canaris de confidentialité et revue de JUnit |
| Explosion de cardinalité Prometheus | Labels et valeurs explicitement bornés, aucun identifiant ou route brute |
| Endpoint métriques exposé sur Internet | Activation explicite, bearer comparé à temps constant, `404` uniforme et filtrage reverse proxy/réseau |
| Deux registries du même processus créent des séries dupliquées | Registre injectable par conteneur/fixture ; aucun registre global partagé en test multi-instance |
| Vert local incomplet à cause de Docker Desktop | Détection Windows puis WSL et ports de test paramétrables ; Azure obligatoire |
| Test ignoré masque une régression Redis ou PostgreSQL | `REQUIRE_INFRASTRUCTURE_TESTS=true` et analyse JUnit bloquante |
| Observabilité rend le chemin Google fragile | Collecte locale non bloquante, aucune dépendance réseau dans la requête, règles Google inchangées |

## 13. Seize décisions proposées à validation

1. Clore 2.6 par ce sous-incrément unique sans nouvelle migration PostgreSQL, en conservant `20260815_0013` comme tête attendue.
2. Ajouter un port `MetricsRecorder` typé avec un adaptateur nul et un adaptateur Prometheus, sans dépendance de domaine à Prometheus.
3. Limiter les métriques aux six familles définies et aux labels/valeurs fermés de la section 4.2 ; interdire tout identifiant comme label.
4. Utiliser des journaux JSON en staging/production, texte seulement en développement/test, avec `request_id` et `instance_id` non secrets.
5. Interdire dans les logs et rapports tous secrets, corps, données personnelles, contenu Google, `place_id`, coordonnées et URL fournisseur ; l’audit PostgreSQL reste distinct.
6. Ajouter `GET /internal/metrics`, hors navigation et hors API utilisateur, désactivé par défaut et répondant `404` lorsqu’il est désactivé ou non autorisé.
7. Exiger un bearer métriques dédié d’au moins 32 octets, comparé à temps constant, lorsque les métriques sont activées ; appliquer aussi un filtrage réseau/reverse proxy en staging/production.
8. Exiger `METRICS_ENABLED=true`, `METRICS_BEARER_TOKEN` valide et `LOG_FORMAT=json` dans les profils staging/production.
9. Rendre les erreurs d’observabilité non bloquantes : aucun second appel Google, aucune consommation supplémentaire et aucun repli mémoire.
10. Ajouter un test multi-instance avec deux conteneurs et registries distincts partageant PostgreSQL/Redis, couvrant verrou, jetons, quotas et compteurs.
11. Vérifier les TTL de toutes les clés temporaires avec des durées de test courtes et prouver leur disparition.
12. Étendre le verrou local à l’instrumentation, au scan de confidentialité et à un rapport `quality-summary.md` versionné 2.6.3, sans secret.
13. Maintenir la détection Docker Windows/WSL et les ports paramétrables ; le moteur WSL est une voie supportée pour la recette locale.
14. Faire d’Azure Pipelines la preuve obligatoire : dépendances réelles, zéro skip, JUnit publiés même en échec, contrôles de qualité et artefact confidentiel.
15. Produire une recette QA 2.6 dédiée pour les deux instances, la contention, le quota QA, les expirations et l’accès métriques ; ne pas afficher de métriques dans le CRM.
16. Déclarer la phase 2.6 prête pour clôture uniquement quand le Go/No-Go de la section 11 est entièrement vert, ou quand toute réserve est explicitement validée par le responsable produit.

## 14. Décision attendue

Après validation des seize décisions, l’implémentation 2.6.3 pourra commencer. Elle livrera les adaptateurs, les
tests, les mises à jour Azure et la documentation finale ; elle se terminera par un rapport d’implémentation et la
recette QA regroupée de toute la phase 2.6.
