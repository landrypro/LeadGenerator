# Recette fonctionnelle QA — Phase 3.4 Opportunités

**Version :** 1.0  
**Statut :** prête à exécuter  
**Tête Alembic attendue :** `20260910_0020 (head)`

Utiliser uniquement des organisations, utilisateurs et prospects fictifs. Ne saisir aucun secret ni contenu descriptif
Google. Pour chaque scénario, consigner compte, organisation, identifiants techniques utiles, résultat et capture.

## 1. Préparation

Créer les organisations A et B ; préparer Admin A, Manager A, Sales A, Sales A2 et Admin B. Dans A, créer les prospects
`OPP Montants`, `OPP Cycle`, `OPP Concurrence` et `OPP Pipeline`. Dans B, créer `OPP Isolation`. Vérifier que les deux
organisations utilisent des devises et fuseaux connus.

## 2. Scénarios fonctionnels

### OPP-01 — Création et montant exact

Créer sur `OPP Montants` une affaire de `12500.5000 CAD`, probabilité 40 %, échéance future. Attendu : montant inchangé,
valeur pondérée `5000.2000 CAD`, une seule création dans la chronologie et aucune modification du pipeline prospect.

**Verdict : OK —** opportunité « Clinique Proximité » créée avec `12 500,5 CAD`, probabilité 40 % et valeur pondérée
affichée à `5 000,2 CAD` ; validation fonctionnelle et capture fournies le 10 septembre 2026.

### OPP-02 — Devises séparées

Créer une affaire CAD et une USD. Attendu : deux agrégats distincts sur fiche et portefeuille ; aucun total général
multidevise ni conversion implicite.

**Verdict : OK —** les valeurs pondérées sont présentées dans deux agrégats indépendants, `20 000 CAD` et
`6 250 USD`, sans total multidevise ni conversion implicite ; validation fonctionnelle et capture fournies le
10 septembre 2026.

### OPP-03 — Validations et échéance

Essayer montant nul, négatif, exponentiel, cinq décimales, devise invalide, probabilité 101 et échéance passée. Attendu :
refus sans écriture partielle. Vérifier ensuite une affaire arrivée à échéance : elle devient « En retard » sans changer
d’étape ni créer de rappel.

**Verdict : partiellement OK —** les messages accessibles pour le montant, la probabilité et l’échéance sont validés.
Le contrôle visuel de la devise invalide `ZZZ` est reporté à la recette finale : lorsqu’elle est la seule erreur, la
commande atteint l’API et le message de devise doit être présenté sous ce champ. Aucun enregistrement partiel n’a été
constaté.

### OPP-04 — Étapes ouvertes

Sur `OPP Cycle`, avancer puis reculer d’un cran. Essayer un saut. Attendu : transitions voisines acceptées, saut refusé,
versions et événements cohérents.

**Verdict : OK —** les transitions voisines dans les deux sens et leurs événements de chronologie ont été constatés.
Le saut direct `Découverte` → `Proposition` a été refusé par l’API avec le statut `422`; l’opportunité est restée à
`discovery`, en version `1`, sans écriture ni événement supplémentaire. Preuves fournies les 11 et 17 septembre 2026.

### OPP-05 — Gagnée

Depuis Proposition ou Négociation, marquer gagnée. Attendu : étape Gagnée, probabilité 100, aucun motif de perte,
lecture seule jusqu’à réouverture et aucune création automatique de client.

**Verdict : OK —** l’anomalie bloquante a été corrigée et le rejeu fonctionnel du 17 septembre 2026 est conforme.
La commande `proposal` → `won`, envoyée depuis la version `3`, retourne la version `4`, la probabilité `100`, un
`closed_at` renseigné et aucun motif de perte. L’interface affiche l’étape « Gagnée », la valeur pondérée complète
et uniquement les actions terminales « Réouvrir » et « Aligner le pipeline ». Le verrou global après correctif est
également vert : 300 tests backend et 167 tests frontend, sans skip.

### OPP-06 — Perdue et motifs

Depuis une étape ouverte, marquer perdue avec chaque motif contrôlé ; pour « Autre », omettre puis fournir la note.
Attendu : codes jamais affichés, probabilité 0, note obligatoire seulement pour « Autre », terminalité respectée.

**Verdict : OK —** les motifs sont présentés avec des libellés métier. Une opportunité clôturée affiche « Perdue » et
`0 %`, avec l'action « Réouvrir ». Le motif `other` accompagné de sa note est correctement persisté et horodaté ; une
tentative sans note a été refusée côté interface, sans requête de transition ni écriture.

### OPP-07 — Réouverture

Avec Admin A puis Manager A, rouvrir une gagnée et une perdue avec motif et probabilité ouverte. Attendu : réouverture
autorisée et historisée. Avec Sales A, l’action est absente et l’API répond 403.

