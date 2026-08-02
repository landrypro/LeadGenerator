# Prospect CRM

Prospect est une application React et FastAPI en migration vers un CRM de gestion commerciale. La phase 1 fournit une recherche Google Places ponctuelle et conforme : une seule requête Text Search par action, vingt établissements au maximum, aucun contact dans la liste et aucune persistance des résultats Google.

Ce fichier réunit le guide utilisateur et la documentation technique du socle actuel. La spécification complète se trouve dans [`docs/SPECIFICATION_CRM_V1.md`](docs/SPECIFICATION_CRM_V1.md), les décisions validées sur les sources dans [`docs/PHASE_1_1_ACQUISITION_CONSERVATION.md`](docs/PHASE_1_1_ACQUISITION_CONSERVATION.md) et la conception validée des fondations dans [`docs/PHASE_2_SPECIFICATIONS_DETAILLEES.md`](docs/PHASE_2_SPECIFICATIONS_DETAILLEES.md). Le contrat de 2.3.3 et son rapport d’implémentation se trouvent dans [`docs/PHASE_2_3_3_SPECIFICATIONS_DETAILLEES.md`](docs/PHASE_2_3_3_SPECIFICATIONS_DETAILLEES.md) et [`docs/PHASE_2_3_3_RAPPORT_IMPLEMENTATION.md`](docs/PHASE_2_3_3_RAPPORT_IMPLEMENTATION.md).

## Fonctionnalités disponibles

- connexion et déconnexion avec un compte créé par l’exploitant ;
- mots de passe hachés avec Argon2id et inscription publique désactivée ;
- session opaque conservée côté serveur dans Redis, cookie `HttpOnly` et protection CSRF ;
- expiration après 30 minutes d’inactivité et 12 heures au maximum, configurables ;
- limitation des échecs de connexion par adresse réseau et identité pseudonymisée ;
- provisioning plateforme idempotent d’une organisation et de sa première invitation Admin ;
- invitation à usage unique, renvoi explicite plafonné, révocation et acceptation par compte nouveau ou existant ;
- organisation activée atomiquement avec sa première appartenance Admin ;
- consultation et modification optimiste de l’organisation active ;
- annuaire paginé des membres selon la matrice Administrateur/Gestionnaire/Commercial ;
- modification versionnée des rôles et états, avec protection concurrente du dernier Administrateur actif ;
- invitations de membres Admin, Gestionnaire ou Commercial, renvoi et révocation ;
- changement d’organisation active par appartenance avec rotation atomique du cookie et du CSRF ;
- page d’acceptation dédiée, jeton retiré du fragment avant React et conservé uniquement en mémoire ;
- compte authentifié sans organisation placé dans un état restreint sans capacité fonctionnelle ;
- rôle PostgreSQL Web non propriétaire et tables locataires protégées par Row-Level Security ;
- contexte d’organisation limité à chaque transaction, sans persistance dans le pool de connexions ;
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

Le navigateur reçoit un cookie de session inaccessible à JavaScript. Le jeton CSRF reste uniquement dans la mémoire de la page. Aucun mot de passe, identifiant de session ou jeton n’est écrit dans `localStorage` ou `sessionStorage`.

### Accepter une invitation

1. Ouvrez le lien complet reçu par courriel. Le jeton placé après `#token=` est retiré de l’adresse avant tout appel réseau.
2. Si le courriel ne correspond encore à aucun compte, saisissez un nom affiché et un nouveau mot de passe deux fois.
3. Si le compte existe, connectez-vous dans la page d’invitation, puis confirmez l’acceptation sans changer de page.
4. Après succès, une nouvelle session est installée dans l’organisation rejointe. Seule la toute première invitation Admin active une organisation encore en provisioning ; une invitation de membre conserve l’organisation active et applique exactement le rôle proposé.

Un lien expiré, révoqué, déjà utilisé ou inconnu produit volontairement le même message public. Un compte actif sans organisation reste limité à l’acceptation d’invitation et à la déconnexion ; il n’accède pas à la recherche.

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

- Python 3.12, version de référence utilisée par la CI (qualifier séparément toute version majeure ultérieure) ;
- Node.js 22 ou ultérieur ;
- un projet Google Cloud avec facturation activée ;
- Places API (New) activée ;
- Maps Static API activée pour la carte.
- Docker Desktop avec les conteneurs Linux pour PostgreSQL, Redis et Mailpit.

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

Le fichier réel reste local et ignoré par Git :

```powershell
Copy-Item .env.example .env
notepad .env
```

Renseignez `GOOGLE_MAPS_API_KEY` dans `.env`. `GOOGLE_MAPS_STATIC_API_KEY` reste facultative ; la clé Places sert de
repli. Le backend doit être démarré avec `--env-file .env` et entièrement redémarré après toute modification du fichier.

