# Rapport d’audit de sécurité — LeadGenerator

**Date :** 5 septembre 2026  
**Révision examinée :** `e535848d42b3ca527fc3a640adc1576664640819`  
**Périmètre :** backend FastAPI, client web, migrations PostgreSQL/RLS, Redis, Docker Compose, Dockerfile, Caddy et pipeline Azure DevOps.  
**Nature de l’audit :** revue statique ciblée, complétée par des vérifications locales non destructives. Aucun code n’a été modifié.

## 1. Résumé exécutif

L’application possède plusieurs contrôles solides : cookies HttpOnly et SameSite, protection CSRF par jeton en mémoire, validation d’origine, Argon2id avec vérification factice pour les comptes inconnus, RLS PostgreSQL forcée sur les données métier, rôle applicatif sans `BYPASSRLS`, limites de taille sur les CSV et absence de sink XSS évident côté client.

Les risques prioritaires concernent surtout la chaîne de déploiement et la disponibilité :

1. la contrainte `fastapi==0.116.1` autorise une résolution Starlette dans une plage affectée par le déni de service `Range` de `FileResponse`/`StaticFiles` ; l’image sert effectivement des fichiers statiques ;
2. `--forwarded-allow-ips "*"` fait dépendre la limitation de connexion de l’adresse `X-Forwarded-For` ; une exposition directe ou un proxy mal configuré permettrait de contourner cette limitation ;
3. le contrôle de quota Google crée une clé Redis distincte pour chaque requête refusée jusqu’à l’expiration quotidienne, alors que Redis n’a ni `maxmemory` ni politique d’éviction définie dans Compose QA ;
4. la vérification et l’enregistrement de l’échec de connexion sont séparés : une rafale concurrente peut faire exécuter de nombreux hachages Argon2 coûteux avant l’incrément des compteurs ;
5. le service web reçoit tout le fichier `.env.qa`. Si ce fichier contient l’URL de migration ou des secrets d’administration, une compromission du processus web donnerait un chemin vers des privilèges supérieurs ;
6. la mise à jour d’une tâche ne vérifie pas que le prospect associé est encore modifiable. Un utilisateur autorisé à modifier la tâche peut donc potentiellement modifier une tâche d’un prospect archivé.

Les points 1 à 5 sont conditionnels à la version réellement construite, à la topologie du proxy et au contenu réel des secrets de déploiement. Ils doivent être vérifiés immédiatement dans l’image et l’environnement QA ; ils ne doivent pas être traités comme des preuves d’exploitation publique sans cette vérification.

## 2. Matrice des constats

| ID | Gravité | Confiance | Statut | Sujet |
|---|---|---|---|---|
| F-01 | Haute | Haute | Conditionnel à la résolution de dépendances | Starlette vulnérable à un `Range` malveillant |
| F-02 | Moyenne | Haute | Conditionnel à une vieille Starlette et à un Host contrôlable | Décision de sanitisation fondée sur `request.url.path` |
| F-03 | Moyenne à haute | Moyenne | Conditionnel à l’exposition directe ou au proxy non nettoyant | Usurpation de l’IP cliente et contournement des limites |
| F-04 | Haute | Moyenne | Conditionnel au contenu de `.env.qa` | Secrets de migration/admin transmis au processus web |
| F-05 | Moyenne à haute | Moyenne | Risque de disponibilité, non mesuré en charge | Rafale de hachages Argon2 concurrents |
| F-06 | Moyenne | Haute | Reproductible par inspection du flux | Croissance Redis sur les refus de quota |
| F-07 | Moyenne | Haute | Déduit du code | Modification de tâches liées à un prospect archivé |
| F-08 | Moyenne | Haute | Risque de release | Révision Alembic attendue obsolète par rapport aux migrations présentes |
| F-09 | Moyenne | Moyenne | Dev uniquement, si exposé sur un réseau partagé | PostgreSQL/Redis publiés avec secrets par défaut |
| F-10 | Faible à moyenne | Moyenne | À confirmer dans les privilèges PostgreSQL | `CREATE` du schéma `public` non explicitement révoqué |
| F-11 | Moyenne | Faible à moyenne | À mesurer | Épuisement de ressources par imports CSV autorisés concurrents |
| F-12 | Faible | Haute | Information limitée | Endpoints de santé publics et booléen de configuration |
| F-13 | Faible | Haute | Défense en profondeur | CSP absente de Caddy |
| F-14 | Moyenne | Haute | Processus de supply chain incomplet | Pas de `pip-audit`/SBOM et tags d’image flottants |