**Verdict : OK avec réserve —** la réouverture autorisée remet l'affaire à une étape ouverte, à `50 %`, sans clôture ni
motif de perte ; la carte Sales ne propose pas l'action « Réouvrir ». La preuve API du refus `403
opportunity_action_forbidden` pour Sales reste à rejouer avant la recette finale.

### OPP-08 — Modification et responsable

Modifier nom, montant, devise avec montant confirmé, probabilité, échéance et responsable. Désactiver ensuite le
responsable. Attendu : lecture maintenue, mutations bloquées jusqu’à réaffectation par Admin/Manager.

**Pré-OPP-08 — OK —** l’éditeur de la fiche prospect accepte la modification des champs commerciaux. Un changement de
devise exige une confirmation explicite du montant et conserve ce montant sans conversion automatique. La réponse
finale a confirmé `10000.0000 USD`, une valeur pondérée `4900.0000`, ainsi qu’une version passée de `5` à `6` après
réaffectation vers un membre actif.

**Verdict : OK —** après désactivation du Gestionnaire responsable, l’opportunité reste visible et ne présente plus
que l’action « Réaffecter le responsable » à un rôle de gestion. La réaffectation isolée vers `CommercialdemoA` a
rétabli les actions normales. La désactivation d’une appartenance retire également son accès à l’organisation et au
menu CRM ; après réactivation et reconnexion, le compte retrouve ses capacités. Preuves par captures du 17 septembre
2026.

### OPP-09 — Concurrence

1. Avec un Administrateur ou un Gestionnaire actif, créer une nouvelle affaire ouverte `OPP-09 Concurrence` sur le
   prospect `OPP Concurrence`, puis l’ouvrir dans deux fenêtres indépendantes. Relever dans chaque réponse de lecture
   le même identifiant et la même version initiale `V`.
2. Dans la première fenêtre, modifier uniquement le nom, par exemple en `OPP-09 gagnant A`, et enregistrer. Conserver
   la réponse `PATCH` : elle doit réussir et retourner la version `V + 1`.
3. Sans recharger la seconde fenêtre, modifier un autre champ, par exemple la probabilité, et enregistrer. Conserver
   le corps de sa requête : il doit encore contenir la version `V`.
4. Attendu pour cette seconde requête : HTTP `409`, code `opportunity_version_conflict`, message « L’opportunité a
   changé depuis sa lecture. » et champ `current_version` égal à `V + 1`.
5. Recharger la seconde fenêtre. Attendu : seul le nom enregistré dans la première fenêtre est conservé ; sa seconde
   modification n’est pas persistée. La chronologie ne contient qu’un seul événement « Opportunité modifiée » pour ce
   scénario et la version reste `V + 1`.

### OPP-10 — Idempotence

Ce contrôle est API : l’interface génère volontairement une nouvelle clé à chaque action. Utiliser une session
Administrateur ou Gestionnaire active et conserver la même clé dans les trois envois.

1. Sur le prospect ouvert `OPP Concurrence`, préparer une création `OPP-10 Idempotence` avec une clé neuve `K`, par
   exemple :

   ```powershell
   $idempotencyKey = [guid]::NewGuid().ToString()
   $body = @{ name = 'OPP-10 Idempotence'; amount = '1000'; currency_code = 'CAD'; probability = 25; expected_close_on = '2026-09-25'; idempotency_key = $idempotencyKey } | ConvertTo-Json -Compress
   $uri = "$api/api/prospects/$prospectId/opportunities"
   $first = Invoke-RestMethod -Uri $uri -Method Post -WebSession $session -Headers $headers -ContentType 'application/json' -Body $body
   $replay = Invoke-RestMethod -Uri $uri -Method Post -WebSession $session -Headers $headers -ContentType 'application/json' -Body $body
   $first, $replay | Select-Object id, name, version, created_at
   ```

   `api`, `session`, `headers` et `prospectId` sont ceux déjà employés pour les contrôles précédents. L’échéance doit
   être ajustée si elle est désormais passée.
2. Attendu : les deux réponses réussissent, retournent le même `id`, la même version `1` et le même `created_at`.
   Vérifier que la liste du prospect ne contient qu’une seule affaire portant ce nom et que `GET
   /api/opportunities/{id}/events?limit=100` ne contient qu’un événement `created`.
3. Sans changer `idempotency_key`, modifier seulement `name` dans une copie de `$body`, puis envoyer la même requête :

   ```powershell
   $conflictingBody = @{ name = 'OPP-10 Idempotence différente'; amount = '1000'; currency_code = 'CAD'; probability = 25; expected_close_on = '2026-09-25'; idempotency_key = $idempotencyKey } | ConvertTo-Json -Compress
   try {
     Invoke-RestMethod -Uri $uri -Method Post -WebSession $session -Headers $headers -ContentType 'application/json' -Body $conflictingBody
   } catch {
     $status = $_.Exception.Response.StatusCode.value__
     $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
     $errorBody = $reader.ReadToEnd() | ConvertFrom-Json
     [pscustomobject]@{ status = $status; code = $errorBody.error.code; message = $errorBody.error.message }
   }
   ```

4. Attendu : HTTP `409`, code `opportunity_idempotency_conflict`, message « La clé de requête a déjà été utilisée. ».
   L’affaire initiale reste inchangée, aucun doublon ni événement supplémentaire n’est créé.
5. Conserver les trois réponses et une lecture finale de l’affaire comme preuve. Ne réutiliser ensuite jamais la clé
   `K` : chaque nouvelle intention doit obtenir une nouvelle clé.

**Verdict : OK —** le 18 septembre 2026, les deux créations strictement identiques ont retourné l’affaire
`cd6a0c34-a237-4ac2-beeb-faea595d046a`, nommée `OPP-10 Idempotence`, en version `1`. La commande divergente portant
la même clé a été refusée en `409`. La lecture finale confirme une seule affaire et un seul événement `created`
(`from_version: 1`, `resulting_version: 1`).

### OPP-11 — Portefeuille et pagination

Créer plus de 25 affaires, filtrer par texte, étape, devise et retard, puis « Charger plus ». Attendu : tri stable,
aucun doublon, agrégats cohérents et filtres conservés.

**Verdict : OK avec réserve —** le lot `OPP-11-20260918-104723` a créé 26 affaires ouvertes, alternant `1 000 CAD`
à 25 % et `2 000 USD` à 50 %. La première page a affiché 25 cartes avec « Charger plus » ; la seconde a ajouté la
26e sans doublon et a retiré le bouton. Les filtres texte, étape `discovery`, devise `CAD`/`USD` et « En retard » ont
été vérifiés. Le filtre de retard retourne légitimement un état vide pour ce lot, dont l’échéance est le 25 septembre
2026.

**Réserve OPP-11-A — anomalie mineure à corriger :** pendant la saisie d’une devise, l’interface émet des requêtes
avec les valeurs incomplètes `U`, `US`, `C` ou `CA`. L’API les refuse en `415`, puis la requête complète `USD` ou
`CAD` réussit en `200` et le filtre final fonctionne. Ne déclencher la requête qu’avec une devise vide ou de trois
caractères, idéalement après soumission explicite du formulaire. Cette anomalie ne crée aucune écriture et ne fausse
pas le résultat filtré final.

### OPP-12 — Chronologie et synthèses

Ce contrôle vérifie le lien entre les mutations d’une affaire, l’historique du prospect et les trois vues qui
consomment les synthèses. Utiliser un prospect ouvert et une session Administrateur ou Gestionnaire active. Conserver
les réponses de création, modification, transition, historique, chronologie et synthèse comme preuves.

1. Créer une affaire dédiée `OPP-12 Chronologie` sur le prospect choisi, avec `3 000 CAD`, probabilité `25` et une
   échéance future. Relever son identifiant et sa version initiale `1`.
2. Modifier l’affaire en une seule commande, par exemple le nom et le montant (`3 500 CAD`), avec la version `1` et
   une nouvelle clé d’idempotence. Attendu : la réponse retourne la version `2` et la valeur pondérée correspondante
   (`875 CAD`).
3. Déplacer l’affaire de `discovery` vers `qualification` avec la version `2` et une nouvelle clé d’idempotence.
   Une transition ouverte ne porte pas de motif ni de note selon le contrat métier. Attendu : la réponse retourne la
   version `3`, l’étape `qualification` et la probabilité inchangée à `25`.
4. Relire `GET /api/opportunities/{id}/events?limit=100`. Attendu : trois événements dans l’ordre inverse
   chronologique — `stage_changed`, `updated`, `created` — avec les versions `2 → 3`, `1 → 2` et `1 → 1`.
   `changed_fields` peut indiquer les noms de champs modifiés, mais aucun montant, note ou autre valeur métier ne doit
   être recopié dans le résumé d’un événement.
5. Relire `GET /api/prospects/{prospectId}/timeline`. Attendu : les trois événements d’opportunité apparaissent dans
   la chronologie du prospect, avec les libellés métier « Opportunité créée », « Opportunité modifiée » et « Étape de
   l’opportunité modifiée ». L’interface affiche l’étape source et cible pour le déplacement, sans exposer la note de
   motif ni le montant dans cet élément résumé. Les valeurs détaillées restent consultables uniquement dans la fiche
   de l’affaire, pas dans l’événement de chronologie.
6. Vérifier la synthèse de la fiche avec `GET
   /api/prospects/opportunity-summaries?prospect_id={prospectId}`. Attendu : une affaire ouverte, l’agrégat CAD à
   `3 500` et une valeur pondérée à `875`, sans mélange avec une autre devise.
7. Ouvrir successivement la fiche du prospect, `/app/opportunities` et `/app/pipeline`. Attendu : la fiche affiche
   l’affaire et ses agrégats ; la liste portefeuille affiche la carte `OPP-12 Chronologie` ; le prospect correspondant
   dans le Kanban affiche le nombre d’affaires ouvertes et la valeur pondérée CAD. Les trois vues doivent rester
   cohérentes après actualisation.

Exemple de commandes PowerShell (adapter `$api`, `$session`, `$headers`, `$prospectId` et `$closeDate`) :

```powershell
$createBody = @{ name = 'OPP-12 Chronologie'; amount = '3000'; currency_code = 'CAD'; probability = 25; expected_close_on = $closeDate; idempotency_key = [guid]::NewGuid().ToString() } | ConvertTo-Json -Compress
$created = Invoke-RestMethod -Uri "$api/api/prospects/$prospectId/opportunities" -Method Post -WebSession $session -Headers $headers -ContentType 'application/json' -Body $createBody

