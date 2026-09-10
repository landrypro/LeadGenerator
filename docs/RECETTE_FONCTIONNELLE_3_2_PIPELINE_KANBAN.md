# Recette fonctionnelle QA — Phase 3.2 Pipeline Kanban

**Version :** 1.0  
**Date :** 4 septembre 2026  
**Statut :** prêt pour la recette fonctionnelle  
**Périmètre :** pipeline commercial, droits, isolation, audit, concurrence et verrou qualité.

> Cette recette utilise des prospects de test. Ne pas la réaliser sur une organisation de production contenant des données réelles.

## 1. Objectif

Valider que chaque organisation peut suivre ses prospects dans un pipeline commercial de neuf étapes, que les déplacements respectent les règles métier, que les droits sont appliqués, et que toute action utile est traçable.

Les neuf étapes attendues sont :

1. Nouveau
2. Qualification
3. Qualifié
4. Contacté
5. Opportunité
6. Soumission envoyée
7. Négociation
8. Gagné
9. Perdu

## 2. Préparation technique

### 2.1 Démarrer les dépendances

Dans le terminal WSL Ubuntu, depuis le dossier du projet :

```bash
cd "/mnt/c/Users/Admin/OneDrive/Family Room/Documents/LeadGenerator"
docker compose up -d --wait
docker compose ps
```

Attendu : `postgresql`, `redis` et `mailpit` sont démarrés et en état `healthy` lorsque cet état est disponible.

### 2.2 Appliquer les migrations

Dans PowerShell, depuis la racine du projet, avec `DATABASE_URL` et `MIGRATION_DATABASE_URL` déjà configurées dans votre session ou dans `.env` :

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini current
```

Attendu : la dernière ligne indique `20260904_0015 (head)`.

### 2.3 Démarrer l’API et le client

Terminal PowerShell 1 :

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --env-file .env
```

Terminal PowerShell 2 :

```powershell
cd client
npm ci
npm run dev
```

Si `vite` est introuvable, `npm ci` réinstalle les dépendances attendues. Fermez auparavant les serveurs Vite et éditeurs qui pourraient verrouiller un fichier de `node_modules`.

Vérifier ensuite :

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/health/ready"
```

Attendu : `status` vaut `ready`, avec PostgreSQL et Redis à `ok`.

Ouvrir ensuite `http://localhost:5173`.

### 2.4 Comptes et données nécessaires

Préparer les comptes suivants dans deux organisations distinctes :

| Compte | Organisation | Rôle | Usage de recette |
|---|---|---|---|
| Admin A | Organisation A | Administrateur | Configuration, réouverture, audit |
| Manager A | Organisation A | Gestionnaire | Déplacements et réouverture |
| Sales A | Organisation A | Commercial | Déplacements et lecture |
| Admin B | Organisation B | Administrateur | Vérification de l’isolation |

Créer au minimum quatre prospects manuels dans l’organisation A : `KAN Nouveau`, `KAN Perdu`, `KAN Concurrence` et `KAN Filtre`. Ils peuvent être créés depuis **Prospects > Ajouter un prospect**.

Conserver dans le relevé QA : l’adresse des comptes, le nom de l’organisation active, l’identifiant du prospect utilisé et une capture des résultats importants. Ne jamais inscrire les mots de passe dans le relevé.

## 3. Règles de test

- Ouvrir une fenêtre privée distincte pour chaque compte utilisé simultanément.
- Recharger la page après un déplacement et vérifier que la carte n’apparaît qu’une seule fois.
- Pour un appel API modifiant un état, conserver la même `idempotency_key` seulement lorsqu’on teste explicitement le rejeu.
- Les données créées pendant la recette peuvent être archivées logiquement après l’exécution ; ne pas les supprimer physiquement.

## 4. Parcours fonctionnels

### KAN-01 — Affichage du tableau

1. Connectez-vous avec **Admin A** et vérifiez que l’organisation A est active.
2. Ouvrez le menu **Pipeline**.
3. Vérifiez les neuf colonnes dans l’ordre défini à la section 1.
4. Vérifiez que chaque colonne affiche son compteur et les cartes de l’organisation A.
5. Ouvrez une carte puis revenez au tableau.

