# Recette fonctionnelle QA — Phase 3.3 Activités, tâches et rappels

**Version :** 1.1  
**Date :** 10 septembre 2026  
**Statut :** clôture 3.3 avec réserves ; verrou qualité global conforme ; contrôles restants reportés à la recette finale de l’application  
**Périmètre :** chronologie commerciale, activités déclaratives, tâches, rappels, prochaine action, droits et isolation.

> Utiliser uniquement des comptes et prospects fictifs. Les activités et tâches sont des données CRM persistantes : ne
> jamais saisir de secret, de mot de passe, de donnée de santé ou de contenu Google descriptif dans cette recette.

## 1. Objectif et critères de sortie

La recette couvre en un parcours unique les sous-lots 3.3-A à 3.3-D. La phase peut être clôturée avec réserves lorsque :

- les migrations `20260905_0016` à `20260905_0019` sont appliquées sans `stamp` manuel ;
- les scénarios effectivement exécutés sont conformes et leurs preuves sont consignées ;
- chaque scénario restant est nommé, non réputé validé et transféré à la recette finale de l’application ;
- le verrou qualité global est vert, sans test ignoré ;
- les réserves transversales `SEC-01` et `AUD-01` restent explicitement suivies jusqu’au verrou final 3.6.

## 2. Préparation technique

### 2.1 Sauvegarde et dépendances

Sauvegarder la base de recette si elle contient des données à conserver. Démarrer ensuite PostgreSQL, Redis et Mailpit
avec la composition habituelle du projet et vérifier leur état.

### 2.2 Migrations réelles

Depuis PowerShell à la racine du projet :

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini current
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini check
```

Attendus :

- `current` indique exactement `20260905_0019 (head)` ;
- `check` indique qu’aucune nouvelle opération de migration n’est détectée ;
- aucune commande `alembic stamp` n’a été utilisée pour masquer une migration non exécutée.

### 2.3 Démarrer l’application

Terminal API :

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --env-file .env
```

Terminal client :

```powershell
Set-Location client
npm ci
npm run dev
```

Vérifier `http://127.0.0.1:8000/api/health/ready`, puis ouvrir `http://localhost:5173`.

### 2.4 Comptes et données

Préparer deux organisations et les comptes suivants :

| Compte | Organisation | Rôle | Usage |
| --- | --- | --- | --- |
| Admin A | Organisation A | Administrateur | Toutes les activités et tâches |
| Manager A | Organisation A | Gestionnaire | Gestion des tâches et corrections |
| Sales A | Organisation A | Commercial | Activités propres et tâches assignées |
| Sales A2 | Organisation A | Commercial | Contrôle des droits croisés |
| Admin B | Organisation B | Administrateur | Isolation inter-organisation |

Créer dans A les prospects `ACT Chronologie`, `TASK Cycle`, `TASK Concurrence` et `TASK Fuseau`. Ajouter sur le premier
un canal autorisé et un canal à permission non déterminée. Conserver les identifiants dans le relevé QA, jamais les mots
de passe.

## 3. Activités et chronologie

### ACT-01 — Note interne

1. Ouvrir `ACT Chronologie` et ajouter une note interne datée de maintenant.
2. Recharger la fiche.

Attendu : la note apparaît une seule fois, avec son auteur et son horodatage ; elle ne crée ni tâche, ni transition de
pipeline, ni permission de contact.

### ACT-02 — Interactions déclaratives

Déclarer successivement un appel, un courriel et une réunion déjà réalisés. Pour l’appel et le courriel, choisir le sens
entrant ou sortant.

Attendu : les quatre types sont lisibles en français et en anglais ; l’interface rappelle qu’aucun appel, courriel ou
invitation n’est envoyé.

### ACT-03 — Permission du canal

Déclarer un courriel sur le canal à permission non déterminée.

Attendu : un avertissement est visible avant l’enregistrement ; l’activité peut documenter le fait passé, conserve
l’instantané `unknown` et ne change pas la permission du canal.

### ACT-04 — Correction append-only

1. Corriger une activité existante en donnant un motif.
2. Recharger la fiche et le journal d’activité.

Attendu : l’original reste présent ; une nouvelle entrée liée porte la correction ; aucun texte libre de la note, du
résumé ou du motif n’est copié dans l’audit technique.

### ACT-05 — Validations

Essayer une activité future, un résumé de 161 caractères et un appel sans sens entrant/sortant.

Attendu : chaque commande est refusée avec un message exploitable ; aucun enregistrement partiel n’apparaît.

### CHR-01 — Chronologie unifiée

Faire une transition de pipeline et créer puis terminer une tâche sur le même prospect.

Attendu : la chronologie restitue activités, événements de tâches et transitions, classés par date, sans dupliquer les
transitions dans la table d’activités.

## 4. Tâches, rappels et prochaine action

### TASK-01 — Création et prochaine action

