# Marketteo CRM — Recette locale regroupée 2.5.1 + 2.5.2

| Métadonnée | Valeur à renseigner |
| --- | --- |
| Périmètre | 2.5.1 Modèle prospects + 2.5.2 création minimale et ajout Google |
| Environnement | Local Windows + WSL (`Ubuntu-24.04`) |
| Révision Git | __________ |
| Migration attendue | `20260814_0009 (head)` |
| Date | 14 août 2026 |
| Testeur | Responsable produit |
| Décision | **GO avec réserves** — étapes 9 et 10 à solder |

## 1. Objectif

Cette recette valide que Marketteo sait désormais :

- disposer du socle PostgreSQL/RLS des prospects ;
- créer un prospect manuel minimal ;
- ajouter au CRM un résultat Google explicitement sélectionné ;
- conserver durablement uniquement le `place_id` issu de Google ;
- empêcher les doublons actifs par organisation ;
- auditer les créations sans stocker de contenu Google dans l’audit ;
- conserver les protections Google existantes : un Text Search, 20 résultats maximum, aucun contact, `no-store`.

## 2. Précautions

- Utiliser uniquement des comptes et données de test.
- Ne pas capturer de mot de passe, cookie, jeton CSRF, clé Google ou jeton d’invitation.
- Ne lancer qu’une petite recherche Google réelle pendant la recette.
- Ne pas corriger PostgreSQL à la main pour faire réussir un scénario fonctionnel.
- Utiliser un suffixe de recette, par exemple `QA-20260814-01`.

## 3. Services locaux

Dans WSL, depuis le dossier du projet :

```bash
cd "/mnt/c/Users/Admin/OneDrive/Family Room/Documents/LeadGenerator"
docker compose ps
```

Attendu :

- `postgresql` healthy, exposé idéalement sur `55432->5432` ;
- `redis` healthy, exposé sur `6379` ;
- `mailpit` healthy, exposé sur `8025`.

Si les services ne sont pas démarrés :

```bash
docker compose up -d --wait
docker compose --profile database-tools run --rm database-role-provisioner
```

## 4. Variables PowerShell locales

Dans PowerShell, depuis la racine du projet :

```powershell
cd "C:\Users\Admin\OneDrive\Family Room\Documents\LeadGenerator"

$env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://prospect:prospect-development-only@127.0.0.1:55432/prospect"
$env:DATABASE_URL = "postgresql+asyncpg://prospect_app:prospect-app-development-only@127.0.0.1:55432/prospect"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:PUBLIC_APP_URL = "http://localhost:5173"
$env:CORS_ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
$env:INVITATION_DELIVERY_BACKEND = "mailpit"
$env:GOOGLE_MAPS_API_KEY = "VOTRE_CLE_GOOGLE"
```

Vérifier que la clé est vue par le backend après démarrage :

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/health" | Format-List *
```

Attendu : `google_api_key_configured : True`.

## 5. Migration

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini current
```

Attendu : `20260814_0009 (head)`.

## 6. Démarrage applicatif

Backend :

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --env-file .env
```

Frontend, dans un second terminal :

```powershell
cd "C:\Users\Admin\OneDrive\Family Room\Documents\LeadGenerator\client"
npm.cmd run dev
```

Vérifier :

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/health/ready"
```

Attendu :

```json
{
  "status": "ready",
  "dependencies": {
    "postgresql": "ok",
    "redis": "ok"
  }
}
```

## 7. Recette API minimale

Cette partie valide la création manuelle, indépendamment de l’interface complète des prospects qui arrivera plus tard.

```powershell
$apiRoot = "http://127.0.0.1:8000"
$origin = "http://localhost:5173"
$session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()

$login = Invoke-RestMethod `
  -Uri "$apiRoot/api/auth/login" `
  -Method Post `
  -WebSession $session `
  -Headers @{ Origin = $origin } `
  -ContentType "application/json" `
  -Body '{"email":"admin@example.ca","password":"VOTRE_MOT_DE_PASSE"}'

$headers = @{
  Origin = $origin
  "X-CSRF-Token" = $login.csrf_token
}

$manual = Invoke-RestMethod `
  -Uri "$apiRoot/api/prospects" `
  -Method Post `
  -WebSession $session `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"internal_alias":"Prospect manuel QA 2.5.2"}'

$manual

$page = Invoke-RestMethod `
  -Uri "$apiRoot/api/prospects?limit=25" `
  -Method Get `
  -WebSession $session