$updateBody = @{ version = $created.version; name = 'OPP-12 Chronologie'; amount = '3500'; probability = 25; idempotency_key = [guid]::NewGuid().ToString() } | ConvertTo-Json -Compress
$updated = Invoke-RestMethod -Uri "$api/api/opportunities/$($created.id)" -Method Patch -WebSession $session -Headers $headers -ContentType 'application/json' -Body $updateBody

$transitionBody = @{ version = $updated.version; to_stage = 'qualification'; idempotency_key = [guid]::NewGuid().ToString() } | ConvertTo-Json -Compress
$moved = Invoke-RestMethod -Uri "$api/api/opportunities/$($created.id)/stage-transitions" -Method Post -WebSession $session -Headers $headers -ContentType 'application/json' -Body $transitionBody

$events = Invoke-RestMethod -Uri "$api/api/opportunities/$($created.id)/events?limit=100" -WebSession $session -Headers $headers
$timeline = Invoke-RestMethod -Uri "$api/api/prospects/$prospectId/timeline?limit=100" -WebSession $session -Headers $headers
$summary = Invoke-RestMethod -Uri "$api/api/prospects/opportunity-summaries?prospect_id=$prospectId" -WebSession $session -Headers $headers
$moved | Select-Object id, name, amount, currency_code, weighted_amount, stage_code, version
$events.items | Select-Object event_type, from_version, resulting_version, changed_fields, reason_note
$timeline.opportunity_events | Select-Object event_type, from_stage, to_stage, resulting_version, changed_fields
$summary.items | Select-Object prospect_id, open_count, aggregates_by_currency
```

**Verdict : OK —** le 19 septembre 2026, l’affaire `OPP-12 Chronologie2` (`2b1f408d-060d-4c9d-8a5c-6013ed8ee37b`)
a été créée sur le prospect `99237ec5-5599-4bef-bf0b-c45c7cd74269` en version `1` (`3 000 CAD`, pondéré `750 CAD`),
puis modifiée en version `2` (`3 500 CAD`, pondéré `875 CAD`) et déplacée en `qualification` en version `3`.
Les réponses API de la fiche, de la chronologie et des opportunités sont revenues en `200`. La carte portefeuille
affiche `3 500 CAD` et `875 CAD` pondérés. Le prospect reste dans la colonne Kanban `Nouveau`, ce qui est conforme :
le déplacement d’une opportunité ne déplace pas automatiquement son prospect. L’alignement explicite sera couvert par
OPP-13.

### OPP-13 — Alignement pipeline

Ce contrôle vérifie que l’alignement du prospect est une action explicite, indépendante de la transition d’opportunité,
et qu’il respecte le graphe du pipeline prospect. Préparer une session Administrateur ou Gestionnaire active.

#### OPP-13-A — Garde-fou sur un saut interdit

1. Utiliser l’affaire `OPP-12 Chronologie2` validée précédemment, dont l’étape est `qualification`, avec le prospect
   encore en `Nouveau`. L’opportunité suggère donc l’étape prospect `Qualifié`, soit un saut de deux crans (`Nouveau`
   → `Qualification` → `Qualifié`).
2. Sur la fiche du prospect, cliquer « Aligner le pipeline ». Attendu : le panneau explique que les deux parcours
   restent indépendants et affiche « Cette transition n’est pas permise directement. Déplacez le prospect étape par
   étape dans le Kanban. » avec le bouton « Fermer » uniquement.
3. Fermer le panneau. Attendu : aucune requête `POST /api/prospects/{id}/stage-transitions`, aucune modification de
   version et aucun événement de pipeline supplémentaire.

#### OPP-13-B — Alignement autorisé d’un cran

1. Sur un prospect de test en `Nouveau`, le déplacer une seule fois dans le Kanban vers `Qualification`. Conserver la
   réponse de transition et sa nouvelle version `P`.
2. Créer sur ce prospect une affaire `OPP-13 Alignement` à l’étape initiale `discovery`. L’opportunité suggère alors
   `Nouveau`, qui est adjacent à `Qualification` dans le graphe prospect.
3. Depuis la fiche, cliquer « Aligner le pipeline », puis confirmer. Attendu : une seule requête
   `POST /api/prospects/{prospectId}/stage-transitions` réussit en `200`, avec `to_stage: new`, `from_version: P` et
   `resulting_version: P + 1`. L’interface affiche « Le pipeline du prospect a été aligné. ».
4. Relire le prospect et ses transitions. Attendu : son étape est `new`, sa version est `P + 1` et une seule
   transition `qualifying → new` est ajoutée. Relire l’opportunité : elle reste en `discovery`, sa version et son
   historique d’opportunité sont inchangés.
5. Actualiser la fiche et le Kanban. Attendu : le prospect apparaît dans `Nouveau`, le bouton d’alignement disparaît
   lorsque les étapes correspondent, et aucune transition automatique supplémentaire n’est créée.

Les correspondances utilisées par l’interface sont : `discovery → new`, `qualification → qualified`,
`proposal → proposal_sent` et `negotiation → negotiation`. Un alignement ne peut donc jamais contourner les étapes
intermédiaires du Kanban.

Exemple API pour le parcours autorisé (adapter `$api`, `$session`, `$headers`, `$prospectId` et `$closeDate`) :

```powershell
$prospect = Invoke-RestMethod -Uri "$api/api/prospects/$prospectId" -WebSession $session -Headers $headers
$toQualifying = @{ version = $prospect.version; to_stage = 'qualifying'; idempotency_key = [guid]::NewGuid().ToString() } | ConvertTo-Json -Compress
$transition = Invoke-RestMethod -Uri "$api/api/prospects/$prospectId/stage-transitions" -Method Post -WebSession $session -Headers $headers -ContentType 'application/json' -Body $toQualifying
$prospectAfterMove = Invoke-RestMethod -Uri "$api/api/prospects/$prospectId" -WebSession $session -Headers $headers