| Variable | Obligatoire | Usage |
| --- | --- | --- |
| `GOOGLE_MAPS_API_KEY` | Oui | Clé serveur restreinte à Places API (New). |
| `GOOGLE_MAPS_STATIC_API_KEY` | Non | Clé serveur distincte recommandée pour Maps Static API ; la clé Places sert de repli. |

Les clés sont lues depuis l’environnement du serveur et ne sont jamais renvoyées au navigateur. Restreignez-les aux API nécessaires et aux adresses IP du serveur lorsque l’hébergement le permet.

### Démarrage

Démarrez d’abord les dépendances locales :

```powershell
docker compose up -d --wait
docker compose run --rm database-role-provisioner
$env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://prospect:prospect-development-only@127.0.0.1:5432/prospect"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
$env:DATABASE_URL = "postgresql+asyncpg://prospect_app:prospect-app-development-only@127.0.0.1:5432/prospect"
```

La commande `docker compose run --rm database-role-provisioner` provisionne ou remet en conformité le rôle fixe
`prospect_app` sans recréer le volume. Le serveur Web utilise exclusivement `DATABASE_URL` ; Alembic utilise
exclusivement `MIGRATION_DATABASE_URL`. Ne remplacez pas le rôle Web par le propriétaire en cas d’erreur RLS.

Le passage de PostgreSQL 17.5 à 17.10 reste dans la même version majeure. Avant la première mise à niveau d’un volume
contenant des données utiles, réalisez néanmoins une sauvegarde vérifiée du volume ou un export PostgreSQL. Le fichier
Compose de test utilise un stockage temporaire indépendant et ne touche jamais au volume de développement.

Créez ensuite, une seule fois, le premier administrateur de plateforme. La commande refuse de créer un second administrateur initial et ne prend jamais le mot de passe en argument de ligne de commande :

```powershell
$env:BOOTSTRAP_PLATFORM_ADMIN_CONFIRM = "CREATE_FIRST_PLATFORM_ADMIN"
$env:BOOTSTRAP_PLATFORM_ADMIN_EMAIL = "admin@example.ca"
$env:BOOTSTRAP_PLATFORM_ADMIN_DISPLAY_NAME = "Administrateur"
.\.venv\Scripts\python.exe -m backend.app.cli.bootstrap_platform_admin
```

Le mot de passe est demandé de manière interactive. Pour une automatisation contrôlée, `BOOTSTRAP_PLATFORM_ADMIN_PASSWORD` peut être fourni par un coffre de secrets et doit être retiré immédiatement après usage.

Si le mot de passe du premier administrateur est perdu, il ne peut pas être relu depuis son hash Argon2id. Utilisez la
commande de récupération locale, après avoir configuré `MIGRATION_DATABASE_URL` :

```powershell
$env:ADMIN_PASSWORD_RESET_CONFIRM = "RESET_PLATFORM_ADMIN_PASSWORD"
$env:ADMIN_PASSWORD_RESET_EMAIL = "admin@example.ca"
.\.venv\Scripts\python.exe -m backend.app.cli.reset_platform_admin_password
```

Le nouveau mot de passe est demandé et confirmé sans être affiché. La commande refuse un compte non plateforme et
incrémente sa version afin d’invalider toutes les sessions antérieures.

Terminal 1 :

```powershell
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000 --env-file .env
```

Terminal 2 :

```powershell
cd client
npm run dev
```

Ouvrez `http://localhost:5173`. Vite redirige `/api` vers `http://127.0.0.1:8000`.

`GET /api/health/live` vérifie le processus. `GET /api/health/ready` retourne `200` uniquement lorsque PostgreSQL et Redis répondent ; la route historique `GET /api/health` reste disponible pendant la migration.

Mailpit reçoit uniquement les courriels locaux de test. Son interface est disponible sur `http://127.0.0.1:8025` et n’entre pas dans la disponibilité globale de l’application.

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
| `DATABASE_URL` | rôle `prospect_app` | Connexion du serveur Web, non propriétaire et sans `BYPASSRLS`. |
| `MIGRATION_DATABASE_URL` | rôle propriétaire | Connexion réservée aux migrations Alembic. |
| `POSTGRES_APP_PASSWORD` | secret local distinct | Mot de passe provisionné pour `prospect_app`, identique à celui de `DATABASE_URL`. |
| `INVITATION_DELIVERY_BACKEND` | `mailpit` | Interception locale seulement ; refusée en staging et production. |
| `INVITATION_SMTP_HOST` / `INVITATION_SMTP_PORT` | `127.0.0.1:1025` | Destination Mailpit locale, jamais dérivée d’une requête. |
| `RATE_LIMIT_HMAC_KEY` | aucun secret par défaut | Secret local aléatoire d’au moins 32 octets pour pseudonymiser les dimensions Redis. |