Attendu : les étapes, compteurs, cartes et liens vers les fiches sont lisibles ; aucune carte de l’organisation B n’est visible.

### KAN-02 — Déplacement normal et progression commerciale

1. Dans la colonne **Nouveau**, repérez `KAN Nouveau`.
2. Utilisez le contrôle de déplacement proposé par la carte pour la déplacer vers **Qualification**.
3. Rafraîchissez la page.
4. Déplacez ensuite la même carte dans l’ordre : **Qualifié**, **Contacté**, **Opportunité**, **Soumission envoyée**, puis **Négociation**.

Attendu : chaque déplacement est confirmé, la carte quitte sa colonne source, rejoint une seule fois la colonne cible, et persiste après rechargement.

### KAN-03 — Retour autorisé

1. Depuis **Négociation**, ramenez `KAN Nouveau` vers **Soumission envoyée**.
2. Ramenez-la ensuite vers **Opportunité**.
3. Rechargez le tableau.

Attendu : les retours immédiatement prévus sont acceptés et persistent.

### KAN-04 — Passage interdit

1. Prenez un prospect resté à l’étape **Nouveau**.
2. Vérifiez dans l’interface qu’aucun contrôle normal ne permet de l’envoyer directement vers **Gagné** ou **Soumission envoyée**.
3. Confirmez que la carte demeure dans **Nouveau**.

Attendu : l’interface ne propose que les transitions autorisées. La vérification API détaillée de la section 5 doit retourner `422` pour une tentative de saut.

### KAN-05 — Perte avec motif

1. Amenez `KAN Perdu` à une étape non terminale, par exemple **Qualification**.
2. Sélectionnez le déplacement vers **Perdu**.
3. Choisissez un motif explicite, par exemple `Pas de besoin` ou `Sans réponse`.
4. Confirmez le déplacement puis rechargez la page.

Attendu : la carte est dans **Perdu**, aucun déplacement commercial standard ultérieur n’est proposé, et l’historique contient le motif.

### KAN-06 — Motif « Autre » obligatoire

1. Utilisez un nouveau prospect et amenez-le à **Qualification**.
2. Choisissez le motif de perte `Autre` sans saisir de note.
3. Tentez de confirmer.
4. Saisissez ensuite une note non sensible, par exemple `Hors cible de la campagne de test`, puis confirmez.

Attendu : la première tentative est refusée ; la seconde est acceptée. La note ne doit pas être affichée dans une liste publique ou dans une notification non autorisée.

### KAN-07 — Étape gagnée et état terminal

1. Amenez un prospect jusqu’à **Soumission envoyée**.
2. Déplacez-le vers **Gagné**.
3. Rechargez le tableau et observez la carte.
4. Vérifiez qu’aucun déplacement commercial normal n’est proposé depuis **Gagné**.

Attendu : `Gagné` est terminal ; seul le processus de réouverture peut faire sortir le prospect de cet état.

### KAN-08 — Recherche et filtres du portefeuille

1. Ouvrez **Prospects**.
2. Recherchez `KAN Filtre` par son nom.
3. Vérifiez qu’il est le seul résultat correspondant.
4. Effacez la recherche et vérifiez le retour de la liste complète de l’organisation active.
5. Si les filtres de priorité et de responsable sont proposés dans l’environnement testé, appliquez-les un à un puis combinés.

Attendu : les critères ne retournent que les prospects de l’organisation active et le résultat est cohérent après rechargement.

### KAN-09 — Historique et journal d’activité

1. Avec **Admin A**, ouvrez **Journal d’activité** après les scénarios KAN-02 à KAN-07.
2. Recherchez les événements liés aux changements d’étape du prospect de test.
3. Vérifiez au minimum : l’acteur, l’horodatage, l’organisation, l’étape source et l’étape cible.
4. Vérifiez que le motif de perte est présent lorsque la perte a été effectuée.

Attendu : un événement est visible pour chaque transition effectuée. Les données sensibles de contact ne sont pas ajoutées au journal à la place des métadonnées de workflow.

### KAN-10 — Réouverture contrôlée