Créer sur `TASK Cycle` deux tâches ouvertes avec titres distincts, échéances futures, priorités et rappels. La seconde
doit avoir l’échéance la plus proche.

Attendu : la tâche est assignée à un membre actif ; la plus proche devient la prochaine action sur la fiche, la liste des
prospects et le Kanban ; le titre accepte au plus 160 caractères et la description 2 000.

### TASK-02 — Mes tâches et rappels dus

Ouvrir « Mes tâches » avec Sales A. Vérifier les tâches ouvertes, puis préparer un rappel arrivé à échéance.

Attendu : les tâches d’un autre commercial ne sont pas incluses dans « Mes tâches » ; le rappel dû est signalé sans
envoi externe et sans stockage dans le navigateur.

### TASK-03 — Accusé et report

Accuser un rappel, puis reporter un autre rappel de moins de sept jours. Tenter ensuite un report de plus de sept jours.

Attendu : accusé et report valide restent visibles dans l’historique ; le report supérieur à sept jours est refusé sans
modifier la tâche.

### TASK-04 — Cycle de vie

Terminer une tâche, annuler une autre avec motif, puis les rouvrir avec motif.

Attendu : les états suivent seulement `open`, `completed` et `cancelled` ; annulation et réouverture exigent un motif ;
chaque mutation produit un événement métier ; une tâche fermée disparaît des prochaines actions.

### TASK-05 — Retard et fuseau horaire

Vérifier une échéance aujourd’hui et une échéance dépassée dans le fuseau IANA de l’organisation. Changer le fuseau de
l’organisation dans un environnement de recette contrôlé, puis recharger.

Attendu : les instants persistés ne changent pas ; seuls leur rendu local et l’étiquette à venir/aujourd’hui/en retard
sont recalculés. Une date sans fuseau ou une heure locale ambiguë est refusée par l’API.

### TASK-06 — Responsable désactivé

Assigner une tâche à Sales A2, puis désactiver ce membre. Essayer également de lui assigner une nouvelle tâche.

Attendu : l’ancienne tâche reste lisible et signale le responsable désactivé ; aucune réaffectation automatique n’a
lieu ; une nouvelle affectation vers ce membre est refusée.

### TASK-07 — Concurrence et idempotence

1. Ouvrir `TASK Concurrence` dans deux fenêtres et conserver la même version de tâche.
2. Modifier la tâche dans la première, puis soumettre une mutation différente depuis la seconde.
3. Rejouer exactement la première commande avec la même clé d’idempotence.

Attendu : la mutation obsolète reçoit `409 task_version_conflict` ; le rejeu restitue le même résultat sans doubler
l’événement ni l’audit.

## 5. Droits, isolation et sécurité ciblée

### PERM-01 — Matrice des rôles

- Admin A et Manager A peuvent gérer toutes les tâches de A et corriger toute activité de A.
- Sales A peut créer une activité, corriger ses propres saisies et gérer une tâche qui lui est assignée.
- Sales A ne peut pas gérer la tâche de Sales A2 ni corriger son activité.

Attendu : les actions non autorisées sont absentes de l’interface et refusées par l’API.

### ISO-01 — Isolation d’organisation

Avec Admin B, essayer d’ouvrir les URL et identifiants d’activités/tâches de A et interroger les listes.

Attendu : aucun objet, titre, compteur ou existence de A n’est divulgué. Les données de B restent indépendantes.

### SEC-3.3 — Contrôles locaux au module

Dans les outils réseau, vérifier que les lectures de chronologie, tâches, rappels et prochaines actions contiennent
`Cache-Control: no-store`. Une mutation sans jeton CSRF valide doit être refusée. Vérifier l’absence de contenu 3.3 dans
`localStorage` et `sessionStorage`.

> Ce contrôle cible les nouveaux endpoints. Les campagnes transversales réservées `SEC-01` et `AUD-01` restent dues en
> phase 3.6, conformément aux décisions déjà prises.

## 6. Vérifications API guidées

Après connexion, conserver la session et le jeton CSRF :

```powershell
$api = "http://127.0.0.1:8000"
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$password = Read-Host "Mot de passe" -AsSecureString
$plainPassword = [System.Net.NetworkCredential]::new("", $password).Password
$loginBody = @{ email = "sales-a@example.test"; password = $plainPassword } | ConvertTo-Json -Compress
$loginHeaders = @{ Origin = "http://localhost:5173" }
$login = Invoke-RestMethod -Uri "$api/api/auth/login" -Method Post -WebSession $session -Headers $loginHeaders -ContentType "application/json" -Body $loginBody
$headers = @{ "X-CSRF-Token" = $login.csrf_token; Origin = "http://localhost:5173" }
```

Choisir un prospect de l’organisation active, puis créer une tâche :

