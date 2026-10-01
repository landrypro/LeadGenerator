gestionnairerecette33@marketteo.com
Gestionnaire

salesrecette33@marketteo.com
Commercial

sales2recette33@marketteo.com
Commercial

Sales Manager33

Sales 2 Recette33
---------------------------------------------------------



6. Vérifications API guidées

Après connexion, conserver la session et le jeton CSRF :

```powershell
$api = "http://127.0.0.1:8000"
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$password = Read-Host "Mot de passe" -AsSecureString
$plainPassword = [System.Net.NetworkCredential]::new("", $password).Password

$loginBody = @{
  email = "votre-adresse-admin@example.ca"
  password = $plainPassword
} | ConvertTo-Json -Compress

$login = Invoke-RestMethod -Uri "$api/api/auth/login" -Method Post -WebSession $session -Headers $loginHeaders -ContentType "application/json" -Body $loginBody

$headers = @{
  "X-CSRF-Token" = $login.csrf_token
  Origin = "http://localhost:5173"
}
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