$opportunityBody = @{ name = 'OPP-13 Alignement'; amount = '2000'; currency_code = 'CAD'; probability = 25; expected_close_on = $closeDate; idempotency_key = [guid]::NewGuid().ToString() } | ConvertTo-Json -Compress
$opportunity = Invoke-RestMethod -Uri "$api/api/prospects/$prospectId/opportunities" -Method Post -WebSession $session -Headers $headers -ContentType 'application/json' -Body $opportunityBody

$alignBody = @{ version = $prospectAfterMove.version; to_stage = 'new'; idempotency_key = [guid]::NewGuid().ToString() } | ConvertTo-Json -Compress
$aligned = Invoke-RestMethod -Uri "$api/api/prospects/$prospectId/stage-transitions" -Method Post -WebSession $session -Headers $headers -ContentType 'application/json' -Body $alignBody
$prospectFinal = Invoke-RestMethod -Uri "$api/api/prospects/$prospectId" -WebSession $session -Headers $headers
$opportunityFinal = Invoke-RestMethod -Uri "$api/api/opportunities/$($opportunity.id)" -WebSession $session -Headers $headers
$aligned, $prospectFinal, $opportunityFinal | Select-Object id, prospect_id, from_stage, to_stage, from_version, resulting_version, stage_code, version
```

**Verdict : OK —** le 19 septembre 2026, le garde-fou OPP-13-A a refusé le saut direct `Nouveau → Qualifié` et a
conservé les deux parcours indépendants. Le parcours OPP-13-B a ensuite aligné explicitement le prospect d’un seul
cran : la transition API `qualifying → qualified` a réussi en `200`, avec une version prospect passée de `2` à `3`.
L’opportunité `OPP-13 Alignement` est restée séparée, en `qualification`, sans mutation supplémentaire. Le Kanban
confirme que le prospect est désormais dans `Qualifié` et que l’alignement est terminé.

### OPP-14 — Rôles

Ce contrôle nécessite trois sessions dans la même organisation : un Administrateur ou Gestionnaire, `Sales A`
propriétaire d’une affaire ouverte et `Sales A2` qui n’en est pas le propriétaire. Ne pas utiliser une affaire
terminale afin de séparer ce contrôle de la réserve OPP-07.

1. Avec la session Administrateur ou Gestionnaire, relever dans `GET /api/organization/members?limit=100` les
   identifiants de deux membres Sales actifs, puis dans `GET /api/opportunities?limit=100` deux affaires ouvertes dont
   les responsables sont distincts. Conserver les champs `id`, `owner_membership_id`, `version` et `stage_code`.
2. Vérifier la visibilité Admin/Manager : le portefeuille et la fiche prospect affichent les affaires des deux
   responsables ; la réponse de liste ne force pas de filtre sur `owner_membership_id`. La réaffectation d’une affaire
   vers un autre membre actif est disponible pour ces rôles.
3. Avec la session `Sales A`, ouvrir `/app/opportunities`. Attendu : le menu reste accessible, mais seules les affaires
   dont `owner_membership_id` est celui de `Sales A` sont listées. Sur sa propre affaire, les actions normales de
   modification, transition et clôture restent disponibles ; l’action de réaffectation n’est pas proposée.
4. Avec la session `Sales A2`, ouvrir le même portefeuille. Attendu : l’affaire de `Sales A` n’est pas affichée et la
   fiche du prospect ne présente aucune opportunité appartenant à `Sales A`. Une lecture directe par identifiant doit
   être refusée par l’API en `403` avec le code `opportunity_action_forbidden`.
5. Toujours avec `Sales A2`, tenter directement une modification de l’affaire de `Sales A` (par exemple probabilité
   inchangée ou nouveau nom) et une transition d’étape. Attendu pour chaque requête : `403`, code
   `opportunity_action_forbidden`, sans changement de version, sans changement de valeur et sans nouvel événement.
6. Avec `Sales A`, tenter de fournir `owner_membership_id` égal à celui de `Sales A2` dans un `PATCH` de sa propre
   affaire. Attendu : `403` `opportunity_action_forbidden`, car seul un Administrateur ou un Gestionnaire peut
   réaffecter. Vérifier que le responsable, la version et l’historique restent inchangés.
7. Comparer les lectures avant/après chaque refus. Les filtres de portefeuille, les synthèses et les événements ne
   doivent jamais révéler ni modifier les affaires d’un autre Sales. Les actions masquées dans l’interface doivent donc
   être également bloquées côté API.

Exemple de préparation et de contrôle API (à exécuter avec la session Admin/Manager, puis rejouer les mutations avec
les sessions Sales concernées ; adapter `$api`, `$session`, `$headers`) :

```powershell
$members = Invoke-RestMethod -Uri "$api/api/organization/members?limit=100" -WebSession $session -Headers $headers
$members.items | Where-Object { $_.role -eq 'sales' -and $_.status -eq 'active' } | Select-Object membership_id, role, status, user