1. Avec **Admin A**, dans la colonne **Perdu** ou **Gagné**, sélectionnez **Réouvrir** sur un prospect.
2. Dans la fenêtre de confirmation, choisissez par exemple **Le prospect a repris contact**.
3. Pour **Autre motif**, vérifiez qu’une précision est obligatoire.
4. Confirmez la réouverture, puis rechargez le tableau.
5. Vérifiez que le prospect revient à l’étape antérieure permise ou à **Qualification** si l’historique ne permet pas de la déterminer, et que le journal d’activité contient l’événement.

Attendu : la réouverture est possible pour un administrateur ou un gestionnaire, jamais pour un commercial ; un événement d’audit est créé.

### KAN-11 — Droits par rôle

1. Connectez-vous avec **Sales A** dans une fenêtre privée.
2. Vérifiez que le tableau et les cartes sont consultables.
3. Effectuez un déplacement autorisé sur un prospect de test.
4. Tentez ensuite un appel de réouverture et un appel de configuration avec les requêtes de section 5.
5. Recommencez la réouverture avec **Manager A**.
6. Recommencez la configuration avec **Admin A**.

Attendu :

| Capacité | Admin | Gestionnaire | Commercial |
|---|---:|---:|---:|
| Lire tableau, cartes, historique | Oui | Oui | Oui |
| Déplacer une carte | Oui | Oui | Oui |
| Réouvrir une carte terminale | Oui | Oui | Non (`403`) |
| Configurer une étape | Oui | Non (`403`) | Non (`403`) |

### KAN-12 — Isolation entre organisations

1. Avec **Admin A**, notez l’identifiant d’un prospect de l’organisation A depuis l’URL de sa fiche.
2. Connectez-vous avec **Admin B** dans une fenêtre privée et vérifiez que l’organisation B est active.
3. Ouvrez le tableau Pipeline et la liste Prospects.
4. Recherchez le nom et tentez d’ouvrir l’URL connue du prospect de l’organisation A.

Attendu : la carte et la fiche de l’organisation A ne sont pas accessibles depuis l’organisation B. L’API ne doit révéler aucune donnée inter-organisation.

### KAN-13 — Concurrence et version optimiste

1. Ouvrez le même prospect à l’étape **Nouveau** avec **Admin A** dans deux fenêtres privées distinctes.
2. Dans la première fenêtre, déplacez-le vers **Qualification**.
3. Sans recharger la seconde fenêtre, tentez le même déplacement ou un autre déplacement autorisé reposant sur l’ancienne version.
4. Rechargez la seconde fenêtre.

Attendu : le second enregistrement est refusé par un conflit `409` ou l’interface demande de recharger. Il ne crée ni doublon de transition ni écrasement silencieux. Après rechargement, la carte reflète la première transition.

### KAN-14 — Limite d’affichage de colonne

1. Créez ou placez plus de 25 prospects de test dans une même étape.
2. Ouvrez le tableau Pipeline et notez le nombre de cartes visibles dans cette colonne.
3. Sélectionnez **Charger plus** dans cette colonne.
4. Vérifiez que les 25 cartes suivantes sont ajoutées sans doublon, jusqu’à 50 cartes au total.

Attendu selon la spécification : la première page affiche au plus 25 cartes et permet de consulter progressivement jusqu’à 50 cartes sans charger toute la base.

## 5. Vérifications API guidées

Ces contrôles complètent l’interface pour les droits, les conflits, le rejeu, l’historique, la réouverture et la configuration. Utilisez un compte de recette ; remplacez les valeurs entre chevrons.

### 5.1 Connexion de test

Dans PowerShell :

```powershell
$api = "http://127.0.0.1:8000"
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$loginHeaders = @{ Origin = "http://localhost:5173" }
$password = Read-Host "Mot de passe" -AsSecureString
$plainPassword = [System.Net.NetworkCredential]::new("", $password).Password
$loginBody = @{ email = "<admin-a@exemple.test>"; password = $plainPassword } | ConvertTo-Json
$login = Invoke-RestMethod -Uri "$api/api/auth/login" -Method Post -WebSession $session -Headers $loginHeaders -ContentType "application/json" -Body $loginBody
$headers = @{ "X-CSRF-Token" = $login.csrf_token; Origin = "http://localhost:5173" }
```

Vérifiez ensuite le contexte de l'utilisateur :

```powershell
Invoke-RestMethod -Uri "$api/api/auth/me" -WebSession $session
```

