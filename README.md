# Prospect CRM

Prospect est une application React et FastAPI en migration vers un CRM de gestion commerciale. La phase 1 fournit une recherche Google Places ponctuelle et conforme : une seule requête Text Search par action, vingt établissements au maximum, aucun contact dans la liste et aucune persistance des résultats Google.

Ce fichier réunit le guide utilisateur et la documentation technique du socle actuel. La spécification complète se trouve dans [`docs/SPECIFICATION_CRM_V1.md`](docs/SPECIFICATION_CRM_V1.md), les décisions validées sur les sources dans [`docs/PHASE_1_1_ACQUISITION_CONSERVATION.md`](docs/PHASE_1_1_ACQUISITION_CONSERVATION.md) et la conception validée des fondations dans [`docs/PHASE_2_SPECIFICATIONS_DETAILLEES.md`](docs/PHASE_2_SPECIFICATIONS_DETAILLEES.md).

## Fonctionnalités disponibles

- connexion et déconnexion avec un compte créé par l’exploitant ;
- mots de passe hachés avec Argon2id et inscription publique désactivée ;
- session opaque conservée côté serveur dans Redis, cookie `HttpOnly` et protection CSRF ;
- expiration après 30 minutes d’inactivité et 12 heures au maximum, configurables ;
- limitation des échecs de connexion par adresse réseau et identité pseudonymisée ;
- recherche explicite d’établissements autour d’un point et d’un rayon ;
- exactement un appel Text Search par action, sans page suivante ni balayage multi-zone ;
- réponse et affichage limités à vingt établissements ;
- liste sans téléphone ni site Web ;
- résultats temporaires conservés uniquement dans l’état mémoire React ;
- attribution visible `Google Maps`, non traduisible et conforme au style textuel officiel dans le conteneur des résultats ;
- carte Google statique protégée par un jeton serveur court et à usage unique ;
- identification temporaire du demandeur et verrou par adresse professionnelle ;
- export des résultats Google indisponible : bouton visible mais désactivé et route historique absente ;
- pages de conditions d’utilisation et de confidentialité.

## Guide utilisateur

### Se connecter

1. Ouvrez l’application et saisissez le courriel du compte fourni par l’administrateur.
2. Saisissez le mot de passe sans le partager ni l’enregistrer dans un emplacement non approuvé.
3. Cliquez sur **Se connecter**.
4. Utilisez le bouton **Se déconnecter** dans l’en-tête lorsque vous avez terminé.

Le navigateur reçoit un cookie de session inaccessible à JavaScript. Le jeton CSRF reste uniquement dans la mémoire de la page. Aucun mot de passe, identifiant de session ou jeton n’est écrit dans `localStorage` ou `sessionStorage`. La création d’organisation, les invitations et la gestion des rôles seront livrées dans l’incrément 2.3.

### Effectuer une recherche

1. Saisissez un type d’entreprise simple, par exemple `plombier`.
2. Indiquez le centre géographique et un rayon de 1 à 50 km.
3. Choisissez si les entreprises de zone de service doivent être incluses.
4. Cliquez sur **Rechercher des établissements**.
5. Renseignez le prénom, la raison sociale et l’adresse professionnelle du demandeur, puis confirmez.

Le serveur interroge Google une seule fois avec `pageSize: 20`. Il ne suit pas `nextPageToken`. Les résultats situés hors du rayon sont exclus ; les établissements sans coordonnées ne sont conservés que si l’option de zone de service est active.

### Consulter les résultats

La page affiche le nom, l’adresse, la distance, le statut, le type d’activité et, lorsqu’elle est fournie, l’URL Google Maps. Le téléphone et le site Web ne font pas partie de cette liste. Le filtre local utilise uniquement le nom, l’adresse et le type.

Les résultats :

- ne sont écrits dans aucune base applicative ;
- ne sont pas placés dans `localStorage`, `sessionStorage`, IndexedDB ou un cache de service worker ;
- ne sont pas exportables ;
- disparaissent lorsque la vue est rechargée ou fermée.

Le bouton **Exporter Excel** reste affiché pour préparer le futur module d’échanges du CRM, mais il est toujours désactivé pendant cette phase.

## Installation locale

### Prérequis

- Python 3.12 ou ultérieur ;
- Node.js 22 ou ultérieur ;
- un projet Google Cloud avec facturation activée ;
- Places API (New) activée ;
- Maps Static API activée pour la carte.
- Docker Desktop avec les conteneurs Linux pour PostgreSQL et Redis.

### Dépendances

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt

cd client
npm ci
cd ..
```

### Clés Google

```powershell
$env:GOOGLE_MAPS_API_KEY = "VOTRE_CLE_PLACES"
$env:GOOGLE_MAPS_STATIC_API_KEY = "VOTRE_CLE_MAPS_STATIC"
```

| Variable | Obligatoire | Usage |
| --- | --- | --- |
| `GOOGLE_MAPS_API_KEY` | Oui | Clé serveur restreinte à Places API (New). |
| `GOOGLE_MAPS_STATIC_API_KEY` | Non | Clé serveur distincte recommandée pour Maps Static API ; la clé Places sert de repli. |

Les clés sont lues depuis l’environnement du serveur et ne sont jamais renvoyées au navigateur. Restreignez-les aux API nécessaires et aux adresses IP du serveur lorsque l’hébergement le permet.

### Démarrage

Démarrez d’abord les dépendances locales :

```powershell
docker compose up -d --wait
$env:DATABASE_URL = "postgresql+asyncpg://prospect:prospect-development-only@127.0.0.1:5432/prospect"
$env:MIGRATION_DATABASE_URL = $env:DATABASE_URL
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

Créez ensuite, une seule fois, le premier administrateur de plateforme. La commande refuse de créer un second administrateur initial et ne prend jamais le mot de passe en argument de ligne de commande :

```powershell
$env:BOOTSTRAP_PLATFORM_ADMIN_CONFIRM = "CREATE_FIRST_PLATFORM_ADMIN"
$env:BOOTSTRAP_PLATFORM_ADMIN_EMAIL = "admin@example.ca"
$env:BOOTSTRAP_PLATFORM_ADMIN_DISPLAY_NAME = "Administrateur"
.\.venv\Scripts\python.exe -m backend.app.cli.bootstrap_platform_admin
```

Le mot de passe est demandé de manière interactive. Pour une automatisation contrôlée, `BOOTSTRAP_PLATFORM_ADMIN_PASSWORD` peut être fourni par un coffre de secrets et doit être retiré immédiatement après usage.

Terminal 1 :

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2 :

```powershell
cd client
npm run dev
```

Ouvrez `http://localhost:5173`. Vite redirige `/api` vers `http://127.0.0.1:8000`.

`GET /api/health/live` vérifie le processus. `GET /api/health/ready` retourne `200` uniquement lorsque PostgreSQL et Redis répondent ; la route historique `GET /api/health` reste disponible pendant la migration.

Variables d’identité principales :

| Variable | Valeur initiale | Usage |
| --- | --- | --- |
| `PUBLIC_APP_URL` | `http://localhost:5173` en local | Origine publique de confiance. |
| `CORS_ALLOWED_ORIGINS` | origines Vite locales | Liste exacte des origines autorisées. |
| `SESSION_COOKIE_NAME` | `prospect_session` | En production : `__Host-prospect_session`. |
| `SESSION_COOKIE_SECURE` | `false` en local | Obligatoirement `true` en production. |
| `SESSION_IDLE_SECONDS` | `1800` | Expiration d’inactivité. |
| `SESSION_ABSOLUTE_SECONDS` | `43200` | Durée absolue maximale. |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | `900` | Fenêtre de limitation des connexions. |

## Contrat API de la phase 1

### Authentification — incrément 2.2

- `POST /api/auth/login` vérifie le courriel et le mot de passe, crée une session opaque et pose le cookie ;
- `GET /api/auth/me` restaure l’utilisateur, l’organisation active éventuelle, les appartenances, les capacités et le jeton CSRF ;
- `POST /api/auth/logout` exige `X-CSRF-Token`, révoque la session puis supprime le cookie.

Les réponses portent `Cache-Control: no-store`. Une erreur de connexion reste générique et ne révèle pas si le courriel existe. Les mutations authentifiées acceptent exclusivement JSON et vérifient une origine ou un référent de confiance.

### `POST /api/google/places/search`

Exemple :

```json
{
  "query": "plombier",
  "center_latitude": 46.8139,
  "center_longitude": -71.208,
  "radius_km": 15,
  "include_service_area_businesses": true,
  "language_code": "fr",
  "region_code": "CA",
  "requester": {
    "first_name": "Alex",
    "company_name": "Entreprise Exemple",
    "business_address": "100 rue Principale, Québec, Canada"
  }
}
```

La réponse contient `places`, `stats`, `searched_at`, les `search_parameters` réellement soumis et un `map_snapshot_token`. Le schéma des établissements n’expose ni téléphone ni site Web. La liste possède au maximum vingt éléments et la réponse porte `Cache-Control: no-store, max-age=0`.

Les anciens chemins `POST /api/leads/search` et `POST /api/leads/export` ne sont plus montés et sont absents du schéma OpenAPI.

### `POST /api/map/snapshot`

```json
{
  "token": "JETON_RECU_APRES_LA_RECHERCHE"
}
```

Le serveur conserve les coordonnées de la carte et refuse qu’elles soient fournies librement par le navigateur. Le jeton :