$portfolio = Invoke-RestMethod -Uri "$api/api/opportunities?limit=100" -WebSession $session -Headers $headers
$portfolio.items | Select-Object id, name, owner_membership_id, stage_code, version

# Avec Sales A2, lecture directe de l’affaire appartenant à Sales A :
try {
  Invoke-RestMethod -Uri "$api/api/opportunities/$($oppA.id)" -WebSession $sessionSalesA2 -Headers $headersSalesA2
} catch {
  $response = $_.Exception.Response
  $reader = [System.IO.StreamReader]::new($response.GetResponseStream())
  [pscustomobject]@{ status = $response.StatusCode.value__; body = $reader.ReadToEnd() }
}

# Avec Sales A2, tentative de mutation interdite :
$forbiddenBody = @{ version = $oppA.version; probability = $oppA.probability; idempotency_key = [guid]::NewGuid().ToString() } | ConvertTo-Json -Compress
try {
  Invoke-RestMethod -Uri "$api/api/opportunities/$($oppA.id)" -Method Patch -WebSession $sessionSalesA2 -Headers $headersSalesA2 -ContentType 'application/json' -Body $forbiddenBody
} catch {
  $response = $_.Exception.Response
  $reader = [System.IO.StreamReader]::new($response.GetResponseStream())
  [pscustomobject]@{ status = $response.StatusCode.value__; body = $reader.ReadToEnd() }
}
```

Pour les contrôles négatifs, relever la version et la liste des événements avant la requête, puis les relire après. Le
résultat attendu est strictement identique.

**Verdict : OK avec réserve —** le 20 septembre 2026, le Responsable a vu les deux affaires de test et un total
pondéré de `1 500 CAD`, tandis que la session Sales n’a vu que `Test OPP-14` et son total pondéré de `500 CAD`.
La lecture directe de `Test OPP-15` depuis la session Sales a retourné `403` avec le code
`opportunity_action_forbidden`. **Réserve OPP-14-A :** la mutation interdite (`PATCH` ou transition) et la relecture
de preuve d’absence d’écriture n’ont pas été rejouées, le navigateur de recette ne proposant pas « Edit and resend ».
Ce contrôle API devra être repris avant la recette finale.

### OPP-15 — Isolation

Ce contrôle porte sur deux organisations distinctes, et non sur deux Sales de la même organisation. Préparer une
session Administrateur ou Gestionnaire pour l’organisation `A` et une autre pour l’organisation `B`. Créer ou relever
une affaire ouverte dans chaque organisation, puis conserver leurs identifiants, versions et nombre d’événements.

1. Dans `A`, relever `oppAId`, son prospect parent, sa version et ses événements. Dans `B`, relever de même `oppBId`.
   Les deux affaires doivent être ouvertes afin de distinguer tout refus d’isolation d’une règle de terminalité.
2. Avec la session `A`, vérifier le portefeuille et la fiche : aucune affaire de `B` n’est présente. Tenter ensuite
   `GET /api/opportunities/{oppBId}`. Attendu : `404`, code `opportunity_not_found` ; l’identifiant de `B` ne doit pas
   être révélé comme une ressource existante.
3. Toujours avec `A`, tenter un `PATCH` puis une transition sur `oppBId`, avec une version et une nouvelle clé
   d’idempotence. Attendu pour chaque requête : `404 opportunity_not_found`, aucune écriture et aucun événement dans
   l’organisation `B`. Le même résultat est attendu sur `GET /api/opportunities/{oppBId}/events`.
4. Relire `oppBId` et ses événements depuis la session `B`. Attendu : version, valeurs commerciales et nombre
   d’événements strictement identiques aux valeurs relevées avant les tentatives de `A`.
5. Rejouer symétriquement les étapes 2 à 4 depuis `B` contre `oppAId`, puis vérifier depuis `A`. Les deux sens sont
   requis : `A → B` et `B → A`.
6. Conserver les réponses de refus et les deux relectures propriétaires. Un refus `403` signalerait un problème de
   non-révélation : l’attendu inter-organisation est bien `404`.

Exemple PowerShell pour `A → B` (adapter `$api`, les deux sessions, les en-têtes et les identifiants) :

```powershell
# Avant les tentatives, lecture propriétaire depuis B.
$beforeB = Invoke-RestMethod -Uri "$api/api/opportunities/$oppBId" -WebSession $sessionB -Headers $headersB
$beforeEventsB = Invoke-RestMethod -Uri "$api/api/opportunities/$oppBId/events?limit=100" -WebSession $sessionB -Headers $headersB

