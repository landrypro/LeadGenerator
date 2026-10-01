# Phase 4.3 — Exports internes et administration des imports

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Lot | 4.3 — Exports internes et administration des imports |
| Version | 1.2 — GO d’implémentation consigné |
| Statut | Décisions `P4.3-01` à `P4.3-08` validées ; mesure QA réalisée sur un échantillon limité ; GO d’implémentation 4.3 donné |
| Date | 24 septembre 2026 (UTC) |
| Contrat parent | [`PHASE_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_SPECIFICATIONS_DETAILLEES.md), section 6 et décisions `P4-03`/`P4-04` |
| Prérequis | Import CSV 3.1 en place ; socle worker 4.2 et verrou qualité local VERT ; recette fonctionnelle globale en 4.6 |

## 1. Résultat attendu et frontière

Une personne autorisée demande un fichier CSV des données CRM de son périmètre, suit sa préparation et le télécharge
pendant une durée limitée. Le serveur impose le périmètre, le schéma et les droits de chaque donnée, y compris quand
le client modifie sa requête. L’administration des imports rend les sessions, exécutions et motifs de quarantaine
consultables dans le temps et permet une correction suivie d’un nouveau lot, sans réutiliser un fichier source supprimé.

Le lot **n’introduit ni export Google, ni XLSX, ni accès public à la file de travaux, ni connecteur, ni envoi de
messages**. L’ancien export Excel des résultats Google (`export_leads.py`/`excel.py`) reste hors du parcours CRM ; ses
colonnes `PlaceId` et contenus Google ne sont jamais repris. L’import 3.1 demeure synchrone, avec aperçu et confirmation
explicite. La recette fonctionnelle transversale de la phase 4 reste planifiée en 4.6 ; le verrou technique 4.3 reste
exigé à la fin de son implémentation.

## 2. État de départ et dépendances réelles

- Le socle 3.1 persiste `import_declarations`, `csv_import_sessions`, `csv_import_runs`,
  `csv_import_quarantines` et `csv_import_fingerprints`. Il limite le fichier source à **10 Mio**, **5 000 lignes**,
  **50 colonnes**, **4 096 caractères par cellule**, montre au plus **100 lignes** en aperçu et expire le fichier
  temporaire après **24 h**. La confirmation idempotente écrit les prospects et supprime le fichier source ; le rapport
  de quarantaine ne conserve que ligne, codes de motif et référence opaque.
- Le socle 4.2 fournit la file PostgreSQL, deux processus worker, un travail actif par organisation, trois tentatives
  au plus, une limite de 100 travaux en attente par organisation et un bail de 90 s. Il ne possède à ce jour qu’un
  gestionnaire de démonstration interne ; le type métier d’export, ses droits SQL/RLS, ses routes et ses artefacts
  restent à créer. Les métadonnées des travaux terminés et les fichiers d’export auront des conservations distinctes.
- Les droits actuels sont `imports:read`/`imports:declare` pour Admin et Gestionnaire, plus `imports:archive` pour Admin.
  Commercial ne dispose d’aucune capacité d’import. Il n’existe pas encore de capacité d’export ni de preuve explicite
  que chaque donnée issue d’un fournisseur externe est **redistribuable par export**. L’attestation d’acquisition ne
  sera pas interprétée comme cette permission.
- La QA actuelle utilise un volume privé Compose partagé entre API et worker sur un même hôte. Le contrat multi-hôte
  reste à établir avant tout déploiement d’exports sur plusieurs hôtes.

## 3. Contrat fonctionnel des exports

### 3.1 Demande et portée

Chaque demande cible **un seul jeu de données** et une version de schéma CSV. Les six jeux V1 sont `prospects`,
`contacts`, `contact_channels`, `activities`, `tasks` et `opportunities`. Le client choisit une liste de colonnes
dans la liste blanche du jeu et de la version ; le serveur refuse (`422`) tout nom inconnu, doublon ou colonne
interdite. Une liste vide prend les colonnes par défaut du jeu. L’ordre retenu est celui du registre de schéma, pas
celui arbitrairement fourni par le client. Aucun export « toutes tables » ou jointure libre n’est exposé.

La portée `self` est obligatoire pour Commercial. Admin et Gestionnaire peuvent choisir `self` ou `organization` ;
la portée organisation inclut les objets non attribués. `self` reprend la règle d’attribution du tableau de bord 4.1 :

| Jeu | Filtre `self` exécuté côté serveur |
| --- | --- |
| `prospects` | `prospects.owner_id = appartenance_active.id` ; exclut les non attribués. |
| `contacts`, `contact_channels` | Prospect parent possédé par l’appartenance active ; un canal directement lié au prospect suit ce prospect. |
| `activities` | `prospect_activities.actor_id = utilisateur_actif.id`, dans l’organisation active. |
| `tasks` | `prospect_tasks.assigned_membership_id = appartenance_active.id`. |
| `opportunities` | `opportunities.owner_membership_id = appartenance_active.id`. |

Les filtres V1 sont : `created_from`/`created_to` pour prospects et contacts, `obtained_from`/`obtained_to` pour
canaux, `occurred_from`/`occurred_to` pour activités, `due_from`/`due_to` pour tâches,
`expected_close_from`/`expected_close_to` pour opportunités ; et,
selon le jeu, `stage_code`, `status`, `priority` ou `owner_membership_id`. Les bornes métier de type date sont
interprétées dans le fuseau IANA de l’organisation puis converties en UTC par le serveur, comme en 4.1. Chaque
couple de bornes est inclusif en jours locaux et limité à **366 jours**. La portée `self` refuse un filtre de
responsable différent ; le filtre de responsable de la portée organisation est validé dans la même organisation.
Les identifiants d’organisation, expressions SQL, choix de table, préfixes de fichier et chemins ne sont jamais des
paramètres client.

À l’admission, l’API fige la requête canonique et l’identité de l’appartenance active. L’exécution relit les droits,
la source et les données courantes sous une transaction de lecture cohérente ; `snapshot_at` décrit **l’instant de
lecture du worker**, pas l’instant de la demande. Les lignes sont ordonnées par identifiant stable. Le nombre de lignes
annoncé correspond aux lignes réellement écrites. Une révocation avant publication empêche la mise à disposition.

### 3.2 Liste blanche et format CSV V1

Les noms ci-dessous sont les **codes de colonnes** du schéma `crm_csv_v1`. Les codes en gras sont présents par défaut ;
les autres sont sélectionnables. Aucun `organization_id`, `google_place_id`, `source_label`, `value_normalized`,
preuve de consentement, note libre longue ou champ Google affiché en direct n’est exportable.

| Jeu | Colonnes autorisées `crm_csv_v1` | Règle spécifique |
| --- | --- | --- |
| `prospects` | **`prospect_id`**, **`internal_alias`**, **`stage_code`**, **`owner_membership_id`**, **`priority`**, **`tags`**, `industry_label`, `segment_code`, `size_band`, `address_line_1`, `address_line_2`, `city`, `region`, `postal_code`, `country_code`, **`created_at`**, `updated_at` | `internal_alias` et champs de profil/adresse ne sont renseignés que si leur provenance autorise l’export ; sinon cellule vide et compteur de champs omis. |
| `contacts` | **`contact_id`**, **`prospect_id`**, **`display_name`**, `role_label`, **`created_at`** | Personne active et provenance du contact vérifiée ; aucune coordonnée fusionnée dans cette ligne. |
| `contact_channels` | **`channel_id`**, **`prospect_id`**, **`contact_id`**, **`channel_type`**, **`value`**, **`purpose`**, `permission_status`, `obtained_at` | Une ligne par canal actif ; `prospect_id` ou `contact_id` est vide selon sa cible. `value` exige une provenance exportable. `permission_status` est l’état effectif au `snapshot_at` ou `unknown` en son absence ; il est informatif, jamais une autorisation d’envoi. |
| `activities` | **`activity_id`**, **`prospect_id`**, `contact_id`, **`activity_type`**, **`direction`**, **`summary`**, **`occurred_at`**, `actor_user_id` | Exclut `note` et les références de correction détaillées ; les identifiants de contact ne sortent que si leur ressource est autorisée. |
| `tasks` | **`task_id`**, **`prospect_id`**, **`assigned_membership_id`**, **`title`**, **`priority`**, **`status`**, **`due_at`**, `completed_at` | Exclut `description`, motif d’annulation et champs de rappel. |
| `opportunities` | **`opportunity_id`**, **`prospect_id`**, **`owner_membership_id`**, **`name`**, **`amount`**, **`currency_code`**, **`probability`**, **`stage_code`**, **`expected_close_on`**, `closed_at` | Montant décimal exact, devise distincte ; aucun taux ou total multidevise. |

Le registre associe chaque code à la colonne source, son type, sa classe de provenance, ses capacités et sa version.
L’autorisation d’un jeu requiert la capacité `exports:create:self` ou `exports:create:organization` **et** la
capacité de lecture métier correspondante (`prospects:read`, `contacts:read`, `activities:read`, `tasks:read` ou
`opportunities:read`). `contact_channels` requiert `contacts:read`. Les projections SQL explicites excluent toute
sélection `*`. Une nouvelle colonne exige une nouvelle version de schéma et des tests de non-régression ; une
ancienne version encore annoncée reste lisible avec les mêmes colonnes et règles.

Format : UTF-8 avec BOM, séparateur virgule, guillemets selon RFC 4180, fins de ligne CRLF, en-têtes avec les codes
ci-dessus. Les dates/instants sont en ISO 8601 UTC avec `Z` ; `expected_close_on` est une date `YYYY-MM-DD` ;
`amount` utilise le point décimal et **quatre décimales**, accompagné de `currency_code` ; `tags` contient un tableau
JSON compact et correctement cité en CSV ; `NULL` devient cellule vide. Aucun format dépendant de la langue ou du
fuseau du navigateur ne change le fichier. Toute valeur texte susceptible d’être interprétée comme formule de
tableur, y compris après espaces ou caractères de contrôle initiaux puis `=`, `+`, `-` ou `@`, reçoit un préfixe
apostrophe dans **le fichier uniquement**. Les tabulations et retours de ligne contenus dans une cellule sont
normalisés avant cette vérification. Les données stockées en base ne sont pas modifiées. Le test couvre aussi les
guillemets, virgules, caractères non ASCII, champs vides et titres commençant par une formule.

### 3.3 Provenance et admissibilité des données

Les champs CRM créés directement par un utilisateur (étape, responsable, priorité, tags, activité, tâche,
opportunité) sont internes, sous réserve des droits métier et de conservation. Une donnée issue d’une acquisition ou
d’un fournisseur externe ne sort que si une **règle d’export explicite, active et attestée** couvre sa source,
sa catégorie de champ et sa finalité. Un statut absent, expiré, révoqué ou ambigu est refusé par défaut. Le lot
ajoute la représentation et la vérification de cette règle aux enregistrements de provenance/acquisition concernés ;
il ne déduit pas l’exportabilité du seul `rights_attested` ni du statut de permission de contact.

Les contenus Google affichés en direct et `place_id` sont exclus sans exception V1. Un alias ou un profil initialisé
à partir de Google et sans origine indépendante attestée n’est pas considéré comme « interne » du seul fait qu’il
réside en colonne CRM : ses cellules de texte sont vides dans l’export. Si la provenance nécessaire pour distinguer
une valeur est insuffisante, cette valeur est omise ; si la ligne ne peut pas être exportée sans ambiguïté (contact
ou canal, par exemple), elle est omise entièrement. La réponse et l’audit indiquent seulement les nombres de lignes
ou champs omis, jamais leur contenu. Les données archivées, purgées ou sous restriction incompatible sont exclues.

### 3.4 Cycle, limites et téléchargement

Tous les exports V1 passent par un type fermé `export_csv:1` du worker 4.2 ; l’API répond `202` avec un identifiant
d’export opaque et son état. Une seconde demande portant la même clé d’idempotence et la même requête canonique
rend le même export ; une autre requête avec cette clé répond `409`. Une clé dont le fichier a expiré rend l’état
`expired` : une **nouvelle clé** est requise pour régénérer un fichier. La clé brute ne figure pas dans les journaux.

| Limite validée | Valeur initiale | Comportement |
| --- | --- | --- |
| Lignes par fichier | 50 000 | Dépassement : échec `limit_exceeded`, aucun fichier partiel publié. |
| Taille du fichier | 50 Mio | Contrôle pendant l’écriture, même issue. |
| Exports non terminés par organisation | 5 | Refus `429` à l’admission, en plus de la limite worker 4.2. |
| Stockage des fichiers prêts par organisation | 250 Mio | Refus `429` si la capacité réservée ne peut pas être garantie ; balayage des expirés préalable. |
| Durée de disponibilité | 24 h après publication | Téléchargement impossible ensuite ; purge physique bornée et reprise en cas d’échec. |
| Durée maximale d’une tentative | 30 min | Utilise la borne 4.2 ; publication atomique ou échec nettoyé. |

Ces valeurs initiales sont **approuvées par `P4.3-04`** comme plafonds conservateurs. La mesure QA ci-dessous
ne permet pas de les dimensionner à partir d’un volume représentatif. Tout ajustement des plafonds ou de
l’expiration demande une nouvelle validation produit. Le risque de refus des gros exports devra également être
consigné dans le rapport d’implémentation 4.3.

La mesure QA a été autorisée le 24 septembre 2026. Le protocole reproductible est
[`Measure-QAVolumetry.sql`](../scripts/Measure-QAVolumetry.sql), exécuté depuis
[`Measure-QAVolumetry.ps1`](../scripts/Measure-QAVolumetry.ps1). Il ne renvoie que les UUID d’organisation,
comptages et tailles estimées par jeu, puis les percentiles 50/95 et maximum entre organisations actives. Il
compte les enregistrements actifs pour prospects, contacts et canaux, et tous les états d’activité, tâche et
opportunité. Les tailles sont des majorants indicatifs des colonnes par défaut et de toutes les colonnes permises,
avant filtres, droits de provenance et neutralisation effective ; elles ne remplacent pas un export réel.
Le responsable produit a exécuté le script en QA le **24 septembre 2026** et transmis la sortie complète, terminée
par `COMMIT`. L’échantillon comprend **quatre organisations actives** ; une seule possède des données dans les six
jeux considérés. Les valeurs de taille ci-dessous sont celles imprimées par le script, arrondies à trois décimales
de Mio. Un `0.000` pour la taille signifie « inférieur au seuil d’affichage », et non fichier de zéro octet.

| Jeu | Lignes totales QA | Organisations avec lignes | P50 lignes/org. | P95 lignes/org. | Maximum lignes/org. | P50 taille large (Mio) | P95 taille large (Mio) | Maximum taille large (Mio) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `prospects` | 3 | 1/4 | 0,0 | 2,6 | 3 | 0,000 | 0,001 | 0,001 |
| `opportunities` | 1 | 1/4 | 0,0 | 0,9 | 1 | 0,000 | 0,000 | 0,000 |
| `contacts` | 0 | 0/4 | 0,0 | 0,0 | 0 | 0,000 | 0,000 | 0,000 |
| `contact_channels` | 0 | 0/4 | 0,0 | 0,0 | 0 | 0,000 | 0,000 | 0,000 |
| `activities` | 0 | 0/4 | 0,0 | 0,0 | 0 | 0,000 | 0,000 | 0,000 |
| `tasks` | 0 | 0/4 | 0,0 | 0,0 | 0 | 0,000 | 0,000 | 0,000 |

Le P95 de 2,6 prospects et 0,9 opportunité est une **interpolation statistique sur quatre organisations**,
pas un volume réellement observé. Les maximums observés (3 lignes et 0,001 Mio pour les prospects ; 1 ligne et
moins de 0,001 Mio pour les opportunités) sont très inférieurs à 50 000 lignes et 50 Mio. Cet échantillon ne
permet cependant pas d’inférer les volumes futurs, de valider la concurrence de cinq exports, le stockage de
250 Mio ou la durée de 24 h. Les plafonds approuvés restent inchangés. Un jeu synthétique proche des plafonds et
un test du quota de stockage devront compléter le verrou technique 4.3 ; les résultats QA présents servent de
référence de départ et leur manque de représentativité est une limite explicite.

Le worker écrit un fichier provisoire dans le volume privé partagé, calcule SHA-256, compte les lignes, vérifie la
possession du bail et les droits, puis publie par renommage atomique et valide le registre d’artefacts. Le registre
contient `organization_id`, demandeur, jeu, version, portée, filtres canoniques minimisés, `job_id`, `status`,
`snapshot_at`, volume, octets, empreinte, référence opaque et `expires_at`. Une panne ou perte du bail supprime ou
isole le provisoire ; une reprise ne crée jamais deux fichiers accessibles pour la même demande. Le registre et le
balayeur réconcilient les fichiers orphelins. Les permissions du volume sont privées, l’accès du worker est limité
aux projections CRM autorisées par un rôle PostgreSQL et des règles RLS dédiées. Aucun chemin local n’est envoyé au
client. Le multi-hôte reste bloqué sans stockage privé partagé ou objet, suppression vérifiable et contrat de reprise.

Les états publics sont `queued`, `running`, `ready`, `failed`, `cancelled` et `expired`. Seul `ready` est
téléchargeable. `queued` peut devenir `running`, `cancelled` ou `failed` ; `running` peut revenir en attente lors
d’une reprise du worker, ou devenir `ready`, `failed` ou `cancelled` ; `ready` devient `expired` par échéance,
révocation ou purge métier. Un échec de nettoyage n’inverse pas `expired` et reste visible à l’exploitation. Le
balayeur cherche les provisoires non référencés après expiration du bail et les artefacts `ready` sans fichier ;
il réconcilie ces cas avant qu’un téléchargement soit autorisé.

Le téléchargement est une route authentifiée de **streaming serveur**. Avant ouverture du fichier, elle revérifie
session, organisation active, appartenance, capacité du jeu, portée, identité du demandeur, état `ready`, expiration
et règle de provenance toujours valide. Un autre membre, même Admin, crée son propre export. Une révocation rend le
fichier inaccessible et déclenche sa purge ; le contenu n’est pas recalculé pour le rendre partiellement téléchargeable.
La réponse réussie porte `Content-Type: text/csv; charset=utf-8`, `Content-Disposition: attachment`,
`Cache-Control: no-store`, `X-Content-Type-Options: nosniff` et une taille contrôlée. Le nom de fichier est généré
par le serveur sans donnée personnelle. Un export inconnu ou d’une autre organisation répond `404` indistinct ;
une permission révoquée dans l’organisation répond `403`, un fichier expiré `410`. Aucun URL signé public.

### 3.5 Modèle persistant et migrations

Une migration 4.3 crée `export_requests` et `export_artifacts` avec clés `(organization_id, id)` et liens composés
vers l’organisation et `jobs`. `export_requests` porte demandeur (`user_id` et `membership_id`), jeu, version,
portée, filtres structurés, colonnes, empreinte de commande, condensat d’idempotence, dates et état projeté.
`export_artifacts` porte la référence de fichier opaque, la taille, SHA-256, les comptes de lignes et de champs
omis, `snapshot_at`, publication, échéance et suppression. Contraintes : unicité d’un artefact courant par
demande, unicité de la clé d’idempotence dans l’organisation et le type, états fermés, dates cohérentes, index de
balayage sur échéance/état et index de liste sur `(organization_id, requester, created_at, id)`.

La règle d’export de provenance est une donnée structurée distincte de `rights_attested`. Elle référence source
et/ou acquisition, catégories/champs couverts, finalité, statut `allowed|denied|unknown`, validité, acteur et
date d’attestation, référence de preuve opaque. Un changement de règle est versionné et audité. Les données
historiques sans règle explicite migrent en `unknown`, jamais en `allowed`. Les politiques RLS des nouvelles tables
isolent l’organisation ; l’API voit uniquement les demandes du demandeur, le worker voit les seules ressources
requises par `export_csv:1` avec un rôle SQL distinct et des projections en lecture. Les identifiants étrangers
utilisent des clés composées par organisation pour empêcher un lien interorganisation, même en cas d’erreur applicative.

Le schéma des imports ajoute `retry_of_run_id` nullable à `csv_import_sessions`, avec clé étrangère composée
`(organization_id, retry_of_run_id)` vers `csv_import_runs`, plus un index d’historique. Aucun contenu CSV ou
correction de cellule n’est stocké dans ce lien. Les migrations conservent les anciens runs et leurs compteurs
sans recalcul ; les sessions antérieures ont simplement `retry_of_run_id = NULL`.

## 4. Administration des imports 3.1

### 4.1 Historique et rapports

L’écran d’administration liste les déclarations, sessions et exécutions de l’organisation active, de la plus récente
à la plus ancienne, par curseur stable (25 éléments, maximum 100). Filtres : statut, période de création, déclaration
et auteur. Une fiche montre source déclarée **sans contenu brut**, statut et dates, schéma/mapping, totaux
`ready`, `created`, `duplicate`, `review`, `quarantined` et motifs agrégés. Dans le run 3.1,
`review_count` est **inclus dans** `quarantined_count` : l’interface affiche « rejetées/quarantainées » comme
`quarantined_count`, dont `review_count` à revoir, et « doublons » séparément. La somme des lignes uniques du run
est `created_count + duplicate_count + quarantined_count` ; le nombre « à revoir » ne s’y ajoute pas.
Les compteurs d’un run sont immuables après confirmation.

La quarantaine est consultable par page et curseur, avec `line_number`, `reason_codes` et `opaque_reference` ; ni
ligne CSV brute, ni valeur de contact, ni fichier source. L’API actuelle plafonnée à 500 entrées est étendue pour
paginer plutôt que tronquer silencieusement les résultats. Un lot absent ou d’une autre organisation répond `404`
sans signaler son existence. La durée de conservation des métadonnées de rapport reste celle de la politique métier
applicable ; le délai de 24 h du fichier brut et celui des `jobs` 4.2 ne les effacent pas implicitement.

### 4.2 Correction et relance contrôlée

Deux opérations restent distinctes :

1. **Répétition technique** : renvoyer la même confirmation avec la même clé et la même empreinte retourne le même
   `csv_import_run`, les mêmes compteurs et aucune nouvelle écriture CRM ; une empreinte différente répond `409`.
2. **Correction métier** : l’utilisateur corrige localement les lignes signalées, crée ou réutilise une déclaration
   toujours approuvée (nouvelle déclaration si l’empreinte déclarée du fichier change), téléverse **un nouveau CSV**,
   refait aperçu, mapping et validation, puis confirme avec une nouvelle clé. Le téléversement accepte le paramètre
   fermé `retry_of_run_id` ; la nouvelle session conserve ce lien vers le run initial et le motif `correction`.
   Le run initial demeure immuable. Les empreintes 3.1 empêchent de recréer les lignes déjà acquises. Aucune ligne
   rejetée ou en quarantaine n’est automatiquement promue en contact ni en permission `allowed`.

La répétition technique doit consulter le run idempotent **avant** de dépendre de la présence du fichier supprimé
ou du délai de 24 h, tant que le rapport est conservé. C’est une adaptation explicite du flux 3.1 actuel.
La relance métier n’est offerte que pour un run de la même organisation et une acquisition encore approuvée. Les droits de
source, catégories déclarées et finalité sont revalidés lors du téléversement, de la validation et de la confirmation.
Une acquisition révoquée impose une nouvelle déclaration conforme ; le système n’accepte pas une simple correction
de fichier sous l’ancienne autorisation. Le lien parent-enfant sert uniquement au suivi et ne contourne ni les
limites 3.1, ni la déduplication, ni l’effacement du nouveau fichier source après confirmation/expiration.

### 4.3 Matrice de droits

| Action | Commercial | Gestionnaire | Admin | Contrôle additionnel |
| --- | --- | --- | --- | --- |
| Lister/lire déclarations, sessions, runs et quarantaine | Non | `imports:read` | `imports:read` | Organisation active, métadonnées minimisées. |
| Déclarer et téléverser | Non | `imports:declare` | `imports:declare` | Source, finalité et droits approuvés. |
| Modifier le mapping et valider | Non | `imports:correct` | `imports:correct` | Session non confirmée et fichier non expiré. |
| Confirmer le lot | Non | `imports:confirm` | `imports:confirm` | Prévisualisation/validation préalables, clé d’idempotence. |
| Créer un nouveau lot lié à un run | Non | `imports:retry` | `imports:retry` | Run parent de l’organisation et nouvelle déclaration/source valide. |
| Archiver une déclaration | Non | Non | `imports:archive` | Règles de conservation existantes. |

Les trois capacités nouvelles sont ajoutées aux rôles indiqués lors de la migration 4.3, avec transition cohérente
des routes 3.1 existantes : Gestionnaire conserve la capacité effective de terminer un import qu’il pouvait déjà
déclarer. Elles ne donnent aucun droit de lecture ou de correction à Commercial. L’interface masque les actions
interdites, tandis que l’API applique chaque contrôle indépendamment.

## 5. API et expérience utilisateur

| Route proposée | Effet | Contrôles principaux |
| --- | --- | --- |
| `POST /api/exports` | Crée la demande et enfile `export_csv:1` ; `Idempotency-Key` obligatoire. | CSRF, capacité de portée et de jeu, schéma/filtres fermés, quotas. |
| `GET /api/exports` | Historique minimal de ses propres demandes, curseur 25/max 100. | Organisation active, capacité d’export. |
| `GET /api/exports/{id}` | État `queued/running/ready/failed/expired`, compteurs, dates et code d’erreur fermé. | Demandeur et organisation. |
| `GET /api/exports/{id}/download` | Télécharge le CSV prêt. | Contrôles de la section 3.4, audit du succès. |
| `GET /api/csv-import-sessions` et `GET /api/csv-import-runs` | Historique paginé et filtres fermés. | `imports:read`. |
| `GET /api/csv-import-sessions/{id}` et `GET /api/csv-import-runs/{id}` | Détail minimisé. | `imports:read`. |
| `GET /api/csv-import-runs/{id}/quarantines` | Étend la route existante avec curseur. | `imports:read`, aucun contenu brut. |
| `PUT /api/import-declarations/{id}/file?retry_of_run_id={run_id}` | Étend le téléversement 3.1 et crée une nouvelle session liée au run. | CSRF, `imports:retry`, `imports:declare`, déclaration/source toujours valides. |

Le téléversement et la confirmation continuent d’employer les routes 3.1 et leurs limites. Les routes
de liste ne retournent jamais `file_ref`, chemin, clé d’idempotence brute, adresse, téléphone ou contenu de cellule.
Toutes les réponses portent `Cache-Control: no-store`. Les erreurs publiques utilisent des codes stables
(`invalid_column`, `scope_forbidden`, `source_export_forbidden`, `limit_exceeded`, `artifact_expired`,
`authorization_revoked`) et des messages localisés, sans SQL ou chemin. Les mutations utilisent la protection CSRF
existante ; les GET ne changent aucun état métier.

L’interface propose « Exports » et « Imports » selon les capacités. Le parcours export montre jeu de données,
portée, filtres, colonnes, rappel de la nature sensible du fichier, état, volume et échéance ; le bouton Télécharger
n’apparaît qu’à l’état prêt. Le parcours imports reprend les déclarations existantes, ajoute historique des runs,
motifs et relance par nouveau fichier. Les états vide, préparation, échec, expiration et source révoquée sont
expliqués en `fr-CA` et `en-CA`, utilisables au clavier, à 200 % de zoom et avec annonces de statut accessibles.

## 6. Audit, conservation et exploitation

Les événements `export_requested`, `export_ready`, `export_failed`, `export_downloaded`, `export_expired`,
`import_retry_started` et `import_report_viewed` (pour les fiches et quarantaines, pas pour chaque ligne de liste) portent acteur,
organisation, identifiant opaque, jeu, version, portée, filtres structurés non libres, nombres et dates. Un texte
de recherche, une adresse, un nom, une coordonnée, une ligne CSV, une preuve brute ou le contenu du fichier ne sont
jamais enregistrés dans l’audit ou les journaux. Les échecs de téléchargement et de purge sont comptés sans inclure
de chemin local dans les réponses.

Un balayeur indépendant marque l’artefact expiré, retire le fichier et confirme l’effacement ; les échecs sont
rejoués, comptés et alertés. Une suppression de fichier ne supprime ni l’audit, ni le rapport d’import, ni une
donnée métier. À l’inverse, une purge métier ou une révocation de source invalide les artefacts concernés avant
leur terme normal. Le registre conserve le minimum de métadonnées nécessaire au suivi et à l’idempotence tant que
le travail 4.2 associé est conservé (30 jours succès/annulation, 90 jours échec) ; **aucun CSV ne suit cette durée**.
La politique de conservation métier et les suspensions de purge existantes restent applicables aux rapports d’import.

## 7. Validation et preuves attendues

| ID | Scénario | Résultat exigé |
| --- | --- | --- |
| `EXP-01` | Commercial demande `self`, puis forge `organization`, un autre responsable ou une autre organisation. | Seul son périmètre serveur sort ; refus/`404` sans fuite, y compris par ID direct. |
| `EXP-02` | Admin envoie colonne inconnue, `place_id`, colonne Google ou change l’ordre/duplique une colonne. | `422`, aucun travail admis ; aucun champ non listé dans un CSV valide. |
| `EXP-03` | Prospect Google avec alias dérivé, contact externe sans droit d’export, canal avec permission `allowed` mais licence expirée. | Texte dérivé omis et lignes non admissibles exclues ; `allowed` ne contourne pas la provenance. |
| `EXP-04` | Titres `=...`, ` +...`, `@...`, retour ligne, guillemets, virgule et Unicode dans chaque jeu. | CSV analysable, données affichées comme texte, aucune formule active ; données source intactes. |
| `EXP-05` | Période traversant changement d’heure ; opportunités CAD et USD. | Bornes IANA exactes ; montants par ligne, devise conservée, aucune conversion. |
| `EXP-06` | Deux workers, panne après écriture provisoire, bail perdu, nouvelle tentative. | Un seul artefact publié, empreinte et compteurs exacts ; provisoires supprimés. |
| `EXP-07` | Clé d’idempotence rejouée identique puis modifiée ; taille ou nombre de lignes dépassé. | Même demande puis `409` ; échec fermé sans fichier partiel pour dépassement. |
| `EXP-08` | Demandeur désactivé ou source révoquée avant génération, puis avant téléchargement ; fichier expiré. | Aucun effet ni téléchargement après révocation ; `410` après expiration et purge physique vérifiée. |
| `EXP-09` | Accès à un export par un autre membre de la même organisation, puis par une autre organisation. | Téléchargement refusé au premier ; `404` indistinct au second, sans fuite de métadonnées. |
| `EXP-10` | Jeu synthétique proche de 50 000 lignes et 50 Mio, cinq demandes actives, quota de 250 Mio et expiration à 24 h. | Plafonds appliqués sans fichier partiel, durée et disque bornés, purge vérifiée ; résultats consignés dans le rapport 4.3. |
| `IMP-01` | Lister et paginer plus de 500 quarantaines ; comparer totaux et motifs au run. | Aucun tronquage silencieux, curseur stable, aucune valeur de ligne brute. |
| `IMP-02` | Rejouer la confirmation avec même clé, puis corriger via nouveau fichier lié au run. | Première reprise sans doublon ; nouveau run traçable, seules lignes admissibles créées, source supprimée. |
| `IMP-03` | Relancer un run d’une autre organisation, une acquisition révoquée ou confirmer sans droit. | Refus avant effet ; aucun statut ou contenu étranger révélé. |
| `IMP-04` | Nouvelle ligne de contact sans permission explicite, doublon exact et ligne ambiguë. | `unknown`, doublon ignoré, ambiguïté en quarantaine, compteurs cohérents. |

Le verrou technique de l’incrément couvre tests unitaires de sérialisation et d’autorisation, intégration PostgreSQL
avec RLS pour API **et** rôle worker, concurrence/reprise 4.2, durée de vie du volume, audit minimisé, parcours UI
bilingue et accessible, build frontend et contrôle du diff. Aucun `skip` n’est transformé en réussite. La recette
fonctionnelle utilisateur de bout en bout sera consolidée au lot 4.6, conformément à la décision déjà prise.

## 8. Décisions validées par le responsable produit

Le responsable produit a validé explicitement les huit décisions `P4.3-01` à `P4.3-08` le 24 septembre 2026,
puis donné le GO distinct pour l’implémentation de la phase 4.3.

| ID | Décision validée | Effet |
| --- | --- | --- |
| `P4.3-01` | Six jeux CSV séparés, schéma fermé `crm_csv_v1`, colonnes et format de la section 3.2 ; pas de XLSX V1. | Fichiers stables, sans jointure libre ni colonne Google. |
| `P4.3-02` | Commercial `self`, Gestionnaire/Admin `self` ou organisation ; attribution par jeu conforme à 4.1 ; téléchargement réservé au demandeur. | Portée explicite à chaque étape. |
| `P4.3-03` | Tous les exports utilisent `export_csv:1` sur le worker 4.2 et un registre privé d’artefacts ; multi-hôte bloqué sans stockage validé. | Une chaîne unique et reprenable. |
| `P4.3-04` | Plafonds initiaux de 50 000 lignes/50 Mio, 5 demandes actives et 250 Mio par organisation, disponibilité 24 h ; mesure QA limitée consignée en section 3.4. | Risque de disque et d’export excessif borné, sous réserve de l’essai de charge `EXP-10`. |
| `P4.3-05` | Règle d’export explicite par source/catégorie/finalité ; inconnu ou révoqué refusé ; contenu Google dérivé exclu. | Aucune autorisation déduite d’une simple provenance ou permission de contact. |
| `P4.3-06` | Historique import paginé et rapports minimisés ; quarantaine paginée sans ligne brute. | Les lots 3.1 restent auditables après effacement du CSV. |
| `P4.3-07` | Correction par nouveau fichier/session/run lié ; confirmation technique rejouée avec même clé retourne le même run. | Historique immuable et déduplication 3.1 préservés. |
| `P4.3-08` | Capacités import distinctes `read`, `correct`, `confirm`, `retry` et capacités export par portée ; matrice de la section 4.3. | Chaque lecture et mutation est vérifiée côté serveur. |

La mesure QA prescrite est consignée en section 3.4. Les plafonds initiaux restent ceux validés ; tout ajustement
devra faire l’objet d’une nouvelle décision produit.