$page.items | Select-Object internal_alias,origin,source_label,google_place_id,stage_code
```

Attendu :

- `POST /api/prospects` retourne `201 Created` ;
- le prospect manuel a `origin = manual` ;
- `google_place_id` vaut `null` ;
- la liste retourne le prospect ;
- les réponses portent `Cache-Control: no-store` si vérifiées via `Invoke-WebRequest`.

## 8. Recette UI Google vers CRM

Ouvrir `http://localhost:5173`, puis se connecter avec un utilisateur membre d’une organisation active.

### UI-01 — Recherche Google conforme

1. Vérifier que le badge indique `API configurée`.
2. Rechercher `plombier` ou `restaurant`.
3. Utiliser un rayon raisonnable, par exemple 15 km autour de Québec.

Attendu :

- 20 résultats maximum ;
- `Appels effectués = 1` ;
- l’attribution `Google Maps` est visible ;
- aucun téléphone, site Web ou courriel n’est affiché ;
- l’export Excel reste désactivé.

### UI-02 — Ajout individuel

1. Sur une ligne de résultat, cliquer `Ajouter`.
2. Attendre la fin de l’action.

Attendu :

- le bouton passe à `Ajouté` ;
- la ligne ne devient pas éditable ;
- aucun appel Google supplémentaire n’est visible côté compteur ;
- aucun nom, adresse, téléphone ou site Web n’est annoncé comme conservé dans le CRM.

### UI-03 — Doublon Google actif

1. Relancer la même recherche.
2. Ajouter le même établissement si visible.

Attendu :

- le système retourne un état `Déjà au CRM` ;
- aucun doublon actif n’est créé en base ;
- aucun nouvel audit `prospect.created` n’est créé pour le doublon.

### UI-04 — Ajout groupé

1. Sélectionner deux ou trois lignes avec les cases à cocher.
2. Cliquer `Ajouter la sélection`.

Attendu :

- chaque ligne sélectionnée passe à `Ajouté` ou `Déjà au CRM` ;
- les lignes non sélectionnées restent inchangées ;
- le bouton groupé se désactive pendant l’ajout ;
- la sélection est vidée après succès.

### UI-05 — Absence de stockage navigateur

Dans les outils développeur du navigateur :

1. Ouvrir l’onglet Application.
2. Vérifier `Local Storage`.
3. Vérifier `Session Storage`.
4. Recharger la page.

Attendu :

- aucun résultat Google ni prospect CRM n’est écrit dans le stockage navigateur ;
- les résultats temporaires disparaissent après rechargement ;
- les prospects restent présents en base.

## 9. Preuves PostgreSQL

Depuis WSL :

```bash
cd "/mnt/c/Users/Admin/OneDrive/Family Room/Documents/LeadGenerator"

docker compose exec -T postgresql psql -U prospect -d prospect -c "
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'prospects'
ORDER BY ordinal_position;
"
```

Attendu :

- présence de `google_place_id`, `internal_alias`, `origin`, `source_label`, `stage_code`, `priority` ;
- absence de colonnes persistantes Google telles que `name`, `address`, `phone`, `website`, `google_maps_url`.

Vérifier les prospects créés :

```bash
docker compose exec -T postgresql psql -U prospect -d prospect -c "
SELECT internal_alias, origin, source_label, google_place_id, stage_code, priority
FROM prospects
ORDER BY created_at DESC
LIMIT 10;
"
```

Attendu :

- les prospects Google ont `origin = google_place` ;
- leur `source_label` vaut `google_places:text_search` ;
- leur `internal_alias` est neutre, par exemple `Prospect Google XXXXX` ;
- seul `google_place_id` contient une valeur Google persistante.

Vérifier l’audit :