# Lecture croisée depuis A : 404 opportunity_not_found attendu.
try {
  Invoke-RestMethod -Uri "$api/api/opportunities/$oppBId" -WebSession $sessionA -Headers $headersA
} catch {
  $response = $_.Exception.Response
  $reader = [System.IO.StreamReader]::new($response.GetResponseStream())
  [pscustomobject]@{ operation = 'read'; status = $response.StatusCode.value__; body = $reader.ReadToEnd() }
}

# Mutation croisée depuis A : 404 opportunity_not_found attendu.
$forbiddenBody = @{ version = $beforeB.version; name = 'Tentative inter-organisation'; idempotency_key = [guid]::NewGuid().ToString() } | ConvertTo-Json -Compress
try {
  Invoke-RestMethod -Uri "$api/api/opportunities/$oppBId" -Method Patch -WebSession $sessionA -Headers $headersA -ContentType 'application/json' -Body $forbiddenBody
} catch {
  $response = $_.Exception.Response
  $reader = [System.IO.StreamReader]::new($response.GetResponseStream())
  [pscustomobject]@{ operation = 'patch'; status = $response.StatusCode.value__; body = $reader.ReadToEnd() }
}

# Après les refus, relecture propriétaire depuis B : aucun changement attendu.
$afterB = Invoke-RestMethod -Uri "$api/api/opportunities/$oppBId" -WebSession $sessionB -Headers $headersB
$afterEventsB = Invoke-RestMethod -Uri "$api/api/opportunities/$oppBId/events?limit=100" -WebSession $sessionB -Headers $headersB
[pscustomobject]@{ version_before = $beforeB.version; version_after = $afterB.version; events_before = @($beforeEventsB.items).Count; events_after = @($afterEventsB.items).Count }
```

Répéter le même bloc en inversant `A` et `B`, puis conserver les quatre refus `404` et les deux comparaisons
propriétaires comme preuves.

**Verdict : OK —** le 21 septembre 2026, l’isolation a été vérifiée dans les deux sens entre deux organisations.
`OPP-15-A` (`7b01f628-0fdd-44b1-88bb-c6388f958166`) et `OPP-15-B`
(`a2eee394-3541-4094-9491-6c846d972143`) sont restées en `discovery`, version `1`, avec leur unique événement
`created` (`1` → `1`). Les lectures croisées, les `PATCH`, les transitions et les lectures d’événements ont tous été
refusés en `404`; le code stable `opportunity_not_found` a été observé. Aucune valeur, version ou liste d’événements
n’a changé après les tentatives croisées.

### OPP-16 — Sécurité et navigateur

Utiliser une session Administrateur ou Gestionnaire, une opportunité ouverte dont cette session peut modifier les
données et DevTools ouvert sur l’origine réellement utilisée, par exemple `http://localhost:5173`. Ne jamais afficher
ni conserver la valeur du cookie de session ou du jeton CSRF dans une capture.

La session A d’OPP-15 peut être réutilisée avec les identifiants suivants :

```powershell
$opportunityId = '7b01f628-0fdd-44b1-88bb-c6388f958166'
$prospectId = '98c9094f-2937-4ecc-aebb-f2d8e2aa4e11'
```

#### OPP-16-A — Réponses non stockables

1. Ouvrir le portefeuille, puis la fiche prospect d’une opportunité existante et sa chronologie.
2. Dans DevTools > Network, filtrer sur Fetch/XHR, recharger les vues et examiner les **Response Headers** des routes
   suivantes :
   - `GET /api/opportunities?limit=25` ;
   - `GET /api/prospects/{prospectId}/opportunities?limit=25` ;
   - `GET /api/opportunities/{opportunityId}` si le détail est appelé ;
   - `GET /api/opportunities/{opportunityId}/events?limit=100` ;
   - `GET /api/prospects/{prospectId}/timeline?limit=100` ;
   - `GET /api/prospects/opportunity-summaries?prospect_id={prospectId}`.
3. Attendu pour chaque réponse observée : `Cache-Control: no-store, max-age=0`. Recharger une seconde fois : les
   données doivent être redemandées au serveur et aucune réponse Opportunités ne doit provenir d’un cache applicatif.

Contrôle PowerShell facultatif pour produire une preuve compacte, avec une session déjà authentifiée :

```powershell
$urls = @(
  "$api/api/opportunities?limit=25",
  "$api/api/prospects/$prospectId/opportunities?limit=25",
  "$api/api/opportunities/$opportunityId",
  "$api/api/opportunities/$opportunityId/events?limit=100",
  "$api/api/prospects/$prospectId/timeline?limit=100",
  "$api/api/prospects/opportunity-summaries?prospect_id=$prospectId"
)

$noStoreChecks = foreach ($url in $urls) {
  $response = Invoke-WebRequest -UseBasicParsing -Uri $url -WebSession $session -Headers $headers
  [pscustomobject]@{
    route = ([uri]$url).PathAndQuery
    status = [int]$response.StatusCode
    cache_control = $response.Headers['Cache-Control']
  }
}
$noStoreChecks
```