### Tester le provisioning local

La page d’administration plateforme arrivera en 2.3.5. En attendant, le script passe par les vraies routes, le cookie et le CSRF, sans accès direct à la base et sans afficher le jeton :

```powershell
.\scripts\Test-ProvisioningLocal.ps1 `
  -AdministratorEmail "admin@example.ca" `
  -OrganizationName "Entreprise Démonstration" `
  -InviteeEmail "nouvel-admin@example.ca"
```

Le mot de passe plateforme est demandé de façon interactive. Relevez le `CreationRequestId` retourné, ouvrez Mailpit, puis suivez le lien du message. Pour tester l’idempotence HTTP, rejouez manuellement le même UUID et le même corps ; une commande différente avec cet UUID doit être refusée.

### Tester les membres et le changement d’organisation

Jusqu’aux écrans d’administration de 2.3.5, le script 2.3.3 appelle exclusivement les vraies routes HTTP. Sans option,
il affiche l’organisation active, les membres autorisés et les invitations visibles :

```powershell
.\scripts\Test-OrganizationAdministrationLocal.ps1 `
  -AdministratorEmail "admin-organisation@example.ca"
```

Pour inviter un Gestionnaire :

```powershell
.\scripts\Test-OrganizationAdministrationLocal.ps1 `
  -AdministratorEmail "admin-organisation@example.ca" `
  -InviteeEmail "gestionnaire@example.ca" `
  -InviteeRole manager