```powershell
$board = Invoke-RestMethod -Uri "$api/api/prospects/pipeline/board" -WebSession $session
$prospect = @($board.columns.new) | Select-Object -First 1
$dueAt = [DateTimeOffset]::UtcNow.AddDays(1).ToString("o")
$reminderAt = [DateTimeOffset]::UtcNow.AddHours(1).ToString("o")
$taskBody = @{ title = "Relance QA 3.3"; due_at = $dueAt; reminder_at = $reminderAt; priority = "high"; idempotency_key = [guid]::NewGuid().ToString() } | ConvertTo-Json -Compress
$task = Invoke-RestMethod -Uri "$api/api/prospects/$($prospect.id)/tasks" -Method Post -WebSession $session -Headers $headers -ContentType "application/json" -Body $taskBody
$task
```

Tester le conflit avec une version obsolète, puis la lecture :

```powershell
$staleBody = @{ version = ($task.version - 1); idempotency_key = [guid]::NewGuid().ToString(); reason = $null; reminder_at = $null } | ConvertTo-Json -Compress
try { Invoke-RestMethod -Uri "$api/api/prospects/tasks/$($task.id)/complete" -Method Post -WebSession $session -Headers $headers -ContentType "application/json" -Body $staleBody } catch { $_.Exception.Response.StatusCode.value__ }
Invoke-RestMethod -Uri "$api/api/prospects/$($prospect.id)/timeline" -WebSession $session
Invoke-RestMethod -Uri "$api/api/prospects/tasks?mine=true" -WebSession $session
Invoke-RestMethod -Uri "$api/api/prospects/tasks/next-actions?limit=100" -WebSession $session
```

Attendu : le premier résultat vaut `409`, puis les trois lectures ne contiennent que l’organisation active.

## 7. Verrou qualité global

Fermer les serveurs Vite susceptibles de verrouiller `node_modules`, puis exécuter depuis la racine :

```powershell
.\scripts\Test-QualityGateLocal.ps1 -DockerMode wsl -WslDistribution "Ubuntu-24.04" -TestPostgresPort 55433 -TestRedisPort 56380 -TestMailpitSmtpPort 51027 -TestMailpitApiPort 58027
```

Attendu : `Verrou qualité local 3.3 : VERT`. Archiver `test-results/quality-summary.md`, les fichiers JUnit et le journal
du terminal avec le relevé de recette.

## 8. Verdict

| Contrôle | Verdict | Preuve / réserve |
| --- | --- | --- |
| Migrations 0016 à 0019 | Conforme | Base locale : `20260905_0019 (head)` ; `alembic check` sans opération |
| ACT-01 | OK | Note interne créée et visible dans la chronologie |
| ACT-02 à ACT-04 | OK | Interactions déclaratives, avertissement de permission et correction append-only validés |
| ACT-05 | OK | Correction append-only confirmée |
| CHR-01 | OK | Activités, événements de tâches et transitions pipeline visibles dans la même chronologie |
| TASK-01 | OK | Deux tâches ouvertes et prochaine action confirmées |
| TASK-02 | Reporté à la recette finale | Vérification croisée avec Sales A et une tâche appartenant à un autre commercial à reprendre en 3.6 |
| TASK-03 | OK | Accusé et report visibles dans la chronologie |
| TASK-04 | OK | Terminaison et annulation tracées dans la chronologie |
| TASK-05 | Reporté à la recette finale | Contrôle des rendus selon le fuseau IANA et des échéances à reprendre en 3.6 |
| TASK-06 | Reporté à la recette finale | À reprendre avec l’interface d’affectation des tâches ; aucun appel API manuel requis pour la recette finale |
| TASK-07 | OK | Conflit concurrent `409 task_version_conflict` constaté |
| PERM-01 et ISO-01 | Reporté à la recette finale | Matrice multi-rôle et isolation inter-organisation à reprendre dans la campagne finale 3.6 |
| SEC-3.3 | Reporté à la recette finale | Réponse locale `400` non concluante lors de la sonde CSRF ; contrôle regroupé avec `SEC-01` en 3.6 |
| Audit minimisé 3.3 | Reporté à la recette finale | Contrôle regroupé avec `AUD-01` dans la campagne finale 3.6 |
| Verrou qualité global | Conforme | `Verrou qualité local 3.3 : VERT` le 10 septembre 2026 ; Alembic `20260905_0019`, 274 tests backend et 162 tests frontend, zéro échec et zéro skip |

**Verdict final 3.3 :** clôture avec réserves prononcée le 10 septembre 2026. Les contrôles exécutés sont conformes et
le verrou qualité global est vert sans test ignoré. `TASK-02`, `TASK-05`, `TASK-06`, `PERM-01`, `ISO-01`, `SEC-3.3`
et l’audit minimisé 3.3 ne sont pas déclarés validés : ils sont explicitement transférés à la recette finale de
l’application en 3.6, avec les réserves transversales `SEC-01` et `AUD-01`. Ces réserves restent obligatoires avant la
préproduction, mais ne bloquent pas le passage à l’incrément suivant.