#### OPP-16-B — Mutation sans CSRF

1. Depuis la session propriétaire, relever l’opportunité ouverte et ses événements avant le contrôle.
2. Créer une nouvelle `WebRequestSession`, s’y authentifier, mais ne jamais recopier le `csrf_token` retourné dans ses
   en-têtes. Ne pas réutiliser une session dont `Headers.Keys` contient déjà `X-CSRF-Token`, car elle fausserait le
   contrôle. Construire des en-têtes contenant une origine approuvée mais **aucun** `X-CSRF-Token`, puis tenter un
   `PATCH` JSON valide avec la version courante et une nouvelle clé d’idempotence.
3. Attendu : `400`, code `csrf_failed`. Relire avec les en-têtes normaux : nom, étape, version et nombre d’événements
   sont strictement inchangés.

Exemple avec `OPP-15-A`, encore ouverte en version `1` à la fin d’OPP-15 :

```powershell
$opportunityId = '7b01f628-0fdd-44b1-88bb-c6388f958166'
$prospectId = '98c9094f-2937-4ecc-aebb-f2d8e2aa4e11'
$before = Invoke-RestMethod -Uri "$api/api/opportunities/$opportunityId" -WebSession $session -Headers $headers
$beforeEvents = Invoke-RestMethod -Uri "$api/api/opportunities/$opportunityId/events?limit=100" -WebSession $session -Headers $headers

$csrfTestSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$csrfLoginHeaders = @{ Origin = 'http://localhost:5173'; Accept = 'application/json' }
$csrfLoginBody = @{ email = $email; password = $plainPassword } | ConvertTo-Json -Compress
$null = Invoke-RestMethod -Uri "$api/api/auth/login" -Method Post -WebSession $csrfTestSession `
  -Headers $csrfLoginHeaders -ContentType 'application/json' -Body $csrfLoginBody
if ($csrfTestSession.Headers.Keys -contains 'X-CSRF-Token') {
  throw 'La session de test contient déjà un jeton CSRF.'
}

$headersWithoutCsrf = @{ Origin = 'http://localhost:5173'; Accept = 'application/json' }
$body = @{
  version = $before.version
  name = 'OPP-16 CSRF ne doit pas passer'
  idempotency_key = [guid]::NewGuid().ToString()
} | ConvertTo-Json -Compress