## 3. Détails des constats

### F-01 — Déni de service `Range` dans Starlette

**Preuve.** `backend/requirements.txt` fixe FastAPI `0.116.1`, dont la plage déclarée accepte Starlette `<0.48.0`. Le Dockerfile installe cette contrainte à chaque build puis l’application monte `StaticFiles` et renvoie des `FileResponse` (`backend/app/bootstrap.py:802, 810-811`). Une version Starlette de cette plage peut donc être retenue par le résolveur. L’avis public [GHSA-7f5h-v6xp-fcq8](https://github.com/advisories/GHSA-7f5h-v6xp-fcq8) décrit une consommation CPU quadratique provoquée par un en-tête `Range` spécialement construit, corrigée en `0.49.1`.

**Impact.** Une requête non authentifiée vers un fichier servi par l’application peut monopoliser le CPU et dégrader la disponibilité. L’exploitabilité exacte dépend de la version embarquée et d’un éventuel filtrage en amont.

**Critique.** Le fichier de lock n’est pas disponible dans le dépôt pour cette image et l’environnement virtuel local contient d’autres versions (`fastapi 0.139.2`, `starlette 1.3.1`). La version locale ne prouve donc pas la version de production. C’est un risque de build, pas une preuve que l’image QA actuelle est vulnérable.

**Recommandations.** Construire l’image et afficher les versions installées ; utiliser une combinaison FastAPI/Starlette explicitement corrigée et compatible ; ajouter `pip-audit` ou un scanner d’image au pipeline ; tester une requête `Range` hostile avec un budget CPU et une limite de taille.

### F-02 — Sanitisation d’erreur dépendante de `request.url.path`

**Preuve.** `backend/app/bootstrap.py:699-763` classe les erreurs sensibles avec `request.url.path.startswith(...)`. L’avis [GHSA-86qp-5c8j-p5mr](https://github.com/advisories/GHSA-86qp-5c8j-p5mr) décrit une ambiguïté de chemin liée à un `Host` malformé dans les versions Starlette concernées.

**Impact.** Avec une version affectée et un chemin d’accès au serveur permettant de contrôler `Host`, une erreur pourrait suivre la mauvaise branche de sanitisation et révéler davantage de détails qu’attendu. La revue n’a pas démontré de fuite d’identifiants ni de contournement d’authentification.

**Recommandations.** Mettre à jour Starlette dans une combinaison supportée ; utiliser le chemin brut du scope ou les métadonnées de route pour décider de la sanitisation ; ajouter un test d’intégration avec plusieurs valeurs `Host` et vérifier que les réponses des routes sensibles restent génériques.

### F-03 — Confiance illimitée dans les en-têtes de proxy

**Preuve.** Le conteneur démarre Uvicorn avec `--proxy-headers --forwarded-allow-ips "*"` (`Dockerfile:34`). Le routeur d’authentification transmet `request.client.host` au limiteur de connexion. Uvicorn reconstruit alors l’adresse cliente à partir des en-têtes transmis par le proxy.

**Scénario.** Si le port 8000 devient accessible depuis un réseau non maîtrisé, ou si le proxy frontal laisse passer `X-Forwarded-For`, un attaquant peut changer l’IP apparente à chaque requête et contourner la limitation par IP. Le risque est réduit si le réseau Docker interdit toute connexion directe et si Caddy remplace systématiquement ces en-têtes.

**Recommandations.** Remplacer `*` par les seuls CIDR des reverse proxies ; bloquer le port applicatif au niveau réseau ; supprimer et reconstruire les en-têtes à la frontière ; vérifier par un test de déploiement que l’IP retenue ne peut pas être choisie par le client.

### F-04 — Sur-exposition potentielle des secrets `.env.qa`

**Preuve.** `compose.qa.yaml:9-10` injecte le même `.env.qa` dans le service web que dans le service de migration (`:35-40`). L’exemple d’environnement sépare pourtant l’URL applicative de l’URL de migration propriétaire.

**Impact.** Une exécution de code dans le processus web, un endpoint de debug oublié ou une dépendance compromise pourrait lire les secrets de migration, les mots de passe PostgreSQL ou d’autres secrets qui ne sont pas nécessaires au trafic HTTP. Cela peut contourner la séparation RLS et augmenter l’impact d’une compromission.

**Critique.** `.env.qa` n’est pas présent dans le workspace audité ; la présence réelle de ces variables dans l’environnement de production n’a donc pas été prouvée.

**Recommandations.** Donner au service web une allow-list minimale de variables ; réserver `MIGRATION_DATABASE_URL`, `POSTGRES_PASSWORD` et les identifiants de provisionnement aux jobs/outils ; inspecter l’environnement du conteneur sans journaliser les valeurs ; faire tourner les secrets si une exposition est confirmée.

### F-05 — Rafale de hachages Argon2 avant réservation du quota

**Preuve.** Le limiteur est consulté avant la vérification Argon2, puis l’échec est enregistré après la vérification (`backend/app/application/use_cases/authentication.py`). Les paramètres utilisent environ 64 MiB par hachage (`time_cost=3`, `memory_cost=65536`, `parallelism=4`) et une vérification factice est exécutée pour un identifiant inconnu.

**Impact.** Des requêtes de connexion non authentifiées concurrentes provenant d’une même IP peuvent toutes franchir le contrôle initial avant l’incrément du compteur. Elles consomment donc CPU et mémoire simultanément. La gravité dépend de la concurrence Uvicorn, de la mémoire du conteneur et d’un éventuel WAF ; aucune campagne de charge n’a été lancée.

**Recommandations.** Réserver atomiquement un jeton avant le hachage, ajouter une limite de concurrence par processus/organisation et appliquer une protection en amont. Mesurer le débit légitime et le comportement sous charge pour choisir des paramètres Argon2 sans réintroduire d’énumération de comptes.

### F-06 — Croissance Redis sur les refus de quota Google

**Preuve.** `SearchGooglePlacesUseCase` génère un nouvel UUID pour chaque recherche (`backend/app/application/use_cases/search_google_places.py:43-68`). `google_quota.py` inclut cet UUID dans la clé `operation`. Une requête refusée après épuisement du quota peut donc créer une nouvelle clé avec une expiration au prochain jour UTC. Redis QA est lancé avec AOF mais sans `maxmemory`, éviction ou authentification explicite (`compose.qa.yaml:73-83`).

**Impact.** Un utilisateur authentifié peut remplir progressivement la mémoire Redis en répétant une opération déjà refusée, jusqu’à provoquer évictions, erreurs ou redémarrage du service.

**Recommandations.** Mémoriser un état négatif par organisation/période avec TTL borné ; limiter spécifiquement le chemin refusé ; configurer `maxmemory` et une politique d’éviction adaptée, ainsi qu’une alerte sur la mémoire et le nombre de clés ; tester le comportement quand Redis atteint sa limite.

### F-07 — Tâche modifiable après archivage du prospect

**Preuve.** `UpdateTaskUseCase` (`backend/app/application/use_cases/activities.py:235-264`) charge la tâche, vérifie la capacité et l’assignation, puis met à jour la tâche. Il n’appelle pas `_require_writable_prospect`, alors que cette fonction bloque explicitement un prospect archivé (`:391-395`) et qu’elle est utilisée dans d’autres flux.

**Impact.** Un responsable ou l’utilisateur assigné peut modifier, rouvrir ou compléter une tâche liée à un prospect archivé. Cela compromet l’intégrité de la conservation et peut produire des événements métier après l’archivage.

**Recommandations.** Décider explicitement si l’archivage doit geler aussi les tâches. Si oui, charger le prospect dans la même unité de travail et appliquer le contrôle avant toute mutation ; sinon, documenter les actions post-archivage autorisées et les limiter à un sous-ensemble audité. Ajouter des tests pour chaque rôle et chaque transition de statut.

### F-08 — Garde de release Alembic potentiellement obsolète

**Preuve.** Le pipeline attend `20260904_0015` (`azure-pipelines.yml:18, 66-69`). Le workspace contient des migrations non suivies plus récentes (`20260905_0016_activity_task_foundation.py` et `20260905_0017_activity_task_commands.py`).

**Impact.** Si ces migrations sont livrées sans mettre à jour la variable de contrôle, le pipeline peut refuser une release légitime ; si elles ne sont pas livrées avec le code qui les attend, l’application peut démarrer sur un schéma incomplet. Le second cas peut provoquer des erreurs ou supprimer les garanties d’idempotence attendues.

**Recommandations.** Faire échouer la CI lorsque des fichiers de migration présents ne correspondent pas à la révision attendue ; vérifier `alembic heads/current` sur une base vierge et une base existante ; versionner ensemble code, migrations et valeur attendue ; exécuter les migrations avant d’exposer le trafic.

### F-09 — Services de développement publiés avec secrets faibles

**Preuve.** `compose.yaml` publie PostgreSQL et Redis sur les ports hôte avec des valeurs par défaut explicitement orientées développement.

**Impact.** Sur une machine partagée, un poste de démonstration ou un serveur où Compose est exposé au-delà de localhost, un tiers peut atteindre directement les bases. Ce n’est pas une vulnérabilité QA si `compose.yaml` reste strictement local.

**Recommandations.** Lier les ports à `127.0.0.1`, refuser tout démarrage hors profil de développement lorsque les secrets par défaut sont utilisés, et documenter le cloisonnement réseau.

### F-10 — Privilèges du schéma `public` à vérifier pour les fonctions SECURITY DEFINER

**Preuve.** Les migrations utilisent des fonctions `SECURITY DEFINER` avec un `search_path` incluant `public`, mais la revue n’a pas trouvé de révocation explicite de `CREATE` sur ce schéma. Les fonctions limitent déjà leur `search_path`, révoquent `PUBLIC` et accordent des droits ciblés, ce qui est un bon contrôle.

**Impact conditionnel.** Si le rôle applicatif ou `PUBLIC` peut créer des objets dans `public`, un objet portant un nom résolu par une fonction pourrait être utilisé pour détourner une résolution. Les valeurs par défaut des versions PostgreSQL récentes peuvent déjà empêcher ce scénario ; les privilèges réels n’ont pas été interrogés.

**Recommandations.** Vérifier `has_schema_privilege` et les ACL de chaque environnement ; révoquer explicitement `CREATE ON SCHEMA public FROM PUBLIC` ; préférer un schéma privé pour les fonctions et qualifier les objets ; conserver un test de privilèges dans la suite RLS.

### F-11 — Import CSV : risque de ressources sous concurrence

**Preuve.** Les contrôles limitent chaque fichier à 10 MiB, 5 000 lignes, 50 colonnes et 4 096 caractères par cellule. Ces limites réduisent fortement les abus unitaires, mais l’analyse et la confirmation réalisent des opérations mémoire et base par import. Aucun quota de concurrence par organisation n’a été établi dans la revue.

**Impact.** Plusieurs utilisateurs autorisés peuvent saturer la mémoire, le pool SQL ou la durée de requête. Il s’agit d’un risque de disponibilité authentifié, non d’une injection démontrée.

**Recommandations.** Ajouter un quota de taille cumulée et de concurrence par organisation, une file de traitement ou un budget de temps, puis tester avec plusieurs imports simultanés.

### F-12 — Endpoints de santé publics

**Preuve.** `/api/health` renvoie notamment un booléen `google_api_key_configured` (`backend/app/presentation/api/routers/health.py:13`) et `/api/health/ready` sonde PostgreSQL et Redis (`:22+`).

**Impact.** Cela donne une information de configuration et permet de déclencher des sondes de dépendances. L’impact est faible et aucune donnée métier n’est exposée.

**Recommandations.** Garder `/live` public ; réserver `/ready` au réseau d’orchestration ou limiter sa fréquence ; décider si le booléen de configuration est réellement nécessaire dans une réponse publique.

### F-13 — CSP absente de la configuration Caddy

Les en-têtes présents couvrent HSTS, `nosniff`, `X-Frame-Options` et le référent. Aucune Content-Security-Policy n’a été trouvée. C’est une faiblesse de défense en profondeur, pas une XSS démontrée. Définir une CSP initialement en `Report-Only`, puis la durcir après inventaire des scripts, assets et appels externes.

### F-14 — Supply chain et reproductibilité

Le pipeline vérifie Ruff, mypy, les tests et `npm audit`, mais pas les paquets Python avec `pip-audit`, pas de SBOM, et le Dockerfile utilise `node:22-alpine` et `python:3.12-slim` sans digest. Le `pip install --upgrade pip` rend également le build dépendant de l’état courant de l’index. Ajouter un lock/contraintes hashées, un scan Python et image, une SBOM signée, des digests d’image et une promotion immuable.

## 4. Contrôles positifs observés

- Cookies de session `HttpOnly`, `SameSite=Lax`, et configuration de production exigeant `Secure` et le préfixe `__Host-`.
- Vérification CSRF par comparaison constante et validation explicite de l’origine/referer.
- Argon2id, sel aléatoire, vérification factice pour les utilisateurs inexistants et absence de mot de passe dans les journaux observés.
- RLS activée et forcée sur les tables locataires ; rôle applicatif sans `BYPASSRLS` ; contexte tenant défini dans la transaction et tests de réutilisation du pool.
- Requêtes SQL paramétrées et liste blanche pour les noms de colonnes construits dynamiquement.
- Fichiers CSV avec références opaques, bornes de taille et contrôle UTF-8/NUL.
- Pas de `dangerouslySetInnerHTML`, `eval`, `localStorage` ou `sessionStorage` trouvés dans le client audité.
- Caddy ne publie pas directement le port applicatif dans Compose QA ; le service web est exécuté sous un utilisateur non root.

Ces contrôles réduisent le risque mais ne remplacent pas un test d’intrusion sur l’environnement réellement exposé.

## 5. Plan de remédiation priorisé

### Sous 24 heures

1. Construire l’image exacte de production, relever les versions FastAPI/Starlette et corriger toute version Starlette affectée par F-01/F-02.
2. Vérifier que seul Caddy peut joindre le port 8000 et remplacer `forwarded-allow-ips "*"` par les réseaux de proxy réellement utilisés.
3. Comparer les variables du conteneur web à celles des services de migration et retirer tout secret propriétaire du web.
4. Réconcilier les migrations 0016/0017 avec la révision attendue par le pipeline avant toute mise en production.

### Prochain sprint

1. Durcir le limiteur de connexion contre la concurrence Argon2 et effectuer un test de charge contrôlé.
2. Réduire les écritures Redis sur les refus de quota et définir une limite mémoire avec alertes.
3. Décider et tester la politique d’archivage des tâches.
4. Vérifier les ACL du schéma `public`, les rôles RLS et les `SECURITY DEFINER` sur une base QA réelle.
5. Ajouter `pip-audit`, SBOM, digest d’image et contrôle des dépendances transitive au pipeline.

### Durcissement ultérieur

Ajouter quotas d’import, CSP, restriction des endpoints de santé, ports de développement liés à localhost, chiffrement/rotation des sauvegardes et un test périodique de restauration.

## 6. Méthode et limites

La revue a été menée en trois axes parallèles : HTTP/authentification, accès aux données/RLS et infrastructure/dépendances. Les observations ont été recoupées par inspection des fichiers, recherche ciblée et quelques probes locales non destructives. Aucun service de production ou QA n’a été attaqué, aucun secret réel n’a été affiché, et aucune modification de code n’a été effectuée.

Le workspace contenait déjà des modifications et fichiers non suivis ; les conclusions portant sur les migrations et les fichiers d’environnement doivent donc être confirmées sur l’artefact de release et la configuration réellement déployée. Ce rapport est un audit de risque et une base de remédiation ; il ne constitue pas une certification de sécurité ni la preuve d’une exploitation à distance.