Attendu pour les contrôles 5.2 à 5.6 : `active_organization` est renseignée et `memberships` contient une appartenance active. Utilisez un compte Administrateur de l'organisation de recette pour les opérations d'écriture. Un compte uniquement `platform_admin`, sans organisation active, peut se connecter mais ne peut pas lire ni modifier le pipeline d'une organisation.

Ne copiez ni la sortie de `$login` ni le mot de passe dans le rapport QA.

### 5.2 Lire le tableau et choisir une carte

```powershell
$board = Invoke-RestMethod -Uri "$api/api/prospects/pipeline/board" -WebSession $session
$prospect = $board.columns.new[0]
$prospect
```

Attendu : la carte contient au minimum son `id`, son `version`, son étape et les informations CRM autorisées.

### 5.3 Transition, rejeu idempotent et historique

```powershell
$command = @{
  version = $prospect.version
  to_stage = "qualifying"
  idempotency_key = [guid]::NewGuid().ToString()
} | ConvertTo-Json

$first = Invoke-RestMethod -Uri "$api/api/prospects/$($prospect.id)/stage-transitions" -Method Post -WebSession $session -Headers $headers -ContentType "application/json" -Body $command
$replay = Invoke-RestMethod -Uri "$api/api/prospects/$($prospect.id)/stage-transitions" -Method Post -WebSession $session -Headers $headers -ContentType "application/json" -Body $command
$history = Invoke-RestMethod -Uri "$api/api/prospects/$($prospect.id)/stage-transitions" -WebSession $session
```

Attendu : `$first.id` et `$replay.id` sont identiques ; l’historique ne contient qu’une transition créée pour cette même clé d’idempotence.

### 5.4 Saut interdit et conflit de version

Pour le saut interdit, utilisez une carte à l’étape `new` et remplacez `to_stage` par `won` :

```powershell
$invalid = @{ version = $prospect.version; to_stage = "won"; idempotency_key = [guid]::NewGuid().ToString() } | ConvertTo-Json
try {
  Invoke-RestMethod -Uri "$api/api/prospects/$($prospect.id)/stage-transitions" -Method Post -WebSession $session -Headers $headers -ContentType "application/json" -Body $invalid
} catch {
  $_.Exception.Response.StatusCode.value__
}
```

Attendu : `422`.

Pour le conflit, envoyez une première transition valide, puis envoyez une seconde transition avec l’ancienne `version` et une nouvelle clé d’idempotence.

Attendu : `409` pour la seconde requête.

### 5.5 Réouverture

Sur une carte réellement à l’étape `lost` ou `won` :

```powershell
$reopen = @{
  version = <version-courante>
  reason_code = "customer_reengaged"
  idempotency_key = [guid]::NewGuid().ToString()
} | ConvertTo-Json

Invoke-RestMethod -Uri "$api/api/prospects/<prospect-id>/reopen" -Method Post -WebSession $session -Headers $headers -ContentType "application/json" -Body $reopen
```

Attendu : `200` pour Admin ou Gestionnaire ; `403` pour Commercial. Si `reason_code` vaut `other`, ajouter `reason_note` non vide.

### 5.6 Configuration des étapes

Lire la configuration :

```powershell
$stages = Invoke-RestMethod -Uri "$api/api/prospects/pipeline/stages" -WebSession $session
$stages
```

Avec Admin, modifiez seulement une donnée de test réversible (par exemple le libellé anglais ou la couleur d’une étape), en réutilisant la `version` renvoyée :

```powershell
$qualifyingStage = @($stages | Where-Object { $_.code -eq "qualifying" })[0]
$update = @{
  version = $qualifyingStage.version
  color_token = "#0f766e"
  labels = @{ "fr-CA" = "Qualification"; "en-CA" = "Qualification" }
} | ConvertTo-Json -Depth 3
$updatedStage = Invoke-RestMethod -Uri "$api/api/prospects/pipeline/stages/qualifying" -Method Patch -WebSession $session -Headers $headers -ContentType "application/json" -Body $update

# Remettre immédiatement les valeurs lues avant le test.
$restore = @{ version = $updatedStage.version; color_token = $qualifyingStage.color_token; labels = $qualifyingStage.labels } | ConvertTo-Json -Depth 3
Invoke-RestMethod -Uri "$api/api/prospects/pipeline/stages/qualifying" -Method Patch -WebSession $session -Headers $headers -ContentType "application/json" -Body $restore
```