```bash
docker compose exec -T postgresql psql -U prospect -d prospect -c "
SELECT action, entity_type, metadata
FROM audit_events
WHERE action = 'prospect.created'
ORDER BY occurred_at DESC
LIMIT 20;
"
```

Attendu :

- `action = prospect.created` ;
- `entity_type = prospect` ;
- `metadata` contient uniquement une origine, par exemple `{\"origin\":\"google_place\"}` ou `{\"origin\":\"manual\"}` ;
- aucun `place_id`, nom, adresse, téléphone, site Web, URL Google ou jeton n’est présent.

## 10. Contrôles automatisés rapides

Depuis PowerShell :

```powershell
.\.venv\Scripts\python.exe -m ruff check backend\app tests
.\.venv\Scripts\python.exe -m mypy backend\app
.\.venv\Scripts\python.exe -m pytest -q

cd client
npm.cmd run lint
npm.cmd test -- --run src/features/lead-search/LeadGeneratorPage.test.jsx
npm.cmd run build
cd ..
```

Attendu :

- Ruff vert ;
- mypy vert ;
- pytest vert ;
- ESLint vert ;
- Vitest ciblé vert ;
- build Vite vert.

## 11. Verrou qualité complet

Le script complet démarre une composition de test isolée. Si les services applicatifs locaux utilisent déjà `55432`,
`6379`, `8025` ou des ports proches, utiliser des ports alternatifs pour éviter les conflits.

PowerShell, recommandé avec Docker fonctionnel dans `Ubuntu-24.04` :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test-QualityGateLocal.ps1 `
  -DockerMode wsl `
  -WslDistribution "Ubuntu-24.04" `
  -TestPostgresPort 56432 `
  -TestRedisPort 57379 `
  -TestMailpitSmtpPort 51027 `
  -TestMailpitApiPort 58027
```

Attendu final : `Verrou qualité local 2.5.2 : VERT`.

Le script met à jour les preuves dans `test-results/`, notamment :

- `test-results/pytest-quality.xml` ;
- `test-results/vitest.xml` ;
- `test-results/alembic-current.txt`.

## 12. Critères GO

La recette est conforme si :

- migration à `20260814_0009 (head)` ;
- readiness backend `ready` ;
- création manuelle validée par API ;
- ajout Google individuel et groupé validés par UI ;
- doublon actif retourné comme existant ou non dupliqué ;
- base PostgreSQL ne conserve depuis Google que `google_place_id` ;
- audit minimal sans données Google ;
- stockage navigateur vide pour résultats/prospects ;
- contrôles automatisés rapides verts ;
- verrou qualité complet vert ou anomalie d’environnement documentée.

## 13. Décision

| Contrôle | Statut | Preuve / commentaire |
| --- | --- | --- |
| Services ready | CONFORME | PostgreSQL et Redis prêts pendant la recette. |
| Migration `20260814_0009` | CONFORME | Alembic confirmé à `20260814_0009 (head)`. |
| Création prospect manuel API | CONFORME | Validation fonctionnelle accordée. |
| Recherche Google limitée | CONFORME | Validation fonctionnelle accordée. |
| Ajout individuel Google | CONFORME | Validation fonctionnelle accordée. |
| Ajout groupé Google | CONFORME | Validation fonctionnelle accordée. |
| Doublon actif | CONFORME | Validation fonctionnelle accordée. |
| Absence stockage navigateur | CONFORME | Couvert par la recette et les tests frontend. |
| Vérification PostgreSQL | RÉSERVE | Étape 9 à exécuter et preuve à consigner. |
| Audit minimal | RÉSERVE | Vérification SQL de l’étape 9 à consigner. |
| Contrôles rapides | RÉSERVE | Étape 10 à exécuter séparément et preuve à consigner. |
| Verrou qualité complet | CONFORME | `Verrou qualité local 2.5.2 : VERT` ; 31 fichiers et 135 tests frontend verts. |

Décision finale : **GO avec réserves**, prononcé le 14 août 2026. Les réserves portent exclusivement sur la
collecte des preuves des étapes 9 et 10 ; aucune anomalie fonctionnelle bloquante n’est ouverte.