```

Le script accepte aussi `-MembershipId`, `-MembershipVersion`, `-NewRole`, `-NewStatus` et
`-SwitchMembershipId`. Le mot de passe reste interactif ; aucun jeton d’invitation, cookie ou CSRF n’est affiché.

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

### Provisioning et invitations — incrément 2.3.2

- `GET /api/platform/organizations` liste uniquement les métadonnées de provisioning ;
- `POST /api/platform/organizations` crée de manière idempotente avec `creation_request_id` ;
- `POST /api/platform/organizations/{id}/first-invitation/resend` exige un nouveau `resend_request_id` ;
- `POST /api/platform/organizations/{id}/first-invitation/revoke` révoque l’invitation active ;
- `POST /api/auth/invitations/preview` expose seulement organisation, rôle, expiration et existence éventuelle du compte ;
- `POST /api/auth/invitations/accept` accepte pour un nouveau compte, ou pour la session correspondant au destinataire avec CSRF.

Les routes plateforme exigent la capacité plateforme, une origine fiable et JSON strict. Toutes les réponses sont `no-store`. Aucun jeton brut, hash, mot de passe, détail SMTP ou trace SQL n’apparaît dans les réponses ou dans OpenAPI.

### Organisation, membres et invitations — incrément 2.3.3

- `GET /api/organization` lit l’organisation active ;
- `PATCH /api/organization` modifie nom, langue ou fuseau avec `version` obligatoire ;
- `GET /api/organization/members` retourne une page de membres avec un curseur signé ;
- `PATCH /api/organization/members/{membership_id}` modifie rôle ou état avec verrou optimiste ;
- `GET/POST /api/organization/invitations` liste ou crée les invitations de membre ;
- `POST /api/organization/invitations/{id}/resend` renouvelle le jeton de façon idempotente ;
- `DELETE /api/organization/invitations/{id}` révoque sans suppression physique ;
- `POST /api/auth/switch-organization` choisit une appartenance active et fait tourner la seule session courante.

Un Administrateur gère l’organisation, les membres et les invitations. Un Gestionnaire lit l’organisation et les
membres, sans mutation. Un Commercial lit uniquement l’organisation et conserve la capacité de recherche. Les
identifiants absents ou appartenant à une autre organisation produisent le même `404`. Une auto-rétrogradation ou
auto-désactivation réussie expire le cookie courant et exige une reconnexion.

## Architecture

Le backend conserve des dépendances dirigées vers le domaine et l’application :

| Zone | Responsabilité |
| --- | --- |
| `backend/app/domain/` | Identité, organisation, membres, invitations, session, modèles Google et règles sans framework. |
| `backend/app/application/use_cases/` | Authentification, provisioning, administration locataire, invitations, readiness, recherche et carte. |
| `backend/app/application/ports/` | Interfaces des dépôts, mots de passe, sessions, limites, livraison, PostgreSQL/Redis et Google. |
| `backend/app/application/tenancy.py` | Contextes locataire et acteur plateforme, créés par le serveur et indépendants de PostgreSQL. |
| `backend/app/infrastructure/postgres/` | Passerelles de provisioning et d’organisation, unités de travail acteur/locataire, RLS et migrations Alembic. |
| `backend/app/infrastructure/redis/` | Sessions opaques, rotation atomique, purge par version et limitations HMAC. |
| `backend/app/infrastructure/pagination.py` | Curseurs opaques signés HMAC pour les listes locataires. |
| `backend/app/infrastructure/invitations/` | Jetons cryptographiques et livraison SMTP Mailpit locale. |
| `backend/app/infrastructure/security/` | Adaptateur Argon2id exécuté hors de la boucle asynchrone. |
| `backend/app/infrastructure/google/` | Appel HTTP Google et adaptation des données. |
| `backend/app/infrastructure/memory/` | Verrou et jetons temporaires, remplaçables par Redis. |
| `backend/app/presentation/api/` | Schémas Pydantic, mappers et routes FastAPI. |
| `client/src/features/lead-search/` | Écran transitoire de recherche, état local et composants React. |
| `client/src/features/auth/` | Connexion, restauration et état de session conservé uniquement en mémoire. |
| `client/src/features/invitations/` | Extraction pré-React du fragment et parcours d’acceptation en mémoire. |
| `client/src/shared/` | Client HTTP, erreurs et comportements réutilisables. |

Le port `PlacesGateway` expose une seule méthode `search`. Il ne connaît aucun jeton de pagination. Le masque de champs Google n’inclut ni contact ni `nextPageToken`, et le client HTTP n’effectue aucune nouvelle tentative automatique afin de garantir un seul POST Text Search par action.

## Sécurité et conformité

- clés Google exclusivement côté serveur ;
- mot de passe Argon2id de 12 à 128 caractères, sans normalisation ni troncature ;
- session aléatoire de 256 bits dont seul le hash indexe Redis ;
- cookie `HttpOnly`, `SameSite=Lax`, `Secure` et préfixé `__Host-` en production ;
- CSRF en mémoire et validation stricte de l’origine sur les mutations authentifiées ;
- compte désactivé ou version d’identité modifiée refusant immédiatement une ancienne session ;
- purge Redis sélective supprimant uniquement les sessions antérieures à la nouvelle version d’identité ;
- changement d’organisation renouvelant uniquement la session courante, sans modifier les autres sessions ;
- protection du dernier Administrateur sous verrou PostgreSQL organisation puis appartenance ;
- curseurs de pagination 2.3.3 signés et vérifiés avant toute requête ;
- rôle Web PostgreSQL non propriétaire, sans privilège élevé et sans droit de suppression physique ;
- politiques `ENABLE` et `FORCE ROW LEVEL SECURITY` sur organisations, appartenances et invitations ;
- fonctions `SECURITY DEFINER` étroites, `search_path` fixé, `PUBLIC` révoqué et signatures seules accordées au rôle Web ;
- jetons d’invitation aléatoires de 256 bits dont seul le SHA-256 est conservé en PostgreSQL ;
- limitation Redis atomique par HMAC d’adresse et de hash de jeton, fermée en cas d’indisponibilité ;
- première acceptation et activation sérialisées en transaction PostgreSQL ;
- paramètres RLS posés avec une portée strictement transactionnelle puis effacés au commit ou rollback ;
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

Le dernier passage valide 111 tests backend hors intégration et 21 tests d’intégration, dont les scénarios
PostgreSQL/Redis/Mailpit exécutés sur une base temporaire vierge, soit 132 scénarios backend sans test ignoré, ainsi
que 22 tests React répartis dans 9 fichiers. La suite protège
les migrations 0001→0005, RLS, concurrence du dernier Administrateur, cycles d’invitation, rotation et purge de
session, Mailpit, absence de stockage navigateur et toutes les garanties Google historiques.

## Suite de la migration CRM V1

Les incréments 2.1, 2.2, 2.3.1 et 2.3.2 sont terminés localement. L’implémentation 2.3.3 est complète, sa matrice
automatisée est verte et ses trois critiques ainsi que ses deux revues figurent dans
[`docs/PHASE_2_3_3_RAPPORT_IMPLEMENTATION.md`](docs/PHASE_2_3_3_RAPPORT_IMPLEMENTATION.md). Il reste au responsable
produit à exécuter le protocole local avant de déclarer 2.3.3 accepté et d’autoriser 2.3.4.

## Références

- [Text Search (New)](https://developers.google.com/maps/documentation/places/web-service/text-search)
- [Attribution Google Maps](https://developers.google.com/maps/documentation/places/web-service/policies)
- [Sécurité des clés API Google Maps](https://developers.google.com/maps/api-security-best-practices)
- [Maps Static API](https://developers.google.com/maps/documentation/maps-static/overview)