try {
  Invoke-RestMethod -Uri "$api/api/opportunities/$opportunityId" -Method Patch -WebSession $csrfTestSession `
    -Headers $headersWithoutCsrf -ContentType 'application/json' -Body $body -ErrorAction Stop
  throw 'ÉCHEC OPP-16 : la mutation sans CSRF a réussi.'
} catch {
  if ($_.Exception.Message -like 'ÉCHEC OPP-16*') { throw }
  $raw = $_.ErrorDetails.Message
  $errorBody = if ($raw) { $raw | ConvertFrom-Json } else { $null }
  [pscustomobject]@{
    status = [int]$_.Exception.Response.StatusCode
    code = $errorBody.error.code
    message = $errorBody.error.message
  }
}

$after = Invoke-RestMethod -Uri "$api/api/opportunities/$opportunityId" -WebSession $session -Headers $headers
$afterEvents = Invoke-RestMethod -Uri "$api/api/opportunities/$opportunityId/events?limit=100" -WebSession $session -Headers $headers
[pscustomobject]@{
  version_before = $before.version
  version_after = $after.version
  name_unchanged = ($before.name -eq $after.name)
  stage_unchanged = ($before.stage_code -eq $after.stage_code)
  events_before = @($beforeEvents.items).Count
  events_after = @($afterEvents.items).Count
}
```

#### OPP-16-C — Stockages du navigateur

1. Après avoir visité le portefeuille, la fiche prospect, la chronologie et chargé plusieurs pages ou filtres, ouvrir
   DevTools > Application pour l’origine de recette.
2. Inspecter `Local Storage`, `Session Storage`, IndexedDB, Cache Storage et Service Workers sans cliquer sur
   « Clear site data », qui fermerait la session.
3. Rechercher notamment les noms `OPP-15-A` et `OPP-15-B`, leurs identifiants, le montant, la devise, les filtres et les
   curseurs chargés. Attendu : aucune donnée Opportunités 3.4 dans ces stockages, aucun cache de réponse API et aucun
   service worker conservant ces données. Les données visibles doivent rester uniquement en mémoire et disparaître
   après fermeture ou rechargement de la page.

**Verdict : OK —** le 21 septembre 2026, les six lectures du portefeuille, de la fiche, du détail, des événements, de
la chronologie et des synthèses ont répondu `200` avec `Cache-Control: no-store, max-age=0`. Une session PowerShell
dédiée, authentifiée sans recopier son jeton CSRF, a vu son `PATCH` refusé en `400 csrf_failed`; l’affaire est restée
en version `2`, avec le même nom, la même étape et deux événements. Le premier essai, réalisé avec une session qui
conservait encore le jeton, avait légitimement produit une mise à jour ; le nom `OPP-15-A` a ensuite été restauré par
une commande autorisée, portant la version à `3`. Enfin, le navigateur ne contenait aucune donnée Opportunités dans
Session Storage, IndexedDB ou Cache Storage, et aucun service worker ne la conservait. Local Storage contenait
uniquement le marqueur technique `ecodis-offline-v2-migrated=true`.

### OPP-17 — Français, anglais et clavier

Ce scénario doit être exécuté avec un Administrateur ou Gestionnaire disposant de `organization:update`, sur un
prospect actif dédié. Relever avant le test la locale initiale de l’organisation et la restaurer à la fin. Utiliser la
souris uniquement pour prendre les captures ou lancer l’outil axe ; toutes les interactions métier se font avec
`Tab`, `Maj+Tab`, `Entrée`, `Espace`, les flèches et `Échap`.

#### OPP-17-A — Parcours `fr-CA`

1. Ouvrir `/app/admin/organization`, sélectionner « Français (Canada) », enregistrer, puis actualiser la session si
   nécessaire. Attendu : l’organisation active expose `locale: fr-CA`.
2. Au clavier, ouvrir la fiche du prospect et créer `OPP-17 FR` avec un montant décimal utilisant la virgule, par
   exemple `1250,50 CAD`, une probabilité de `50` et une échéance future. Attendu : création réussie et affichage
   `1 250,5 CAD`; si la virgule est refusée, relever une anomalie de normalisation `fr-CA`.
3. Parcourir la carte avec `Tab` et déplacer l’affaire vers `qualification` avec le sélecteur et les flèches. Attendu :
   libellés français (`Découverte`, `Qualification`, `Proposition`, `Négociation`, `Gagnée`, `Perdue`) et aucun code
   backend tel que `discovery`, `lost` ou `no_budget` visible.
4. Atteindre « Perdue » au clavier, choisir un motif compréhensible, confirmer, puis rouvrir avec un motif de
   réouverture. Attendu : focus visible à chaque étape, formulaire nommé, `Échap` ou « Annuler » sans écriture, focus
   restauré au déclencheur après fermeture et confirmation annoncée.
5. Sur `/app/opportunities`, parcourir puis soumettre au clavier les filtres texte, étape, devise et retard. Attendu :
   ordre logique, résultats cohérents, focus conservé lors de « Charger plus » et messages français sans code interne.

#### OPP-17-B — Parcours `en-CA`

1. Dans `/app/admin/organization`, sélectionner « English (Canada) », enregistrer et recharger les vues CRM. Attendu :
   `locale: en-CA` et aucun mélange français/anglais après chargement.
2. Rejouer au clavier la création avec `OPP-17 EN`, montant `1250.50 CAD`, puis transition, perte, réouverture et
   filtres. Attendu : montant `1,250.5 CAD`, date au format anglais canadien, étapes `Discovery`, `Qualification`,
   `Proposal`, `Negotiation`, `Won`, `Lost`, motifs, boutons, aides, erreurs et états vides en anglais.
3. Un écran où seuls les montants, dates ou étapes sont anglais mais où subsistent « Opportunités », « Modifier »,
   « Perdue », « Réouvrir », « Motif » ou « Filtrer » est **non conforme** : tous les nouveaux textes 3.4 doivent être
   traduits selon la locale de l’organisation.

#### OPP-17-C — Accessibilité et preuves

1. Sur la fiche, le formulaire de création, les formulaires de perte/réouverture, le portefeuille et l’état vide,
   vérifier à 200 % de zoom : aucune action perdue, ordre visuel et ordre de tabulation identiques, focus toujours
   visible, libellé relié à chaque champ et absence de dépendance exclusive à la couleur.
2. Exécuter axe sur ces vues dans les deux locales. Attendu : zéro violation. Conserver le rapport ou les captures ;
   le contrôle automatisé ciblé peut également être rejoué avec :

   ```powershell
   npm --prefix client test -- src/features/opportunities/components/OpportunitySection.test.jsx
   ```

3. Restaurer la locale initiale de l’organisation et vérifier une dernière fois la fiche et le portefeuille. Conserver
   les captures `fr-CA`, `en-CA`, les deux affaires de test, le résultat axe et toute anomalie de langue ou de focus.

## 3. Régression 3.1 à 3.3

| ID | Contrôle minimal | Verdict |
| --- | --- | --- |
| REG-31 | Import CSV : aperçu, mapping, confirmation et isolation | À exécuter |
| REG-32 | Kanban : neuf étapes, transition, perte/réouverture, charger plus | À exécuter |
| REG-33 | Chronologie : note, activité, tâche, prochaine action et rappel | À exécuter |

## 4. Verdict

| Élément | Résultat |
| --- | --- |
| Migration reconstruite | Conforme — `20260910_0020 (head)`, aucune dérive Alembic |
| OPP-01 | OK — création, montant exact et valeur pondérée validés par capture |
| OPP-02 | OK — agrégats CAD et USD séparés, sans total multidevise |
| OPP-03 | Partiellement OK — devise invalide à confirmer isolément en recette finale |
| OPP-04 | OK — transitions voisines, chronologie, version et refus d’un saut validés |
| OPP-05 | OK — transition Gagnée, probabilité 100, clôture, terminalité et version validées |
| OPP-06 | OK — perte avec motifs, note obligatoire pour « Autre » et terminalité validées |
| OPP-07 | OK avec réserve — action absente pour Sales ; refus API `403` à rejouer avant recette finale |
| Pré-OPP-08 | OK — éditeur, confirmation montant/devise et réaffectation validés |
| OPP-08 | OK — responsable désactivé, accès retiré, réaffectation isolée et retour contrôlé validés |
| OPP-09 | OK — conflit de version affiché ; seconde écriture refusée avant relecture |
| OPP-10 | OK — rejeu identique sans doublon, conflit `409` pour commande divergente et unique événement `created` |
| OPP-11 | OK avec réserve — pagination et filtres validés ; requêtes `415` durant la saisie partielle d’une devise à corriger |
| OPP-12 | OK — chronologie, versions, valeur pondérée, portefeuille et indépendance du prospect dans le Kanban validés |
| OPP-13 | OK — garde-fou contre les sauts interdits et alignement explicite d’un cran validés |
| OPP-14 | OK avec réserve — visibilité et lecture API non autorisée validées ; mutation interdite à rejouer avant recette finale |
| OPP-15 | OK — isolation bidirectionnelle des lectures, mutations et événements, sans écriture croisée |
| OPP-16 | OK — `no-store`, refus CSRF sans écriture et absence de stockage navigateur validés |
| OPP-17 | À exécuter |
| REG-31 à REG-33 | À renseigner |
| Verrou global sans skip | Conforme — `Verrou qualité local 3.4 : VERT` le 17 septembre 2026 |
| Réserves transférées | À renseigner |
| GO de clôture produit | À renseigner |