Attendu : `200` pour Admin, `403` pour Gestionnaire et Commercial, un événement d’audit créé, puis remise de la valeur initiale après le test.

## 6. Contrôles sécurité et conformité

### SEC-01 — En-têtes et absence de cache applicatif

1. Dans les outils de développement du navigateur, ouvrez l’onglet Réseau.
2. Chargez le tableau Pipeline, l’historique et une fiche prospect.
3. Vérifiez les réponses API associées.

Attendu : les réponses privées portent `Cache-Control: no-store` ; les données d’une organisation ne sont pas accessibles depuis une autre session.

### AUD-01 — Non-divulgation dans l’audit

1. Réalisez une transition avec motif et note de test.
2. Consultez le Journal d’activité et l’historique.

Attendu : l’audit expose l’action, l’acteur et les métadonnées utiles de workflow, sans recopier inutilement des coordonnées de contacts ou secrets techniques.

## 7. Verrou qualité final

Fermez les serveurs locaux qui utilisent les ports de test si nécessaire, puis lancez :

```powershell
.\scripts\Test-QualityGateLocal.ps1 -DockerMode wsl -WslDistribution "Ubuntu-24.04"
```

Si les ports de la composition de test sont déjà utilisés, utiliser des ports libres, par exemple :

```powershell
.\scripts\Test-QualityGateLocal.ps1 `
  -DockerMode wsl `
  -WslDistribution "Ubuntu-24.04" `
  -TestPostgresPort 55433 `
  -TestRedisPort 56380 `
  -TestMailpitSmtpPort 51027 `
  -TestMailpitApiPort 58027
```

Attendu : le message final est `Verrou qualité local 3.2 : VERT`. Le verrou exécute notamment Ruff, mypy, pytest, Alembic, ESLint, Vitest et le build client.

Pour conserver la preuve :

```powershell
.\scripts\Test-QualityGateLocal.ps1 -DockerMode wsl -WslDistribution "Ubuntu-24.04" *>&1 | Tee-Object -FilePath "test-results\quality-gate-3.2.txt"
```

## 8. Feuille de synthèse QA

| Cas | Résultat attendu | Statut | Preuve / anomalie |
|---|---|---|---|
| PRE-01 | Dépendances et santé prêtes  |OK  |  |
| MIG-01 | `20260904_0015 (head)` | OK |  |
| KAN-01 | Neuf colonnes et compteurs | OK |  |
| KAN-02 | Progression normale persistante | OK |  |
| KAN-03 | Retour autorisé |OK  |  |
| KAN-04 | Saut interdit refusé | OK |  |
| KAN-05 | Perte avec motif |OK  |  |
| KAN-06 | Note requise pour `other` |OK  |  |
| KAN-07 | Gagné terminal |OK  |  |
| KAN-08 | Recherche et filtres |OK  |  |
| KAN-09 | Historique et audit |OK  |  |
| KAN-10 | Réouverture contrôlée | OK |  |
| KAN-11 | Droits Admin / Gestionnaire / Commercial |OK  |  |
| KAN-12 | Isolation des organisations | OK |  |
| KAN-13 | Conflit optimiste `409` | OK |  |
| KAN-14 | Pagination de colonne jusqu’à 50 |OK  |  |
| SEC-01 | `Cache-Control: no-store` |OK(avec reserve)  |  |
| AUD-01 | Audit sans données inutiles |OK(avec reserve)  |  |
| QG-01 | Verrou qualité vert | OK |  |

## 9. Critères de clôture

La recette 3.2 peut être déclarée conforme si tous les scénarios obligatoires sont passants, aucune donnée d’une organisation n’est visible par une autre, les conflits et droits sont correctement refusés, et le verrou qualité est vert.

La clôture doit rester **avec réserve** tant que KAN-14 ne satisfait pas l’exigence de consultation progressive jusqu’à 50 cartes par colonne, ou tant que les fonctions d’historique, de réouverture et de configuration ne disposent pas d’un écran utilisateur lorsque celui-ci est exigé pour le périmètre de livraison.