- expire après cinq minutes par défaut ;
- n’autorise qu’un appel simultané ;
- est consommé après une réponse Google réussie ;
- redevient disponible si l’appel Google échoue ;
- protège l’unique génération de carte facturable associée à la recherche.

La réponse de carte porte également `Cache-Control: no-store, max-age=0`.

## Architecture

Le backend conserve des dépendances dirigées vers le domaine et l’application :

| Zone | Responsabilité |
| --- | --- |
| `backend/app/domain/` | Identité, rôles, session, modèles Google et règles sans framework. |
| `backend/app/application/use_cases/` | Authentification, bootstrap, readiness, recherche et carte. |
| `backend/app/application/ports/` | Interfaces des dépôts, mots de passe, sessions, limites, PostgreSQL/Redis et Google. |
| `backend/app/infrastructure/postgres/` | Modèles d’identité, dépôt, unités de travail et migrations Alembic. |
| `backend/app/infrastructure/redis/` | Sessions opaques et limitation atomique des connexions. |
| `backend/app/infrastructure/security/` | Adaptateur Argon2id exécuté hors de la boucle asynchrone. |
| `backend/app/infrastructure/google/` | Appel HTTP Google et adaptation des données. |
| `backend/app/infrastructure/memory/` | Verrou et jetons temporaires, remplaçables par Redis. |
| `backend/app/presentation/api/` | Schémas Pydantic, mappers et routes FastAPI. |
| `client/src/features/lead-search/` | Écran transitoire de recherche, état local et composants React. |
| `client/src/features/auth/` | Connexion, restauration et état de session conservé uniquement en mémoire. |
| `client/src/shared/` | Client HTTP, erreurs et comportements réutilisables. |

Le port `PlacesGateway` expose une seule méthode `search`. Il ne connaît aucun jeton de pagination. Le masque de champs Google n’inclut ni contact ni `nextPageToken`, et le client HTTP n’effectue aucune nouvelle tentative automatique afin de garantir un seul POST Text Search par action.

## Sécurité et conformité

- clés Google exclusivement côté serveur ;
- mot de passe Argon2id de 12 à 128 caractères, sans normalisation ni troncature ;
- session aléatoire de 256 bits dont seul le hash indexe Redis ;
- cookie `HttpOnly`, `SameSite=Lax`, `Secure` et préfixé `__Host-` en production ;
- CSRF en mémoire et validation stricte de l’origine sur les mutations authentifiées ;
- compte désactivé ou version d’identité modifiée refusant immédiatement une ancienne session ;
- erreurs d’authentification minimisées, sans écho du mot de passe ;
- masque de champs Google minimal ;
- aucune persistance ni cache navigateur des résultats ;
- réponses Google et carte marquées `no-store` ;
- verrou Unicode par adresse professionnelle ;
- carte facturable derrière un jeton aléatoire et à usage unique ;
- résultat limité dans le client Google, le cas d’usage et le schéma HTTP ;
- attribution `Google Maps` visible sur la liste ;
- route d’export historique absente.

Les registres de verrou et de jetons restent en mémoire pour cette phase. Ils devront passer dans un stockage partagé avant un déploiement répliqué.

## Qualité

Backend :

```powershell
.\.venv\Scripts\python.exe -m ruff check backend/app tests
.\.venv\Scripts\python.exe -m ruff format --check backend/app tests
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini check
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend :

```powershell
cd client
npm run lint
npm test
npm run build
```

La suite protège notamment l’appel Google unique, l’absence de pagination, la limite de vingt, l’absence des contacts, le retrait de l’export HTTP, l’absence de stockage navigateur, l’attribution, le parcours React et le jeton de carte.

## Suite de la migration CRM V1

Les incréments 2.1 et 2.2 sont implémentés et documentés dans [`docs/PHASE_2_1_RAPPORT_IMPLEMENTATION.md`](docs/PHASE_2_1_RAPPORT_IMPLEMENTATION.md) et [`docs/PHASE_2_2_RAPPORT_IMPLEMENTATION.md`](docs/PHASE_2_2_RAPPORT_IMPLEMENTATION.md). L’incrément 2.3 ajoutera l’administration des organisations et membres, les invitations à usage unique, l’isolation RLS et la protection authentifiée des routes Google. Le découpage complet reste défini dans [`docs/PHASE_2_SPECIFICATIONS_DETAILLEES.md`](docs/PHASE_2_SPECIFICATIONS_DETAILLEES.md).

## Références

- [Text Search (New)](https://developers.google.com/maps/documentation/places/web-service/text-search)
- [Attribution Google Maps](https://developers.google.com/maps/documentation/places/web-service/policies)
- [Sécurité des clés API Google Maps](https://developers.google.com/maps/api-security-best-practices)
- [Maps Static API](https://developers.google.com/maps/documentation/maps-static/overview)
